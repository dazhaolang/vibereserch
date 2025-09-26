"""
共享文献管理服务
实现去重存储和智能文献处理
"""

import hashlib
import os
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from loguru import logger

from app.models.shared_literature import (
    SharedLiterature, 
    UserLiteratureReference,
    SharedLiteratureSegment,
    LiteratureProcessingTask
)
from app.services.research_rabbit_client import ResearchRabbitClient
from app.services.pdf_processor import PDFProcessor
from app.core.database import get_db


class SharedLiteratureService:
    """共享文献管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.pdf_processor = PDFProcessor()
    
    def create_content_hash(self, content: bytes) -> str:
        """创建内容哈希用于去重"""
        return hashlib.sha256(content).hexdigest()
    
    def create_title_hash(self, title: str) -> str:
        """创建标题哈希用于去重"""
        # 清理标题，移除特殊字符和多余空格
        clean_title = ''.join(c.lower() for c in title if c.isalnum() or c.isspace())
        clean_title = ' '.join(clean_title.split())
        return hashlib.md5(clean_title.encode()).hexdigest()
    
    async def find_existing_literature(
        self, 
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
        title: Optional[str] = None,
        content_hash: Optional[str] = None
    ) -> Optional[SharedLiterature]:
        """查找是否已存在相同文献"""
        
        # 优先级：DOI > ArXiv ID > 内容哈希 > 标题哈希
        if doi:
            existing = self.db.query(SharedLiterature).filter(
                SharedLiterature.doi == doi
            ).first()
            if existing:
                logger.info(f"通过DOI找到已存在文献: {doi}")
                return existing
        
        if arxiv_id:
            existing = self.db.query(SharedLiterature).filter(
                SharedLiterature.arxiv_id == arxiv_id
            ).first()
            if existing:
                logger.info(f"通过ArXiv ID找到已存在文献: {arxiv_id}")
                return existing
        
        if content_hash:
            existing = self.db.query(SharedLiterature).filter(
                SharedLiterature.content_hash == content_hash
            ).first()
            if existing:
                logger.info(f"通过内容哈希找到已存在文献: {content_hash}")
                return existing
        
        if title:
            title_hash = self.create_title_hash(title)
            existing = self.db.query(SharedLiterature).filter(
                SharedLiterature.title_hash == title_hash
            ).first()
            if existing:
                logger.info(f"通过标题哈希找到已存在文献: {title}")
                return existing
        
        return None
    
    async def add_literature_from_search(
        self, 
        user_id: int,
        project_id: int,
        paper_data: Dict
    ) -> Tuple[UserLiteratureReference, bool]:
        """从搜索结果添加文献到用户库"""
        
        # 提取文献标识信息
        doi = paper_data.get("doi") or paper_data.get("externalIds", {}).get("DOI")
        arxiv_id = paper_data.get("externalIds", {}).get("ArXiv")
        title = paper_data.get("title", "")
        
        # 查找是否已存在
        existing_lit = await self.find_existing_literature(
            doi=doi,
            arxiv_id=arxiv_id,
            title=title
        )
        
        is_new_literature = False
        
        if existing_lit:
            logger.info(f"文献已存在，复用: {existing_lit.title[:50]}...")
            shared_literature = existing_lit
            
            # 更新使用统计
            shared_literature.reference_count += 1
            
        else:
            logger.info(f"创建新的共享文献: {title[:50]}...")
            is_new_literature = True
            
            # 创建新的共享文献记录
            shared_literature = SharedLiterature(
                doi=doi,
                arxiv_id=arxiv_id,
                title=title,
                title_hash=self.create_title_hash(title) if title else None,
                authors=[author.get("name", "") for author in paper_data.get("authors", [])],
                abstract=paper_data.get("abstract", ""),
                journal=paper_data.get("venue", {}).get("name", ""),
                publication_year=paper_data.get("year"),
                source_platform="semantic_scholar",
                source_url=paper_data.get("url", ""),
                citation_count=paper_data.get("citationCount", 0),
                quality_score=80.0,  # Research Rabbit的文献质量较高
                reference_count=1,
                processing_status="pending"
            )
            
            self.db.add(shared_literature)
            self.db.flush()  # 获取ID
            
            # 创建处理任务
            await self._create_processing_task(shared_literature.id)
        
        # 检查用户是否已引用该文献
        existing_ref = self.db.query(UserLiteratureReference).filter(
            and_(
                UserLiteratureReference.user_id == user_id,
                UserLiteratureReference.shared_literature_id == shared_literature.id
            )
        ).first()
        
        if existing_ref:
            logger.info("用户已引用该文献，更新访问时间")
            existing_ref.last_accessed = datetime.utcnow()
            user_reference = existing_ref
        else:
            # 创建用户引用
            user_reference = UserLiteratureReference(
                user_id=user_id,
                shared_literature_id=shared_literature.id,
                reading_status="unread",
                importance_score=0.5,
                added_at=datetime.utcnow(),
                last_accessed=datetime.utcnow()
            )
            self.db.add(user_reference)
            self.db.flush()
        
        # 关联到项目（如果还未关联）
        # 这里需要用新的项目关联逻辑
        
        self.db.commit()
        return user_reference, is_new_literature
    
    async def add_literature_from_upload(
        self,
        user_id: int,
        project_id: int,
        file_content: bytes,
        filename: str,
        metadata: Dict
    ) -> Tuple[UserLiteratureReference, bool]:
        """从上传文件添加文献"""
        
        # 计算内容哈希
        content_hash = self.create_content_hash(file_content)
        
        # 提取文献信息
        title = metadata.get("title", filename)
        doi = metadata.get("doi")
        
        # 查找是否已存在
        existing_lit = await self.find_existing_literature(
            doi=doi,
            title=title,
            content_hash=content_hash
        )
        
        is_new_literature = False
        
        if existing_lit:
            logger.info(f"上传文献已存在，复用: {existing_lit.title[:50]}...")
            shared_literature = existing_lit
            shared_literature.reference_count += 1
        else:
            logger.info(f"创建新的上传文献: {title[:50]}...")
            is_new_literature = True
            
            # 保存PDF文件
            pdf_path = await self._save_pdf_file(file_content, content_hash)
            
            # 创建共享文献记录
            shared_literature = SharedLiterature(
                title=title,
                title_hash=self.create_title_hash(title),
                content_hash=content_hash,
                doi=doi,
                authors=metadata.get("authors", []),
                abstract=metadata.get("abstract", ""),
                source_platform="upload",
                pdf_path=pdf_path,
                is_downloaded=True,
                quality_score=75.0,
                reference_count=1,
                processing_status="ready_for_processing"
            )
            
            self.db.add(shared_literature)
            self.db.flush()
            
            # 创建处理任务
            await self._create_processing_task(shared_literature.id, task_type="process")
        
        # 创建用户引用
        user_reference = await self._create_user_reference(user_id, shared_literature.id)
        
        self.db.commit()
        return user_reference, is_new_literature
    
    async def _create_processing_task(
        self, 
        shared_literature_id: int, 
        task_type: str = "both",
        priority: int = 5
    ):
        """创建文献处理任务"""
        
        # 检查是否已有处理任务
        existing_task = self.db.query(LiteratureProcessingTask).filter(
            and_(
                LiteratureProcessingTask.shared_literature_id == shared_literature_id,
                LiteratureProcessingTask.status.in_(["pending", "running"])
            )
        ).first()
        
        if existing_task:
            logger.info(f"文献 {shared_literature_id} 已有处理任务")
            return existing_task
        
        # 创建新任务
        task = LiteratureProcessingTask(
            shared_literature_id=shared_literature_id,
            task_type=task_type,
            priority=priority,
            status="pending"
        )
        
        self.db.add(task)
        logger.info(f"创建文献处理任务: {shared_literature_id}, 类型: {task_type}")
        return task
    
    async def process_literature_queue(self, batch_size: int = 5):
        """处理文献队列"""
        
        # 获取待处理任务
        pending_tasks = self.db.query(LiteratureProcessingTask).filter(
            LiteratureProcessingTask.status == "pending"
        ).order_by(
            LiteratureProcessingTask.priority.desc(),
            LiteratureProcessingTask.created_at.asc()
        ).limit(batch_size).all()
        
        if not pending_tasks:
            logger.info("没有待处理的文献任务")
            return
        
        logger.info(f"开始处理 {len(pending_tasks)} 个文献任务")
        
        # 并发处理任务
        tasks = [self._process_single_literature(task) for task in pending_tasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if r is True)
        logger.info(f"文献处理完成: {success_count}/{len(results)} 成功")
    
    async def _process_single_literature(self, task: LiteratureProcessingTask) -> bool:
        """处理单篇文献"""
        
        try:
            # 更新任务状态
            task.status = "running"
            task.started_at = datetime.utcnow()
            self.db.commit()
            
            shared_lit = self.db.query(SharedLiterature).get(task.shared_literature_id)
            if not shared_lit:
                raise Exception(f"找不到文献 {task.shared_literature_id}")
            
            logger.info(f"处理文献: {shared_lit.title[:50]}...")
            
            # 步骤1: 下载PDF（如果需要）
            if task.task_type in ["both", "download"] and not shared_lit.is_downloaded:
                await self._download_pdf(shared_lit)
            
            # 步骤2: 处理PDF（如果需要）
            if task.task_type in ["both", "process"] and not shared_lit.is_processed:
                await self._process_pdf(shared_lit)
            
            # 更新任务状态
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            
            self.db.commit()
            logger.info(f"文献处理完成: {shared_lit.title[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"文献处理失败: {e}")
            
            # 更新任务状态
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            
            self.db.commit()
            return False
    
    async def _download_pdf(self, shared_lit: SharedLiterature):
        """下载PDF文件"""
        
        if not shared_lit.source_url:
            raise Exception("没有PDF下载链接")
        
        # 尝试通过Research Rabbit获取PDF
        async with ResearchRabbitClient() as client:
            if shared_lit.doi:
                pdf_info = await client.get_pdf_info(shared_lit.doi)
                if pdf_info and pdf_info.get("url_for_pdf"):
                    pdf_content = await client.download_pdf(pdf_info["url_for_pdf"])
                    if pdf_content:
                        # 计算并验证内容哈希
                        content_hash = self.create_content_hash(pdf_content)
                        
                        # 保存文件
                        pdf_path = await self._save_pdf_file(pdf_content, content_hash)
                        
                        # 更新记录
                        shared_lit.pdf_path = pdf_path
                        shared_lit.content_hash = content_hash
                        shared_lit.is_downloaded = True
                        shared_lit.download_count += 1
                        
                        logger.info(f"PDF下载成功: {len(pdf_content)} bytes")
                        return
        
        raise Exception("PDF下载失败")
    
    async def _process_pdf(self, shared_lit: SharedLiterature):
        """处理PDF文件提取内容"""
        
        if not shared_lit.pdf_path or not os.path.exists(shared_lit.pdf_path):
            raise Exception("PDF文件不存在")
        
        logger.info(f"开始处理PDF: {shared_lit.pdf_path}")
        
        # 使用MinerU处理PDF
        result = await self.pdf_processor.process_pdf(shared_lit.pdf_path)
        
        if not result.get("success"):
            raise Exception(f"PDF处理失败: {result.get('error')}")
        
        content = result.get("content", {})
        
        # 提取并保存主要内容
        title = content.get("title") or shared_lit.title
        abstract = content.get("abstract", "")
        text_content = content.get("text_content", "")
        
        # 创建Markdown内容
        markdown_content = self._create_markdown_content(title, abstract, text_content, content)
        
        # 更新共享文献记录
        shared_lit.markdown_content = markdown_content
        shared_lit.structured_data = {
            "title": title,
            "abstract": abstract,
            "text_content": text_content,
            "images": content.get("images", []),
            "tables": content.get("tables", []),
            "sections": content.get("sections", [])
        }
        shared_lit.processing_metadata = {
            "processor": "mineru",
            "version": "1.3.12",
            "processed_at": datetime.utcnow().isoformat(),
            "text_length": len(text_content),
            "image_count": len(content.get("images", [])),
            "table_count": len(content.get("tables", []))
        }
        shared_lit.is_processed = True
        shared_lit.processing_status = "completed"
        shared_lit.last_processed_at = datetime.utcnow()
        
        # 创建段落记录
        await self._create_literature_segments(shared_lit.id, content)
        
        logger.info(f"PDF处理完成，文本长度: {len(text_content)}")
    
    def _create_markdown_content(self, title: str, abstract: str, text_content: str, content: Dict) -> str:
        """创建Markdown格式的内容"""
        
        markdown_parts = []
        
        # 标题
        if title:
            markdown_parts.append(f"# {title}\n")
        
        # 摘要
        if abstract:
            markdown_parts.append(f"## Abstract\n\n{abstract}\n")
        
        # 主要内容
        if text_content:
            markdown_parts.append(f"## Content\n\n{text_content}\n")
        
        # 图片信息
        images = content.get("images", [])
        if images:
            markdown_parts.append("## Images\n")
            for i, img in enumerate(images, 1):
                markdown_parts.append(f"![Image {i}]({img.get('path', '')})\n")
        
        # 表格信息
        tables = content.get("tables", [])
        if tables:
            markdown_parts.append("## Tables\n")
            for i, table in enumerate(tables, 1):
                markdown_parts.append(f"### Table {i}\n\n{table.get('content', '')}\n")
        
        return "\n".join(markdown_parts)
    
    async def _create_literature_segments(self, shared_lit_id: int, content: Dict):
        """创建文献段落记录"""
        
        sections = content.get("sections", [])
        if not sections:
            # 如果没有章节信息，创建一个主要内容段落
            segment = SharedLiteratureSegment(
                shared_literature_id=shared_lit_id,
                segment_type="content",
                section_title="Main Content",
                content=content.get("text_content", ""),
                markdown_content=content.get("text_content", ""),
                extraction_confidence=0.8
            )
            self.db.add(segment)
            return
        
        # 创建各章节段落
        for i, section in enumerate(sections):
            segment = SharedLiteratureSegment(
                shared_literature_id=shared_lit_id,
                segment_type=self._classify_section_type(section.get("title", "")),
                section_title=section.get("title", f"Section {i+1}"),
                content=section.get("content", ""),
                markdown_content=section.get("content", ""),
                page_number=section.get("page"),
                paragraph_index=i,
                section_level=section.get("level", 1),
                extraction_confidence=section.get("confidence", 0.8)
            )
            self.db.add(segment)
    
    def _classify_section_type(self, title: str) -> str:
        """分类章节类型"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ["abstract", "summary"]):
            return "abstract"
        elif any(word in title_lower for word in ["introduction", "intro"]):
            return "introduction"
        elif any(word in title_lower for word in ["method", "methodology", "approach"]):
            return "method"
        elif any(word in title_lower for word in ["result", "finding", "outcome"]):
            return "result"
        elif any(word in title_lower for word in ["conclusion", "summary", "discussion"]):
            return "conclusion"
        elif any(word in title_lower for word in ["related work", "background", "literature review"]):
            return "background"
        else:
            return "content"
    
    async def _save_pdf_file(self, pdf_content: bytes, content_hash: str) -> str:
        """保存PDF文件到共享存储"""
        
        # 使用内容哈希作为文件名，避免重复
        pdf_dir = "/shared_literature_storage/pdfs"
        os.makedirs(pdf_dir, exist_ok=True)
        
        pdf_filename = f"{content_hash}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)
        
        # 如果文件已存在，直接返回路径
        if os.path.exists(pdf_path):
            logger.info(f"PDF文件已存在: {pdf_path}")
            return pdf_path
        
        # 保存新文件
        with open(pdf_path, 'wb') as f:
            f.write(pdf_content)
        
        logger.info(f"PDF文件保存成功: {pdf_path}")
        return pdf_path
    
    async def _create_user_reference(self, user_id: int, shared_literature_id: int) -> UserLiteratureReference:
        """创建用户文献引用"""
        
        # 检查是否已存在
        existing = self.db.query(UserLiteratureReference).filter(
            and_(
                UserLiteratureReference.user_id == user_id,
                UserLiteratureReference.shared_literature_id == shared_literature_id
            )
        ).first()
        
        if existing:
            existing.last_accessed = datetime.utcnow()
            return existing
        
        # 创建新引用
        reference = UserLiteratureReference(
            user_id=user_id,
            shared_literature_id=shared_literature_id,
            reading_status="unread",
            importance_score=0.5,
            added_at=datetime.utcnow(),
            last_accessed=datetime.utcnow()
        )
        
        self.db.add(reference)
        return reference
    
    def get_user_literature_references(
        self, 
        user_id: int, 
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserLiteratureReference]:
        """获取用户的文献引用列表"""
        
        query = self.db.query(UserLiteratureReference).filter(
            UserLiteratureReference.user_id == user_id
        )
        
        if status:
            query = query.filter(UserLiteratureReference.reading_status == status)
        
        if project_id:
            # 这里需要通过项目关联过滤
            pass
        
        return query.order_by(
            UserLiteratureReference.added_at.desc()
        ).offset(offset).limit(limit).all()
    
    def get_processing_statistics(self) -> Dict:
        """获取处理统计信息"""
        
        total_literature = self.db.query(SharedLiterature).count()
        processed_literature = self.db.query(SharedLiterature).filter(
            SharedLiterature.is_processed == True
        ).count()
        
        pending_tasks = self.db.query(LiteratureProcessingTask).filter(
            LiteratureProcessingTask.status == "pending"
        ).count()
        
        running_tasks = self.db.query(LiteratureProcessingTask).filter(
            LiteratureProcessingTask.status == "running"
        ).count()
        
        return {
            "total_literature": total_literature,
            "processed_literature": processed_literature,
            "processing_rate": processed_literature / max(total_literature, 1),
            "pending_tasks": pending_tasks,
            "running_tasks": running_tasks,
            "storage_saved": self._calculate_storage_saved()
        }
    
    def _calculate_storage_saved(self) -> Dict:
        """计算节省的存储空间"""
        
        # 计算引用总数和唯一文献数
        total_references = self.db.query(UserLiteratureReference).count()
        unique_literature = self.db.query(SharedLiterature).count()
        
        if unique_literature == 0:
            return {"saved_files": 0, "saved_processing": 0}
        
        # 估算节省的文件存储
        saved_files = total_references - unique_literature
        
        # 估算节省的处理次数
        saved_processing = total_references - unique_literature
        
        return {
            "saved_files": saved_files,
            "saved_processing": saved_processing,
            "deduplication_rate": saved_files / max(total_references, 1)
        }
