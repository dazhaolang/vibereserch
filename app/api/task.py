"""
任务管理API路由
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.task import Task, TaskProgress
from app.models.project import Project

router = APIRouter()

@router.get("/{task_id}")
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取任务详情"""
    
    # 获取任务
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 验证权限：确保任务属于用户的项目
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    
    return {
        "id": task.id,
        "project_id": task.project_id,
        "task_type": task.task_type,
        "title": task.title,
        "description": task.description,
        "config": task.config,
        "input_data": task.input_data,
        "status": task.status,
        "progress_percentage": task.progress_percentage,
        "current_step": task.current_step,
        "result": task.result,
        "error_message": task.error_message,
        "estimated_duration": task.estimated_duration,
        "actual_duration": task.actual_duration,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat() if task.updated_at else None
    }

@router.get("/{task_id}/progress")
async def get_task_progress(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取任务进度历史"""
    
    # 获取任务并验证权限
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    
    # 获取进度记录
    progress_list = db.query(TaskProgress).filter(
        TaskProgress.task_id == task_id
    ).order_by(TaskProgress.started_at.desc()).all()
    
    progress_data = []
    for progress in progress_list:
        progress_data.append({
            "id": progress.id,
            "step_name": progress.step_name,
            "progress_percentage": progress.progress_percentage,
            "step_result": progress.step_result,
            "started_at": progress.started_at.isoformat(),
            "completed_at": progress.completed_at.isoformat() if progress.completed_at else None
        })
    
    return {
        "task_id": task_id,
        "current_status": task.status,
        "current_progress": task.progress_percentage,
        "current_step": task.current_step,
        "progress_history": progress_data
    }