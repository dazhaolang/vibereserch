"""
可靠性优化的经验生成任务
"""

import asyncio
from typing import List
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.task import Task, TaskProgress
from app.models.project import Project
from app.models.literature import Literature, LiteratureSegment
from app.services.experience_engine import EnhancedExperienceEngine


async def start_reliability_optimized_experience_generation_task(
    task_id: int,
    research_question: str,
    reliability_threshold: float = 0.6,
    enable_deviation_filtering: bool = True
):
    """启动基于可靠性优化的经验生成任务"""
    db = SessionLocal()
    
    try:
        # 更新任务状态
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return
        
        task.status = "running"
        task.current_step = "初始化可靠性优化经验生成"
        db.commit()
        
        logger.info(f"开始可靠性优化经验生成任务: {task_id}")
        
        # 创建进度记录
        progress = TaskProgress(
            task_id=task_id,
            step_name="开始可靠性优化经验生成",
            progress_percentage=5.0,
            step_result={
                "research_question": research_question,
                "reliability_threshold": reliability_threshold,
                "enable_deviation_filtering": enable_deviation_filtering
            }
        )
        db.add(progress)
        db.commit()
        
        # 获取项目文献段落
        literature_segments = db.query(LiteratureSegment).join(Literature).filter(
            Literature.projects.any(id=task.project_id)
        ).all()
        
        if not literature_segments:
            task.status = "failed"
            task.error_message = "项目中没有可用的文献段落"
            db.commit()
            logger.error(f"任务失败: {task.error_message}")
            return
        
        # 初始化增强版经验引擎
        experience_engine = EnhancedExperienceEngine(db)
        
        # 运行可靠性优化的经验增强流程
        result = await experience_engine.run_experience_enhancement(
            project_id=task.project_id,
            research_question=research_question,
            literature_segments=literature_segments,
            task_id=task_id
        )
        
        if result["success"]:
            # 任务成功完成
            task.status = "completed"
            task.current_step = "经验生成完成"
            task.progress_percentage = 100.0
            task.result = result
            
            # 记录最终结果
            final_progress = TaskProgress(
                task_id=task_id,
                step_name="可靠性优化经验生成完成",
                progress_percentage=100.0,
                step_result={
                    "final_experience_id": result.get("final_experience_id"),
                    "total_rounds": result.get("total_rounds"),
                    "metadata": result.get("metadata", {}),
                    "reliability_optimization": True
                }
            )
            db.add(final_progress)
            
            logger.info(f"可靠性优化经验生成任务完成: {task_id}")
            
        else:
            # 任务失败
            task.status = "failed"
            task.error_message = result.get("error", "经验生成失败")
            
            logger.error(f"可靠性优化经验生成任务失败: {task_id}, 错误: {task.error_message}")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"可靠性优化经验生成任务异常: {task_id}, 错误: {e}")
        
        # 更新任务状态为失败
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                db.commit()
        except Exception as commit_error:
            logger.error(f"更新任务状态失败: {commit_error}")
    
    finally:
        db.close()