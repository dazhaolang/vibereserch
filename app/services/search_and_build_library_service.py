"""
搜索建库原子化工具 - search_and_build_library
完整的搜索→筛选→下载PDF→转Markdown→清洁优化→结构化处理→入库流水线
支持200-500篇文献的大规模批量处理
"""

import asyncio
import os
import json
import time
import tempfile
import hashlib
from typing import List, Dict, Optional, Any, Tuple, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import aiohttp
import aiofiles
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.models.task import Task
from app.services.research_rabbit_client import ResearchRabbitClient
from app.services.pdf_processor import PDFProcessor
from app.services.lightweight_structuring_service import LightweightStructuringService
from app.services.ai_service import AIService
from app.services.semantic_chunker import create_semantic_chunker


class ProcessingStage(Enum):
    """处理阶段枚举"""
    INITIALIZATION = "initialization"
    SEARCH = "search"
    AI_FILTERING = "ai_filtering"
    PDF_DOWNLOAD = "pdf_download"
    CONTENT_EXTRACTION = "content_extraction"
    STRUCTURE_PROCESSING = "structure_processing"
    DATABASE_INGESTION = "database_ingestion"
    CLEANUP = "cleanup"
    COMPLETED = "completed"


@dataclass
class ProcessingConfig:
    """处理配置"""
    batch_size: int = 10  # 批处理大小
    max_concurrent_downloads: int = 5  # 最大并发下载数
    max_concurrent_ai_calls: int = 3  # 最大并发AI调用数
    enable_ai_filtering: bool = True  # 启用AI筛选
    enable_pdf_processing: bool = True  # 启用PDF处理
    enable_structured_extraction: bool = True  # 启用结构化提取
    quality_threshold: float = 6.0  # 质量阈值
    max_retries: int = 3  # 最大重试次数
    timeout_seconds: int = 300  # 任务超时时间（秒）


@dataclass
class ProcessingStats:
    """处理统计"""
    total_found: int = 0
    ai_filtered: int = 0
    pdf_downloaded: int = 0
    successfully_processed: int = 0
    structure_extracted: int = 0
    database_ingested: int = 0
    errors: int = 0
    duplicates: int = 0
    processing_time: float = 0.0


@dataclass
class LiteratureItem:
    """文献条目"""
    paper_id: str
    raw_data: Dict
    quality_score: float = 0.0
    is_duplicate: bool = False
    ai_filtered: bool = False
    pdf_path: Optional[str] = None
    content_extracted: bool = False
    structured_data: Optional[Dict] = None
    literature_id: Optional[int] = None
    error: Optional[str] = None


