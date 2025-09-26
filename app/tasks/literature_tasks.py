"""
文献处理相关的后台任务
"""

import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Awaitable
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.task import Task
from app.services.task_stream_service import TaskStreamService
from app.services.task_cost_tracker import task_cost_tracker
from app.models.project import Project
from app.models.experience import MainExperience
from app.models.literature import Literature, LiteratureSegment
from app.models.user import User
from app.services.literature_collector import EnhancedLiteratureCollector
from app.services.pdf_processor import PDFProcessor
from app.services.research_ai_service import research_ai_service
from app.services.experience_engine import EnhancedExperienceEngine
from app.services.rag_service import RAGService
from app.services.task_orchestrator import TaskOrchestrator
from app.tasks.literature_tasks_helper import create_basic_segments

async def safe_broadcast_update(progress_service, task_id: int, data: dict):
    """安全的WebSocket广播更新"""
    try:
        await progress_service.broadcast_task_update(task_id, data)
    except Exception as ws_error:
        logger.warning(f"WebSocket更新失败 (Task {task_id}): {ws_error}")

def ai_search_batch_task(
    task_id: int,
    query: str,
    max_results: int
):
    """
    AI批量搜索文献的后台任务
    """
    import asyncio
    
    try:
        # 运行异步搜索任务
        asyncio.run(ai_search_batch_async(task_id, query, max_results))
    except Exception as e:
        logger.error(f"AI搜索任务失败: {e}")
        # 更新任务状态为失败
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                task.progress_percentage = 0
                db.commit()
                
                # 发送WebSocket更新
                from app.services.stream_progress_service import StreamProgressService
                progress_service = StreamProgressService()
                # Note: Cannot await in sync function, WebSocket update will be handled by async task
        finally:
            db.close()

async def ai_search_batch_async(
    task_id: int,
    query: str,
    max_results: int
):
    """
    异步AI搜索任务实现
    """
    db = SessionLocal()
    task_stream = TaskStreamService(db)
    token = None

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("任务不存在")

        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            raise ValueError("项目不存在")

        from app.services.research_rabbit_client import ResearchRabbitClient
        from app.services.shared_literature_service import SharedLiteratureService

        literature_service = SharedLiteratureService(db)

        token = task_cost_tracker.activate(task.id, db)
        await task_stream.start_task(task, "🔍 正在为您寻找相关研究文献...")

        total_found = 0
        total_added = 0

        async with ResearchRabbitClient() as client:
            await task_stream.update_progress(
                task,
                f"📚 正在搜索主题：{query}",
                10,
                {"query": query}
            )

            papers = await client.search_all_papers(query, max_results)
            total_found = len(papers)

            await task_stream.update_progress(
                task,
                f"✅ 发现 {total_found} 篇相关论文，正在筛选优质内容...",
                30,
                {"found_count": total_found}
            )

            new_papers: List[Dict[str, Any]] = []

            for i, paper in enumerate(papers):
                try:
                    external_ids = paper.get("externalIds") or {}
                    if isinstance(external_ids, str):
                        external_ids = {}

                    doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None
                    arxiv_id = external_ids.get("ArXiv") if isinstance(external_ids, dict) else None
                    title = paper.get("title", "")

                    existing_lit = await literature_service.find_existing_literature(
                        doi=doi,
                        arxiv_id=arxiv_id,
                        title=title
                    )

                    if existing_lit is None:
                        new_papers.append(paper)

                    if (i + 1) % 5 == 0:
                        progress = 30 + int((i + 1) / max(1, len(papers)) * 40)
                        await task_stream.update_progress(
                            task,
                            f"⏳ 已评估 {i + 1}/{len(papers)} 篇论文",
                            progress,
                            {
                                "processed_count": i + 1,
                                "total_count": len(papers),
                                "eta_minutes": ((len(papers) - (i + 1)) * 2) // 60 + 1
                            }
                        )

                except Exception as item_error:
                    logger.warning(f"处理文献 {i} 时出错: {item_error}")
                    continue

            if new_papers:
                await task_stream.update_progress(
                    task,
                    f"📖 正在为项目添加 {len(new_papers)} 篇优质论文...",
                    70,
                    {"new_count": len(new_papers)}
                )

                user = db.query(User).filter(User.id == project.owner_id).first()
                if user:
                    for paper in new_papers:
                        try:
                            await literature_service.add_literature_from_search(
                                user_id=user.id,
                                project_id=task.project_id,
                                paper_data=paper
                            )
                            total_added += 1
                        except Exception as add_error:
                            logger.warning(f"添加文献失败: {add_error}")
                            continue

        completion_details = {
            "success": True,
            "total_found": total_found,
            "total_added": total_added,
            "query": query
        }
        await task_stream.complete_task(task, completion_details)
        return completion_details

    except Exception as e:
        logger.error(f"AI搜索任务失败: {e}")
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            await task_stream.fail_task(task, str(e))
        return {"success": False, "error": str(e)}

    finally:
        if token is not None:
            task_cost_tracker.deactivate(token)
        db.close()

