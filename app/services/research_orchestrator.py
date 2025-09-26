"""Research mode orchestration helpers."""

import copy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.rag_service import RAGService
from app.services.smart_research_assistant import smart_research_assistant
from app.services.agent_orchestrator import get_agent_orchestrator
from app.services.task_orchestrator import TaskOrchestrator
from app.services.task_logger import task_logger
from app.models.user import User
from app.models.project import Project
from loguru import logger


class ResearchOrchestrator:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.task_orchestrator = TaskOrchestrator(db)
        # 创建任务日志会话
        self.run_id = task_logger.create_run_session()

    def _ensure_project_for_auto(
        self,
        project_id: int,
        query: str,
        normalized_keywords: List[str],
        config: Dict[str, Any],
    ) -> Tuple[Project, bool]:
        """确保自动模式拥有合法项目，必要时自动创建。"""

        project: Optional[Project] = None
        if project_id:
            project = (
                self.db.query(Project)
                .filter(Project.id == project_id, Project.owner_id == self.user.id)
                .one_or_none()
            )

        created = False
        target_max = int(config.get("collection_max_count") or config.get("max_results") or 1000)

        if project is None:
            created = True
            project = Project(
                name=self._generate_auto_project_name(query),
                description=f"自动研究任务：{query[:200]}",
                research_direction=query[:200],
                keywords=normalized_keywords[:20],
                status="processing",
                owner_id=self.user.id,
                max_literature_count=target_max,
            )
            self.db.add(project)
            self.db.commit()
            self.db.refresh(project)
            logger.info(
                "Auto mode created new project %s for user %s", project.id, self.user.id
            )
        else:
            should_commit = False
            if project.status not in {"processing", "pending"}:
                project.status = "processing"
                should_commit = True

            if target_max and (project.max_literature_count or 0) < target_max:
                project.max_literature_count = target_max
                should_commit = True

            if should_commit:
                self.db.commit()
                self.db.refresh(project)

        return project, created

    @staticmethod
    def _generate_auto_project_name(query: str) -> str:
        base = (query.strip() or "自动研究").split("\n")[0][:32]
        timestamp = datetime.utcnow().strftime("%m%d%H%M")
        return f"{base} · {timestamp}" if base else f"自动研究 · {timestamp}"

    async def run_rag(
        self,
        project_id: int,
        query: str,
        max_literature_count: int,
        context_literature_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        logger.info(f"RAG mode triggered by user {self.user.id} on project {project_id}")
        result = await smart_research_assistant.answer_complex_research_question(
            question=query,
            project_id=project_id,
            user_id=self.user.id,
            context_literature_ids=context_literature_ids,
            max_literature_count=max_literature_count,
        )
        return result

    async def run_deep(
        self,
        project_id: int,
        query: str,
        processing_method: str,
    ) -> Dict[str, Any]:
        logger.info(f"Deep research mode queued by user {self.user.id} on project {project_id}")

        task = self.task_orchestrator.trigger_experience_task(
            owner_id=self.user.id,
            project_id=project_id,
            research_question=query,
            processing_method=processing_method,
        )
        return {
            "message": "深度研究任务已启动，经验生成完成后再进行问答",
            "task_id": task.id,
        }

    async def run_auto(
        self,
        project_id: int,
        query: str,
        keywords: List[str],
        config: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(
            "Auto research mode orchestration for user %s on project %s via %s",
            self.user.id,
            project_id,
            agent or "claude",
        )
        config = config or {}

        # 自动模式配置验证与边界强化
        validated_config = self._validate_auto_config(config)
        logger.info(f"Auto mode validated config: {validated_config}")

        agent_executor = get_agent_orchestrator(agent)

        # 确保关键词列表有效，避免后续搜索阶段出现空查询
        normalized_keywords = keywords[:] if keywords else [query]

        project, created_project = self._ensure_project_for_auto(
            project_id=project_id,
            query=query,
            normalized_keywords=normalized_keywords,
            config=validated_config,
        )
        project_id = project.id

        agent_context = {
            "mode": "auto",
            "project_id": project_id,
            "user_id": self.user.id,
            "keywords": normalized_keywords,
            "config": validated_config,
            "query": query,
            "agent": agent_executor.name,
        }

        agent_plan: Dict[str, Any] = {}
        try:
            agent_result = await agent_executor.orchestrate(query, agent_context)
            agent_plan = (
                agent_result.get("tool_plan")
                or agent_result.get("agent_plan")
                or agent_result
            )
        except Exception as agent_error:
            logger.warning(
                "Agent %s 编排失败，回退默认策略: %s",
                agent_executor.name,
                agent_error,
            )

        tasks_started: List[Dict[str, Any]] = []

        pipeline_descriptor = {
            "mode": "auto",
            "query": query,
            "processing_method": validated_config.get("processing_method", "standard"),
            "agent_plan": agent_plan,
            "agent": agent_executor.name,
            "project_id": project_id,
            "created_new_project": created_project,
        }

        # 记录模式执行日志
        structured_plan = self._structure_plan_for_frontend(agent_plan, tasks_started)
        structured_plan["project_id"] = project_id
        structured_plan["created_new_project"] = created_project
        task_logger.log_mode_execution(
            self.run_id,
            "auto",
            query,
            validated_config,
            structured_plan
        )

        search_task_config = {
            "enable_ai_filtering": validated_config.get("enable_ai_filtering", True),
            "enable_pdf_processing": validated_config.get("enable_pdf_processing", True),
            "enable_structured_extraction": validated_config.get("enable_structured_extraction", True),
            "batch_size": validated_config.get("batch_size", 10),
            "max_concurrent_downloads": validated_config.get("max_concurrent_downloads", 5),
        }
        search_task_config["auto_pipeline"] = {
            **pipeline_descriptor,
            "on_complete": {
                "type": "experience_generation",
                "payload": {
                    "query": query,
                    "processing_method": pipeline_descriptor["processing_method"],
                },
            },
        }

        if validated_config.get("collect_first"):
            collection_extra_config = {
                "auto_pipeline": {
                    **pipeline_descriptor,
                    "on_complete": {
                        "type": "search_and_build_library",
                        "payload": {
                            "keywords": keywords,
                            "config": copy.deepcopy(search_task_config),
                        },
                    },
                }
            }

            collection_task = self.task_orchestrator.trigger_collection_task(
                owner_id=self.user.id,
                project_id=project_id,
                keywords=normalized_keywords,
                max_count=validated_config.get("collection_max_count", 100),
                sources=validated_config.get("sources", []),
                extra_config=collection_extra_config,
            )

            # 记录任务触发日志
            task_logger.log_task_trigger(
                self.run_id,
                str(collection_task.id),
                "auto",
                {"type": "collection", "keywords": normalized_keywords, **validated_config},
                self.user.id,
                project_id
            )
            tasks_started.append(
                {
                    "task_id": collection_task.id,
                    "type": "literature_collection",
                    "status": "pending",
                    "title": "文献采集",
                    "description": "采集候选文献以供后续建库",
                }
            )
            tasks_started.append(
                {
                    "type": "search_and_build_library",
                    "status": "pending",
                    "title": "搜索建库流水线",
                    "description": "等待文献采集完成后启动搜索建库流程",
                }
            )
            tasks_started.append(
                {
                    "type": "experience_generation",
                    "status": "pending",
                    "title": "经验生成",
                    "description": "建库完成后生成研究经验",
                }
            )
        else:
            search_task = self.task_orchestrator.trigger_search_pipeline(
                owner_id=self.user.id,
                project_id=project_id,
                keywords=normalized_keywords,
                config=search_task_config,
            )

            # 记录任务触发日志
            task_logger.log_task_trigger(
                self.run_id,
                str(search_task.id),
                "auto",
                {"type": "search_pipeline", "keywords": normalized_keywords, **search_task_config},
                self.user.id,
                project_id
            )
            tasks_started.append(
                {
                    "task_id": search_task.id,
                    "type": "search_and_build_library",
                    "status": "pending",
                    "title": "搜索建库流水线",
                    "description": "执行搜索、下载、清洗与入库",
                }
            )
            tasks_started.append(
                {
                    "type": "experience_generation",
                    "status": "pending",
                    "title": "经验生成",
                    "description": "建库完成后生成研究经验",
                }
            )

        return {
            "message": "已启动全自动研究任务链，可在任务中心查看进度",
            "tasks": tasks_started,
            "agent_plan": agent_plan,
            "agent": agent_executor.name,
            # 为前端直接绑定添加扁平化字段
            "structured_plan": structured_plan,
            "total_stages": len(tasks_started),
            "current_stage_index": 0,
            "stage_details": self._extract_stage_details(tasks_started, agent_plan),
            "project_id": project_id,
            "project_status": project.status,
            "project": {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "owner_id": project.owner_id,
            },
            "created_new_project": created_project,
        }

    def _validate_auto_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和清理自动模式配置，防止agent注入未授权工具
        """
        # 允许的配置项白名单
        allowed_keys = {
            "processing_method", "enable_ai_filtering", "enable_pdf_processing",
            "enable_structured_extraction", "batch_size", "max_concurrent_downloads",
            "collect_first", "collection_max_count", "sources", "agent_tools"
        }

        # 允许的agent工具白名单
        allowed_agent_tools = {
            "collect_literature", "process_literature", "generate_experience",
            "search_literature", "analyze_content", "extract_insights"
        }

        # 清理配置，移除未授权项
        validated_config = {}
        for key, value in config.items():
            if key in allowed_keys:
                if key == "agent_tools" and isinstance(value, list):
                    # 验证agent工具白名单
                    validated_tools = [tool for tool in value if tool in allowed_agent_tools]
                    validated_config[key] = validated_tools
                    if len(validated_tools) != len(value):
                        logger.warning(f"Filtered unauthorized agent tools: {set(value) - set(validated_tools)}")
                else:
                    validated_config[key] = value
            else:
                logger.warning(f"Removed unauthorized config key: {key}")

        # 设置安全默认值
        validated_config.setdefault("processing_method", "standard")
        validated_config.setdefault("enable_ai_filtering", True)
        validated_config.setdefault("batch_size", 10)
        validated_config.setdefault("max_concurrent_downloads", 5)

        # 限制批次大小和并发数，防止资源滥用
        if validated_config["batch_size"] > 50:
            validated_config["batch_size"] = 50
            logger.warning("Batch size limited to 50")

        if validated_config["max_concurrent_downloads"] > 10:
            validated_config["max_concurrent_downloads"] = 10
            logger.warning("Max concurrent downloads limited to 10")

        return validated_config

    def _structure_plan_for_frontend(self, agent_plan: Dict[str, Any], tasks_started: List[Dict]) -> Dict[str, Any]:
        """
        将agent_plan结构化为前端易用的格式
        """
        structured = {
            "phases": [],
            "timeline": [],
            "resource_estimates": {},
            "dependencies": []
        }

        # 从任务列表构建阶段信息
        for i, task in enumerate(tasks_started):
            phase = {
                "id": i + 1,
                "name": self._get_phase_name(task["type"]),
                "type": task["type"],
                "status": task.get("status", "pending"),
                "task_id": task.get("task_id"),
                "estimated_duration": self._get_estimated_duration(task["type"]),
                "description": self._get_phase_description(task["type"])
            }
            structured["phases"].append(phase)

        # 构建时间线
        current_time = 0
        for phase in structured["phases"]:
            structured["timeline"].append({
                "phase_id": phase["id"],
                "start_time": current_time,
                "end_time": current_time + phase["estimated_duration"],
                "status": phase["status"]
            })
            current_time += phase["estimated_duration"]

        # 添加资源估算
        structured["resource_estimates"] = {
            "total_duration_minutes": current_time,
            "peak_memory_mb": len(tasks_started) * 100,
            "estimated_tokens": len(tasks_started) * 2000,
            "concurrent_tasks": min(3, len(tasks_started))
        }

        # 从agent_plan提取依赖关系
        if agent_plan and "dependencies" in agent_plan:
            structured["dependencies"] = agent_plan["dependencies"]
        else:
            # 默认串行依赖
            for i in range(1, len(structured["phases"])):
                structured["dependencies"].append({
                    "from_phase": i,
                    "to_phase": i + 1,
                    "type": "sequential"
                })

        return structured

    def _extract_stage_details(self, tasks_started: List[Dict], agent_plan: Dict[str, Any]) -> List[Dict]:
        """
        提取阶段详细信息供前端进度面板使用
        """
        stage_details = []

        for i, task in enumerate(tasks_started):
            detail = {
                "stage_index": i,
                "stage_name": self._get_phase_name(task["type"]),
                "stage_type": task["type"],
                "status": task.get("status", "pending"),
                "task_id": task.get("task_id"),
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "error": None,
                "substeps": self._get_substeps(task["type"]),
                "metrics": {
                    "processed_items": 0,
                    "total_items": 0,
                    "success_rate": 0
                }
            }
            stage_details.append(detail)

        return stage_details

    def _get_phase_name(self, task_type: str) -> str:
        """获取阶段显示名称"""
        phase_names = {
            "literature_collection": "文献采集",
            "search_and_build_library": "搜索建库",
            "experience_generation": "经验生成",
            "content_analysis": "内容分析",
            "insight_extraction": "洞察提取"
        }
        return phase_names.get(task_type, task_type.replace("_", " ").title())

    def _get_phase_description(self, task_type: str) -> str:
        """获取阶段描述"""
        descriptions = {
            "literature_collection": "从指定来源采集相关文献资料",
            "search_and_build_library": "智能搜索并构建结构化文献库",
            "experience_generation": "基于文献内容生成经验知识",
            "content_analysis": "深度分析文献内容和模式",
            "insight_extraction": "提取关键洞察和发现"
        }
        return descriptions.get(task_type, f"执行{task_type}相关任务")

    def _get_estimated_duration(self, task_type: str) -> int:
        """获取阶段预估时长（分钟）"""
        durations = {
            "literature_collection": 5,
            "search_and_build_library": 10,
            "experience_generation": 8,
            "content_analysis": 6,
            "insight_extraction": 4
        }
        return durations.get(task_type, 5)

    def _get_substeps(self, task_type: str) -> List[str]:
        """获取阶段子步骤"""
        substeps = {
            "literature_collection": ["初始化采集器", "搜索相关文献", "筛选高质量文献", "下载文献内容"],
            "search_and_build_library": ["关键词扩展", "多源搜索", "PDF处理", "结构化提取", "入库索引"],
            "experience_generation": ["段落分析", "模式识别", "经验提取", "质量评估", "经验优化"],
            "content_analysis": ["内容解析", "主题建模", "关联分析", "趋势识别"],
            "insight_extraction": ["核心观点提取", "证据整理", "结论生成", "报告编制"]
        }
        return substeps.get(task_type, ["初始化", "处理", "完成"])
