"""Research mode API endpoints."""

import json
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.project import Project
from app.models.task import Task, TaskType
from app.models.user import User
from app.schemas.research_schemas import (
    ResearchAnalysisRequest,
    ResearchAnalysisResponse,
    ResearchHistoryResponse,
    ResearchQueryRequest,
    ResearchQueryResponse,
    ResearchResult,
    ResearchResultResponse,
    ResearchTaskStatusResponse,
)
from app.services.intelligent_interaction_engine import IntelligentInteractionEngine
from app.services.research_orchestrator import ResearchOrchestrator
from app.services.task_service import TaskService
from app.services.research_share_store import share_store

router = APIRouter()


_MODE_BY_TASK_TYPE = {
    TaskType.LITERATURE_COLLECTION.value: "auto",
    TaskType.LITERATURE_PROCESSING.value: "rag",
    TaskType.EXPERIENCE_GENERATION.value: "deep",
    TaskType.PDF_PROCESSING.value: "rag",
    "search_and_build_library": "auto",
}

_RESEARCH_TASK_TYPES: Iterable[str] = {
    TaskType.LITERATURE_COLLECTION.value,
    TaskType.LITERATURE_PROCESSING.value,
    TaskType.EXPERIENCE_GENERATION.value,
    TaskType.PDF_PROCESSING.value,
    "search_and_build_library",
}


def _resolve_mode(task: Task, fallback: str = "auto") -> str:
    if task.result and isinstance(task.result, dict):
        mode = task.result.get("mode")
        if isinstance(mode, str):
            return mode
    if task.input_data and isinstance(task.input_data, dict):
        mode = task.input_data.get("mode")
        if isinstance(mode, str):
            return mode
    return _MODE_BY_TASK_TYPE.get(task.task_type, fallback)


def _extract_query(task: Task) -> str:
    if task.input_data and isinstance(task.input_data, dict):
        for key in ("query", "research_question", "prompt", "title"):
            value = task.input_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        keywords = task.input_data.get("keywords")
        if isinstance(keywords, list) and keywords:
            return ", ".join(str(item) for item in keywords if item)
    if task.config and isinstance(task.config, dict):
        query = task.config.get("query")
        if isinstance(query, str) and query.strip():
            return query.strip()
    return task.title or f"Task {task.id}"


def _safe_list(value: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return None


def _build_research_result(task: Task) -> ResearchResult:
    mode = _resolve_mode(task)
    result_payload = task.result if isinstance(task.result, dict) else {}
    metadata: Dict[str, Any] = {
        "task_type": task.task_type,
        "config": task.config or {},
    }
    if task.input_data:
        metadata["input_data"] = task.input_data

    main_answer = None
    for key in ("main_answer", "answer", "summary", "response"):
        value = result_payload.get(key)
        if isinstance(value, str) and value.strip():
            main_answer = value.strip()
            break

    return ResearchResult(
        id=task.id,
        task_id=task.id,
        project_id=task.project_id,
        mode=mode,
        query=_extract_query(task),
        status=task.status,
        progress=task.progress_percentage,
        created_at=task.created_at,
        completed_at=task.completed_at,
        error_message=task.error_message,
        main_answer=main_answer,
        literature_sources=_safe_list(result_payload.get("literature_sources"))
        or _safe_list(result_payload.get("sources")),
        experience_books=_safe_list(result_payload.get("experience_books")),
        experiment_suggestions=_safe_list(result_payload.get("experiment_suggestions")),
        confidence_metrics=result_payload.get("confidence_metrics")
        if isinstance(result_payload.get("confidence_metrics"), dict)
        else None,
        metadata=metadata,
    )


def _task_summary(task: Task) -> Dict[str, Any]:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "task_type": task.task_type,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "progress_percentage": task.progress_percentage,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "config": task.config if isinstance(task.config, dict) else None,
        "input_data": task.input_data if isinstance(task.input_data, dict) else None,
    }


def _prepare_export_payload(
    task: Task,
    *,
    include_sources: bool,
    include_metadata: bool,
    include_experiences: bool,
    include_experiments: bool,
    include_raw: bool,
) -> Dict[str, Any]:
    result_model = _build_research_result(task)
    result_data = result_model.model_dump()

    if not include_sources:
        result_data.pop("literature_sources", None)
    if not include_metadata:
        result_data.pop("metadata", None)
    if not include_experiences:
        result_data.pop("experience_books", None)
    if not include_experiments:
        result_data.pop("experiment_suggestions", None)

    export_payload: Dict[str, Any] = {
        "task": _task_summary(task),
        "result": result_data,
    }

    if include_raw and isinstance(task.result, dict):
        export_payload["raw_payload"] = task.result

    return export_payload


