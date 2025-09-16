"""
增强的进度追踪服务 - 数据库持久化 + 实时推送
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import get_db
from app.models.task import Task, TaskProgress, TaskStatus, TaskType
from app.services.stream_progress_service import (
    stream_progress_service,
    ProgressEvent,
    WorkflowStage
)

@dataclass
class DetailedProgressStep:
    """详细进度步骤定义"""
    step_id: str
    step_name: str
    step_description: str
    estimated_duration: int  # 秒
    dependencies: List[str] = None  # 依赖步骤
    progress_weight: float = 1.0  # 在总进度中的权重

class EnhancedProgressService:
    """增强的进度追踪服务 - 集成数据库持久化"""

    def __init__(self):
        self.detailed_steps = self._define_detailed_steps()

    def _define_detailed_steps(self) -> Dict[str, List[DetailedProgressStep]]:
        """定义详细的处理步骤"""
        return {
            "literature_collection": [
                DetailedProgressStep("init_search", "初始化搜索参数", "配置搜索关键词和过滤条件", 5),
                DetailedProgressStep("connect_api", "连接ResearchRabbit API", "建立文献数据库连接", 10),
                DetailedProgressStep("search_execute", "执行文献搜索", "批量搜索相关文献", 60),
                DetailedProgressStep("quality_filter", "质量筛选和排序", "按照相关性和质量评分过滤", 45),
                DetailedProgressStep("metadata_download", "下载文献元数据", "获取详细的文献信息", 30),
                DetailedProgressStep("database_save", "保存到数据库", "将文献信息存储到本地数据库", 15)
            ],
            "pdf_processing": [
                DetailedProgressStep("pdf_download", "下载PDF文件", "从文献源下载PDF原文", 120),
                DetailedProgressStep("pdf_to_markdown", "PDF转Markdown", "使用MinerU Magic PDF转换", 180),
                DetailedProgressStep("text_cleanup", "文本清理优化", "清理和优化转换后的文本", 60),
                DetailedProgressStep("quality_check", "质量检查", "验证转换质量和完整性", 30)
            ],
            "structured_processing": [
                DetailedProgressStep("template_generate", "生成提取模板", "AI自动生成结构化提取规则", 60),
                DetailedProgressStep("content_extract", "提取文段信息", "按模板提取关键信息段落", 120),
                DetailedProgressStep("data_validate", "数据验证", "验证提取结果的准确性", 45),
                DetailedProgressStep("structured_save", "保存结构化结果", "存储提取的结构化数据", 30)
            ],
            "experience_generation": [
                DetailedProgressStep("iteration_1", "迭代轮次1", "基于文献内容生成初版经验", 90),
                DetailedProgressStep("iteration_2", "迭代轮次2", "整合新文献优化经验内容", 90),
                DetailedProgressStep("iteration_3", "迭代轮次3", "进一步完善和验证经验", 90),
                DetailedProgressStep("experience_summary", "经验汇总", "整合多轮迭代结果", 60),
                DetailedProgressStep("quality_assessment", "质量评估", "评估经验书的完整性和实用性", 30)
            ],
            "intelligent_qa": [
                DetailedProgressStep("question_analysis", "问题分析", "分析用户问题的意图和需求", 30),
                DetailedProgressStep("knowledge_retrieval", "知识检索", "从经验库中检索相关知识", 45),
                DetailedProgressStep("answer_generation", "答案生成", "基于经验生成结构化答案", 90),
                DetailedProgressStep("result_validation", "结果验证", "验证答案的准确性和完整性", 30)
            ]
        }

    async def create_persistent_task(
        self,
        project_id: int,
        task_type: TaskType,
        title: str,
        description: str,
        config: Dict[str, Any],
        input_data: Dict[str, Any],
        db: Session
    ) -> Task:
        """创建持久化任务"""

        # 计算预估总时长
        workflow_type = self._map_task_type_to_workflow(task_type)
        total_duration = sum(
            step.estimated_duration
            for step in self.detailed_steps.get(workflow_type, [])
        )

        # 创建数据库任务记录
        db_task = Task(
            project_id=project_id,
            task_type=task_type.value,
            title=title,
            description=description,
            config=config,
            input_data=input_data,
            status=TaskStatus.PENDING.value,
            progress_percentage=0.0,
            estimated_duration=total_duration
        )

        db.add(db_task)
        db.commit()
        db.refresh(db_task)

        # 在内存服务中创建对应的工作流任务
        workflow_stages = self._get_workflow_stages_for_task(task_type)
        await stream_progress_service.create_workflow_task(
            task_id=str(db_task.id),
            task_name=title,
            workflow_stages=workflow_stages,
            initial_data={
                "project_id": project_id,
                "database_task_id": db_task.id,
                "task_type": task_type.value
            }
        )

        logger.info(f"创建持久化任务: {db_task.id} - {title}")
        return db_task

    async def update_task_progress(
        self,
        task_id: str,
        step_id: str,
        step_progress: int,
        step_message: str,
        step_result: Optional[Dict] = None,
        db: Session = None
    ):
        """更新任务进度（同时更新数据库和内存）"""

        if not db:
            db = next(get_db())

        try:
            # 更新数据库记录
            db_task = db.query(Task).filter(Task.id == int(task_id)).first()
            if db_task:
                # 创建详细的进度记录
                progress_log = TaskProgress(
                    task_id=int(task_id),
                    step_name=step_id,
                    step_description=step_message,
                    progress_percentage=step_progress,
                    step_result=step_result or {},
                    completed_at=datetime.now() if step_progress >= 100 else None
                )
                db.add(progress_log)

                # 更新主任务状态
                db_task.current_step = step_message
                db_task.progress_percentage = self._calculate_overall_progress(
                    db_task.task_type, step_id, step_progress
                )

                if step_progress >= 100:
                    db_task.status = TaskStatus.COMPLETED.value
                    db_task.completed_at = datetime.now()
                elif db_task.status == TaskStatus.PENDING.value:
                    db_task.status = TaskStatus.RUNNING.value
                    db_task.started_at = datetime.now()

                db.commit()

                # 更新内存中的进度服务
                workflow_stage = self._map_step_to_stage(step_id)
                await stream_progress_service.update_stage_progress(
                    task_id=task_id,
                    stage=workflow_stage,
                    step_progress=step_progress,
                    message=step_message,
                    sub_progress={
                        "step_id": step_id,
                        "step_progress": step_progress,
                        "database_synced": True
                    },
                    results_data=step_result,
                    status="stage_completed" if step_progress >= 100 else "running"
                )

                logger.info(f"任务进度更新: {task_id} - {step_id} ({step_progress}%)")

        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")
            if db:
                db.rollback()

    async def get_task_progress_from_db(self, task_id: str, db: Session) -> Dict:
        """从数据库获取任务进度"""

        db_task = db.query(Task).filter(Task.id == int(task_id)).first()
        if not db_task:
            return {"error": "Task not found"}

        # 获取详细进度记录
        progress_logs = db.query(TaskProgress).filter(
            TaskProgress.task_id == int(task_id)
        ).order_by(TaskProgress.started_at.asc()).all()

        return {
            "task_id": task_id,
            "title": db_task.title,
            "description": db_task.description,
            "status": db_task.status,
            "progress_percentage": db_task.progress_percentage,
            "current_step": db_task.current_step,
            "estimated_duration": db_task.estimated_duration,
            "started_at": db_task.started_at.isoformat() if db_task.started_at else None,
            "completed_at": db_task.completed_at.isoformat() if db_task.completed_at else None,
            "progress_history": [
                {
                    "step_name": log.step_name,
                    "step_description": log.step_description,
                    "progress_percentage": log.progress_percentage,
                    "started_at": log.started_at.isoformat(),
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "step_result": log.step_result
                }
                for log in progress_logs
            ]
        }

    async def restore_task_progress(self, task_id: str, db: Session):
        """从数据库恢复任务进度到内存服务"""

        task_progress = await self.get_task_progress_from_db(task_id, db)
        if "error" in task_progress:
            return False

        # 在内存服务中重建任务状态
        if task_id not in stream_progress_service.active_tasks:
            workflow_stages = self._get_workflow_stages_for_task_type(task_progress.get("task_type"))
            await stream_progress_service.create_workflow_task(
                task_id=task_id,
                task_name=task_progress["title"],
                workflow_stages=workflow_stages,
                initial_data={
                    "restored_from_db": True,
                    "progress_percentage": task_progress["progress_percentage"],
                    "current_step": task_progress["current_step"]
                }
            )

        logger.info(f"从数据库恢复任务进度: {task_id}")
        return True

    def _map_task_type_to_workflow(self, task_type: TaskType) -> str:
        """将任务类型映射到工作流类型"""
        mapping = {
            TaskType.LITERATURE_COLLECTION: "literature_collection",
            TaskType.STRUCTURE_EXTRACTION: "structured_processing",
            TaskType.EXPERIENCE_GENERATION: "experience_generation",
            TaskType.QUESTION_ANALYSIS: "intelligent_qa"
        }
        return mapping.get(task_type, "literature_collection")

    def _get_workflow_stages_for_task(self, task_type: TaskType) -> List[str]:
        """获取任务类型对应的工作流阶段"""
        if task_type == TaskType.LITERATURE_COLLECTION:
            return ["collection", "structuring"]
        elif task_type == TaskType.EXPERIENCE_GENERATION:
            return ["experience"]
        elif task_type == TaskType.QUESTION_ANALYSIS:
            return ["interaction"]
        else:
            return ["collection", "structuring", "experience", "interaction"]

    def _calculate_overall_progress(self, task_type: str, current_step_id: str, step_progress: int) -> float:
        """计算总体进度百分比"""
        workflow_type = task_type.lower().replace("_", "_")
        steps = self.detailed_steps.get(workflow_type, [])

        if not steps:
            return step_progress

        # 找到当前步骤的索引
        current_index = -1
        for i, step in enumerate(steps):
            if step.step_id == current_step_id:
                current_index = i
                break

        if current_index == -1:
            return step_progress

        # 计算已完成步骤的权重
        completed_weight = sum(step.progress_weight for step in steps[:current_index])
        current_step_weight = steps[current_index].progress_weight * (step_progress / 100)
        total_weight = sum(step.progress_weight for step in steps)

        return ((completed_weight + current_step_weight) / total_weight) * 100

    def _map_step_to_stage(self, step_id: str) -> str:
        """将步骤ID映射到工作流阶段"""
        if step_id in ["init_search", "connect_api", "search_execute", "quality_filter", "metadata_download", "database_save"]:
            return "collection"
        elif step_id in ["pdf_download", "pdf_to_markdown", "text_cleanup", "quality_check", "template_generate", "content_extract", "data_validate", "structured_save"]:
            return "structuring"
        elif step_id in ["iteration_1", "iteration_2", "iteration_3", "experience_summary", "quality_assessment"]:
            return "experience"
        elif step_id in ["question_analysis", "knowledge_retrieval", "answer_generation", "result_validation"]:
            return "interaction"
        else:
            return "collection"

# 全局增强进度服务实例
enhanced_progress_service = EnhancedProgressService()