async def start_search_and_build_library_task(
    task_id: int,
    keywords: List[str],
    project_id: int,
    user_id: int,
    config: Dict[str, Any]
):
    """启动搜索建库原子化任务，统一由TaskStreamService托管进度。"""
    db = SessionLocal()

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == user_id
        ).first()
        if not project:
            raise ValueError(f"项目不存在或无权访问: {project_id}")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"用户不存在: {user_id}")

        task_stream = TaskStreamService(db)

        async def run_pipeline(progress_callback):
            from app.services.search_and_build_library_service import (
                create_search_and_build_library_service,
            )
            from app.services.search_pipeline import ProcessingConfig

            await progress_callback(
                "准备搜索建库上下文",
                5,
                {"keywords": keywords, "project_id": project_id},
            )

            processing_config = ProcessingConfig(
                batch_size=config.get("batch_size", 10),
                max_concurrent_downloads=config.get("max_concurrent_downloads", 5),
                max_concurrent_ai_calls=config.get("max_concurrent_ai_calls", 3),
                enable_ai_filtering=config.get("enable_ai_filtering", True),
                enable_pdf_processing=config.get("enable_pdf_processing", True),
                enable_structured_extraction=config.get("enable_structured_extraction", True),
                quality_threshold=config.get("quality_threshold", 6.0),
                max_retries=config.get("max_retries", 3),
                timeout_seconds=config.get("timeout_seconds", 3600),
                max_results=config.get("max_results", 200),
            )

            async def pipeline_progress(step: str, progress: int, details: Dict = None):
                await progress_callback(step, progress, details or {})

            async with create_search_and_build_library_service(db) as service:
                result = await service.execute_full_pipeline(
                    keywords=keywords,
                    project=project,
                    config=processing_config,
                    progress_callback=pipeline_progress,
                )

            if not result.get("success"):
                raise RuntimeError(result.get("error", "搜索建库失败"))

            stats = result.get("stats", {})
            completion_details = {
                "success": True,
                "stats": stats,
                "processed_items": result.get("processed_items", 0),
                "processing_time": result.get("processing_time", 0),
            }
            return completion_details

        result = await task_stream.run_with_progress(
            task,
            "初始化搜索建库流水线",
            run_pipeline,
        )

        if result.get("success"):
            await _ensure_project_main_experience(project, db)

        await _schedule_auto_pipeline_next_step(task, db)
        return result

    except Exception as exc:
        logger.error(f"搜索建库任务异常: {exc}")
        raise
    finally:
        db.close()