def _render_markdown_export(payload: Dict[str, Any]) -> str:
    task_info = payload.get("task", {})
    result = payload.get("result", {})
    lines: List[str] = []
    lines.append(f"# 研究任务 #{task_info.get('id', '')}")
    lines.append("")
    lines.append("## 基本信息")
    lines.append(f"- 项目 ID: {task_info.get('project_id', '未知')}")
    lines.append(f"- 模式: {result.get('mode', '未知')}")
    lines.append(f"- 状态: {result.get('status', 'unknown')}")
    if task_info.get("created_at"):
        lines.append(f"- 创建时间: {task_info['created_at']}")
    if task_info.get("completed_at"):
        lines.append(f"- 完成时间: {task_info['completed_at']}")

    lines.append("")
    lines.append("## 研究问题")
    lines.append(result.get("query", "(未记录)") or "(未记录)")

    lines.append("")
    lines.append("## 主回答")
    main_answer = result.get("main_answer")
    lines.append(main_answer or "(暂无回答)")

    sources = result.get("literature_sources") or []
    if sources:
        lines.append("")
        lines.append("## 参考文献")
        for idx, source in enumerate(sources, 1):
            title = source.get("title") or source.get("name") or "未命名文献"
            authors = ", ".join(source.get("authors", [])) if source.get("authors") else ""
            year = source.get("year") or source.get("published") or ""
            citation = f"{idx}. {title}"
            if authors:
                citation += f" — {authors}"
            if year:
                citation += f" ({year})"
            lines.append(citation)

    experiences = result.get("experience_books") or []
    if experiences:
        lines.append("")
        lines.append("## 经验总结")
        for experience in experiences:
            title = experience.get("title") or "经验"
            lines.append(f"### {title}")
            if experience.get("content"):
                lines.append(experience["content"])
            if experience.get("key_findings"):
                lines.append("- 关键发现:")
                for finding in experience["key_findings"]:
                    lines.append(f"  - {finding}")

    experiments = result.get("experiment_suggestions") or []
    if experiments:
        lines.append("")
        lines.append("## 实验建议")
        for suggestion in experiments:
            name = suggestion.get("name") or "实验建议"
            lines.append(f"### {name}")
            description = suggestion.get("objective") or suggestion.get("description")
            if description:
                lines.append(description)
            methodology = suggestion.get("methodology")
            if methodology:
                lines.append("- 方法: " + methodology)
            expected = suggestion.get("expected_outcome")
            if expected:
                lines.append("- 预期结果: " + expected)
            difficulty = suggestion.get("difficulty")
            if difficulty:
                lines.append("- 难度: " + str(difficulty))

    return "\n".join(lines).strip() + "\n"


