"""Track token usage and estimated costs for tasks."""

from contextvars import ContextVar
from typing import Dict, Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.task import Task

_task_context: ContextVar[Optional[Tuple[Optional[int], Optional[Session]]]] = ContextVar(
    "current_task_context",
    default=None,
)

# Rough USD cost per 1K tokens for common models
_MODEL_PRICING = {
    "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
}


class TaskCostTracker:
    def __init__(self) -> None:
        self._session_factory = SessionLocal

    def activate(self, task_id: Optional[int], session: Optional[Session] = None):
        """Mark subsequent AI usage as belonging to a task."""
        return _task_context.set((task_id, session))

    def deactivate(self, token) -> None:
        if token is not None:
            _task_context.reset(token)

    def record_usage(self, model: str, usage: Dict[str, Optional[int]]) -> None:
        context = _task_context.get()
        if not context:
            return

        task_id, bound_session = context
        if not task_id:
            return

        total_tokens = usage.get("total_tokens") or 0
        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0

        cost = self._estimate_cost(model, prompt_tokens, completion_tokens)
        breakdown = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
        }

        db: Session
        own_session = False
        if bound_session is not None:
            db = bound_session
        else:
            db = self._session_factory()
            own_session = True

        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return

            task.token_usage = (task.token_usage or 0.0) + total_tokens
            task.cost_estimate = (task.cost_estimate or 0.0) + cost

            current_breakdown = task.cost_breakdown or {}
            model_breakdown = current_breakdown.get(model, {})
            model_breakdown["total_tokens"] = model_breakdown.get("total_tokens", 0) + total_tokens
            model_breakdown["prompt_tokens"] = model_breakdown.get("prompt_tokens", 0) + prompt_tokens
            model_breakdown["completion_tokens"] = model_breakdown.get("completion_tokens", 0) + completion_tokens
            model_breakdown["cost"] = model_breakdown.get("cost", 0.0) + cost
            current_breakdown[model] = model_breakdown
            task.cost_breakdown = current_breakdown

            if own_session:
                db.commit()
            else:
                db.flush()
        except Exception as exc:
            if own_session:
                db.rollback()
            logger.warning(f"Failed to record task usage for task {task_id}: {exc}")
        finally:
            if own_session:
                db.close()

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = _MODEL_PRICING.get(model.lower()) or _MODEL_PRICING.get(model)
        if not pricing:
            return 0.0
        prompt_cost = pricing.get("prompt", 0.0) * (prompt_tokens / 1000.0)
        completion_cost = pricing.get("completion", 0.0) * (completion_tokens / 1000.0)
        return prompt_cost + completion_cost


task_cost_tracker = TaskCostTracker()