async def start_literature_collection_task(
    task_id: int,
    keywords: List[str],
    max_count: int,
    sources: List[str]
):
    """启动文献采集任务"""
    db = SessionLocal()

    collector: Optional[EnhancedLiteratureCollector] = None

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {task.project_id}")

        user = db.query(User).filter(User.id == project.owner_id).first()
        if not user:
            raise ValueError(f"用户不存在: {project.owner_id}")

        task_stream = TaskStreamService(db)
        collector = EnhancedLiteratureCollector()

        async def run_collection(progress_callback):
            await progress_callback(
                "准备文献采集上下文",
                5,
                {
                    "keywords": keywords,
                    "max_count": max_count,
                    "sources": sources,
                },
            )

            async def collection_progress(step: str, progress: int, details: Dict = None):
                await progress_callback(step, progress, details or {})

            result = await collector.collect_literature(
                keywords=keywords,
                max_count=max_count,
                project_id=project.id,
                task_id=task.id,
            )

            summary = {
                "success": True,
                "total_collected": len(result.get("literature", [])),
                "statistics": result.get("statistics", {}),
            }
            return summary

        result = await task_stream.run_with_progress(
            task,
            "初始化文献采集",
            run_collection,
        )

        await _schedule_auto_pipeline_next_step(task, db)
        return result

    except Exception as exc:
        logger.error(f"文献采集任务异常: {exc}")
        raise
    finally:
        db.close()

async def _schedule_auto_pipeline_next_step(task: Task, db: Session) -> None:
    """根据任务配置调度自动研究流水线的下一步。"""
    try:
        config = task.config or {}
        pipeline_cfg = config.get("auto_pipeline")
        if not pipeline_cfg:
            return

        next_step = pipeline_cfg.get("on_complete")
        if not next_step:
            return

        project = task.project
        owner_id = project.owner_id if project else None
        if owner_id is None:
            logger.warning(f"任务 {task.id} 缺少项目所有者信息，无法继续自动流水线")
            return

        orchestrator = TaskOrchestrator(db)
        step_type = next_step.get("type")
        payload = next_step.get("payload", {})

        if step_type == "search_and_build_library":
            keywords = payload.get("keywords") or []
            search_config = payload.get("config") or {}
            orchestrator.trigger_search_pipeline(
                owner_id=owner_id,
                project_id=task.project_id,
                keywords=keywords,
                config=search_config,
            )
        elif step_type == "experience_generation":
            research_question = payload.get("query") or pipeline_cfg.get("query") or "通用研究问题"
            processing_method = payload.get("processing_method") or pipeline_cfg.get("processing_method") or "standard"
            orchestrator.trigger_experience_task(
                owner_id=owner_id,
                project_id=task.project_id,
                research_question=research_question,
                processing_method=processing_method,
            )
    except Exception as pipeline_error:
        logger.error(f"自动研究流水线调度失败: {pipeline_error}")


async def _ensure_project_main_experience(project: Project, db: Session) -> None:
    """确保项目存在主经验，如缺失则基于最新结构化文献自动生成。"""
    try:
        existing = (
            db.query(MainExperience)
            .filter(MainExperience.project_id == project.id)
            .first()
        )
        if existing:
            return

        segments = (
            db.query(LiteratureSegment)
            .join(Literature)
            .filter(Literature.projects.any(id=project.id))
            .limit(500)
            .all()
        )
        if not segments:
            return

        engine = EnhancedExperienceEngine(db)
        await engine.create_main_experiences(project, segments)

    except Exception as exc:
        logger.warning(f"自动生成主经验失败 (项目 {project.id}): {exc}")

