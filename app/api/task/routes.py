"""Task management API"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.project import Project
from app.models.task import Task, TaskStatus, TaskType
from app.models.user import User
from app.models.literature import Literature
from app.schemas.task_schemas import (
    TaskListResponse,
    TaskDetailResponse,
    TaskRetryRequest,
    TaskCancelResponse,
    TaskStatisticsResponse,
    TaskStatusBreakdown,
    TaskCostSummary,
)
from app.services.task_service import TaskService

router = APIRouter()


def _require_task(task: Optional[Task]) -> Task:
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# =================== Phase B: 文献任务关联 API ===================

class TaskExtractionResult(BaseModel):
    """任务提取结果"""
    id: int
    task_id: int
    extraction_type: str  # 'summary', 'keywords', 'entities', 'themes', 'methodology', 'conclusions'
    content: str
    confidence_score: Optional[float] = None
    created_at: str
    metadata: Optional[dict] = None

class RelatedTask(BaseModel):
    """相关任务"""
    id: int
    title: str
    description: Optional[str] = None
    status: str  # 'pending', 'running', 'completed', 'failed'
    task_type: str  # 'analysis', 'extraction', 'summarization', 'classification', 'other'
    progress: Optional[int] = None
    created_at: str
    updated_at: Optional[str] = None
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    extraction_results: List[TaskExtractionResult] = []
    estimated_duration: Optional[int] = None
    actual_duration: Optional[int] = None

class LiteratureTaskLinkageResponse(BaseModel):
    """文献任务关联响应"""
    literature_id: int
    tasks: List[RelatedTask]


@router.get("/literature/{literature_id}", response_model=LiteratureTaskLinkageResponse)
async def get_literature_related_tasks(
    literature_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文献相关的任务"""

    # 验证文献访问权限
    literature = db.query(Literature).filter(Literature.id == literature_id).first()
    if not literature:
        raise HTTPException(status_code=404, detail="文献不存在")

    # 检查用户是否有权限访问此文献
    user_projects = [p.id for p in current_user.projects]
    literature_projects = [p.id for p in literature.projects] if literature.projects else []

    has_access = False
    if literature.project_id and literature.project_id in user_projects:
        has_access = True
    elif any(pid in user_projects for pid in literature_projects):
        has_access = True

    if not has_access:
        raise HTTPException(status_code=403, detail="无权限访问此文献")

    related_tasks = _get_related_tasks_for_literature(db, literature, current_user)

    return LiteratureTaskLinkageResponse(
        literature_id=literature_id,
        tasks=related_tasks
    )


def _get_related_tasks_for_literature(db: Session, literature: Literature, user: User) -> List[RelatedTask]:
    project_ids = {p.id for p in literature.projects} if literature.projects else set()
    if literature.project_id:
        project_ids.add(literature.project_id)

    if not project_ids:
        return []

    tasks = (
        db.query(Task)
        .join(Project)
        .filter(Project.owner_id == user.id)
        .filter(Task.project_id.in_(project_ids))
        .order_by(Task.created_at.desc())
        .limit(200)
        .all()
    )

    matched_tasks = [task for task in tasks if _task_references_literature(task, literature.id)]

    if not matched_tasks:
        fallback_types = {
            TaskType.LITERATURE_PROCESSING.value,
            TaskType.PDF_PROCESSING.value,
        }
        matched_tasks = [task for task in tasks if task.task_type in fallback_types]

    return [_build_related_task(task) for task in matched_tasks]


def _task_references_literature(task: Task, literature_id: int) -> bool:
    return any(
        _dict_contains_literature(container, literature_id)
        for container in (task.config, task.input_data, task.result)
        if isinstance(container, dict)
    )


def _dict_contains_literature(data: Dict[str, Any], literature_id: int) -> bool:
    for value in data.values():
        if isinstance(value, int) and value == literature_id:
            return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, int) and item == literature_id:
                    return True
                if isinstance(item, dict) and _dict_contains_literature(item, literature_id):
                    return True
        if isinstance(value, dict) and _dict_contains_literature(value, literature_id):
            return True
    return False


