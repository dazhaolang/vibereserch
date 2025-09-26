"""
基于 ResearchRabbit 的文献采集服务。
旧版本的多源采集逻辑已经移除，现仅保留 ResearchRabbit API 流水线。
"""

import asyncio
import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiofiles
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.models.task import Task
from app.services.pdf_processor import PDFProcessor
from app.services.research_rabbit_client import ResearchRabbitClient, ResearchRabbitConfig


class EnhancedLiteratureCollector:
    """仅使用 ResearchRabbit 的文献采集器"""

    def __init__(self) -> None:
        self.pdf_processor = PDFProcessor()

    async def collect_literature(
        self,
        keywords: List[str],
        max_count: int = 100,
        project_id: Optional[int] = None,
        task_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """搜索并写入文献，返回处理统计。"""
        normalized_keywords = [kw.strip() for kw in keywords if kw and kw.strip()]
        if not normalized_keywords:
            raise ValueError("关键词不能为空")

        stats = {
            "total_found": 0,
            "total_processed": 0,
            "with_pdf": 0,
            "duplicates": 0,
            "errors": 0,
        }
        processed_objects: List[Literature] = []

        try:
            if task_id:
                await self._update_task_status(task_id, "running", "正在搜索文献...")

            async with ResearchRabbitClient(ResearchRabbitConfig()) as rr_client:
                query = " ".join(normalized_keywords)
                papers = await rr_client.search_all_papers(query, max_count)
                stats["total_found"] = len(papers)

                if not papers:
                    logger.info("ResearchRabbit 未返回文献")
                    return {"literature": [], "statistics": stats}

                db = SessionLocal()
                try:
                    processed_objects = await self._process_papers_batch(
                        papers[:max_count], rr_client, db, project_id, task_id, stats
                    )
                    stats["total_processed"] = len(processed_objects)

                    if project_id and processed_objects:
                        await self._associate_with_project(processed_objects, project_id, db)

                    db.commit()
                    if task_id:
                        await self._update_task_status(
                            task_id,
                            "completed",
                            f"成功采集 {stats['total_processed']} 篇文献",
                        )
                except Exception as exc:  # pragma: no cover - 运行时异常路径
                    db.rollback()
                    stats["errors"] += 1
                    logger.error(f"文献采集失败: {exc}")
                    if task_id:
                        await self._update_task_status(task_id, "failed", str(exc))
                    raise
                finally:
                    db.close()
        except Exception as exc:  # pragma: no cover - 运行时异常路径
            stats["errors"] += 1
            logger.error(f"文献采集异常: {exc}")
            if task_id:
                await self._update_task_status(task_id, "failed", str(exc))

        return {
            "literature": [self._to_lite_dict(obj) for obj in processed_objects],
            "statistics": stats,
        }

    # 兼容旧接口名称
    async def collect_literature_with_screening(
        self,
        keywords: List[str],
        user: "User",  # noqa: F821 - 仅用于兼容旧签名
        max_count: int = 100,
        sources: Optional[List[str]] = None,
        enable_ai_screening: bool = True,
        progress_callback=None,
    ) -> Dict[str, Any]:
        _ = user, sources, enable_ai_screening, progress_callback  # 参数兼容占位
        return await self.collect_literature(keywords, max_count)

    async def _process_papers_batch(
        self,
        papers: List[Dict[str, Any]],
        rr_client: ResearchRabbitClient,
        db: Session,
        project_id: Optional[int],
        task_id: Optional[int],
        stats: Dict[str, Any],
    ) -> List[Literature]:
        processed: List[Literature] = []
        batch_size = 10

        for index in range(0, len(papers), batch_size):
            batch = papers[index : index + batch_size]
            results = await asyncio.gather(
                *[
                    self._process_single_paper(paper, rr_client, db, stats)
                    for paper in batch
                ],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Literature):
                    processed.append(result)
                    if result.pdf_path:
                        stats["with_pdf"] += 1
                elif result == "duplicate":
                    stats["duplicates"] += 1
                elif isinstance(result, Exception):
                    stats["errors"] += 1

            if task_id:
                current = min(index + batch_size, len(papers))
                await self._update_task_progress(
                    task_id,
                    current * 100 // max(1, len(papers)),
                    f"已处理 {current}/{len(papers)} 篇文献",
                )

        return processed

    async def _process_single_paper(
        self,
        paper: Dict[str, Any],
        rr_client: ResearchRabbitClient,
        db: Session,
        stats: Dict[str, Any],
    ) -> Optional[Literature]:
        try:
            title = (paper.get("title") or "").strip()
            if not title:
                logger.warning("文献标题缺失，跳过")
                return None

            doi = paper.get("externalIds", {}).get("DOI")
            existing = None
            if doi:
                existing = db.query(Literature).filter(Literature.doi == doi).first()
            if not existing:
                existing = (
                    db.query(Literature)
                    .filter(Literature.title == title)
                    .first()
                )

            if existing:
                return "duplicate"

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
                raw_data=paper,
            )

            pdf_path = await self._download_and_process_pdf(doi, title, literature, rr_client, db)
            if pdf_path:
                literature.pdf_path = pdf_path

            db.add(literature)
            db.flush()
            return literature
        except Exception as exc:  # pragma: no cover - 运行时异常路径
            logger.error(f"处理文献失败: {exc}")
            stats["errors"] += 1
            return None

    async def _download_and_process_pdf(
        self,
        doi: Optional[str],
        title: str,
        literature: Literature,
        rr_client: ResearchRabbitClient,
        db: Session,
    ) -> Optional[str]:
        if not doi:
            return None

        try:
            pdf_info = await rr_client.get_pdf_info(doi)
            if not pdf_info or not pdf_info.get("url_for_pdf"):
                return None

            pdf_bytes = await rr_client.download_pdf(pdf_info["url_for_pdf"])
            if not pdf_bytes:
                return None

            filename = self._generate_filename(doi or title, ".pdf")
            pdf_dir = os.path.join(settings.upload_path, "pdfs")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_path = os.path.join(pdf_dir, filename)

            async with aiofiles.open(pdf_path, "wb") as handler:
                await handler.write(pdf_bytes)

            try:
                result = await self.pdf_processor.process_pdf_with_segments(pdf_path)
            except Exception as exc:  # pragma: no cover - PDF 处理异常
                logger.error(f"PDF 解析失败: {exc}")
                return pdf_path

            if not result.get("success"):
                logger.warning(f"MinerU 处理失败: {result.get('error')}")
                return pdf_path

            text_content = result["content"].get("text_content", "") if result.get("content") else ""
            if text_content:
                text_dir = os.path.join(settings.upload_path, "texts")
                os.makedirs(text_dir, exist_ok=True)
                text_path = os.path.join(text_dir, self._generate_filename(doi or title, ".txt"))
                async with aiofiles.open(text_path, "w", encoding="utf-8") as handler:
                    await handler.write(text_content)
                literature.parsed_content = text_content

            segments = result.get("segments", [])
            for segment in segments:
                db.add(
                    LiteratureSegment(
                        literature_id=literature.id,
                        segment_type=segment.get("segment_type", "paragraph"),
                        content=segment.get("content", ""),
                        page_number=segment.get("page_number", 1),
                        extraction_confidence=segment.get("confidence", 0.5),
                        structured_data={
                            "source": "mineru",
                            "processor_version": result.get("metadata", {}).get("version", "unknown"),
                        },
                    )
                )

            literature.is_parsed = bool(segments)
            literature.parsing_status = "completed" if segments else "pending"
            return pdf_path
        except Exception as exc:  # pragma: no cover - 网络异常路径
            logger.error(f"PDF 下载失败: {exc}")
            return None

    async def _associate_with_project(
        self,
        papers: List[Literature],
        project_id: int,
        db: Session,
    ) -> None:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        for paper in papers:
            if paper not in project.literature:
                project.literature.append(paper)
        logger.info(f"已关联 {len(papers)} 篇文献到项目 {project_id}")

    def _extract_authors(self, authors_data: List[Dict[str, Any]]) -> List[str]:
        authors: List[str] = []
        for author in authors_data[:10]:
            name = (author.get("name") or "").strip()
            if name:
                authors.append(name)
        return authors

    @staticmethod
    def _calculate_quality_score(paper: Dict[str, Any]) -> float:
        score = 5.0
        citations = paper.get("citationCount", 0)
        if citations > 100:
            score += 2.0
        elif citations > 50:
            score += 1.5
        elif citations > 10:
            score += 1.0
        elif citations > 0:
            score += 0.5

        year = paper.get("year")
        if year:
            current_year = datetime.now().year
            if year >= current_year - 2:
                score += 1.0
            elif year >= current_year - 5:
                score += 0.5

        if paper.get("isOpenAccess"):
            score += 0.5
        if paper.get("abstract"):
            score += 0.5
        return min(10.0, score)

    def _generate_filename(self, identifier: str, extension: str) -> str:
        digest = hashlib.md5(identifier.encode("utf-8")).hexdigest()
        return f"{digest}{extension}"

    def _to_lite_dict(self, literature: Literature) -> Dict[str, Any]:
        return {
            "id": literature.id,
            "title": literature.title,
            "doi": literature.doi,
            "quality_score": literature.quality_score,
            "is_parsed": literature.is_parsed,
        }

    async def _update_task_status(
        self,
        task_id: int,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return
            task.status = status
            if message:
                task.description = message
            if status in {"completed", "failed"}:
                task.completed_at = datetime.utcnow()
                if status == "failed":
                    task.error_message = message
            db.commit()
        except Exception as exc:  # pragma: no cover - 仅记录
            logger.error(f"更新任务状态失败: {exc}")
        finally:
            db.close()

    async def _update_task_progress(
        self,
        task_id: int,
        progress: int,
        message: Optional[str] = None,
    ) -> None:
        # 保留接口，实际进度可由 TaskStreamService 统一处理。
        _ = task_id, progress, message
        return None
