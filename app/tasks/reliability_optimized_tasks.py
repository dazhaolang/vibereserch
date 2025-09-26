"""可靠性优化的经验生成任务"""

from loguru import logger

from app.core.database import SessionLocal
from app.models.task import Task
from app.models.literature import Literature, LiteratureSegment
from app.services.task_stream_service import TaskStreamService
from app.services.task_cost_tracker import task_cost_tracker
from app.services.experience_engine import EnhancedExperienceEngine


async def start_reliability_optimized_experience_generation_task(
    task_id: int,
    research_question: str,
    reliability_threshold: float = 0.6,
    enable_deviation_filtering: bool = True
):
    """启动基于可靠性优化的经验生成任务"""
    db = SessionLocal()
    token = None

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task_stream = TaskStreamService(db)

        async def run_reliability_experience(progress_callback):
            await progress_callback(
                "初始化可靠性优化经验生成",
                5,
                {
                    "research_question": research_question,
                    "reliability_threshold": reliability_threshold,
                    "enable_deviation_filtering": enable_deviation_filtering,
                },
            )

            literature_segments = db.query(LiteratureSegment).join(Literature).filter(
                Literature.projects.any(id=task.project_id)
            ).all()

            if not literature_segments:
                raise RuntimeError("项目中没有可用的文献段落")

            await progress_callback(
                "加载文献段落",
                15,
                {
                    "segment_count": len(literature_segments),
                    "project_id": task.project_id,
                },
            )

            experience_engine = EnhancedExperienceEngine(db)
            result = await experience_engine.run_experience_enhancement(
                project_id=task.project_id,
                research_question=research_question,
                literature_segments=literature_segments,
                task_id=task_id,
            )

            if not result.get("success"):
                raise RuntimeError(result.get("error", "经验生成失败"))

            await progress_callback(
                "可靠性优化经验生成完成",
                95,
                {
                    "final_experience_id": result.get("final_experience_id"),
                    "total_rounds": result.get("total_rounds"),
                    "metadata": result.get("metadata", {}),
                },
            )

            return {
                **result,
                "reliability_threshold": reliability_threshold,
                "enable_deviation_filtering": enable_deviation_filtering,
            }

        token = task_cost_tracker.activate(task.id, db)
        return await task_stream.run_with_progress(
            task,
            "初始化可靠性优化经验生成",
            run_reliability_experience,
        )

    except Exception as exc:
        logger.error(f"可靠性优化经验生成任务失败: {task_id}, 错误: {exc}")
        raise
    finally:
        if token is not None:
            task_cost_tracker.deactivate(token)
        db.close()