async def start_literature_processing_task(task_id: int):
    """启动文献处理任务"""
    db = SessionLocal()

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task_stream = TaskStreamService(db)

        async def run_processing(progress_callback):
            project = db.query(Project).filter(Project.id == task.project_id).first()
            if not project:
                raise ValueError(f"项目不存在: {task.project_id}")

            unprocessed_literature = db.query(Literature).filter(
                Literature.projects.any(id=task.project_id),
                Literature.is_parsed.is_(False)
            ).all()

            if not unprocessed_literature:
                await progress_callback(
                    "没有需要处理的文献",
                    100,
                    {"processed_count": 0, "total_literature": 0},
                )
                return {
                    "success": True,
                    "processed_count": 0,
                    "total_literature": 0,
                    "message": "没有需要处理的文献",
                }

            await progress_callback(
                "准备文献处理上下文",
                5,
                {"pending_literature": len(unprocessed_literature)},
            )

            sample_literature = [
                {
                    "title": lit.title,
                    "abstract": lit.abstract or "",
                    "authors": lit.authors or [],
                }
                for lit in unprocessed_literature[:5]
            ]

            template_result = await research_ai_service.generate_structure_template(
                project.research_direction or "通用科研",
                sample_literature,
            )

            template_details = {
                "template_generated": template_result.get("success", False),
                "sample_size": len(sample_literature),
            }

            if template_result.get("success"):
                project.structure_template = template_result.get("template")
                db.commit()
                template_details["template_keys"] = list(
                    (project.structure_template or {}).keys()
                )
            else:
                template_details["error"] = template_result.get("error")

            await progress_callback("生成结构化模板", 10, template_details)

            total_items = len(unprocessed_literature)
            literature_ids = [lit.id for lit in unprocessed_literature]

            concurrency_limit = max(settings.literature_processing_concurrency, 1)
            semaphore = asyncio.Semaphore(concurrency_limit)
            progress_lock = asyncio.Lock()

            progress_state: Dict[str, Any] = {
                "processed": 0,
                "processed_success": 0,
                "fallback_used": 0,
                "failures": []
            }

            async def process_single_literature(literature_id: int):
                async with semaphore:
                    local_db = SessionLocal()
                    used_fallback = False
                    success = False
                    failure_info: Optional[Dict[str, Any]] = None
                    try:
                        literature = (
                            local_db.query(Literature)
                            .filter(Literature.id == literature_id)
                            .first()
                        )
                        if not literature:
                            raise ValueError(f"文献不存在: {literature_id}")

                        project_obj = (
                            local_db.query(Project)
                            .filter(Project.id == task.project_id)
                            .first()
                        )
                        if not project_obj:
                            raise ValueError(f"项目不存在: {task.project_id}")

                        logger.info(f"并行处理文献: {literature.title[:50]}...")
                        new_segments = 0

                        if literature.pdf_url or literature.pdf_path:
                            pdf_path = literature.pdf_path or literature.pdf_url
                            if pdf_path and os.path.exists(pdf_path):
                                try:
                                    pdf_processor = PDFProcessor()
                                    result = await pdf_processor.process_pdf_with_segments(
                                        pdf_path,
                                        project_obj.structure_template,
                                    )

                                    if result.get("success"):
                                        segments = result.get("segments", [])
                                        for segment_data in segments:
                                            segment = LiteratureSegment(
                                                literature_id=literature.id,
                                                segment_type=segment_data.get("segment_type", "general"),
                                                content=segment_data.get("content", ""),
                                                page_number=segment_data.get("page_number", 1),
                                                extraction_confidence=segment_data.get("confidence", 0.5),
                                                structured_data={
                                                    "source": "mineru_processing",
                                                    "processor_version": result.get("metadata", {}).get("version", "unknown"),
                                                },
                                            )
                                            local_db.add(segment)
                                            new_segments += 1

                                        literature.is_parsed = True
                                        literature.parsing_status = "completed"
                                        content_payload = result.get("content") or {}
                                        literature.parsed_content = content_payload.get("text_content", "")
                                        success = True
                                    else:
                                        logger.warning(
                                            f"PDF处理失败: {result.get('error', 'Unknown error')}"
                                        )
                                        await create_basic_segments(literature, local_db, project_obj)
                                        used_fallback = True
                                        success = True
                                except Exception as processing_exc:
                                    logger.error(f"PDF处理异常: {processing_exc}")
                                    await create_basic_segments(literature, local_db, project_obj)
                                    used_fallback = True
                                    success = True
                            else:
                                await create_basic_segments(literature, local_db, project_obj)
                                used_fallback = True
                                success = True
                        else:
                            await create_basic_segments(literature, local_db, project_obj)
                            used_fallback = True
                            success = True

                        local_db.commit()

                    except Exception as item_error:
                        local_db.rollback()
                        failure_info = {
                            "literature_id": literature_id,
                            "error": str(item_error),
                        }
                        logger.error(f"并行处理文献失败 {literature_id}: {item_error}")

                        # 更新状态为失败
                        persisted = (
                            local_db.query(Literature)
                            .filter(Literature.id == literature_id)
                            .first()
                        )
                        if persisted:
                            persisted.parsing_status = "failed"
                            local_db.commit()
                    finally:
                        local_db.close()

                    async with progress_lock:
                        progress_state["processed"] += 1
                        if success:
                            progress_state["processed_success"] += 1
                        if used_fallback:
                            progress_state["fallback_used"] += 1
                        if failure_info:
                            progress_state["failures"].append(failure_info)

                        progress_pct = 10 + int(
                            (progress_state["processed"] / max(total_items, 1)) * 80
                        )
                        details = {
                            "processed": progress_state["processed"],
                            "total": total_items,
                            "processed_success": progress_state["processed_success"],
                            "fallback_used": progress_state["fallback_used"],
                        }
                        if failure_info:
                            details["last_failure"] = failure_info

                        await progress_callback(
                            f"处理文献 {progress_state['processed']}/{total_items}",
                            min(progress_pct, 95),
                            details,
                        )

            await asyncio.gather(*[process_single_literature(lit_id) for lit_id in literature_ids])

            summary = {
                "success": True,
                "processed_count": progress_state["processed_success"],
                "total_literature": total_items,
                "fallback_used": progress_state["fallback_used"],
                "failures": progress_state["failures"],
            }
            return summary

        return await task_stream.run_with_progress(
            task,
            "初始化文献处理",
            run_processing,
        )

    except Exception as exc:
        logger.error(f"文献处理任务异常: {exc}")
        raise
    finally:
        db.close()

