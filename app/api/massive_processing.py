"""
大规模文献处理API端点
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.services.massive_processing_integration import (
    start_massive_processing_task,
    get_massive_processing_status,
    stop_massive_processing,
    ProcessingConfigOptimizer,
    MassiveProcessingReporter,
    integrate_with_existing_literature_tasks
)
from sqlalchemy.orm import Session
from loguru import logger

router = APIRouter(prefix="/api/massive-processing", tags=["大规模处理"])


class MassiveProcessingRequest(BaseModel):
    """大规模处理请求模型"""
    project_id: int = Field(..., description="项目ID")
    batch_size: int = Field(20, ge=5, le=50, description="批处理大小")
    max_concurrent: int = Field(10, ge=1, le=50, description="最大并发数")
    max_retries: int = Field(3, ge=1, le=5, description="最大重试次数")
    memory_limit: float = Field(8.0, ge=1.0, le=32.0, description="内存限制(GB)")
    resume_from_checkpoint: bool = Field(True, description="是否从断点恢复")
    enable_performance_monitoring: bool = Field(True, description="是否启用性能监控")


class ProcessingConfigOptimizationRequest(BaseModel):
    """处理配置优化请求模型"""
    project_id: int = Field(..., description="项目ID")
    literature_count: Optional[int] = Field(None, description="文献数量(可选，将自动检测)")


class IntegratedLiteratureProcessingRequest(BaseModel):
    """集成文献处理请求模型"""
    keywords: List[str] = Field(..., min_items=1, description="搜索关键词")
    project_id: int = Field(..., description="项目ID")
    max_count: int = Field(200, ge=10, le=1000, description="最大文献数量")
    enable_massive_processing: bool = Field(True, description="是否启用大规模处理")
    processing_config: Optional[Dict[str, Any]] = Field(None, description="自定义处理配置")


class ProcessingStatusResponse(BaseModel):
    """处理状态响应模型"""
    success: bool
    session_id: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    current_step: Optional[str] = None
    resource_usage: Optional[Dict[str, str]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/start", summary="启动大规模文献处理")
async def start_massive_processing(
    request: MassiveProcessingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    启动大规模文献处理任务

    支持200-500篇文献的高性能并发处理，包含：
    - 智能资源管理和负载均衡
    - 分批并行处理，避免系统过载
    - 实时进度跟踪和状态报告
    - 断点续传和容错恢复
    """
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == request.project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

        # 检查是否有未完成的大规模处理任务
        existing_task = db.query(Task).filter(
            Task.project_id == request.project_id,
            Task.task_type == "massive_literature_processing",
            Task.status.in_(["pending", "running"])
        ).first()

        if existing_task:
            raise HTTPException(
                status_code=400,
                detail=f"项目已有正在进行的大规模处理任务 (ID: {existing_task.id})"
            )

        # 创建任务记录
        task = Task(
            project_id=request.project_id,
            task_type="massive_literature_processing",
            description="大规模文献批量处理",
            status="pending",
            created_by=current_user.id,
            estimated_duration=3600,  # 1小时预估
            metadata={
                "processing_config": request.dict(),
                "created_at": datetime.utcnow().isoformat()
            }
        )
        db.add(task)
        db.commit()

        # 启动后台处理任务
        background_tasks.add_task(
            start_massive_processing_task,
            task_id=task.id,
            project_id=request.project_id,
            processing_config=request.dict()
        )

        logger.info(f"用户 {current_user.id} 启动大规模处理任务 {task.id} for 项目 {request.project_id}")

        return {
            "success": True,
            "task_id": task.id,
            "project_id": request.project_id,
            "message": "大规模处理任务已启动",
            "estimated_time": "根据文献数量和系统配置动态计算",
            "config": request.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动大规模处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动处理失败: {str(e)}")


@router.get("/status/{task_id}", summary="获取处理状态", response_model=ProcessingStatusResponse)
async def get_processing_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取大规模处理任务的实时状态"""
    try:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 验证权限
        project = db.query(Project).filter(
            Project.id == task.project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=403, detail="无权限访问此任务")

        # 构建状态响应
        task_result = task.result or {}
        processing_results = task_result.get("processing_results", {})

        return ProcessingStatusResponse(
            success=True,
            session_id=processing_results.get("session_id"),
            status=task.status,
            progress=task.progress_percentage,
            current_step=task.current_step,
            resource_usage={
                "memory_peak": f"{processing_results.get('memory_peak', 0):.2f}GB",
                "cpu_peak": f"{processing_results.get('cpu_peak', 0):.1f}%",
                "tokens_used": str(processing_results.get('tokens_used', 0))
            },
            performance_metrics={
                "total_literature": processing_results.get("total_literature", 0),
                "successful": processing_results.get("successful", 0),
                "failed": processing_results.get("failed", 0),
                "throughput": f"{processing_results.get('throughput', 0):.2f} 篇/秒",
                "processing_time": f"{processing_results.get('processing_time', 0):.1f}秒"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取处理状态失败: {e}")
        return ProcessingStatusResponse(
            success=False,
            error=str(e)
        )


@router.post("/stop/{task_id}", summary="停止大规模处理")
async def stop_processing(
    task_id: int,
    save_checkpoint: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """停止大规模处理任务并保存进度"""
    try:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 验证权限
        project = db.query(Project).filter(
            Project.id == task.project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=403, detail="无权限操作此任务")

        if task.status not in ["pending", "running"]:
            raise HTTPException(status_code=400, detail=f"任务状态 '{task.status}' 无法停止")

        # 更新任务状态
        task.status = "cancelled"
        task.completed_at = datetime.utcnow()
        task.error_message = f"用户手动停止 (用户ID: {current_user.id})"

        # 保存停止信息
        current_result = task.result or {}
        current_result.update({
            "stopped_by": current_user.id,
            "stop_time": datetime.utcnow().isoformat(),
            "checkpoint_saved": save_checkpoint
        })
        task.result = current_result

        db.commit()

        # 尝试停止实际的处理器（如果有会话ID的话）
        session_id = current_result.get("processing_results", {}).get("session_id")
        if session_id:
            stop_result = await stop_massive_processing(session_id, save_checkpoint)
        else:
            stop_result = {"success": True, "message": "任务已标记为停止"}

        logger.info(f"用户 {current_user.id} 停止大规模处理任务 {task_id}")

        return {
            "success": True,
            "task_id": task_id,
            "message": "处理任务已停止",
            "checkpoint_saved": save_checkpoint,
            "stop_result": stop_result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"停止处理失败: {str(e)}")


@router.post("/optimize-config", summary="优化处理配置")
async def optimize_processing_config(
    request: ProcessingConfigOptimizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """为指定项目优化大规模处理配置参数"""
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == request.project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

        # 获取文献数量（如果未提供）
        literature_count = request.literature_count
        if literature_count is None:
            from app.models.literature import Literature
            literature_count = db.query(Literature).join(Literature.projects).filter(
                Project.id == request.project_id
            ).count()

        # 优化配置
        optimizer = ProcessingConfigOptimizer()
        optimization_result = await optimizer.optimize_config_for_project(
            request.project_id,
            literature_count
        )

        return optimization_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置优化失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置优化失败: {str(e)}")


@router.get("/report/{task_id}", summary="获取处理报告")
async def get_processing_report(
    task_id: int,
    include_detailed_metrics: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取大规模处理的详细报告"""
    try:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 验证权限
        project = db.query(Project).filter(
            Project.id == task.project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=403, detail="无权限访问此任务")

        # 生成报告
        reporter = MassiveProcessingReporter()
        report_result = await reporter.generate_processing_report(
            task_id,
            include_detailed_metrics
        )

        if not report_result["success"]:
            raise HTTPException(status_code=500, detail=report_result["error"])

        return report_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取处理报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取报告失败: {str(e)}")


@router.post("/integrated-processing", summary="集成文献搜索与大规模处理")
async def integrated_literature_processing(
    request: IntegratedLiteratureProcessingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    集成文献搜索采集与大规模批量处理

    一站式解决方案：
    1. 智能文献搜索和采集
    2. 自动配置优化
    3. 大规模批量处理
    """
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == request.project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

        # 启动集成处理
        background_tasks.add_task(
            integrate_with_existing_literature_tasks,
            keywords=request.keywords,
            project_id=request.project_id,
            max_count=request.max_count,
            enable_massive_processing=request.enable_massive_processing,
            processing_config=request.processing_config
        )

        logger.info(f"用户 {current_user.id} 启动集成文献处理 - 项目 {request.project_id}, 关键词: {request.keywords}")

        return {
            "success": True,
            "project_id": request.project_id,
            "keywords": request.keywords,
            "max_count": request.max_count,
            "massive_processing_enabled": request.enable_massive_processing,
            "message": "集成文献处理已启动",
            "recommendation": "可通过WebSocket或定期查询项目状态来跟踪处理进度"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动集成处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动集成处理失败: {str(e)}")


@router.get("/system-status", summary="获取系统处理能力状态")
async def get_system_processing_status():
    """获取系统当前的大规模处理能力状态"""
    try:
        import psutil

        # 系统资源信息
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)

        # 计算建议的处理能力
        available_memory_gb = (memory.available) / (1024**3)
        recommended_concurrent = min(20, max(5, int(available_memory_gb / 0.5)))  # 每个任务约500MB

        # 系统负载评估
        if cpu_percent < 30 and memory.percent < 50:
            load_level = "低"
            max_literature_capacity = 500
        elif cpu_percent < 60 and memory.percent < 70:
            load_level = "中等"
            max_literature_capacity = 200
        else:
            load_level = "高"
            max_literature_capacity = 50

        return {
            "success": True,
            "system_info": {
                "cpu_cores": psutil.cpu_count(),
                "cpu_usage": f"{cpu_percent:.1f}%",
                "memory_total": f"{memory.total / (1024**3):.1f}GB",
                "memory_available": f"{available_memory_gb:.1f}GB",
                "memory_usage": f"{memory.percent:.1f}%"
            },
            "processing_capacity": {
                "load_level": load_level,
                "recommended_concurrent": recommended_concurrent,
                "max_literature_capacity": max_literature_capacity,
                "optimal_batch_size": min(30, max(10, int(available_memory_gb)))
            },
            "recommendations": {
                "best_processing_time": "系统负载较低时建议进行大规模处理",
                "memory_optimization": "建议在处理前关闭不必要的服务以释放内存",
                "concurrent_limit": f"当前建议最大并发数: {recommended_concurrent}"
            }
        }

    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")


@router.get("/tasks/{project_id}", summary="获取项目的处理任务列表")
async def get_project_processing_tasks(
    project_id: int,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定项目的大规模处理任务列表"""
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

        # 查询任务
        query = db.query(Task).filter(
            Task.project_id == project_id,
            Task.task_type == "massive_literature_processing"
        )

        if status_filter:
            query = query.filter(Task.status == status_filter)

        tasks = query.order_by(Task.created_at.desc()).all()

        # 构建任务列表
        task_list = []
        for task in tasks:
            task_result = task.result or {}
            processing_results = task_result.get("processing_results", {})

            task_info = {
                "task_id": task.id,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "progress": task.progress_percentage or 0,
                "current_step": task.current_step,
                "duration": task.actual_duration,
                "description": task.description,
                "performance_summary": task_result.get("performance_summary", {}),
                "error_message": task.error_message
            }

            if processing_results:
                task_info["results"] = {
                    "total_literature": processing_results.get("total_literature", 0),
                    "successful": processing_results.get("successful", 0),
                    "failed": processing_results.get("failed", 0),
                    "session_id": processing_results.get("session_id")
                }

            task_list.append(task_info)

        return {
            "success": True,
            "project_id": project_id,
            "total_tasks": len(task_list),
            "tasks": task_list
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")