"""
文献处理相关的后台任务
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.task import Task, TaskProgress
from app.models.project import Project
from app.models.literature import Literature, LiteratureSegment
from app.models.user import User
from app.services.literature_collector import EnhancedLiteratureCollector
from app.services.pdf_processor import PDFProcessor
from app.services.research_ai_service import research_ai_service
from app.services.experience_engine import EnhancedExperienceEngine
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
    
    try:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("任务不存在")
            
        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            raise ValueError("项目不存在")
        
        # 更新任务状态为运行中
        task.status = "running"
        task.started_at = datetime.utcnow()
        task.progress_percentage = 0
        task.current_step = "🔍 正在为您寻找相关研究文献..."
        db.commit()
        
        # 发送WebSocket更新
        from app.services.stream_progress_service import StreamProgressService
        progress_service = StreamProgressService()
        await safe_broadcast_update(progress_service, task_id, {
            "type": "task_started",
            "task_id": task_id,
            "progress": 0,
            "current_step": "🔍 正在为您寻找相关研究文献..."
        })
        
        # 使用Research Rabbit API搜索
        from app.services.research_rabbit_client import ResearchRabbitClient
        from app.services.shared_literature_service import SharedLiteratureService
        
        literature_service = SharedLiteratureService(db)
        total_found = 0
        total_added = 0
        
        async with ResearchRabbitClient() as client:
            # 更新进度: 10%
            task.progress_percentage = 10
            task.current_step = f"📚 正在搜索主题：{query}"
            db.commit()
            
            await safe_broadcast_update(progress_service, task_id, {
                "type": "task_progress",
                "task_id": task_id,
                "progress": 10,
                "current_step": f"📚 正在搜索主题：{query}"
            })
            
            # 搜索文献
            papers = await client.search_all_papers(query, max_results)
            total_found = len(papers)
            
            # 更新进度: 30%
            task.progress_percentage = 30
            task.current_step = f"✅ 发现 {total_found} 篇相关论文，正在为您筛选优质内容..."
            db.commit()
            
            await safe_broadcast_update(progress_service, task_id, {
                "type": "task_progress", 
                "task_id": task_id,
                "progress": 30,
                "current_step": f"✅ 发现 {total_found} 篇相关论文，正在为您筛选优质内容...",
                "found_count": total_found
            })
            
            # 处理每篇文献
            new_papers = []
            for i, paper in enumerate(papers):
                try:
                    # 安全地获取字段
                    external_ids = paper.get("externalIds") or {}
                    if isinstance(external_ids, str):
                        external_ids = {}
                        
                    doi = external_ids.get("DOI") if isinstance(external_ids, dict) else None
                    arxiv_id = external_ids.get("ArXiv") if isinstance(external_ids, dict) else None
                    title = paper.get("title", "")
                    
                    # 检查是否已存在
                    existing_lit = await literature_service.find_existing_literature(
                        doi=doi, arxiv_id=arxiv_id, title=title
                    )
                    
                    if existing_lit is None:
                        new_papers.append(paper)
                    
                    # 更新进度
                    progress = 30 + int((i + 1) / len(papers) * 40)  # 30% to 70%
                    if (i + 1) % 5 == 0:  # 每5篇更新一次
                        task.progress_percentage = progress
                        task.current_step = f"⏳ 已评估 {i + 1}/{len(papers)} 篇论文 (预计还需 {((len(papers)-(i+1))*2)//60+1} 分钟)"
                        db.commit()
                        
                        await safe_broadcast_update(progress_service, task_id, {
                            "type": "task_progress",
                            "task_id": task_id,
                            "progress": progress,
                            "current_step": f"⏳ 已评估 {i + 1}/{len(papers)} 篇论文 (预计还需 {((len(papers)-(i+1))*2)//60+1} 分钟)",
                            "processed_count": i + 1,
                            "total_count": len(papers)
                        })
                        
                except Exception as e:
                    logger.warning(f"处理文献 {i} 时出错: {e}")
                    continue
            
            # 添加新文献
            if new_papers:
                task.progress_percentage = 70
                task.current_step = f"📖 正在为您的项目添加 {len(new_papers)} 篇优质论文..."
                db.commit()
                
                await safe_broadcast_update(progress_service, task_id, {
                    "type": "task_progress",
                    "task_id": task_id,
                    "progress": 70,
                    "current_step": f"📖 正在为您的项目添加 {len(new_papers)} 篇优质论文...",
                    "new_count": len(new_papers)
                })
                
                # 批量添加文献
                paper_ids = [paper.get("paperId", "") for paper in new_papers if paper.get("paperId")]
                if paper_ids:
                    # 获取用户ID
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
                            except Exception as e:
                                logger.warning(f"添加文献失败: {e}")
                                continue
            
            # 任务完成
            task.status = "completed"
            task.progress_percentage = 100
            task.current_step = "任务完成"
            task.completed_at = datetime.utcnow()
            task.actual_duration = int((task.completed_at - task.started_at).total_seconds())
            task.result = {
                "total_found": total_found,
                "total_added": total_added,
                "query": query,
                "success": True
            }
            db.commit()
            
            # 发送完成消息
            await safe_broadcast_update(progress_service, task_id, {
                "type": "task_completed",
                "task_id": task_id,
                "progress": 100,
                "current_step": "🎉 文献搜索完成！已为您的项目添加高质量研究资料",
                "result": {
                    "total_found": total_found,
                    "total_added": total_added,
                    "query": query,
                    "message": f"成功搜索 {total_found} 篇文献，添加 {total_added} 篇新文献"
                }
            })
            
    except Exception as e:
        # 处理异常
        logger.error(f"AI搜索任务异常: {e}")
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = datetime.utcnow()
        db.commit()
        
        # 发送失败消息
        await safe_broadcast_update(progress_service, task_id, {
            "type": "task_failed",
            "task_id": task_id,
            "error": str(e)
        })
        raise
        
    finally:
        db.close()

async def start_search_and_build_library_task(
    task_id: int,
    keywords: List[str],
    project_id: int,
    user_id: int,
    config: Dict[str, Any]
):
    """
    启动搜索建库原子化任务
    执行完整的搜索→筛选→下载PDF→转Markdown→结构化处理→入库流水线
    """
    db = SessionLocal()

    try:
        # 获取任务和项目信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return {"success": False, "error": "任务不存在"}

        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == user_id
        ).first()
        if not project:
            logger.error(f"项目不存在或无权访问: {project_id}")
            return {"success": False, "error": "项目不存在或无权访问"}

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"用户不存在: {user_id}")
            return {"success": False, "error": "用户不存在"}

        # 更新任务状态
        task.status = "running"
        task.start_time = datetime.utcnow()
        task.current_step = "初始化搜索建库流水线"
        task.progress_percentage = 0
        db.commit()

        logger.info(f"开始搜索建库任务 {task_id}: 关键词={keywords}, 项目={project_id}")

        # 发送WebSocket更新
        from app.services.stream_progress_service import StreamProgressService
        progress_service = StreamProgressService()

        # 定义进度回调函数
        async def progress_callback(step: str, progress: int, details: dict = None):
            try:
                task.current_step = step
                task.progress_percentage = progress
                if details:
                    task.result = details
                db.commit()

                # 发送WebSocket更新
                await safe_broadcast_update(progress_service, task_id, {
                    "type": "task_progress",
                    "task_id": task_id,
                    "progress": progress,
                    "current_step": step,
                    "details": details
                })

                logger.info(f"任务 {task_id} 进度更新: {step} ({progress}%)")
            except Exception as e:
                logger.warning(f"更新任务进度失败: {e}")

        try:
            # 使用搜索建库服务执行完整流水线
            from app.services.search_and_build_library_service import (
                create_search_and_build_library_service,
                ProcessingConfig
            )

            # 构建处理配置
            processing_config = ProcessingConfig(
                batch_size=config.get("batch_size", 10),
                max_concurrent_downloads=config.get("max_concurrent_downloads", 5),
                max_concurrent_ai_calls=3,
                enable_ai_filtering=config.get("enable_ai_filtering", True),
                enable_pdf_processing=config.get("enable_pdf_processing", True),
                enable_structured_extraction=config.get("enable_structured_extraction", True),
                quality_threshold=config.get("quality_threshold", 6.0),
                max_retries=3,
                timeout_seconds=3600  # 1小时超时
            )

            # 执行搜索建库流水线
            async with create_search_and_build_library_service(db) as service:
                result = await service.execute_full_pipeline(
                    keywords=keywords,
                    project=project,
                    config=processing_config,
                    progress_callback=progress_callback
                )

            # 任务完成，更新状态
            if result.get("success"):
                task.status = "completed"
                task.end_time = datetime.utcnow()
                task.current_step = "搜索建库完成"
                task.progress_percentage = 100.0
                task.result = {
                    "success": True,
                    "stats": result.get("stats", {}),
                    "processed_items": result.get("processed_items", 0),
                    "processing_time": result.get("processing_time", 0)
                }

                # 发送完成消息
                await safe_broadcast_update(progress_service, task_id, {
                    "type": "task_completed",
                    "task_id": task_id,
                    "progress": 100,
                    "current_step": "搜索建库完成",
                    "result": task.result
                })

                logger.info(f"搜索建库任务 {task_id} 完成: {result.get('stats', {})}")
            else:
                # 任务失败
                task.status = "failed"
                task.end_time = datetime.utcnow()
                task.error_message = result.get("error", "搜索建库失败")
                task.result = {"success": False, "error": task.error_message}

                # 发送失败消息
                await safe_broadcast_update(progress_service, task_id, {
                    "type": "task_failed",
                    "task_id": task_id,
                    "error": task.error_message
                })

            db.commit()
            return result

        except Exception as e:
            logger.error(f"搜索建库任务执行异常: {e}")

            # 更新任务状态为失败
            task.status = "failed"
            task.end_time = datetime.utcnow()
            task.error_message = str(e)
            task.result = {"success": False, "error": str(e)}

            # 发送失败消息
            await safe_broadcast_update(progress_service, task_id, {
                "type": "task_failed",
                "task_id": task_id,
                "error": str(e)
            })

            db.commit()
            return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"搜索建库任务异常: {e}")
        return {"success": False, "error": str(e)}

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
    
    try:
        # 获取任务和项目信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return
        
        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            logger.error(f"项目不存在: {task.project_id}")
            return
        
        user = db.query(User).filter(User.id == project.owner_id).first()
        if not user:
            logger.error(f"用户不存在: {project.owner_id}")
            return
        
        # 更新任务状态
        task.status = "running"
        task.start_time = datetime.utcnow()
        task.current_step = "初始化文献采集"
        db.commit()
        
        logger.info(f"开始文献采集任务 {task_id}: 关键词={keywords}, 数量={max_count}")
        
        # 使用增强的文献采集器
        collector = EnhancedLiteratureCollector()
        
        # 定义进度回调函数
        async def progress_callback(step: str, progress: int, details: dict = None):
            try:
                task.current_step = step
                task.progress_percentage = progress
                if details:
                    task.result = details
                db.commit()
                logger.info(f"任务 {task_id} 进度更新: {step} ({progress}%)")
            except Exception as e:
                logger.warning(f"更新任务进度失败: {e}")
        
        try:
            # 执行采集
            result = await collector.collect_literature_with_screening(
                keywords=keywords,
                user=user,
                max_count=max_count,
                sources=sources,
                enable_ai_screening=True,
                progress_callback=progress_callback
            )
            
            # 采集完成，更新任务状态
            task.status = "completed"
            task.end_time = datetime.utcnow()
            task.current_step = "文献采集完成"
            task.progress_percentage = 100.0
            task.result = {
                "success": True,
                "total_collected": len(result.get("literature", [])),
                "quality_filtered": result.get("quality_filtered", 0),
                "with_pdf": result.get("with_pdf", 0),
                "statistics": result
            }
            
            db.commit()
            logger.info(f"文献采集任务 {task_id} 完成，采集 {len(result.get('literature', []))} 篇文献")
            
        finally:
            # 关闭采集器资源
            await collector.close()
            
    except Exception as e:
        logger.error(f"文献采集任务异常: {e}")
        
        # 更新任务状态为失败
        try:
            task.status = "failed"
            task.end_time = datetime.utcnow()
            task.error_message = str(e)
            task.result = {"success": False, "error": str(e)}
            db.commit()
        except Exception as commit_error:
            logger.error(f"更新任务状态失败: {commit_error}")
    
    finally:
        db.close()

async def start_literature_processing_task(task_id: int):
    """启动文献处理任务"""
    db = SessionLocal()
    
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return
        
        # 更新任务状态为运行中
        task.status = "running"
        task.started_at = datetime.utcnow()
        task.current_step = "初始化文献处理"
        task.progress_percentage = 0
        db.commit()
        
        # 发送WebSocket更新
        from app.services.stream_progress_service import StreamProgressService
        progress_service = StreamProgressService()
        await safe_broadcast_update(progress_service, task_id, {
            "type": "task_started",
            "task_id": task_id,
            "progress": 0,
            "current_step": "初始化文献处理"
        })
        
        # 获取项目和未处理文献
        project = db.query(Project).filter(Project.id == task.project_id).first()
        unprocessed_literature = db.query(Literature).filter(
            Literature.projects.any(id=task.project_id),
            Literature.is_parsed == False
        ).all()
        
        if not unprocessed_literature:
            task.status = "completed"
            task.error_message = "没有需要处理的文献"
            db.commit()
            return
        
        # 生成结构化模板
        # 使用统一的research_ai_service替代AIService实例
        
        # 准备样本文献数据
        sample_literature = []
        for lit in unprocessed_literature[:5]:
            sample_literature.append({
                "title": lit.title,
                "abstract": lit.abstract or "",
                "authors": lit.authors or []
            })
        
        # 生成模板
        template_result = await research_ai_service.generate_structure_template(
            project.research_direction or "通用科研", 
            sample_literature
        )
        
        if template_result["success"]:
            project.structure_template = template_result["template"]
            db.commit()
        
        # 处理每篇文献
        pdf_processor = PDFProcessor()
        processed_count = 0
        
        for i, literature in enumerate(unprocessed_literature):
            try:
                logger.info(f"处理文献: {literature.title[:50]}...")
                
                # 如果有PDF，先处理PDF
                if literature.pdf_url or literature.pdf_path:
                    # 处理PDF文件
                    pdf_path = literature.pdf_path or literature.pdf_url
                    if pdf_path and os.path.exists(pdf_path):
                        try:
                            # 使用PDF处理器处理文件
                            result = await pdf_processor.process_pdf_with_segments(
                                pdf_path, project.structure_template
                            )
                            
                            if result["success"]:
                                # 保存结构化段落
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
                                            "processor_version": result.get("metadata", {}).get("version", "unknown")
                                        }
                                    )
                                    db.add(segment)
                                
                                # 更新文献状态
                                literature.is_parsed = True
                                literature.parsing_status = "completed"
                                literature.parsed_content = result["content"].get("text_content", "")
                                processed_count += 1
                                
                                logger.info(f"PDF处理成功: {literature.title[:50]} - {len(segments)} 个段落")
                            else:
                                # PDF处理失败，使用基本信息创建段落
                                logger.warning(f"PDF处理失败: {result.get('error', 'Unknown error')}")
                                await create_basic_segments(literature, db, project)
                                
                        except Exception as e:
                            logger.error(f"PDF处理异常: {e}")
                            await create_basic_segments(literature, db, project)
                    else:
                        # PDF文件不存在，使用基本信息
                        await create_basic_segments(literature, db, project)
                else:
                    # 没有PDF，基于摘要和标题生成段落
                    await create_basic_segments(literature, db, project)
                
                # 更新进度
                progress_pct = 20 + (i + 1) / len(unprocessed_literature) * 70
                task.progress_percentage = progress_pct
                task.current_step = f"已处理 {i + 1}/{len(unprocessed_literature)} 篇文献"
                
                # 发送进度更新
                if (i + 1) % 5 == 0:  # 每5篇更新一次
                    db.commit()
                    await safe_broadcast_update(progress_service, task_id, {
                        "type": "task_progress",
                        "task_id": task_id,
                        "progress": progress_pct,
                        "current_step": f"已处理 {i + 1}/{len(unprocessed_literature)} 篇文献",
                        "processed_count": i + 1,
                        "total_count": len(unprocessed_literature)
                    })
                
            except Exception as e:
                logger.error(f"处理文献失败: {literature.title[:50]} - {e}")
                literature.parsing_status = "failed"
        
        db.commit()
        
        # 完成任务
        task.status = "completed"
        task.progress_percentage = 100.0
        task.current_step = "文献处理完成"
        task.completed_at = datetime.utcnow()
        task.actual_duration = int((task.completed_at - task.started_at).total_seconds())
        task.result = {
            "processed_count": processed_count,
            "total_literature": len(unprocessed_literature),
            "success": True
        }
        db.commit()
        
        # 发送完成消息
        await safe_broadcast_update(progress_service, task_id, {
            "type": "task_completed",
            "task_id": task_id,
            "progress": 100,
            "current_step": "文献处理完成",
            "result": {
                "processed_count": processed_count,
                "total_literature": len(unprocessed_literature),
                "message": f"成功处理 {processed_count} 篇文献"
            }
        })
        
        logger.info(f"文献处理任务完成，处理了 {processed_count} 篇文献")
        
    except Exception as e:
        logger.error(f"文献处理任务失败: {e}")
        
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
            
            # 发送失败消息
            await safe_broadcast_update(progress_service, task_id, {
                "type": "task_failed",
                "task_id": task_id,
                "error": str(e)
            })
    
    finally:
        db.close()

async def start_experience_generation_task(task_id: int, research_question: str):
    """启动经验生成任务"""
    db = SessionLocal()
    
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return
        
        task.status = "running"
        task.current_step = "准备经验生成"
        db.commit()
        
        # 获取项目文献段落
        literature_segments = db.query(LiteratureSegment).join(Literature).filter(
            Literature.projects.any(id=task.project_id)
        ).all()
        
        if not literature_segments:
            task.status = "failed"
            task.error_message = "没有可用的文献段落"
            db.commit()
            return
        
        # 启动经验增强引擎
        experience_engine = EnhancedExperienceEngine(db)
        
        result = await experience_engine.run_experience_enhancement(
            task.project_id,
            research_question,
            literature_segments,
            task_id
        )
        
        if result["success"]:
            task.status = "completed"
            task.result = result
        else:
            task.status = "failed"
            task.error_message = result.get("error", "经验生成失败")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"经验生成任务失败: {e}")
        
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            db.commit()
    
    finally:
        db.close()

async def build_literature_index(project_id: int, task_id: str, user_id: int):
    """构建文献库索引的后台任务"""
    db = SessionLocal()
    
    try:
        # 获取项目信息
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"项目不存在: {project_id}")
            return
        
        logger.info(f"开始构建项目 {project_id} 的文献索引，任务ID: {task_id}")
        
        # 发送WebSocket更新
        from app.services.stream_progress_service import StreamProgressService
        progress_service = StreamProgressService()
        progress_service.broadcast_project_update(project_id, {
            "type": "indexing_started",
            "task_id": task_id,
            "estimated_time": f"{len(project.literature) * 2}-{len(project.literature) * 5} 秒"
        })
        
        # 获取所有文献段落
        literature_segments = db.query(LiteratureSegment).join(Literature).filter(
            Literature.projects.any(id=project_id)
        ).all()
        
        if not literature_segments:
            # 索引失败 - 没有段落数据
            project.status = 'error'
            db.commit()
            
            progress_service.broadcast_project_update(project_id, {
                "type": "indexing_failed",
                "error": "没有可用的文献段落数据，请先处理文献"
            })
            return
        
        total_segments = len(literature_segments)
        logger.info(f"找到 {total_segments} 个文献段落，开始构建索引")
        
        # 模拟索引构建过程
        for i, segment in enumerate(literature_segments):
            # 这里可以添加实际的向量化和索引构建逻辑
            # 例如：生成embeddings，存储到vector数据库等
            
            # 更新进度
            progress = int((i + 1) / total_segments * 100)
            
            if (i + 1) % 10 == 0 or i == total_segments - 1:  # 每10个段落或最后一个更新一次
                progress_service.broadcast_project_update(project_id, {
                    "type": "indexing_progress",
                    "progress": progress
                })
                logger.info(f"索引进度: {i + 1}/{total_segments} ({progress}%)")
        
        # 索引构建完成
        project.status = 'indexed'
        project.indexed_at = datetime.utcnow()
        project.index_version = 1  # 可以用于版本控制
        db.commit()
        
        # 发送完成消息
        progress_service.broadcast_project_update(project_id, {
            "type": "indexing_completed",
            "segments_indexed": total_segments
        })
        
        logger.info(f"项目 {project_id} 索引构建完成，共索引 {total_segments} 个段落")
        
    except Exception as e:
        logger.error(f"索引构建失败: {e}")
        
        # 更新项目状态为错误
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = 'error'
                db.commit()
                
                # 发送失败消息
                progress_service.broadcast_project_update(project_id, {
                    "type": "indexing_failed",
                    "error": str(e)
                })
        except Exception as commit_error:
            logger.error(f"更新项目状态失败: {commit_error}")

    finally:
        db.close()


async def download_and_process_pdf_task(literature_id: int, user_id: int):
    """
    从ResearchRabbit自动下载PDF并处理的后台任务
    """
    db = SessionLocal()

    try:
        # 获取文献记录
        literature = db.query(Literature).filter(Literature.id == literature_id).first()
        if not literature:
            logger.error(f"未找到文献记录 ID: {literature_id}")
            return

        logger.info(f"开始处理文献PDF: {literature.title[:50]}...")

        # 更新状态为处理中
        literature.parsing_status = "processing"
        db.commit()

        # 获取项目信息用于进度推送
        project = db.query(Project).join(Project.literature).filter(Literature.id == literature_id).first()
        project_id = project.id if project else None

        # 1. 通过DOI获取PDF下载信息
        from app.services.research_rabbit_client import ResearchRabbitClient
        rabbit_client = ResearchRabbitClient()

        pdf_info = None
        if literature.doi:
            logger.info(f"通过DOI获取PDF信息: {literature.doi}")
            pdf_info = await rabbit_client.get_pdf_info(literature.doi)

        if not pdf_info or not pdf_info.get("url_for_pdf"):
            logger.warning(f"未找到PDF下载链接: {literature.title[:50]}")
            # 使用基本信息创建段落
            await create_basic_segments(literature, db, project)
            literature.parsing_status = "completed"
            db.commit()

            # 发送完成通知
            if project_id:
                from app.services.stream_progress_service import stream_progress_service
                await safe_broadcast_update(stream_progress_service, 0, {
                    "type": "literature_processed",
                    "literature_id": literature_id,
                    "project_id": project_id,
                    "status": "no_pdf",
                    "message": f"文献处理完成（未找到PDF）: {literature.title[:50]}"
                })
            return

        # 2. 下载PDF文件
        logger.info(f"开始下载PDF: {pdf_info['url_for_pdf']}")
        pdf_data = await rabbit_client.download_pdf(pdf_info["url_for_pdf"])

        if not pdf_data:
            logger.warning(f"PDF下载失败: {literature.title[:50]}")
            # 使用基本信息创建段落
            await create_basic_segments(literature, db, project)
            literature.parsing_status = "completed"
            db.commit()

            # 发送失败通知
            if project_id:
                from app.services.stream_progress_service import stream_progress_service
                await safe_broadcast_update(stream_progress_service, 0, {
                    "type": "literature_processed",
                    "literature_id": literature_id,
                    "project_id": project_id,
                    "status": "download_failed",
                    "message": f"PDF下载失败: {literature.title[:50]}"
                })
            return

        # 3. 保存PDF文件
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(pdf_data)
            temp_pdf_path = temp_file.name

        try:
            # 4. 使用PDFProcessor处理PDF
            from app.services.pdf_processor import PDFProcessor
            pdf_processor = PDFProcessor()

            logger.info(f"开始PDF处理和Markdown转换: {literature.title[:50]}")

            # 生成结构模板（如果需要）
            structure_template = None
            if project and project.structure_template:
                structure_template = project.structure_template

            # 处理PDF文件
            result = await pdf_processor.process_pdf_with_segments(
                temp_pdf_path,
                structure_template
            )

            if result.get("success"):
                # 5. 保存处理结果
                segments_data = result.get("segments", [])

                # 更新文献状态
                literature.parsing_status = "completed"
                literature.is_downloaded = True
                literature.is_parsed = True
                literature.pdf_path = temp_pdf_path  # 保存PDF路径

                # 保存段落
                for segment_data in segments_data:
                    segment = LiteratureSegment(
                        literature_id=literature.id,
                        segment_type=segment_data.get("segment_type", "paragraph"),
                        content=segment_data.get("content", ""),
                        order=segment_data.get("order", 0),
                        page_number=segment_data.get("page_number"),
                        metadata=segment_data.get("metadata", {})
                    )
                    db.add(segment)

                db.commit()

                logger.info(f"PDF处理成功: {literature.title[:50]} - {len(segments_data)} 个段落")

                # 发送成功通知
                if project_id:
                    from app.services.stream_progress_service import stream_progress_service
                    await safe_broadcast_update(stream_progress_service, 0, {
                        "type": "literature_processed",
                        "literature_id": literature_id,
                        "project_id": project_id,
                        "status": "success",
                        "segments_count": len(segments_data),
                        "message": f"PDF处理成功: {literature.title[:50]}"
                    })

            else:
                # PDF处理失败，使用基本信息
                logger.warning(f"PDF处理失败: {result.get('error', 'Unknown error')}")
                await create_basic_segments(literature, db, project)
                literature.parsing_status = "completed"
                db.commit()

                # 发送处理失败通知
                if project_id:
                    from app.services.stream_progress_service import stream_progress_service
                    await safe_broadcast_update(stream_progress_service, 0, {
                        "type": "literature_processed",
                        "literature_id": literature_id,
                        "project_id": project_id,
                        "status": "processing_failed",
                        "message": f"PDF处理失败，使用基本信息: {literature.title[:50]}"
                    })

        finally:
            # 清理临时PDF文件
            if os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")

    except Exception as e:
        logger.error(f"PDF下载处理任务失败 (文献ID: {literature_id}): {e}")

        # 更新失败状态
        literature = db.query(Literature).filter(Literature.id == literature_id).first()
        if literature:
            literature.parsing_status = "failed"
            db.commit()

            # 发送错误通知
            project = db.query(Project).join(Project.literature).filter(Literature.id == literature_id).first()
            if project:
                from app.services.stream_progress_service import stream_progress_service
                await safe_broadcast_update(stream_progress_service, 0, {
                    "type": "literature_processed",
                    "literature_id": literature_id,
                    "project_id": project.id,
                    "status": "error",
                    "message": f"处理失败: {str(e)[:100]}"
                })

    finally:
        db.close()