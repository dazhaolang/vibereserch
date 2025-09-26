"""统一的任务编排服务，封装 TaskService 的业务逻辑。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.task import Task


class TaskOrchestrator:
    """负责触发和追踪研究流水线中的后台任务。"""

    def __init__(self, db: Session):
        self.db = db
        from app.services.task_service import TaskService  # 避免循环引用

        self.task_service = TaskService(db)

    def trigger_search_pipeline(
        self,
        owner_id: int,
        project_id: int,
        keywords: Optional[list[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Task:
        logger.info(
            "创建搜索建库任务 | project=%s keywords=%s",
            project_id,
            keywords,
        )
        return self.task_service.create_search_build_task(
            owner_id=owner_id,
            project_id=project_id,
            keywords=keywords or [],
            config=config or {},
        )

    def trigger_experience_task(
        self,
        owner_id: int,
        project_id: int,
        research_question: str,
        processing_method: str,
    ) -> Task:
        logger.info(
            "创建经验生成任务 | project=%s method=%s",
            project_id,
            processing_method,
        )
        return self.task_service.create_experience_task(
            owner_id=owner_id,
            project_id=project_id,
            research_question=research_question,
            processing_method=processing_method,
        )

    def trigger_collection_task(
        self,
        owner_id: int,
        project_id: int,
        keywords: list[str],
        max_count: int,
        sources: Optional[list[str]] = None,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> Task:
        logger.info("创建文献采集任务 | project=%s", project_id)
        sanitized_sources = ["researchrabbit"]

        return self.task_service.create_literature_collection_task(
            owner_id=owner_id,
            project_id=project_id,
            keywords=keywords,
            max_count=max_count,
            sources=sanitized_sources,
            extra_config=extra_config,
        )
