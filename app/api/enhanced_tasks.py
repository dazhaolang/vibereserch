"""
增强的任务进度API
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.task import Task, TaskProgress, TaskType, TaskStatus
from app.services.enhanced_progress_service import enhanced_progress_service
from app.services.stream_progress_service import stream_progress_service
from app.services.task_service import TaskService
from app.schemas.task_schemas import (
    TaskDetailResponse,
    TaskListResponse,
    TaskStatisticsResponse,
    TaskCostSummary,
    TaskStatusBreakdown,
)
from loguru import logger

router = APIRouter()

class TaskCreateRequest(BaseModel):
    project_id: int
    task_type: str
    title: str
    description: Optional[str] = None
    config: Dict[str, Any] = {}
    input_data: Dict[str, Any] = {}

class TaskProgressResponse(BaseModel):
    task_id: str
    title: str
    description: Optional[str]
    status: str
    progress_percentage: float
    current_step: Optional[str]
    estimated_duration: Optional[int]
    started_at: Optional[str]
    completed_at: Optional[str]
    progress_history: List[Dict[str, Any]]

class TaskOverviewCostSummary(BaseModel):
    total_cost: float = 0.0
    estimated_remaining: float = 0.0
    total_token_usage: float = 0.0


class TaskOverviewResponse(BaseModel):
    total_tasks: int
    status_breakdown: Dict[str, int] = Field(default_factory=dict)
    running_task_ids: List[int] = Field(default_factory=list)
    cost_summary: TaskOverviewCostSummary
    recent_tasks: List[TaskDetailResponse] = Field(default_factory=list)


class TaskPerformanceMetricsResponse(BaseModel):
    average_duration_seconds: float
    success_rate: float
    average_progress: float
    running_tasks: int


class TaskCostAnalysisResponse(BaseModel):
    total_cost_estimate: float
    average_cost_estimate: float
    total_token_usage: float
    model_breakdown: Dict[str, Dict[str, float]] = Field(default_factory=dict)


@router.get("/list", response_model=TaskListResponse)
async def list_tasks(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """列出当前用户的任务"""

    status_enum: Optional[TaskStatus] = None
    if status:
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的任务状态: {status}")

    service = TaskService(db)
    tasks = service.list_tasks(
        owner_id=current_user.id,
        project_id=project_id,
        status=status_enum,
    )

    return TaskListResponse(
        tasks=[TaskDetailResponse.from_orm(task) for task in tasks]
    )


@router.get("/overview", response_model=TaskOverviewResponse)
async def get_task_overview(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """返回任务概览指标，供前端仪表盘使用"""

    service = TaskService(db)
    stats = service.get_task_statistics(
        owner_id=current_user.id,
        project_id=project_id,
        limit_recent=5,
    )

    status_breakdown = {
        item["status"]: item["count"]
        for item in stats.get("status_breakdown", [])
    }

    recent_tasks = [
        TaskDetailResponse.from_orm(task)
        for task in stats.get("recent_tasks", [])
    ]

    cost_summary = stats.get("cost_summary", {})

    return TaskOverviewResponse(
        total_tasks=stats.get("total_tasks", 0),
        status_breakdown=status_breakdown,
        running_task_ids=stats.get("running_task_ids", []),
        cost_summary=TaskOverviewCostSummary(
            total_cost=cost_summary.get("total_cost_estimate", 0.0),
            estimated_remaining=cost_summary.get("estimated_remaining", 0.0),
            total_token_usage=cost_summary.get("total_token_usage", 0.0),
        ),
        recent_tasks=recent_tasks,
    )


@router.get("/statistics", response_model=TaskStatisticsResponse)
async def get_task_statistics(
    project_id: Optional[int] = None,
    limit_recent: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """返回任务统计详情"""

    service = TaskService(db)
    stats = service.get_task_statistics(
        owner_id=current_user.id,
        project_id=project_id,
        limit_recent=limit_recent,
    )

    cost_summary = stats.get("cost_summary", {})
    breakdown = [
        TaskStatusBreakdown(status=item["status"], count=item["count"])
        for item in stats.get("status_breakdown", [])
    ]
    recent = [TaskDetailResponse.from_orm(task) for task in stats.get("recent_tasks", [])]

    return TaskStatisticsResponse(
        total_tasks=stats.get("total_tasks", 0),
        status_breakdown=breakdown,
        running_tasks=stats.get("running_task_ids", []),
        recent_tasks=recent,
        cost_summary=TaskCostSummary(
            total_token_usage=cost_summary.get("total_token_usage", 0.0),
            total_cost_estimate=cost_summary.get("total_cost_estimate", 0.0),
            models=cost_summary.get("models", {}),
        ),
    )


@router.get("/performance_metrics", response_model=TaskPerformanceMetricsResponse)
async def get_task_performance_metrics(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """计算任务执行的性能指标"""

    service = TaskService(db)
    tasks = service.list_tasks(owner_id=current_user.id, project_id=project_id)

    durations = [task.actual_duration for task in tasks if task.actual_duration]
    average_duration = sum(durations) / len(durations) if durations else 0.0

    completed = [task for task in tasks if task.status == TaskStatus.COMPLETED.value]
    success_rate = len(completed) / len(tasks) if tasks else 0.0

    average_progress = (
        sum(task.progress_percentage for task in tasks) / len(tasks)
        if tasks
        else 0.0
    )

    running_tasks = len(
        [
            task
            for task in tasks
            if task.status in {TaskStatus.PENDING.value, TaskStatus.RUNNING.value}
        ]
    )

    return TaskPerformanceMetricsResponse(
        average_duration_seconds=average_duration,
        success_rate=success_rate,
        average_progress=average_progress,
        running_tasks=running_tasks,
    )


@router.get("/cost_analysis", response_model=TaskCostAnalysisResponse)
async def get_task_cost_analysis(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """汇总任务成本信息，用于成本面板展示"""

    service = TaskService(db)
    tasks = service.list_tasks(owner_id=current_user.id, project_id=project_id)

    total_cost = sum(task.cost_estimate or 0.0 for task in tasks)
    total_tokens = sum(task.token_usage or 0.0 for task in tasks)
    average_cost = total_cost / len(tasks) if tasks else 0.0

    model_breakdown: Dict[str, Dict[str, float]] = {}
    for task in tasks:
        if not task.cost_breakdown:
            continue
        for model_name, metrics in task.cost_breakdown.items():
            entry = model_breakdown.setdefault(
                model_name,
                {"total_tokens": 0.0, "cost": 0.0},
            )
            entry["total_tokens"] += metrics.get("total_tokens", 0.0) or 0.0
            entry["cost"] += metrics.get("cost", 0.0) or 0.0

    return TaskCostAnalysisResponse(
        total_cost_estimate=total_cost,
        average_cost_estimate=average_cost,
        total_token_usage=total_tokens,
        model_breakdown=model_breakdown,
    )

@router.post("/create")
async def create_task(
    task_data: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """创建新的后台任务"""

    try:
        # 验证任务类型
        task_type = TaskType(task_data.task_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的任务类型: {task_data.task_type}")

    # 创建持久化任务
    db_task = await enhanced_progress_service.create_persistent_task(
        project_id=task_data.project_id,
        task_type=task_type,
        title=task_data.title,
        description=task_data.description,
        config=task_data.config,
        input_data=task_data.input_data,
        db=db
    )

    # 启动后台任务处理
    background_tasks.add_task(
        execute_background_task,
        str(db_task.id),
        task_type,
        task_data.config,
        task_data.input_data
    )

    return {
        "task_id": str(db_task.id),
        "message": "任务已创建并开始处理",
        "websocket_url": f"/ws/progress/{db_task.id}",
        "estimated_duration": db_task.estimated_duration
    }

@router.get("/{task_id}/progress", response_model=TaskProgressResponse)
async def get_task_progress(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取任务进度详情"""

    task_progress = await enhanced_progress_service.get_task_progress_from_db(task_id, db)

    if "error" in task_progress:
        raise HTTPException(status_code=404, detail=task_progress["error"])

    # 确保内存服务中有任务状态（支持页面刷新后恢复）
    if task_id not in stream_progress_service.active_tasks:
        await enhanced_progress_service.restore_task_progress(task_id, db)

    return TaskProgressResponse(**task_progress)