class SearchAndBuildLibraryService:
    """搜索建库原子化服务"""

    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.pdf_processor = PDFProcessor()
        self.structuring_service = LightweightStructuringService(db)
        self.semantic_chunker = create_semantic_chunker()

        # 初始化客户端
        self.research_client = None
        self.temp_dir = None

        # 处理统计和状态
        self.stats = ProcessingStats()
        self.processed_items: List[LiteratureItem] = []
        self.progress_callback: Optional[Callable] = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.research_client = ResearchRabbitClient()
        await self.research_client.__aenter__()
        self.temp_dir = tempfile.mkdtemp(prefix="search_build_")
        logger.info(f"初始化搜索建库服务，临时目录: {self.temp_dir}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.research_client:
            await self.research_client.__aexit__(exc_type, exc_val, exc_tb)

        # 清理临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"清理临时目录: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")

    async def execute_full_pipeline(
        self,
        keywords: List[str],
        project: Project,
        config: ProcessingConfig,
        progress_callback: Optional[Callable[[str, int, Dict], None]] = None
    ) -> Dict[str, Any]:
        """
        执行完整的搜索建库流水线

        Args:
            keywords: 搜索关键词列表
            project: 项目对象
            config: 处理配置
            progress_callback: 进度回调函数

        Returns:
            处理结果字典
        """
        self.progress_callback = progress_callback
        start_time = time.time()

        try:
            logger.info(f"开始搜索建库流水线: {keywords}, 项目ID: {project.id}")
            await self._update_progress("初始化搜索建库流水线", 0)

            # 1. 搜索阶段
            await self._update_progress("搜索文献", 5)
            search_results = await self._execute_search_stage(keywords, config)

            # 2. AI筛选阶段
            if config.enable_ai_filtering and search_results:
                await self._update_progress("AI智能筛选", 15)
                filtered_results = await self._execute_ai_filtering_stage(
                    search_results, project, config
                )
            else:
                filtered_results = search_results

            # 3. 去重和质量评估
            await self._update_progress("去重和质量评估", 25)
            unique_results = await self._execute_deduplication_stage(
                filtered_results, project, config
            )

            # 4. PDF下载阶段
            if config.enable_pdf_processing:
                await self._update_progress("批量下载PDF", 35)
                download_results = await self._execute_pdf_download_stage(
                    unique_results, config
                )
            else:
                download_results = unique_results

            # 5. 内容提取阶段
            await self._update_progress("提取文献内容", 50)
            extraction_results = await self._execute_content_extraction_stage(
                download_results, config
            )

            # 6. 结构化处理阶段
            if config.enable_structured_extraction:
                await self._update_progress("结构化数据处理", 70)
                structured_results = await self._execute_structure_processing_stage(
                    extraction_results, project, config
                )
            else:
                structured_results = extraction_results

            # 7. 数据库入库阶段
            await self._update_progress("数据库入库", 85)
            ingestion_results = await self._execute_database_ingestion_stage(
                structured_results, project, config
            )

            # 8. 清理和完成
            await self._update_progress("清理临时文件", 95)
            await self._execute_cleanup_stage()

            # 计算最终统计
            self.stats.processing_time = time.time() - start_time

            await self._update_progress("搜索建库完成", 100, {
                "stats": {
                    "total_found": self.stats.total_found,
                    "successfully_processed": self.stats.successfully_processed,
                    "database_ingested": self.stats.database_ingested,
                    "processing_time": round(self.stats.processing_time, 2)
                }
            })

            return {
                "success": True,
                "stats": self.stats.__dict__,
                "processed_items": len(ingestion_results),
                "processing_time": self.stats.processing_time
            }

        except Exception as e:
            logger.error(f"搜索建库流水线失败: {e}")
            await self._update_progress(f"处理失败: {str(e)}", -1)
            return {
                "success": False,
                "error": str(e),
                "stats": self.stats.__dict__,
                "processing_time": time.time() - start_time
            }

    async def _execute_search_stage(
        self,
        keywords: List[str],
        config: ProcessingConfig
    ) -> List[LiteratureItem]:
        """执行搜索阶段"""
        try:
            query = " ".join(keywords)
            papers = await self.research_client.search_all_papers(
                query, max_count=500  # 搜索更多结果用于筛选
            )

            self.stats.total_found = len(papers)
            logger.info(f"搜索阶段完成，找到 {len(papers)} 篇文献")

            # 转换为LiteratureItem对象
            literature_items = []
            for paper in papers:
                item = LiteratureItem(
                    paper_id=paper.get("paperId", ""),
                    raw_data=paper,
                    quality_score=self._calculate_basic_quality_score(paper)
                )
                literature_items.append(item)

            return literature_items

        except Exception as e:
            logger.error(f"搜索阶段失败: {e}")
            raise

    async def _execute_ai_filtering_stage(
        self,
        items: List[LiteratureItem],
        project: Project,
        config: ProcessingConfig
    ) -> List[LiteratureItem]:
        """执行AI筛选阶段"""
        try:
            # 构建筛选提示词
            filter_prompt = self._build_ai_filter_prompt(project)

            # 分批并行AI筛选
            filtered_items = []
            semaphore = asyncio.Semaphore(config.max_concurrent_ai_calls)

            async def filter_single_item(item: LiteratureItem) -> LiteratureItem:
                async with semaphore:
                    try:
                        relevance_score = await self._evaluate_relevance_with_ai(
                            item, filter_prompt
                        )
                        item.ai_filtered = relevance_score >= config.quality_threshold
                        if item.ai_filtered:
                            item.quality_score = max(item.quality_score, relevance_score)
                        return item
                    except Exception as e:
                        logger.warning(f"AI筛选失败 {item.paper_id}: {e}")
                        item.error = str(e)
                        return item

            # 执行并行筛选
            tasks = [filter_single_item(item) for item in items]
            filtered_items = await asyncio.gather(*tasks, return_exceptions=True)

            # 过滤成功的项目
            valid_items = [
                item for item in filtered_items
                if isinstance(item, LiteratureItem) and item.ai_filtered
            ]

            self.stats.ai_filtered = len(valid_items)
            logger.info(f"AI筛选阶段完成，筛选出 {len(valid_items)} 篇高质量文献")

            return valid_items

        except Exception as e:
            logger.error(f"AI筛选阶段失败: {e}")
            return items  # 失败时返回原始项目

    async def _execute_deduplication_stage(
        self,
        items: List[LiteratureItem],
        project: Project,
        config: ProcessingConfig
    ) -> List[LiteratureItem]:
        """执行去重和质量评估阶段"""
        try:
            unique_items = []
            duplicate_count = 0

            for item in items:
                # 检查数据库中是否已存在
                existing = await self._check_literature_exists(item, project)
                if existing:
                    item.is_duplicate = True
                    duplicate_count += 1
                    continue

                # 检查当前批次中的重复
                is_batch_duplicate = False
                for existing_item in unique_items:
                    if self._is_duplicate_item(item, existing_item):
                        is_batch_duplicate = True
                        break

                if not is_batch_duplicate:
                    unique_items.append(item)

            self.stats.duplicates = duplicate_count
            logger.info(f"去重阶段完成，剩余 {len(unique_items)} 篇唯一文献")

            return unique_items

        except Exception as e:
            logger.error(f"去重阶段失败: {e}")
            raise

    async def _execute_pdf_download_stage(
        self,
        items: List[LiteratureItem],
        config: ProcessingConfig
    ) -> List[LiteratureItem]:
        """执行PDF下载阶段"""
        try:
            semaphore = asyncio.Semaphore(config.max_concurrent_downloads)
            download_success = 0

            async def download_single_pdf(item: LiteratureItem) -> LiteratureItem:
                async with semaphore:
                    try:
                        doi = item.raw_data.get("externalIds", {}).get("DOI")
                        if not doi:
                            return item

                        # 获取PDF下载链接
                        pdf_info = await self.research_client.get_pdf_info(doi)
                        if not pdf_info or not pdf_info.get("url_for_pdf"):
                            return item

                        # 下载PDF
                        pdf_data = await self.research_client.download_pdf(
                            pdf_info["url_for_pdf"]
                        )
                        if not pdf_data:
                            return item

                        # 保存PDF文件
                        pdf_filename = self._generate_safe_filename(
                            item.paper_id, ".pdf"
                        )
                        pdf_path = os.path.join(self.temp_dir, pdf_filename)

                        async with aiofiles.open(pdf_path, "wb") as f:
                            await f.write(pdf_data)

                        item.pdf_path = pdf_path
                        return item

                    except Exception as e:
                        logger.warning(f"PDF下载失败 {item.paper_id}: {e}")
                        item.error = str(e)
                        return item

            # 执行并行下载
            tasks = [download_single_pdf(item) for item in items]
            download_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 统计下载成功数量
            for item in download_results:
                if isinstance(item, LiteratureItem) and item.pdf_path:
                    download_success += 1

            self.stats.pdf_downloaded = download_success
            logger.info(f"PDF下载阶段完成，成功下载 {download_success} 个PDF")

            return [item for item in download_results if isinstance(item, LiteratureItem)]

        except Exception as e:
            logger.error(f"PDF下载阶段失败: {e}")
            raise

    async def _execute_content_extraction_stage(
        self,
        items: List[LiteratureItem],
        config: ProcessingConfig
    ) -> List[LiteratureItem]:
        """执行内容提取阶段"""
        try:
            extraction_success = 0

            for item in items:
                try:
                    # 提取内容
                    content = await self._extract_item_content(item)
                    if content:
                        item.content_extracted = True
                        extraction_success += 1
                except Exception as e:
                    logger.warning(f"内容提取失败 {item.paper_id}: {e}")
                    item.error = str(e)

            self.stats.successfully_processed = extraction_success
            logger.info(f"内容提取阶段完成，成功提取 {extraction_success} 篇文献内容")

            return items

        except Exception as e:
            logger.error(f"内容提取阶段失败: {e}")
            raise

    async def _execute_structure_processing_stage(
        self,
        items: List[LiteratureItem],
        project: Project,
        config: ProcessingConfig
    ) -> List[LiteratureItem]:
        """执行结构化处理阶段"""
        try:
            # 确保项目有结构化模板
            if not project.structure_template:
                sample_literature = [
                    Literature(
                        title=item.raw_data.get("title", ""),
                        abstract=item.raw_data.get("abstract", ""),
                        authors=self._extract_authors(item.raw_data.get("authors", []))
                    )
                    for item in items[:5] if item.content_extracted
                ]

                if sample_literature:
                    template_result = await self.structuring_service.auto_generate_structure_template(
                        project, sample_literature
                    )
                    if template_result["success"]:
                        project.structure_template = template_result["template"]
                        self.db.commit()

            # 执行结构化处理
            structure_success = 0
            for item in items:
                try:
                    if item.content_extracted:
                        structured_data = await self._extract_structured_data(
                            item, project
                        )
                        if structured_data:
                            item.structured_data = structured_data
                            structure_success += 1
                except Exception as e:
                    logger.warning(f"结构化处理失败 {item.paper_id}: {e}")
                    item.error = str(e)

            self.stats.structure_extracted = structure_success
            logger.info(f"结构化处理阶段完成，成功处理 {structure_success} 篇文献")

            return items

        except Exception as e:
            logger.error(f"结构化处理阶段失败: {e}")
            raise

    async def _execute_database_ingestion_stage(
        self,
        items: List[LiteratureItem],
        project: Project,
        config: ProcessingConfig
    ) -> List[LiteratureItem]:
        """执行数据库入库阶段"""
        try:
            ingestion_success = 0
            batch_size = config.batch_size

            # 分批入库以避免数据库锁定
            for i in range(0, len(items), batch_size):
                batch_items = items[i:i+batch_size]

                try:
                    self.db.begin()

                    for item in batch_items:
                        try:
                            literature_id = await self._save_literature_to_database(
                                item, project
                            )
                            if literature_id:
                                item.literature_id = literature_id
                                ingestion_success += 1
                        except Exception as e:
                            logger.warning(f"保存文献失败 {item.paper_id}: {e}")
                            item.error = str(e)

                    self.db.commit()

                except SQLAlchemyError as e:
                    self.db.rollback()
                    logger.error(f"数据库批次提交失败: {e}")
                    for item in batch_items:
                        item.error = f"数据库错误: {str(e)}"

            self.stats.database_ingested = ingestion_success
            logger.info(f"数据库入库阶段完成，成功入库 {ingestion_success} 篇文献")

            return items

        except Exception as e:
            logger.error(f"数据库入库阶段失败: {e}")
            raise

    async def _execute_cleanup_stage(self):
        """执行清理阶段"""
        try:
            # 清理临时PDF文件
            if self.temp_dir and os.path.exists(self.temp_dir):
                temp_files = os.listdir(self.temp_dir)
                for temp_file in temp_files:
                    try:
                        os.remove(os.path.join(self.temp_dir, temp_file))
                    except Exception as e:
                        logger.warning(f"清理临时文件失败 {temp_file}: {e}")

            logger.info("清理阶段完成")

        except Exception as e:
            logger.warning(f"清理阶段失败: {e}")

    async def _evaluate_relevance_with_ai(
        self,
        item: LiteratureItem,
        filter_prompt: str
    ) -> float:
        """使用AI评估文献相关性"""
        try:
            title = item.raw_data.get("title", "")
            abstract = item.raw_data.get("abstract", "")

            evaluation_prompt = f"""
{filter_prompt}

请评估以下论文的相关性（1-10分）：

标题: {title}
摘要: {abstract[:500]}...

只返回数字分数。
"""

            response = await self.ai_service.generate_completion(
                evaluation_prompt,
                model="gpt-3.5-turbo",
                max_tokens=10,
                temperature=0.1
            )

            if response.get("success"):
                try:
                    score = float(response["content"].strip())
                    return min(10.0, max(1.0, score))
                except ValueError:
                    return 5.0  # 默认中等分数

            return 5.0

        except Exception as e:
            logger.warning(f"AI相关性评估失败: {e}")
            return 5.0

    async def _extract_item_content(self, item: LiteratureItem) -> Optional[str]:
        """提取文献项目内容"""
        try:
            content_parts = []

            # 添加标题和摘要
            title = item.raw_data.get("title", "")
            if title:
                content_parts.append(f"标题: {title}")

            abstract = item.raw_data.get("abstract", "")
            if abstract:
                content_parts.append(f"摘要: {abstract}")

            # 如果有PDF文件，提取PDF内容
            if item.pdf_path and os.path.exists(item.pdf_path):
                try:
                    pdf_result = await self.pdf_processor.process_pdf(item.pdf_path)
                    if pdf_result.get("success"):
                        pdf_content = pdf_result["content"].get("text_content", "")
                        if pdf_content:
                            content_parts.append(f"PDF内容:\n{pdf_content}")
                except Exception as e:
                    logger.warning(f"PDF处理失败 {item.paper_id}: {e}")

            return "\n\n".join(content_parts) if content_parts else None

        except Exception as e:
            logger.error(f"内容提取失败 {item.paper_id}: {e}")
            return None

    async def _extract_structured_data(
        self,
        item: LiteratureItem,
        project: Project
    ) -> Optional[Dict]:
        """提取结构化数据"""
        try:
            if not project.structure_template or not project.extraction_prompts:
                return None

            content = await self._extract_item_content(item)
            if not content:
                return None

            # 使用轻结构化服务提取
            structured_data = {}
            template = project.structure_template
            prompts = project.extraction_prompts

            for section_name, section_structure in template.get("structure", {}).items():
                section_data = {}

                for subsection_name, subsection_fields in section_structure.items():
                    prompt_key = f"{section_name}_{subsection_name}"
                    extraction_prompt = prompts.get(prompt_key, "")

                    if extraction_prompt:
                        extracted_content = await self._extract_with_ai(
                            content, extraction_prompt, subsection_fields
                        )

                        if extracted_content:
                            section_data[subsection_name] = extracted_content

                if section_data:
                    structured_data[section_name] = section_data

            return structured_data if structured_data else None

        except Exception as e:
            logger.error(f"结构化数据提取失败 {item.paper_id}: {e}")
            return None

    async def _extract_with_ai(
        self,
        content: str,
        extraction_prompt: str,
        fields: List[str]
    ) -> Optional[Dict]:
        """使用AI提取特定内容"""
        try:
            full_prompt = f"""
{extraction_prompt}

请从以下文献内容中提取相关信息，以JSON格式返回：

目标字段: {', '.join(fields)}

文献内容:
{content[:4000]}...

要求：
1. 以总结式话术呈现核心信息，避免直接复制原文
2. 如果某个字段没有相关信息，设为null
3. 返回格式：{{"字段名": "总结内容", ...}}
4. 确保内容简洁且包含关键信息
"""

            response = await self.ai_service.generate_completion(
                full_prompt,
                model="gpt-3.5-turbo",
                max_tokens=800,
                temperature=0.2
            )

            if response.get("success"):
                try:
                    extracted_data = json.loads(response["content"])
                    return extracted_data
                except json.JSONDecodeError:
                    return {"summary": response["content"][:500]}

            return None

        except Exception as e:
            logger.error(f"AI提取失败: {e}")
            return None

    async def _save_literature_to_database(
        self,
        item: LiteratureItem,
        project: Project
    ) -> Optional[int]:
        """保存文献到数据库"""
        try:
            # 创建Literature对象
            external_ids = item.raw_data.get("externalIds", {})

            literature = Literature(
                title=item.raw_data.get("title", ""),
                authors=self._extract_authors(item.raw_data.get("authors", [])),
                abstract=item.raw_data.get("abstract"),
                journal=item.raw_data.get("venue"),
                publication_year=item.raw_data.get("year"),
                doi=external_ids.get("DOI"),
                external_ids=external_ids,
                citation_count=item.raw_data.get("citationCount", 0),
                reference_count=item.raw_data.get("referenceCount", 0),
                is_open_access=item.raw_data.get("isOpenAccess", False),
                fields_of_study=item.raw_data.get("fieldsOfStudy") or [],
                quality_score=item.quality_score,
                source="search_and_build_library",
                raw_data=item.raw_data,
                is_parsed=bool(item.content_extracted),
                parsing_status="completed" if item.content_extracted else "pending",
                pdf_path=item.pdf_path
            )

            self.db.add(literature)
            self.db.flush()  # 获取ID

            # 关联到项目
            if literature not in project.literature:
                project.literature.append(literature)

            # 保存结构化段落
            if item.structured_data:
                await self._save_structured_segments(
                    literature.id, item.structured_data, project
                )

            return literature.id

        except Exception as e:
            logger.error(f"保存文献到数据库失败 {item.paper_id}: {e}")
            return None

    async def _save_structured_segments(
        self,
        literature_id: int,
        structured_data: Dict,
        project: Project
    ):
        """保存结构化段落"""
        try:
            for section_name, section_data in structured_data.items():
                for subsection_name, subsection_content in section_data.items():
                    segment = LiteratureSegment(
                        literature_id=literature_id,
                        segment_type=f"{section_name}_{subsection_name}",
                        content=json.dumps(subsection_content, ensure_ascii=False),
                        structured_data=subsection_content,
                        extraction_method="ai_structured",
                        extraction_confidence=0.8
                    )
                    self.db.add(segment)
        except Exception as e:
            logger.error(f"保存结构化段落失败: {e}")

    # 辅助方法

    def _calculate_basic_quality_score(self, paper: Dict) -> float:
        """计算基础质量评分"""
        score = 5.0

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

        # 发表年份加分
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

    def _build_ai_filter_prompt(self, project: Project) -> str:
        """构建AI筛选提示词"""
        keywords = project.keywords or []
        research_direction = project.research_direction or "通用科研"

        return f"""
你是一个专业的学术文献评估专家。请评估论文与研究项目的相关性。

研究方向: {research_direction}
关键词: {', '.join(keywords)}

评估标准：
1. 标题和摘要与研究方向的匹配度
2. 关键词的覆盖程度
3. 研究方法的相关性
4. 潜在的学术价值

请给出1-10分的相关性评分。
"""

    async def _check_literature_exists(
        self,
        item: LiteratureItem,
        project: Project
    ) -> bool:
        """检查文献是否已存在"""
        try:
            doi = item.raw_data.get("externalIds", {}).get("DOI")
            title = item.raw_data.get("title", "")

            existing = None
            if doi:
                existing = self.db.query(Literature).filter(Literature.doi == doi).first()
            if not existing and title:
                existing = self.db.query(Literature).filter(Literature.title == title).first()

            return existing is not None

        except Exception as e:
            logger.warning(f"检查文献重复失败: {e}")
            return False

    def _is_duplicate_item(
        self,
        item1: LiteratureItem,
        item2: LiteratureItem
    ) -> bool:
        """检查两个项目是否重复"""
        # DOI匹配
        doi1 = item1.raw_data.get("externalIds", {}).get("DOI")
        doi2 = item2.raw_data.get("externalIds", {}).get("DOI")
        if doi1 and doi2 and doi1 == doi2:
            return True

        # 标题匹配
        title1 = item1.raw_data.get("title", "").strip().lower()
        title2 = item2.raw_data.get("title", "").strip().lower()
        if title1 and title2 and title1 == title2:
            return True

        return False

    def _generate_safe_filename(self, identifier: str, extension: str) -> str:
        """生成安全的文件名"""
        hash_obj = hashlib.md5(identifier.encode('utf-8'))
        filename = hash_obj.hexdigest()
        return f"{filename}{extension}"

    def _extract_authors(self, authors_data: List[Dict]) -> List[str]:
        """提取作者信息"""
        authors = []
        for author in authors_data[:10]:
            name = author.get("name", "").strip()
            if name:
                authors.append(name)
        return authors

    async def _update_progress(self, step: str, progress: int, details: Dict = None):
        """更新进度"""
        if self.progress_callback:
            try:
                await self.progress_callback(step, progress, details or {})
            except Exception as e:
                logger.warning(f"进度回调失败: {e}")


# 工厂函数

def create_search_and_build_library_service(db: Session) -> SearchAndBuildLibraryService:
    """创建搜索建库服务实例"""
    return SearchAndBuildLibraryService(db)


# 便捷接口函数

async def execute_search_and_build_pipeline(
    keywords: List[str],
    project_id: int,
    user_id: int,
    config: Optional[ProcessingConfig] = None,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    执行搜索建库流水线的便捷接口

    Args:
        keywords: 搜索关键词
        project_id: 项目ID
        user_id: 用户ID
        config: 处理配置
        progress_callback: 进度回调

    Returns:
        处理结果
    """
    db = SessionLocal()

    try:
        # 获取项目
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == user_id
        ).first()

        if not project:
            raise ValueError(f"项目不存在或无权访问: {project_id}")

        # 使用默认配置
        if config is None:
            config = ProcessingConfig()

        # 执行流水线
        async with create_search_and_build_library_service(db) as service:
            result = await service.execute_full_pipeline(
                keywords=keywords,
                project=project,
                config=config,
                progress_callback=progress_callback
            )

        return result

    finally:
        db.close()