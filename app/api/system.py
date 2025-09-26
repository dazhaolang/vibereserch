"""系统与项目相关的附加接口"""

import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.project import Project
from app.models.literature import Literature
from app.schemas.project_schemas import ProjectUpdateRequest
from app.schemas.response_schemas import StandardResponse
import psutil
import datetime
from loguru import logger

from app.core.redis import redis_manager

LIGHTWEIGHT_MODE = os.getenv("LIGHTWEIGHT_MODE", "false").lower() in {"1", "true", "yes", "on"}

router = APIRouter()

# ==================== 文献管理补充 API ====================

@router.delete("/{literature_id}", response_model=StandardResponse)
async def delete_literature(
    literature_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除文献"""
    # 查找文献
    literature = db.query(Literature).filter(Literature.id == literature_id).first()
    if not literature:
        raise HTTPException(status_code=404, detail="文献不存在")

    # 检查权限（通过项目所有权）
    user_project_ids = [p.id for p in current_user.projects]
    literature_project_ids = [p.id for p in literature.projects]

    if not any(pid in user_project_ids for pid in literature_project_ids):
        raise HTTPException(status_code=403, detail="无权限删除此文献")

    # 删除文献
    db.delete(literature)
    db.commit()

    logger.info(f"User {current_user.id} deleted literature {literature_id}")

    return StandardResponse(
        success=True,
        message="文献删除成功",
        data={"deleted_id": literature_id}
    )

# ==================== 项目管理补充 API ====================

@router.put("/{project_id}", response_model=StandardResponse)
async def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新项目信息"""
    # 查找项目
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 更新项目信息
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(project)

    logger.info(f"User {current_user.id} updated project {project_id}")

    return StandardResponse(
        success=True,
        message="项目更新成功",
        data={
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "updated_at": project.updated_at.isoformat()
        }
    )

@router.delete("/{project_id}", response_model=StandardResponse)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除项目（软删除）"""
    # 查找项目
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    # 检查项目是否有关联的任务在运行
    from app.models.task import Task
    active_tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status.in_(["pending", "processing"])
    ).count()

    if active_tasks > 0:
        raise HTTPException(
            status_code=400,
            detail=f"项目有 {active_tasks} 个任务正在运行，请先取消或等待完成"
        )

    # 软删除（标记为已删除）
    project.is_deleted = True
    project.deleted_at = datetime.datetime.utcnow()
    db.commit()

    logger.info(f"User {current_user.id} deleted project {project_id}")

    return StandardResponse(
        success=True,
        message="项目删除成功",
        data={"deleted_id": project_id}
    )

# ==================== 系统状态 API ====================

@router.get("/status", response_model=Dict[str, Any])
async def get_system_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取系统状态"""
    try:
        # CPU和内存使用率
        cpu_percent = psutil.cpu_percent(interval=None) or 0.0
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # 数据库连接状态
        db_status = "healthy"
        try:
            db.execute(text("SELECT 1"))
            pool = getattr(db.bind, "pool", None)
            if pool and hasattr(pool, "size"):
                try:
                    db_active_connections = pool.size()
                except TypeError:
                    db_active_connections = 0
            else:
                db_active_connections = 0
        except Exception as e:
            db_status = "unhealthy"
            db_active_connections = 0
            logger.error(f"Database health check failed: {e}")

        # Redis状态（如果配置了）
        if LIGHTWEIGHT_MODE:
            redis_status = "skipped"
        else:
            redis_status = "healthy"
            try:
                client = await redis_manager.get_client()
                if client is None:
                    redis_status = "unavailable"
                else:
                    await client.ping()
            except Exception:
                redis_status = "unhealthy"

        # Elasticsearch状态
        if LIGHTWEIGHT_MODE:
            es_status = "skipped"
        else:
            es_status = "healthy"
            try:
                from app.core.elasticsearch import get_elasticsearch

                es_client_instance = await get_elasticsearch()
                if es_client_instance.client is None:
                    es_status = "unavailable"
                else:
                    await es_client_instance.client.ping()
            except Exception:
                es_status = "unhealthy"

        # 任务队列状态
        from app.models.task import Task
        pending_tasks = db.query(Task).filter(Task.status == "pending").count()
        processing_tasks = db.query(Task).filter(Task.status == "processing").count()

        return {
            "status": "ok",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
            },
            "services": {
                "database": {
                    "status": db_status,
                    "active_connections": db_active_connections
                },
                "redis": {
                    "status": redis_status
                },
                "elasticsearch": {
                    "status": es_status
                },
                "task_queue": {
                    "pending": pending_tasks,
                    "processing": processing_tasks
                }
            },
            "health_check": all([
                db_status == "healthy",
                cpu_percent < 90,
                memory.percent < 90,
                disk.percent < 90
            ])
        }
    except Exception as e:
        logger.error(f"System status check failed: {e}")
        raise HTTPException(status_code=500, detail="系统状态检查失败")

@router.get("/capabilities", response_model=Dict[str, Any])
async def get_system_capabilities():
    """获取系统能力和功能列表"""
    return {
        "version": "1.0.0",
        "name": "VibeSearch",
        "description": "科研文献智能分析平台",
        "capabilities": {
            "research_modes": [
                {
                    "id": "rag",
                    "name": "RAG模式",
                    "description": "快速检索现有知识库",
                    "enabled": True
                },
                {
                    "id": "deep",
                    "name": "深度研究模式",
                    "description": "生成专属研究经验",
                    "enabled": True,
                    "config": {
                        "iterations": 5,
                        "papers_per_iteration": 5
                    }
                },
                {
                    "id": "auto",
                    "name": "全自动模式",
                    "description": "AI智能编排研究流程",
                    "enabled": True
                }
            ],
            "import_formats": [
                "PDF", "DOI", "Zotero (RIS/BIB/JSON/RDF)"
            ],
            "export_formats": [
                "PDF", "Markdown", "JSON", "CSV", "BibTeX"
            ],
            "ai_models": [
                {
                    "id": "claude-3",
                    "name": "Claude 3",
                    "provider": "Anthropic",
                    "enabled": True
                }
            ],
            "mcp_tools": [
                {
                    "id": "sequential-thinking",
                    "name": "Sequential Thinking",
                    "description": "结构化多步推理",
                    "enabled": True
                },
                {
                    "id": "context7",
                    "name": "Context7",
                    "description": "文档检索和模式指导",
                    "enabled": True
                },
                {
                    "id": "magic",
                    "name": "Magic UI",
                    "description": "UI组件生成",
                    "enabled": True
                }
            ],
            "features": {
                "realtime_collaboration": False,
                "offline_mode": False,
                "batch_processing": True,
                "auto_citation": True,
                "knowledge_graph": False,
                "multi_language": False,
                "two_factor_auth": False
            },
            "limits": {
                "max_upload_size_mb": 50,
                "max_concurrent_tasks": 10,
                "max_literature_per_project": 10000,
                "max_projects_per_user": 100,
                "api_rate_limit": {
                    "requests_per_minute": 60,
                    "requests_per_hour": 1000
                }
            },
            "supported_languages": ["zh-CN", "en-US"],
            "api_version": "v1",
            "documentation_url": "/api/docs"
        }
    }

# ==================== 健康检查 API ====================

@router.get("/health")
async def health_check():
    """简单的健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
