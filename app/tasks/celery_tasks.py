"""
Celery任务定义 - 统一的异步任务处理
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from celery import Celery
from loguru import logger

from app.celery import celery_app, default_retry_kwargs, high_priority_retry_kwargs
from app.tasks.literature_tasks import (
    ai_search_batch_async,
    start_literature_collection_task,
    start_literature_processing_task,
    start_experience_generation_task,
    build_literature_index,
    download_and_process_pdf_task
)

@celery_app.task(bind=True, **default_retry_kwargs)
def search_and_build_library_celery(
    self,
    task_id: int,
    keywords: List[str],
    project_id: int,
    user_id: int,
    config: Dict[str, Any]
):
    """
    搜索建库原子化任务的Celery任务
    执行完整的搜索→筛选→下载PDF→转Markdown→结构化处理→入库流水线
    """
    try:
        logger.info(f"启动搜索建库Celery任务: task_id={task_id}, keywords={keywords}")

        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from app.tasks.literature_tasks import start_search_and_build_library_task
            result = loop.run_until_complete(
                start_search_and_build_library_task(
                    task_id=task_id,
                    keywords=keywords,
                    project_id=project_id,
                    user_id=user_id,
                    config=config
                )
            )

            # 搜索建库成功后自动触发主经验生成
            if result.get("success"):
                logger.info(f"搜索建库成功，触发主经验生成: project_id={project_id}")
                main_experience_generation_celery.delay(
                    task_id=None,  # 新建任务
                    project_id=project_id,
                    user_id=user_id
                )
            logger.info(f"搜索建库Celery任务完成: task_id={task_id}")
            return {"success": True, "task_id": task_id, "result": result}
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"搜索建库Celery任务失败: task_id={task_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'task_id': task_id}
        )
        raise

@celery_app.task(bind=True, **default_retry_kwargs)
def ai_search_batch_celery(self, task_id: int, query: str, max_results: int):
    """
    AI批量搜索文献的Celery任务
    """
    try:
        logger.info(f"启动Celery AI搜索任务: task_id={task_id}, query={query}")
        
        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                ai_search_batch_async(task_id, query, max_results)
            )
            logger.info(f"Celery AI搜索任务完成: task_id={task_id}")
            return {"success": True, "task_id": task_id, "result": result}
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Celery AI搜索任务失败: task_id={task_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'task_id': task_id}
        )
        raise

@celery_app.task(bind=True, **default_retry_kwargs)
def literature_collection_celery(self, task_id: int, keywords: List[str], max_count: int, sources: List[str]):
    """
    文献采集的Celery任务
    """
    try:
        logger.info(f"启动Celery文献采集任务: task_id={task_id}, keywords={keywords}")
        
        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                start_literature_collection_task(task_id, keywords, max_count, sources)
            )
            logger.info(f"Celery文献采集任务完成: task_id={task_id}")
            return {"success": True, "task_id": task_id, "result": result}
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Celery文献采集任务失败: task_id={task_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'task_id': task_id}
        )
        raise

@celery_app.task(bind=True, **default_retry_kwargs)
def literature_processing_celery(self, task_id: int):
    """
    文献处理的Celery任务
    """
    try:
        logger.info(f"启动Celery文献处理任务: task_id={task_id}")
        
        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                start_literature_processing_task(task_id)
            )
            logger.info(f"Celery文献处理任务完成: task_id={task_id}")
            return {"success": True, "task_id": task_id, "result": result}
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Celery文献处理任务失败: task_id={task_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'task_id': task_id}
        )
        raise

@celery_app.task(bind=True, **default_retry_kwargs)
def experience_generation_celery(self, task_id: int, research_question: str):
    """
    经验生成的Celery任务
    """
    try:
        logger.info(f"启动Celery经验生成任务: task_id={task_id}, question={research_question}")
        
        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                start_experience_generation_task(task_id, research_question)
            )
            logger.info(f"Celery经验生成任务完成: task_id={task_id}")
            return {"success": True, "task_id": task_id, "result": result}
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Celery经验生成任务失败: task_id={task_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'task_id': task_id}
        )
        raise

@celery_app.task(bind=True, **default_retry_kwargs)
def main_experience_generation_celery(self, task_id: Optional[int], project_id: int, user_id: int):
    """
    主经验生成的Celery任务
    """
    try:
        logger.info(f"启动Celery主经验生成任务: project_id={project_id}, user_id={user_id}")

        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from app.tasks.literature_tasks import start_main_experience_generation_task
            result = loop.run_until_complete(
                start_main_experience_generation_task(task_id, project_id, user_id)
            )
            logger.info(f"Celery主经验生成任务完成: project_id={project_id}")
            return {"success": True, "project_id": project_id, "result": result}
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Celery主经验生成任务失败: project_id={project_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'project_id': project_id}
        )
        raise

@celery_app.task(bind=True, **default_retry_kwargs)
def literature_index_celery(self, project_id: int, task_id: str, user_id: int):
    """
    文献索引构建的Celery任务
    """
    try:
        logger.info(f"启动Celery文献索引任务: project_id={project_id}, task_id={task_id}")
        
        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                build_literature_index(project_id, task_id, user_id)
            )
            logger.info(f"Celery文献索引任务完成: project_id={project_id}")
            return {"success": True, "project_id": project_id, "result": result}
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Celery文献索引任务失败: project_id={project_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'project_id': project_id}
        )
        raise


@celery_app.task(bind=True, **default_retry_kwargs)
def auto_select_clarification_card(self, session_id: str, card_id: str):
    """澄清卡片超时后自动选择推荐选项"""
    from app.core.database import SessionLocal
    from app.models.interaction import ClarificationCard, InteractionSession
    from app.services.intelligent_interaction_engine import IntelligentInteractionEngine

    db = SessionLocal()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        card = (
            db.query(ClarificationCard)
            .filter(ClarificationCard.card_id == card_id)
            .first()
        )
        if not card:
            logger.info(f"澄清卡片不存在，跳过自动处理 | session={session_id} card={card_id}")
            return {"success": False, "reason": "card_not_found"}

        if card.resolved_at is not None:
            logger.info(f"澄清卡片已处理，跳过自动处理 | session={session_id} card={card_id}")
            return {"success": False, "reason": "already_resolved"}

        session = (
            db.query(InteractionSession)
            .filter(InteractionSession.session_id == session_id)
            .first()
        )
        if not session or not session.is_active:
            logger.info(f"会话已结束，跳过自动处理 | session={session_id}")
            return {"success": False, "reason": "session_inactive"}

        recommended_option_id = card.recommended_option_id
        if not recommended_option_id:
            for option in card.options or []:
                option_id = option.get("option_id")
                if option_id:
                    recommended_option_id = option_id
                    break

        if not recommended_option_id:
            logger.warning(
                "澄清卡片缺少推荐选项，无法自动选择 | session=%s card=%s",
                session_id,
                card_id,
            )
            return {"success": False, "reason": "no_recommended_option"}

        selected_option_payload = next(
            (option for option in (card.options or []) if option.get("option_id") == recommended_option_id),
            {},
        )

        engine = IntelligentInteractionEngine(db)
        selection_data = {
            "option_id": recommended_option_id,
            "selection_type": "auto",
            "auto_selection_reason": "timeout_auto_select",
            "timeout_timestamp": datetime.utcnow().isoformat(),
        }

        result = loop.run_until_complete(
            engine.handle_user_selection(session_id=session_id, selection=selection_data)
        )

        async def broadcast_auto_selection():
            try:
                from app.api.websocket import broadcast_intelligent_interaction_event

                await broadcast_intelligent_interaction_event(
                    session_id,
                    {
                        "event_type": "auto_timeout_selection",
                        "selected_option": selected_option_payload,
                        "selection_type": "auto",
                        "timestamp": datetime.utcnow().isoformat(),
                        "result": result,
                    },
                )
            except Exception as broadcast_error:
                logger.warning(f"广播自动澄清事件失败: {broadcast_error}")

        loop.run_until_complete(broadcast_auto_selection())

        logger.info(
            "澄清卡片自动选择完成 | session=%s card=%s option=%s",
            session_id,
            card_id,
            recommended_option_id,
        )

        return {
            "success": True,
            "session_id": session_id,
            "card_id": card_id,
            "selected_option_id": recommended_option_id,
        }

    except Exception as e:
        logger.error(f"澄清卡片自动选择失败: session={session_id}, card={card_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'session_id': session_id, 'card_id': card_id}
        )
        raise
    finally:
        loop.close()
        db.close()


@celery_app.task(bind=True, **default_retry_kwargs)
def download_pdf_celery(self, literature_id: int, user_id: int, task_id: Optional[int] = None):
    """
    ResearchRabbit PDF下载和处理的Celery任务
    """
    logger.info(f"开始Celery PDF下载任务: literature_id={literature_id}, user_id={user_id}")

    try:
        # 运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                download_and_process_pdf_task(literature_id, user_id, task_id)
            )
            logger.info(f"Celery PDF下载任务完成: literature_id={literature_id}")
            return {"success": True, "literature_id": literature_id, "result": result}
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Celery PDF下载任务失败: literature_id={literature_id}, error={e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'literature_id': literature_id}
        )
        raise