def _build_extraction_results(task: Task) -> List[TaskExtractionResult]:
    payload = task.result if isinstance(task.result, dict) else {}
    entries = payload.get("extraction_results")
    if not isinstance(entries, list):
        return []

    results: List[TaskExtractionResult] = []
    default_timestamp = (task.updated_at or task.created_at or datetime.utcnow()).isoformat()

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        extraction_type = str(entry.get("extraction_type") or entry.get("type") or "analysis")
        content = entry.get("content") or entry.get("text")
        if not isinstance(content, str):
            continue
        created_at = entry.get("created_at")
        if not isinstance(created_at, str):
            created_at = default_timestamp
        metadata = {
            k: v
            for k, v in entry.items()
            if k not in {"extraction_type", "type", "content", "text", "confidence", "confidence_score", "created_at"}
        }
        results.append(
            TaskExtractionResult(
                id=int(entry.get("id") or index + 1),
                task_id=task.id,
                extraction_type=extraction_type,
                content=content,
                confidence_score=(entry.get("confidence_score") or entry.get("confidence")),
                created_at=created_at,
                metadata=metadata or None,
            )
        )
    return results


def _build_related_task(task: Task) -> RelatedTask:
    progress = int(task.progress_percentage) if task.progress_percentage is not None else None
    created_at = task.created_at.isoformat() if task.created_at else datetime.utcnow().isoformat()
    updated_at = task.updated_at.isoformat() if task.updated_at else None
    payload = task.result if isinstance(task.result, dict) else {}

    return RelatedTask(
        id=task.id,
        title=task.title or f"任务 {task.id}",
        description=task.description,
        status=task.status,
        task_type=task.task_type,
        progress=progress,
        created_at=created_at,
        updated_at=updated_at,
        result_url=payload.get("result_url") if isinstance(payload.get("result_url"), str) else None,
        error_message=task.error_message,
        extraction_results=_build_extraction_results(task),
        estimated_duration=task.estimated_duration,
        actual_duration=task.actual_duration,
    )


# =================== 原有的任务管理 API ===================

@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    project_id: Optional[int] = None,
    status: Optional[TaskStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    tasks = service.list_tasks(owner_id=current_user.id, project_id=project_id, status=status)
    return TaskListResponse(tasks=[TaskDetailResponse.from_orm(task) for task in tasks])

@router.get("/stats", response_model=TaskStatisticsResponse)
async def get_task_statistics(
    project_id: Optional[int] = None,
    limit_recent: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    stats = service.get_task_statistics(
        owner_id=current_user.id,
        project_id=project_id,
        limit_recent=limit_recent,
    )

    cost_summary = TaskCostSummary(
        total_token_usage=stats["cost_summary"]["total_token_usage"],
        total_cost_estimate=stats["cost_summary"]["total_cost_estimate"],
        models=stats["cost_summary"]["models"],
    )

    breakdown = [
        TaskStatusBreakdown(status=item["status"], count=item["count"])
        for item in stats["status_breakdown"]
    ]

    recent = [TaskDetailResponse.from_orm(task) for task in stats["recent_tasks"]]

    return TaskStatisticsResponse(
        total_tasks=stats["total_tasks"],
        status_breakdown=breakdown,
        running_tasks=stats["running_task_ids"],
        recent_tasks=recent,
        cost_summary=cost_summary,
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    task = _require_task(service.get_task(task_id, current_user.id))
    return TaskDetailResponse.from_orm(task)


@router.post("/{task_id}/retry", response_model=TaskDetailResponse)
async def retry_task(
    task_id: int,
    request: TaskRetryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    try:
        task = _require_task(service.retry_task(task_id, current_user.id, request.force))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return TaskDetailResponse.from_orm(task)


@router.post("/{task_id}/cancel", response_model=TaskCancelResponse)
async def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    result = service.cancel_task(task_id, current_user.id)
    return TaskCancelResponse(**result)