async def start_experience_generation_task(task_id: int, research_question: str):
    """启动经验生成任务"""
    db = SessionLocal()

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task_stream = TaskStreamService(db)

        async def run_experience(progress_callback):
            rag_service = RAGService(db)
            rag_results = await rag_service.search_relevant_segments(
                query=research_question,
                project_id=task.project_id,
                top_k=60,
            )

            segment_ids = [item.get("id") for item in rag_results if item.get("id")]

            if segment_ids:
                segment_order = {seg_id: idx for idx, seg_id in enumerate(segment_ids)}
                literature_segments = (
                    db.query(LiteratureSegment)
                    .filter(LiteratureSegment.id.in_(segment_ids))
                    .all()
                )
                literature_segments.sort(
                    key=lambda segment: segment_order.get(segment.id, len(segment_ids))
                )
            else:
                literature_segments = (
                    db.query(LiteratureSegment)
                    .join(Literature)
                    .filter(Literature.projects.any(id=task.project_id))
                    .all()
                )

            if not literature_segments:
                raise RuntimeError("没有可用的文献段落")

            await progress_callback(
                "准备经验生成上下文",
                10,
                {
                    "segment_count": len(literature_segments),
                    "research_question": research_question,
                },
            )

            experience_engine = EnhancedExperienceEngine(db)
            result = await experience_engine.run_experience_enhancement(
                task.project_id,
                research_question,
                literature_segments,
                task_id,
            )

            if not result.get("success"):
                raise RuntimeError(result.get("error", "经验生成失败"))

            return result

        return await task_stream.run_with_progress(
            task,
            "准备经验生成",
            run_experience,
        )

    except Exception as exc:
        logger.error(f"经验生成任务失败: {exc}")
        raise
    finally:
        db.close()

