"""
Celery任务定义 - 统一的异步任务处理
"""

import asyncio
from typing import List, Dict, Any
from celery import Celery
from loguru import logger

from app.celery import celery_app
from app.tasks.literature_tasks import (
    ai_search_batch_async,
    start_literature_collection_task,
    start_literature_processing_task,
    start_experience_generation_task,
    build_literature_index,
    download_and_process_pdf_task
)

@celery_app.task(bind=True)
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

@celery_app.task(bind=True)
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

@celery_app.task(bind=True)
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

@celery_app.task(bind=True)
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

@celery_app.task(bind=True)
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

@celery_app.task(bind=True)
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


@celery_app.task(bind=True)
def download_pdf_celery(self, literature_id: int, user_id: int):
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
                download_and_process_pdf_task(literature_id, user_id)
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