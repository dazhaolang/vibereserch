"""
基于ResearchRabbit的增强文献采集器
集成搜索、元数据获取、PDF下载和MinerU处理
"""

import asyncio
import os
import tempfile
import hashlib
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import aiofiles
import aiohttp

from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.models.task import Task
from app.services.research_rabbit_client import ResearchRabbitClient, ResearchRabbitConfig
from app.services.pdf_processor import PDFProcessor
from app.core.config import settings


class EnhancedLiteratureCollector:
    """基于ResearchRabbit的增强文献采集器"""
    
    def __init__(self):
        self.rr_client = None
        self.pdf_processor = PDFProcessor()
        self.temp_dir = tempfile.mkdtemp(prefix="literature_")
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        config = ResearchRabbitConfig()
        self.rr_client = ResearchRabbitClient(config)
        await self.rr_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.rr_client:
            await self.rr_client.__aexit__(exc_type, exc_val, exc_tb)
        
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.warning(f"清理临时目录失败: {e}")
    
    async def collect_literature(
        self,
        keywords: List[str],
        max_count: int = 100,
        project_id: Optional[int] = None,
        task_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行文献采集
        
        Args:
            keywords: 搜索关键词列表
            max_count: 最大采集数量
            project_id: 项目ID
            task_id: 任务ID
            
        Returns:
            采集结果统计
        """
        stats = {
            "total_found": 0,
            "total_processed": 0,
            "with_pdf": 0,
            "errors": 0,
            "duplicates": 0
        }
        
        try:
            # 更新任务状态
            if task_id:
                await self._update_task_status(task_id, "running", "开始文献搜索")
            
            # 1. 搜索文献
            logger.info(f"开始搜索关键词: {keywords}")
            query = " ".join(keywords)
            papers = await self.rr_client.search_all_papers(query, max_count)
            
            stats["total_found"] = len(papers)
            logger.info(f"找到 {len(papers)} 篇候选文献")
            
            if not papers:
                return stats
            
            # 2. 批量处理文献
            db = SessionLocal()
            try:
                processed_papers = await self._process_papers_batch(
                    papers, db, project_id, task_id, stats
                )
                stats["total_processed"] = len(processed_papers)
                
                # 3. 构建项目关联
                if project_id and processed_papers:
                    await self._associate_with_project(
                        processed_papers, project_id, db
                    )
                
                db.commit()
                logger.info(f"文献采集完成: {stats}")
                
                if task_id:
                    await self._update_task_status(
                        task_id, "completed", 
                        f"成功采集 {stats['total_processed']} 篇文献"
                    )
                    
            except Exception as e:
                db.rollback()
                logger.error(f"文献处理失败: {e}")
                stats["errors"] += 1
                
                if task_id:
                    await self._update_task_status(
                        task_id, "failed", f"处理失败: {str(e)}"
                    )
                raise
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"文献采集异常: {e}")
            stats["errors"] += 1
            
            if task_id:
                await self._update_task_status(
                    task_id, "failed", f"采集失败: {str(e)}"
                )
        
        return stats
    
    async def _process_papers_batch(
        self,
        papers: List[Dict],
        db: Session,
        project_id: Optional[int],
        task_id: Optional[int],
        stats: Dict[str, Any]
    ) -> List[Literature]:
        """批量处理文献"""
        processed_papers = []
        
        # 分批处理，避免内存溢出
        batch_size = 10
        for i in range(0, len(papers), batch_size):
            batch = papers[i:i+batch_size]
            logger.info(f"处理批次 {i//batch_size + 1}/{(len(papers)-1)//batch_size + 1}")
            
            # 处理当前批次
            batch_results = await asyncio.gather(
                *[self._process_single_paper(paper, db) for paper in batch],
                return_exceptions=True
            )
            
            # 收集成功处理的文献
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"处理文献失败: {result}")
                    stats["errors"] += 1
                elif result is not None:
                    if result == "duplicate":
                        stats["duplicates"] += 1
                    else:
                        processed_papers.append(result)
                        if result.pdf_path:
                            stats["with_pdf"] += 1
            
            # 更新任务进度
            if task_id:
                progress = min(100, (i + batch_size) * 100 // len(papers))
                await self._update_task_progress(
                    task_id, progress, 
                    f"已处理 {min(i + batch_size, len(papers))}/{len(papers)} 篇文献"
                )
        
        return processed_papers
    
    async def _process_single_paper(
        self, 
        paper: Dict, 
        db: Session
    ) -> Optional[Literature]:
        """处理单篇文献"""
        try:
            # 提取基本信息
            paper_id = paper.get("paperId")
            title = paper.get("title", "").strip()
            doi = paper.get("externalIds", {}).get("DOI")
            
            if not title:
                logger.warning("文献标题为空，跳过")
                return None
            
            # 检查是否已存在
            existing = None
            if doi:
                existing = db.query(Literature).filter(Literature.doi == doi).first()
            if not existing:
                existing = db.query(Literature).filter(Literature.title == title).first()
            
            if existing:
                logger.info(f"文献已存在: {title[:50]}...")
                return "duplicate"
            
            # 创建文献对象
            literature = Literature(
                title=title,
                authors=self._extract_authors(paper.get("authors", [])),
                abstract=paper.get("abstract"),
                journal=paper.get("venue"),
                publication_year=paper.get("year"),
                doi=doi,
                external_ids=paper.get("externalIds", {}),
                citation_count=paper.get("citationCount", 0),
                reference_count=paper.get("referenceCount", 0),
                is_open_access=paper.get("isOpenAccess", False),
                fields_of_study=paper.get("fieldsOfStudy") or [],
                quality_score=self._calculate_quality_score(paper),
                source="researchrabbit",
                raw_data=paper
            )
            
            # 尝试下载和处理PDF
            if doi and paper.get("isOpenAccess"):
                pdf_path = await self._download_and_process_pdf(doi, title, literature, db)
                if pdf_path:
                    literature.pdf_path = pdf_path
            
            # 保存到数据库
            db.add(literature)
            db.flush()  # 获取ID
            
            logger.info(f"成功处理文献: {title[:50]}...")
            return literature
            
        except Exception as e:
            logger.error(f"处理文献异常: {e}")
            return None
    
    async def _download_and_process_pdf(
        self, 
        doi: str, 
        title: str,
        literature: Literature,
        db: Session
    ) -> Optional[str]:
        """下载并处理PDF，保存结构化内容到数据库"""
        try:
            # 获取PDF下载链接
            pdf_info = await self.rr_client.get_pdf_info(doi)
            if not pdf_info or not pdf_info.get("url_for_pdf"):
                return None
            
            pdf_url = pdf_info["url_for_pdf"]
            logger.info(f"下载PDF: {pdf_url}")
            
            # 下载PDF
            pdf_data = await self.rr_client.download_pdf(pdf_url)
            if not pdf_data:
                return None
            
            # 保存PDF文件
            pdf_filename = self._generate_filename(doi or title, ".pdf")
            pdf_path = os.path.join(settings.upload_path, "pdfs", pdf_filename)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            
            async with aiofiles.open(pdf_path, "wb") as f:
                await f.write(pdf_data)
            
            # 使用MinerU处理PDF
            try:
                result = await self.pdf_processor.process_pdf_with_segments(pdf_path)
                if result["success"]:
                    # 保存文本内容
                    text_content = result["content"].get("text_content", "")
                    if text_content:
                        text_filename = self._generate_filename(doi or title, ".txt")
                        text_path = os.path.join(settings.upload_path, "texts", text_filename)
                        
                        os.makedirs(os.path.dirname(text_path), exist_ok=True)
                        async with aiofiles.open(text_path, "w", encoding="utf-8") as f:
                            await f.write(text_content)
                    
                    # 保存结构化段落到数据库
                    segments = result.get("segments", [])
                    for segment_data in segments:
                        segment = LiteratureSegment(
                            literature_id=literature.id,
                            segment_type=segment_data.get("segment_type", "paragraph"),
                            content=segment_data.get("content", ""),
                            page_number=segment_data.get("page_number", 1),
                            extraction_confidence=segment_data.get("confidence", 0.5),
                            structured_data={
                                "source": "mineru",
                                "processor_version": result.get("metadata", {}).get("version", "unknown")
                            }
                        )
                        db.add(segment)
                    
                    # 更新文献状态
                    literature.is_parsed = True
                    literature.parsing_status = "completed"
                    literature.parsed_content = text_content
                    
                    logger.info(f"PDF处理完成: {len(segments)} 个段落")
                    return pdf_path
                else:
                    logger.error(f"MinerU处理失败: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"PDF处理失败: {e}")
                # 即使处理失败，也保留PDF文件
                return pdf_path
            
        except Exception as e:
            logger.error(f"PDF下载处理异常: {e}")
            return None
    
    def _extract_authors(self, authors_data: List[Dict]) -> List[str]:
        """提取作者信息"""
        authors = []
        for author in authors_data[:10]:  # 限制作者数量
            name = author.get("name", "").strip()
            if name:
                authors.append(name)
        return authors
    
    def _calculate_quality_score(self, paper: Dict) -> float:
        """计算文献质量评分"""
        score = 5.0  # 基础分
        
        # 引用数加分
        citations = paper.get("citationCount", 0)
        if citations > 100:
            score += 2.0
        elif citations > 50:
            score += 1.5
        elif citations > 10:
            score += 1.0
        elif citations > 0:
            score += 0.5
        
        # 发表年份加分（越新越好）
        year = paper.get("year")
        if year:
            current_year = datetime.now().year
            if year >= current_year - 2:
                score += 1.0
            elif year >= current_year - 5:
                score += 0.5
        
        # 开放获取加分
        if paper.get("isOpenAccess"):
            score += 0.5
        
        # 有摘要加分
        if paper.get("abstract"):
            score += 0.5
        
        return min(10.0, score)
    
    def _generate_filename(self, identifier: str, extension: str) -> str:
        """生成安全的文件名"""
        # 使用MD5哈希生成唯一文件名
        hash_obj = hashlib.md5(identifier.encode('utf-8'))
        filename = hash_obj.hexdigest()
        return f"{filename}{extension}"
    
    async def _associate_with_project(
        self, 
        papers: List[Literature], 
        project_id: int, 
        db: Session
    ):
        """建立文献与项目的关联"""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        
        for paper in papers:
            if paper not in project.literature:
                project.literature.append(paper)
        
        logger.info(f"成功关联 {len(papers)} 篇文献到项目 {project_id}")
    
    async def _update_task_status(
        self, 
        task_id: int, 
        status: str, 
        message: str = None
    ):
        """更新任务状态"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = status
                if message:
                    task.description = message
                if status == "completed":
                    task.end_time = datetime.utcnow()
                elif status == "failed":
                    task.end_time = datetime.utcnow()
                    task.error_message = message
                db.commit()
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
        finally:
            db.close()
    
    async def _update_task_progress(
        self, 
        task_id: int, 
        progress: int, 
        message: str = None
    ):
        """更新任务进度"""
        # 这里可以实现进度更新逻辑
        # 比如更新TaskProgress表或发送WebSocket消息
        pass