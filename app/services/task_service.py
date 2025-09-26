"""Business logic for task management"""

from typing import List, Optional, Dict, Any, Callable

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus, TaskProgress, TaskType
from app.models.project import Project
from app.models.literature import Literature
from app.tasks.celery_tasks import (
    search_and_build_library_celery,
    ai_search_batch_celery,
    literature_collection_celery,
    literature_processing_celery,
    experience_generation_celery,
    literature_index_celery,
    download_pdf_celery,
)
from loguru import logger


class TaskService:
    """Encapsulates task queries and actions"""

    def __init__(self, db: Session):
        self.db = db

    def list_tasks(
        self,
        owner_id: int,
        project_id: Optional[int] = None,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        query = (
            self.db.query(Task)
            .join(Project)
            .filter(Project.owner_id == owner_id)
        )

        if project_id:
            query = query.filter(Task.project_id == project_id)
        if status:
            query = query.filter(Task.status == status.value)

        return query.order_by(Task.created_at.desc()).all()

    def get_task(self, task_id: int, owner_id: int) -> Optional[Task]:
        return (
            self.db.query(Task)
            .join(Project)
            .filter(Task.id == task_id, Project.owner_id == owner_id)
            .first()
        )

    def retry_task(self, task_id: int, owner_id: int, force: bool = False) -> Task:
        task = self.get_task(task_id, owner_id)
        if not task:
            return None

        if task.status not in {TaskStatus.FAILED.value, TaskStatus.CANCELLED.value} and not force:
            raise ValueError("Only failed or cancelled tasks can be retried without force")

        # Reset task state
        task.status = TaskStatus.PENDING.value
        task.progress_percentage = 0.0
        task.current_step = "等待调度"
        task.error_message = None
        task.started_at = None
        task.completed_at = None
        task.actual_duration = None
        task.result = None

        self.db.query(TaskProgress).filter(TaskProgress.task_id == task.id).delete()
        self.db.commit()

        logger.info(f"Retrying task {task_id} of type {task.task_type}")

        self.db.refresh(task)
        self._dispatch_task(task)
        return task

    def cancel_task(self, task_id: int, owner_id: int) -> dict:
        task = self.get_task(task_id, owner_id)
        if not task:
            return {"success": False, "message": "Task not found"}

        if task.status in {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value}:
            return {"success": False, "message": "Task already finished"}

        task.status = TaskStatus.CANCELLED.value
        self.db.commit()

        logger.info(f"Task {task_id} cancelled by user {owner_id}")
        return {"success": True, "message": "Task cancelled"}

    def get_task_statistics(
        self,
        owner_id: int,
        project_id: Optional[int] = None,
        limit_recent: int = 5,
    ) -> Dict[str, Any]:
        """Aggregate high-level task metrics for dashboards."""

        query = (
            self.db.query(Task)
            .join(Project)
            .filter(Project.owner_id == owner_id)
        )

        if project_id:
            query = query.filter(Task.project_id == project_id)

        tasks = query.order_by(Task.created_at.desc()).all()

        status_counter: Dict[str, int] = {}
        running_task_ids: List[int] = []
        total_tokens = 0.0
        total_cost = 0.0
        model_breakdown: Dict[str, Dict[str, float]] = {}

        for task in tasks:
            status_counter[task.status] = status_counter.get(task.status, 0) + 1
            if task.status == TaskStatus.RUNNING.value:
                running_task_ids.append(task.id)

            total_tokens += task.token_usage or 0.0
            total_cost += task.cost_estimate or 0.0

            if task.cost_breakdown:
                for model_name, metrics in task.cost_breakdown.items():
                    entry = model_breakdown.setdefault(
                        model_name,
                        {
                            "total_tokens": 0.0,
                            "prompt_tokens": 0.0,
                            "completion_tokens": 0.0,
                            "cost": 0.0,
                        },
                    )

                    entry["total_tokens"] += metrics.get("total_tokens", 0.0) or 0.0
                    entry["prompt_tokens"] += metrics.get("prompt_tokens", 0.0) or 0.0
                    entry["completion_tokens"] += metrics.get("completion_tokens", 0.0) or 0.0
                    entry["cost"] += metrics.get("cost", 0.0) or 0.0

        status_breakdown = [
            {"status": status, "count": count}
            for status, count in status_counter.items()
        ]

        return {
            "total_tasks": len(tasks),
            "status_breakdown": status_breakdown,
            "running_task_ids": running_task_ids,
            "recent_tasks": tasks[:limit_recent],
            "cost_summary": {
                "total_token_usage": total_tokens,
                "total_cost_estimate": total_cost,
                "models": model_breakdown,
            },
        }

    def _dispatch_task(self, task: Task) -> None:
        """Redispatch task to appropriate Celery worker."""
        dispatch_map: Dict[str, Callable[[Task, Dict[str, Any]], None]] = {
            "search_and_build_library": self._dispatch_search_and_build,
            TaskType.LITERATURE_COLLECTION.value: self._dispatch_literature_collection,
            "experience_generation": self._dispatch_experience_generation,
            "literature_processing": self._dispatch_literature_processing,
            "literature_index": self._dispatch_literature_index,
            TaskType.PDF_PROCESSING.value: self._dispatch_pdf_processing,
        }

        config = task.config or {}
        task_type = task.task_type

        handler = dispatch_map.get(task_type)
        if not handler:
            raise ValueError(f"Unsupported task type: {task_type}")

        handler(task, config)

    def _dispatch_search_and_build(self, task: Task, config: Dict[str, Any]) -> None:
        keywords = config.get("keywords") or []
        user_id = task.project.owner_id if task.project else None
        if user_id is None:
            raise ValueError("Missing project owner for search_and_build_library task")
        search_and_build_library_celery.delay(
            task.id,
            keywords,
            task.project_id,
            user_id,
            config,
        )

    def _dispatch_literature_collection(self, task: Task, config: Dict[str, Any]) -> None:
        if config.get("search_mode") == "ai_batch":
            query = config.get("query")
            max_results = config.get("max_results", 20)
            if not query:
                raise ValueError("Missing query for AI batch search task")
            ai_search_batch_celery.delay(task.id, query, max_results)
            return

        keywords = config.get("keywords") or []
        max_count = config.get("max_count", 100)
        sources = config.get("sources") or []
        literature_collection_celery.delay(task.id, keywords, max_count, sources)

    def _dispatch_experience_generation(self, task: Task, config: Dict[str, Any]) -> None:
        research_question = (task.input_data or {}).get("research_question") or "通用研究问题"
        experience_generation_celery.delay(task.id, research_question)

    def _dispatch_literature_processing(self, task: Task, config: Dict[str, Any]) -> None:
        literature_processing_celery.delay(task.id)

    def _dispatch_literature_index(self, task: Task, config: Dict[str, Any]) -> None:
        user_id = task.project.owner_id if task.project else None
        if user_id is None:
            raise ValueError("Missing project owner for literature index task")
        literature_index_celery.delay(task.project_id, str(task.id), user_id)

    def _dispatch_pdf_processing(self, task: Task, config: Dict[str, Any]) -> None:
        literature_id = config.get("literature_id")
        if not literature_id:
            raise ValueError("Missing literature_id for PDF processing task")
        user_id = task.project.owner_id if task.project else None
        if user_id is None:
            raise ValueError("Missing project owner for PDF processing task")
        download_pdf_celery.delay(literature_id, user_id, task.id)

    def _create_task(
        self,
        owner_id: int,
        project_id: int,
        task_type: str,
        title: str,
        description: str,
        config: Optional[dict] = None,
        input_data: Optional[dict] = None,
        estimated_duration: Optional[int] = None,
    ) -> Task:
        project = (
            self.db.query(Project)
            .filter(Project.id == project_id, Project.owner_id == owner_id)
            .first()
        )
        if not project:
            raise ValueError("项目不存在或无权限访问")

        task = Task(
            project_id=project_id,
            task_type=task_type,
            title=title,
            description=description,
            status=TaskStatus.PENDING.value,
            progress_percentage=0.0,
            config=config or {},
            input_data=input_data or {},
            estimated_duration=estimated_duration,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        self._dispatch_task(task)
        return task

    def create_search_build_task(
        self,
        owner_id: int,
        project_id: int,
        keywords: List[str],
        config: Dict[str, Any],
    ) -> Task:
        return self._create_task(
            owner_id=owner_id,
            project_id=project_id,
            task_type="search_and_build_library",
            title="搜索建库流水线",
            description=f"关键词: {', '.join(keywords) if keywords else '自动'}",
            config={**config, "keywords": keywords},
            estimated_duration=600,
        )

    def create_ai_search_task(
        self,
        owner_id: int,
        project_id: int,
        query: str,
        max_results: int,
    ) -> Task:
        return self._create_task(
            owner_id=owner_id,
            project_id=project_id,
            task_type=TaskType.LITERATURE_COLLECTION.value,
            title=f"AI文献搜索 - {query}",
            description=f"AI批量搜索文献（最多 {max_results} 篇）",
            config={
                "search_mode": "ai_batch",
                "query": query,
                "max_results": max_results,
            },
            estimated_duration=180,
        )

    def create_literature_collection_task(
        self,
        owner_id: int,
        project_id: int,
        keywords: List[str],
        max_count: int,
        sources: Optional[List[str]],
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> Task:
        task_config = {
            "keywords": keywords,
            "max_count": max_count,
            "sources": sources or ["researchrabbit"],
        }
        if extra_config:
            task_config.update(extra_config)
        return self._create_task(
            owner_id=owner_id,
            project_id=project_id,
            task_type="literature_collection",
            title="文献采集",
            description=f"采集关键词文献（{max_count} 篇）",
            config=task_config,
            estimated_duration=300,
        )

    def create_experience_task(
        self,
        owner_id: int,
        project_id: int,
        research_question: str,
        processing_method: str,
    ) -> Task:
        return self._create_task(
            owner_id=owner_id,
            project_id=project_id,
            task_type="experience_generation",
            title="经验生成",
            description=f"研究问题: {research_question}",
            config={"processing_method": processing_method},
            input_data={"research_question": research_question},
            estimated_duration=240,
        )

    def create_literature_processing_task(
        self,
        owner_id: int,
        project_id: int,
        description: Optional[str] = None,
    ) -> Task:
        return self._create_task(
            owner_id=owner_id,
            project_id=project_id,
            task_type=TaskType.LITERATURE_PROCESSING.value,
            title="文献处理",
            description=description or "解析并结构化项目中的文献",
            estimated_duration=420,
        )

    def create_pdf_processing_task(
        self,
        owner_id: int,
        project_id: int,
        literature_id: int,
        literature_title: str,
    ) -> Task:
        literature = (
            self.db.query(Literature)
            .join(Literature.projects)
            .filter(Literature.id == literature_id, Project.id == project_id)
            .first()
        )
        if not literature:
            raise ValueError("文献不存在或未关联到指定项目")

        short_title = literature_title[:40] + ("…" if len(literature_title) > 40 else "")

        return self._create_task(
            owner_id=owner_id,
            project_id=project_id,
            task_type=TaskType.PDF_PROCESSING.value,
            title=f"PDF处理 - {short_title}",
            description=f"下载并处理文献: {literature_title}",
            config={"literature_id": literature_id},
            estimated_duration=180,
        )