async def _perform_indexing(
    db: Session,
    project: Project,
    literature_segments: List[LiteratureSegment],
    progress_callback: Optional[Callable[[str, int, Dict[str, Any]], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """执行索引构建核心逻辑。"""

    if not literature_segments:
        raise RuntimeError("没有可用的文献段落数据，请先处理文献")

    total_segments = len(literature_segments)
    logger.info(f"开始构建项目 {project.id} 的文献索引，共 {total_segments} 个段落")

    for index, _ in enumerate(literature_segments):
        if progress_callback and ((index + 1) % 10 == 0 or index == total_segments - 1):
            progress = int(((index + 1) / total_segments) * 100)
            await progress_callback(
                f"索引构建 {index + 1}/{total_segments}",
                progress,
                {
                    "processed_segments": index + 1,
                    "total_segments": total_segments,
                },
            )

    project.status = "indexed"
    project.updated_at = datetime.utcnow()
    if hasattr(project, "indexed_at"):
        setattr(project, "indexed_at", datetime.utcnow())
    if hasattr(project, "index_version"):
        current_version = getattr(project, "index_version") or 0
        setattr(project, "index_version", current_version + 1)

    db.commit()

    logger.info(f"项目 {project.id} 索引构建完成")
    return {
        "success": True,
        "indexed_segments": total_segments,
    }


async def build_literature_index(project_id: int, task_id: str, user_id: int):
    """构建文献库索引的后台任务，兼容任务系统与直接触发两种模式。"""
    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        if project.owner_id != user_id:
            raise PermissionError("无权访问该项目")

        logger.info(f"开始构建项目 {project_id} 的文献索引，任务ID: {task_id}")

        project.status = "indexing"
        project.updated_at = datetime.utcnow()
        db.commit()

        numeric_task_id: Optional[int] = None
        try:
            numeric_task_id = int(task_id)
        except (TypeError, ValueError):
            numeric_task_id = None

        task: Optional[Task] = None
        if numeric_task_id is not None:
            task = db.query(Task).filter(Task.id == numeric_task_id).first()

        if task:
            task_stream = TaskStreamService(db)

            async def run_indexing(progress_callback):
                literature_segments = db.query(LiteratureSegment).join(Literature).filter(
                    Literature.projects.any(id=project_id)
                ).all()

                await progress_callback(
                    "准备构建文献索引",
                    5,
                    {"segment_count": len(literature_segments)},
                )

                return await _perform_indexing(
                    db,
                    project,
                    literature_segments,
                    progress_callback,
                )

            try:
                result = await task_stream.run_with_progress(
                    task,
                    "准备构建文献索引",
                    run_indexing,
                )
                return result
            except Exception:
                project.status = "error"
                db.commit()
                raise

        from app.services.stream_progress_service import StreamProgressService

        progress_service = StreamProgressService()

        literature_segments = db.query(LiteratureSegment).join(Literature).filter(
            Literature.projects.any(id=project_id)
        ).all()

        estimated_time = (
            f"{len(literature_segments) * 2}-{len(literature_segments) * 5} 秒"
            if literature_segments
            else "无法估算"
        )

        await progress_service.broadcast_project_update(
            project_id,
            {
                "type": "indexing_started",
                "task_id": task_id,
                "estimated_time": estimated_time,
            },
        )

        async def project_progress(step: str, progress: int, details: Dict[str, Any]):
            await progress_service.broadcast_project_update(
                project_id,
                {
                    "type": "indexing_progress",
                    "progress": progress,
                    "message": step,
                    **details,
                },
            )

        try:
            result = await _perform_indexing(
                db,
                project,
                literature_segments,
                project_progress,
            )

            await progress_service.broadcast_project_update(
                project_id,
                {
                    "type": "indexing_completed",
                    "segments_indexed": result.get("indexed_segments", 0),
                },
            )
            return result

        except Exception as exc:
            project.status = "error"
            db.commit()

            await progress_service.broadcast_project_update(
                project_id,
                {
                    "type": "indexing_failed",
                    "error": str(exc),
                },
            )
            logger.error(f"索引构建失败: {exc}")
            raise

    finally:
        db.close()


async def download_and_process_pdf_task(
    literature_id: int,
    user_id: int,
    task_id: Optional[int] = None,
):
    """从ResearchRabbit自动下载PDF并处理的后台任务。"""
    db = SessionLocal()
    task: Optional[Task] = None
    task_stream: Optional[TaskStreamService] = None
    token = None

    async def _run_pipeline(progress_callback: Callable[[str, int, Optional[Dict[str, Any]]], Awaitable[None]]):
        literature = (
            db.query(Literature)
            .filter(Literature.id == literature_id)
            .first()
        )
        if not literature:
            raise ValueError(f"未找到文献记录 ID: {literature_id}")

        project = (
            db.query(Project)
            .join(Project.literature)
            .filter(Literature.id == literature_id)
            .first()
        )
        project_id = project.id if project else None

        await progress_callback(
            "初始化PDF处理",
            5,
            {
                "literature_id": literature_id,
                "title": literature.title,
                "project_id": project_id,
            },
        )

        literature.parsing_status = "processing"
        db.commit()

        from app.services.research_rabbit_client import ResearchRabbitClient

        rabbit_client = ResearchRabbitClient()
        pdf_info = None
        if literature.doi:
            logger.info(f"通过DOI获取PDF信息: {literature.doi}")
            await progress_callback(
                "查询PDF信息",
                15,
                {"doi": literature.doi},
            )
            pdf_info = await rabbit_client.get_pdf_info(literature.doi)

        if not pdf_info or not pdf_info.get("url_for_pdf"):
            logger.warning(f"未找到PDF下载链接: {literature.title[:50]}")
            await create_basic_segments(literature, db, project)
            literature.parsing_status = "completed"
            db.commit()
            return {
                "status": "no_pdf",
                "message": f"文献处理完成（未找到PDF）: {literature.title[:50]}",
                "project_id": project_id,
                "segments_created": 0,
            }

        download_url = pdf_info["url_for_pdf"]
        logger.info(f"开始下载PDF: {download_url}")
        await progress_callback(
            "下载PDF",
            35,
            {"download_url": download_url},
        )
        pdf_data = await rabbit_client.download_pdf(download_url)

        if not pdf_data:
            logger.warning(f"PDF下载失败: {literature.title[:50]}")
            await create_basic_segments(literature, db, project)
            literature.parsing_status = "completed"
            db.commit()
            return {
                "status": "download_failed",
                "message": f"PDF下载失败: {literature.title[:50]}",
                "project_id": project_id,
                "segments_created": 0,
            }

        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(pdf_data)
            temp_pdf_path = temp_file.name

        try:
            from app.services.pdf_processor import PDFProcessor

            await progress_callback(
                "解析PDF内容",
                60,
                {"temp_path": temp_pdf_path},
            )

            pdf_processor = PDFProcessor()
            structure_template = project.structure_template if project and project.structure_template else None

            result = await pdf_processor.process_pdf_with_segments(
                temp_pdf_path,
                structure_template,
            )

            if result.get("success"):
                segments_data = result.get("segments", [])

                literature.parsing_status = "completed"
                literature.is_downloaded = True
                literature.is_parsed = True
                literature.pdf_path = temp_pdf_path

                for segment_data in segments_data:
                    segment = LiteratureSegment(
                        literature_id=literature.id,
                        segment_type=segment_data.get("segment_type", "paragraph"),
                        content=segment_data.get("content", ""),
                        order=segment_data.get("order", 0),
                        page_number=segment_data.get("page_number"),
                        metadata=segment_data.get("metadata", {}),
                    )
                    db.add(segment)

                db.commit()

                await progress_callback(
                    "PDF解析完成",
                    90,
                    {
                        "segments_created": len(segments_data),
                        "metadata": result.get("metadata", {}),
                    },
                )

                return {
                    "status": "success",
                    "message": f"PDF处理成功: {literature.title[:50]}",
                    "project_id": project_id,
                    "segments_created": len(segments_data),
                }

            logger.warning(f"PDF处理失败: {result.get('error', 'Unknown error')}")
            await create_basic_segments(literature, db, project)
            literature.parsing_status = "completed"
            db.commit()

            return {
                "status": "processing_failed",
                "message": f"PDF处理失败，使用基本信息: {literature.title[:50]}",
                "project_id": project_id,
                "segments_created": 0,
            }

        finally:
            if os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                except Exception as clean_error:
                    logger.warning(f"清理临时文件失败: {clean_error}")

    try:
        if task_id is None:
            raise ValueError("PDF处理任务必须绑定有效的任务上下文")

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        task_stream = TaskStreamService(db)
        token = task_cost_tracker.activate(task.id, db)
        return await task_stream.run_with_progress(
            task,
            "初始化PDF处理",
            _run_pipeline,
        )

    except Exception as exc:
        logger.error(f"PDF下载处理任务失败 (文献ID: {literature_id}): {exc}")
        raise

    finally:
        if token is not None:
            task_cost_tracker.deactivate(token)
        db.close()


async def start_main_experience_generation_task(
    task_id: Optional[int],
    project_id: int,
    user_id: int,
):
    """主经验生成的后台任务。"""
    db = SessionLocal()
    task: Optional[Task] = None
    task_stream: Optional[TaskStreamService] = None
    token = None

    async def _run_pipeline(progress_callback: Callable[[str, int, Optional[Dict[str, Any]]], Awaitable[None]]):
        # 获取项目信息
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"未找到项目 ID: {project_id}")

        await progress_callback(
            "开始主经验生成",
            10,
            {
                "project_id": project_id,
                "project_name": project.title,
            },
        )

        # 获取项目的所有文献段落
        literature_segments = (
            db.query(LiteratureSegment)
            .join(Literature)
            .filter(Literature.project_id == project_id)
            .all()
        )

        if not literature_segments:
            raise ValueError(f"项目 {project_id} 中没有文献段落，无法生成主经验")

        await progress_callback(
            f"准备处理 {len(literature_segments)} 个文献段落",
            20,
            {"total_segments": len(literature_segments)},
        )

        # 初始化经验引擎
        experience_engine = EnhancedExperienceEngine()

        # 创建主经验
        result = await experience_engine.create_main_experiences(
            project=project,
            literature_segments=literature_segments,
            progress_callback=progress_callback
        )

        await progress_callback(
            "主经验生成完成",
            100,
            {
                "main_experiences_created": result.get("main_experiences_count", 0),
                "project_id": project_id,
            },
        )

        return {
            "status": "success",
            "message": f"项目 {project.title} 主经验生成完成",
            "project_id": project_id,
            "main_experiences": result,
        }

    try:
        # 如果没有提供task_id，创建新任务
        if task_id is None:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"用户不存在: {user_id}")

            task = Task(
                type="main_experience_generation",
                description=f"生成项目 {project_id} 的主经验库",
                parameters={
                    "project_id": project_id,
                    "user_id": user_id,
                },
                user_id=user_id,
                status="running",
            )
            db.add(task)
            db.commit()
            task_id = task.id
        else:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise ValueError(f"任务不存在: {task_id}")

        task_stream = TaskStreamService(db)
        token = task_cost_tracker.activate(task.id, db)
        return await task_stream.run_with_progress(
            task,
            "初始化主经验生成",
            _run_pipeline,
        )

    except Exception as exc:
        logger.error(f"主经验生成任务失败 (项目ID: {project_id}): {exc}")
        raise

    finally:
        if token is not None:
            task_cost_tracker.deactivate(token)
        db.close()