@router.get("/active")
async def get_active_tasks(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取活动任务列表"""

    query = db.query(Task).filter(
        Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value])
    )

    if project_id:
        query = query.filter(Task.project_id == project_id)

    active_tasks = query.all()

    # 确保所有活动任务在内存服务中都有状态
    for task in active_tasks:
        if str(task.id) not in stream_progress_service.active_tasks:
            await enhanced_progress_service.restore_task_progress(str(task.id), db)

    return [
        {
            "task_id": str(task.id),
            "title": task.title,
            "status": task.status,
            "progress_percentage": task.progress_percentage,
            "current_step": task.current_step,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "project_id": task.project_id
        }
        for task in active_tasks
    ]

@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """取消任务"""

    db_task = db.query(Task).filter(Task.id == int(task_id)).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if db_task.status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]:
        raise HTTPException(status_code=400, detail="任务已完成或已取消")

    # 更新数据库状态
    db_task.status = TaskStatus.CANCELLED.value
    db_task.completed_at = datetime.now()
    db.commit()

    # 更新内存服务状态
    if task_id in stream_progress_service.active_tasks:
        await stream_progress_service.fail_task(task_id, "用户取消")

    return {"message": "任务已取消"}

async def execute_background_task(
    task_id: str,
    task_type: TaskType,
    config: Dict[str, Any],
    input_data: Dict[str, Any]
):
    """执行后台任务的示例实现"""

    try:
        if task_type == TaskType.LITERATURE_COLLECTION:
            await execute_literature_collection_task(task_id, config, input_data)
        elif task_type == TaskType.EXPERIENCE_GENERATION:
            await execute_experience_generation_task(task_id, config, input_data)
        elif task_type == TaskType.QUESTION_ANALYSIS:
            await execute_question_analysis_task(task_id, config, input_data)
        else:
            await execute_full_workflow_task(task_id, config, input_data)

    except Exception as e:
        logger.error(f"后台任务执行失败: {task_id} - {e}")

        # 更新任务状态为失败
        with next(get_db()) as db:
            db_task = db.query(Task).filter(Task.id == int(task_id)).first()
            if db_task:
                db_task.status = TaskStatus.FAILED.value
                db_task.error_message = str(e)
                db_task.completed_at = datetime.now()
                db.commit()

        await stream_progress_service.fail_task(task_id, str(e))

async def execute_literature_collection_task(
    task_id: str,
    config: Dict[str, Any],
    input_data: Dict[str, Any]
):
    """执行文献采集任务的详细实现"""

    db = next(get_db())

    try:
        # 步骤1: 初始化搜索参数
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="init_search",
            step_progress=0,
            step_message="正在初始化搜索参数...",
            db=db
        )

        # 模拟处理时间
        await asyncio.sleep(2)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="init_search",
            step_progress=100,
            step_message="搜索参数初始化完成",
            step_result={"keywords": input_data.get("keywords", [])},
            db=db
        )

        # 步骤2: 连接ResearchRabbit API
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="connect_api",
            step_progress=0,
            step_message="正在连接ResearchRabbit API...",
            db=db
        )

        await asyncio.sleep(3)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="connect_api",
            step_progress=100,
            step_message="API连接建立成功",
            step_result={"api_status": "connected"},
            db=db
        )

        # 步骤3: 执行文献搜索
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="search_execute",
            step_progress=0,
            step_message="正在执行文献搜索...",
            db=db
        )

        # 模拟搜索进度
        for progress in [25, 50, 75, 100]:
            await asyncio.sleep(5)
            message = f"正在搜索文献... ({progress}%)"
            if progress == 100:
                message = "文献搜索完成"

            await enhanced_progress_service.update_task_progress(
                task_id=task_id,
                step_id="search_execute",
                step_progress=progress,
                step_message=message,
                step_result={"found_count": 156} if progress == 100 else None,
                db=db
            )

        # 步骤4: 质量筛选
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="quality_filter",
            step_progress=0,
            step_message="正在进行质量筛选和排序...",
            db=db
        )

        for progress in [30, 60, 100]:
            await asyncio.sleep(4)
            message = f"正在筛选文献... ({progress}%)"
            if progress == 100:
                message = "质量筛选完成"

            await enhanced_progress_service.update_task_progress(
                task_id=task_id,
                step_id="quality_filter",
                step_progress=progress,
                step_message=message,
                step_result={"filtered_count": 89} if progress == 100 else None,
                db=db
            )

        # 步骤5: 下载元数据
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="metadata_download",
            step_progress=0,
            step_message="正在下载文献元数据...",
            db=db
        )

        await asyncio.sleep(8)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="metadata_download",
            step_progress=100,
            step_message="元数据下载完成",
            step_result={"metadata_complete": True},
            db=db
        )

        # 步骤6: 保存到数据库
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="database_save",
            step_progress=0,
            step_message="正在保存到数据库...",
            db=db
        )

        await asyncio.sleep(3)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="database_save",
            step_progress=100,
            step_message="文献采集任务完成",
            step_result={
                "total_collected": 89,
                "high_quality": 67,
                "completion_time": datetime.now().isoformat()
            },
            db=db
        )

    finally:
        db.close()

async def execute_experience_generation_task(
    task_id: str,
    config: Dict[str, Any],
    input_data: Dict[str, Any]
):
    """执行经验生成任务"""

    db = next(get_db())

    try:
        # 经验生成的各个迭代步骤
        iterations = ["iteration_1", "iteration_2", "iteration_3"]

        for i, iteration in enumerate(iterations, 1):
            await enhanced_progress_service.update_task_progress(
                task_id=task_id,
                step_id=iteration,
                step_progress=0,
                step_message=f"正在进行第{i}轮经验迭代...",
                db=db
            )

            # 模拟迭代过程
            for progress in [20, 40, 60, 80, 100]:
                await asyncio.sleep(3)
                message = f"第{i}轮迭代进行中... ({progress}%)"
                if progress == 100:
                    message = f"第{i}轮迭代完成"

                await enhanced_progress_service.update_task_progress(
                    task_id=task_id,
                    step_id=iteration,
                    step_progress=progress,
                    step_message=message,
                    step_result={"iteration": i, "information_gain": 0.3 + i * 0.1} if progress == 100 else None,
                    db=db
                )

        # 经验汇总
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="experience_summary",
            step_progress=0,
            step_message="正在汇总经验内容...",
            db=db
        )

        await asyncio.sleep(5)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="experience_summary",
            step_progress=100,
            step_message="经验汇总完成",
            db=db
        )

        # 质量评估
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="quality_assessment",
            step_progress=0,
            step_message="正在进行质量评估...",
            db=db
        )

        await asyncio.sleep(3)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="quality_assessment",
            step_progress=100,
            step_message="经验生成任务完成",
            step_result={
                "quality_score": 8.7,
                "experience_length": 2456,
                "completion_time": datetime.now().isoformat()
            },
            db=db
        )

    finally:
        db.close()

async def execute_question_analysis_task(
    task_id: str,
    config: Dict[str, Any],
    input_data: Dict[str, Any]
):
    """执行智能问答任务"""

    db = next(get_db())

    try:
        # 问题分析
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="question_analysis",
            step_progress=0,
            step_message="正在分析用户问题...",
            db=db
        )

        await asyncio.sleep(3)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="question_analysis",
            step_progress=100,
            step_message="问题分析完成",
            step_result={"question_intent": "synthesis_method_inquiry"},
            db=db
        )

        # 知识检索
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="knowledge_retrieval",
            step_progress=0,
            step_message="正在检索相关知识...",
            db=db
        )

        await asyncio.sleep(4)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="knowledge_retrieval",
            step_progress=100,
            step_message="知识检索完成",
            step_result={"relevant_segments": 15},
            db=db
        )

        # 答案生成
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="answer_generation",
            step_progress=0,
            step_message="正在生成结构化答案...",
            db=db
        )

        for progress in [25, 50, 75, 100]:
            await asyncio.sleep(3)
            message = f"正在生成答案... ({progress}%)"
            if progress == 100:
                message = "答案生成完成"

            await enhanced_progress_service.update_task_progress(
                task_id=task_id,
                step_id="answer_generation",
                step_progress=progress,
                step_message=message,
                db=db
            )

        # 结果验证
        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="result_validation",
            step_progress=0,
            step_message="正在验证答案准确性...",
            db=db
        )

        await asyncio.sleep(2)

        await enhanced_progress_service.update_task_progress(
            task_id=task_id,
            step_id="result_validation",
            step_progress=100,
            step_message="智能问答任务完成",
            step_result={
                "answer_quality": 9.2,
                "confidence": 0.91,
                "completion_time": datetime.now().isoformat()
            },
            db=db
        )

    finally:
        db.close()

async def execute_full_workflow_task(
    task_id: str,
    config: Dict[str, Any],
    input_data: Dict[str, Any]
):
    """执行完整工作流任务"""

    # 依次执行各个子任务
    await execute_literature_collection_task(task_id, config, input_data)
    await execute_experience_generation_task(task_id, config, input_data)
    await execute_question_analysis_task(task_id, config, input_data)
