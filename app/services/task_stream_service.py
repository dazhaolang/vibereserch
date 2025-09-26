"""Unified task progress handling service."""

from typing import Dict, Optional, Callable, Awaitable
from datetime import datetime

from sqlalchemy.orm import Session
from loguru import logger

from app.models.task import Task, TaskProgress, TaskStatus
from app.services.stream_progress_service import StreamProgressService
from app.services.task_cost_tracker import task_cost_tracker


class TaskStreamService:
    def __init__(self, db: Session, stream_service: Optional[StreamProgressService] = None):
        self.db = db
        self.stream_service = stream_service or StreamProgressService()

    async def start_task(self, task: Task, step: str) -> None:
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.utcnow()
        task.current_step = step
        task.progress_percentage = 0.0
        self.db.commit()
        await self.stream_service.broadcast_task_update(task.id, {
            "type": "task_started",
            "task_id": task.id,
            "progress": 0,
            "current_step": step
        })

    async def update_progress(
        self,
        task: Task,
        step: str,
        progress: int,
        details: Optional[Dict] = None
    ) -> None:
        task.current_step = step
        task.progress_percentage = progress
        if details:
            task.result = details
        progress_log = TaskProgress(
            task_id=task.id,
            step_name=step,
            step_description=details.get("description") if details else None,
            progress_percentage=progress,
            step_result=details
        )
        self.db.add(progress_log)
        self.db.commit()
        await self.stream_service.broadcast_task_update(task.id, {
            "type": "task_progress",
            "task_id": task.id,
            "progress": progress,
            "current_step": step,
            "details": details
        })

    async def complete_task(self, task: Task, details: Optional[Dict] = None) -> None:
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = datetime.utcnow()
        if task.started_at:
            task.actual_duration = int((task.completed_at - task.started_at).total_seconds())
        task.current_step = "任务完成"
        task.progress_percentage = 100.0
        if details:
            task.result = details
        self.db.commit()
        await self.stream_service.broadcast_task_update(task.id, {
            "type": "task_completed",
            "task_id": task.id,
            "progress": 100,
            "current_step": task.current_step,
            "result": details,
            "token_usage": task.token_usage or 0.0,
            "cost_estimate": task.cost_estimate or 0.0,
            "cost_breakdown": task.cost_breakdown or {}
        })

    async def fail_task(self, task: Task, error_message: str) -> None:
        task.status = TaskStatus.FAILED.value
        task.completed_at = datetime.utcnow()
        if task.started_at:
            task.actual_duration = int((task.completed_at - task.started_at).total_seconds())
        task.error_message = error_message
        task.result = {"success": False, "error": error_message}
        self.db.commit()
        await self.stream_service.broadcast_task_update(task.id, {
            "type": "task_failed",
            "task_id": task.id,
            "error": error_message,
            "token_usage": task.token_usage or 0.0,
            "cost_estimate": task.cost_estimate or 0.0,
            "cost_breakdown": task.cost_breakdown or {}
        })

    async def run_with_progress(
        self,
        task: Task,
        initial_step: str,
        coroutine: Callable[[Callable[[str, int, Optional[Dict]], Awaitable[None]]], Awaitable[Dict]]
    ) -> Dict:
        await self.start_task(task, initial_step)

        async def progress_callback(step: str, progress: int, details: Optional[Dict] = None):
            await self.update_progress(task, step, progress, details)

        try:
            token = task_cost_tracker.activate(task.id, self.db)
            result = await coroutine(progress_callback)
            await self.complete_task(task, result)
            return result
        except Exception as exc:
            logger.error(f"Task {task.id} failed: {exc}")
            await self.fail_task(task, str(exc))
            raise
        finally:
            task_cost_tracker.deactivate(token)