@router.post("/query", response_model=ResearchQueryResponse)
async def research_query(
    request: ResearchQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orchestrator = ResearchOrchestrator(db, current_user)

    if request.mode == "rag":
        result = await orchestrator.run_rag(
            project_id=request.project_id,
            query=request.query,
            max_literature_count=request.max_literature_count,
            context_literature_ids=request.context_literature_ids,
        )
        return ResearchQueryResponse(mode="rag", payload=result)

    if request.mode == "deep":
        result = await orchestrator.run_deep(
            project_id=request.project_id,
            query=request.query,
            processing_method=request.processing_method or "deep",
        )
        return ResearchQueryResponse(mode="deep", payload=result)

    if request.mode == "auto":
        result = await orchestrator.run_auto(
            project_id=request.project_id,
            query=request.query,
            keywords=request.keywords or [],
            config=request.auto_config,
            agent=request.agent,
        )
        return ResearchQueryResponse(mode="auto", payload=result)

    raise HTTPException(status_code=400, detail="Unsupported mode")


@router.post("/analysis", response_model=ResearchAnalysisResponse)
async def research_analysis(
    request: ResearchAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    问题拆解与模式推荐分析接口
    复用IntelligentInteractionEngine拉取拆解结果，替换前端mock
    """
    try:
        interaction_engine = IntelligentInteractionEngine(db)

        # 使用智能交互引擎进行问题分析
        analysis_result = await interaction_engine.analyze_query(
            query=request.query,
            project_id=request.project_id,
            context=request.context or {}
        )

        # 转换为API响应格式
        return ResearchAnalysisResponse(
            recommended_mode=analysis_result.get("recommended_mode", "rag"),
            sub_questions=analysis_result.get("sub_questions", []),
            complexity_score=analysis_result.get("complexity_score", 0.5),
            estimated_resources=analysis_result.get("estimated_resources", {}),
            reasoning=analysis_result.get("reasoning", ""),
            suggested_keywords=analysis_result.get("suggested_keywords", []),
            processing_suggestions=analysis_result.get("processing_suggestions", {})
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


def _query_user_task(db: Session, user: User, task_id: int) -> Task:
    task = (
        db.query(Task)
        .join(Project)
        .filter(Task.id == task_id, Project.owner_id == user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/result/{task_id}", response_model=ResearchResultResponse)
async def get_research_result(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _query_user_task(db, current_user, task_id)
    return _build_research_result(task)


@router.get("/history", response_model=ResearchHistoryResponse)
async def get_research_history(
    project_id: Optional[int] = None,
    mode: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = max(page, 1)
    size = max(1, min(size, 100))

    query = (
        db.query(Task)
        .join(Project)
        .filter(Project.owner_id == current_user.id)
        .filter(Task.task_type.in_(_RESEARCH_TASK_TYPES))
    )

    if project_id is not None:
        query = query.filter(Task.project_id == project_id)

    if mode:
        normalized_mode = mode.lower()
        allowed_types = [task_type for task_type, mapped in _MODE_BY_TASK_TYPE.items() if mapped == normalized_mode]
        if not allowed_types:
            return ResearchHistoryResponse(items=[], total=0, page=page, size=size)
        query = query.filter(Task.task_type.in_(allowed_types))

    if status:
        query = query.filter(Task.status == status.lower())

    total = query.count()
    tasks = (
        query.order_by(Task.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    items = [_build_research_result(task) for task in tasks]
    return ResearchHistoryResponse(items=items, total=total, page=page, size=size)


@router.get("/status/{task_id}", response_model=ResearchTaskStatusResponse)
async def get_research_task_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _query_user_task(db, current_user, task_id)
    progress = float(task.progress_percentage or 0.0)
    return ResearchTaskStatusResponse(
        status=task.status,
        progress=progress,
        message=task.current_step,
        estimated_time=task.estimated_duration,
    )


@router.post("/stop/{task_id}")
async def stop_research_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TaskService(db)
    result = service.cancel_task(task_id=task_id, owner_id=current_user.id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Failed to cancel task"))
    return result


@router.post("/retry/{task_id}")
async def retry_research_task(
    task_id: int,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = payload or {}
    force = bool(payload.get("force"))
    service = TaskService(db)
    task = service.retry_task(task_id=task_id, owner_id=current_user.id, force=force)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "success": True,
        "message": "Task retried",
        "new_task_id": task.id,
    }


@router.get("/templates")
async def list_research_templates(
    is_public: Optional[bool] = None,
    page: int = 1,
    size: int = 20,
):
    """返回空的研究模板列表，用于前端占位。"""

    return {
        "items": [],
        "total": 0,
        "page": max(page, 1),
        "size": max(1, size),
        "is_public": is_public,
    }


@router.post("/templates")
async def save_research_template(payload: Dict[str, Any]):
    """保存研究模板的占位实现，直接回显内容。"""

    template = {
        **payload,
        "id": payload.get("id") or f"tmp-{uuid4()}",
        "created_at": payload.get("created_at") or datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    return {"success": True, "data": template}


@router.post("/templates/{template_id}/apply")
async def apply_research_template(
    template_id: str,
    request: Dict[str, Any],
):
    """应用研究模板的占位实现。"""

    return {
        "success": False,
        "task_id": None,
        "message": f"Template '{template_id}' application is not configured",
    }


@router.post("/export/{task_id}")
async def export_research_result(
    task_id: int,
    options: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    format_value = str(options.get("format", "json")).lower()
    include_sources = bool(options.get("include_sources", True))
    include_metadata = bool(options.get("include_metadata", True))
    include_experiences = bool(options.get("include_experience", True))
    include_experiments = bool(options.get("include_experiments", True))
    include_raw = bool(options.get("include_raw_payload", False))

    try:
        task = _query_user_task(db, current_user, task_id)
    except HTTPException:
        raise

    payload = _prepare_export_payload(
        task,
        include_sources=include_sources,
        include_metadata=include_metadata,
        include_experiences=include_experiences,
        include_experiments=include_experiments,
        include_raw=include_raw,
    )

    if format_value == "json":
        data_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        media_type = "application/json"
        extension = "json"
    elif format_value in {"md", "markdown"}:
        markdown = _render_markdown_export(payload)
        data_bytes = markdown.encode("utf-8")
        media_type = "text/markdown"
        extension = "md"
    else:
        raise HTTPException(status_code=400, detail="暂不支持该导出格式")

    buffer = BytesIO(data_bytes)
    buffer.seek(0)

    filename = f"research_{task_id}.{extension}"

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/suggestions")
async def get_research_suggestions(
    request: Dict[str, Any],
):
    """返回基础的研究建议占位数据。"""

    query = request.get("context") or "深入文献分析"
    return {
        "suggestions": [
            {
                "query": f"{query} 的最新进展",
                "mode": "rag",
                "rationale": "快速基于现有文献获取回答",
                "estimated_time": "short",
            },
            {
                "query": f"{query} 的关键挑战",
                "mode": "deep",
                "rationale": "需要系统性的深度分析",
                "estimated_time": "medium",
            },
        ]
    }


@router.post("/rate/{task_id}")
async def rate_research_result(
    task_id: int,
    request: Dict[str, Any],
):
    """反馈占位实现。"""

    rating = request.get("rating")
    return {
        "success": True,
        "message": f"Feedback received with rating={rating}",
    }


@router.post("/share/{task_id}")
async def share_research_result(
    task_id: int,
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成研究结果的分享令牌与链接。"""

    emails = request.get("emails") or []
    if not isinstance(emails, list):
        raise HTTPException(status_code=400, detail="emails 必须为字符串列表")
    if any(not isinstance(item, str) for item in emails):
        raise HTTPException(status_code=400, detail="emails 中的元素必须为字符串")

    message = request.get("message")
    if message is not None and not isinstance(message, str):
        raise HTTPException(status_code=400, detail="message 必须为字符串")

    ttl_minutes_raw = request.get("ttl_minutes", 60)
    try:
        ttl_minutes = int(ttl_minutes_raw)
    except (TypeError, ValueError):
        ttl_minutes = 60

    include_sources = bool(request.get("include_sources", True))
    include_metadata = bool(request.get("include_metadata", True))
    include_experiences = bool(request.get("include_experience", True))
    include_experiments = bool(request.get("include_experiments", True))

    task = _query_user_task(db, current_user, task_id)
    export_payload = _prepare_export_payload(
        task,
        include_sources=include_sources,
        include_metadata=include_metadata,
        include_experiences=include_experiences,
        include_experiments=include_experiments,
        include_raw=True,
    )

    base_url = (
        getattr(settings, "frontend_url", None)
        or getattr(settings, "frontend_base_url", None)
        or "http://localhost:3000"
    )

    record = share_store.create_share(
        db,
        task_id=task_id,
        base_url=base_url,
        payload=export_payload,
        emails=emails,
        message=message,
        ttl_minutes=ttl_minutes,
    )

    return {
        "success": True,
        "share_url": record.share_url,
        "expires_at": record.expires_at.isoformat(),
        "token": record.token,
    }


@router.post("/clone/{task_id}")
async def clone_research_task(
    task_id: int,
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """克隆研究任务占位实现，直接进行任务重试。"""

    service = TaskService(db)
    task = service.retry_task(task_id=task_id, owner_id=current_user.id, force=True)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "success": True,
        "new_task_id": task.id,
        "message": "Task clone triggered by retry",
    }


@router.get("/share/token/{token}")
async def get_shared_research(token: str):
    """根据分享 token 获取共享的研究结果。"""

    record = share_store.get_share(db, token)
    if not record:
        raise HTTPException(status_code=404, detail="分享链接已失效或不存在")

    payload_section: Dict[str, Any] = {}
    if isinstance(record.payload, dict):
        task_section = record.payload.get("task")
        if isinstance(task_section, dict) and {"id", "task_type"}.issubset(task_section.keys()):
            payload_section["task"] = task_section
        result_section = record.payload.get("result")
        if result_section is not None:
            payload_section["result"] = result_section
        if "raw_payload" in record.payload:
            payload_section["raw_payload"] = record.payload["raw_payload"]

    return {
        "success": True,
        "task_id": record.task_id,
        "expires_at": record.expires_at.isoformat(),
        "payload": payload_section,
        "share_url": record.share_url,
        "emails": list(record.emails),
        "message": record.message,
    }


@router.post("/batch")
async def batch_research(
    payload: Dict[str, Any],
):
    """批量研究占位实现。"""

    requests = payload.get("requests")
    if not isinstance(requests, list):
        raise HTTPException(status_code=400, detail="requests must be a list")
    return {
        "success": True,
        "task_ids": [],
        "message": "Batch processing is not yet available",
    }
