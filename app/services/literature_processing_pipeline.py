"""
高性能文献处理管道 - 支持多种PDF处理方式和并发架构
"""

import asyncio
import time
import hashlib
from typing import List, Dict, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import aiofiles
import aiohttp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import PyPDF2
import pdfplumber
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.shared_literature import SharedLiterature, LiteratureProcessingTask
from app.services.research_rabbit_client import ResearchRabbitClient
from app.services.pdf_processor import PDFProcessor
from app.core.config import settings

class ProcessingMethod(Enum):
    """PDF处理方式"""
    FAST_BASIC = "fast_basic"           # 快速基础解析 (PyPDF2) - 1-2秒
    STANDARD = "standard"               # 标准解析 (pdfplumber) - 3-5秒  
    PREMIUM_MINERU = "premium_mineru"   # 高质量解析 (MinerU) - 30-60秒
    
class ProcessingStatus(Enum):
    """处理状态"""
    PENDING = "pending"
    SEARCHING = "searching" 
    DOWNLOADING = "downloading"
    PROCESSING_FAST = "processing_fast"
    PROCESSING_STANDARD = "processing_standard"
    PROCESSING_PREMIUM = "processing_premium"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ProcessingTask:
    """处理任务"""
    task_id: str
    paper_id: str
    title: str
    pdf_url: str
    doi: Optional[str] = None
    method: ProcessingMethod
    priority: int = 5
    created_at: float = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

class LiteratureProcessingPipeline:
    """高性能文献处理管道"""
    
    def __init__(self):
        self.research_rabbit = ResearchRabbitClient()
        self.pdf_processor = PDFProcessor()
        
        # 并发控制
        self.max_concurrent_downloads = 10
        self.max_concurrent_processing = 5
        self.download_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
        self.processing_semaphore = asyncio.Semaphore(self.max_concurrent_processing)
        
        # 任务队列
        self.download_queue = asyncio.Queue()
        self.processing_queue = asyncio.Queue()
        
        # 线程池执行器
        self.thread_executor = ThreadPoolExecutor(max_workers=8)
        self.process_executor = ProcessPoolExecutor(max_workers=4)
        
        # 状态跟踪
        self.task_status: Dict[str, ProcessingStatus] = {}
        self.task_results: Dict[str, Dict] = {}
        self.task_progress: Dict[str, float] = {}
        
        # 启动工作线程
        self._start_workers()
    
    def _start_workers(self):
        """启动后台工作线程"""
        # 下载工作线程
        for i in range(3):
            asyncio.create_task(self._download_worker(f"downloader-{i}"))
        
        # 处理工作线程  
        for i in range(2):
            asyncio.create_task(self._processing_worker(f"processor-{i}"))
    
    async def batch_search_and_process(
        self, 
        query: str, 
        max_results: int = 20,
        preferred_method: ProcessingMethod = ProcessingMethod.FAST_BASIC,
        user_choice_callback = None
    ) -> Dict:
        """批量搜索和处理文献"""
        
        start_time = time.time()
        
        # 1. 并发搜索
        print(f"🔍 开始搜索: {query}")
        self.task_status["search"] = ProcessingStatus.SEARCHING
        
        papers = await self.research_rabbit.search_all_papers(
            query=query,
            max_count=max_results
        )

        if not papers:
            return {"error": "搜索无结果", "papers": []}

        print(f"✅ 搜索完成，找到 {len(papers)} 篇文献")
        
        # 2. 创建处理任务
        tasks = []
        for i, paper in enumerate(papers):
            external_ids = paper.get("externalIds", {}) if isinstance(paper.get("externalIds"), dict) else {}
            task = ProcessingTask(
                task_id=f"task_{int(time.time())}_{i}",
                paper_id=paper.get("paperId") or paper.get("id", f"paper_{i}"),
                title=paper.get("title", "Unknown"),
                pdf_url=paper.get("pdfUrl") or paper.get("pdf_url", ""),
                doi=external_ids.get("DOI"),
                method=preferred_method,
                priority=5 - (i // 5)  # 前几个优先级高
            )
            tasks.append(task)
            self.task_status[task.task_id] = ProcessingStatus.PENDING
            self.task_progress[task.task_id] = 0.0
        
        # 3. 并发执行所有任务
        print(f"⚡ 开始并发处理 {len(tasks)} 个任务...")
        
        # 创建并发任务组
        processing_tasks = [
            asyncio.create_task(self._process_single_paper(task))
            for task in tasks
        ]
        
        # 如果提供了用户选择回调，启动交互式处理
        if user_choice_callback:
            asyncio.create_task(self._handle_user_choices(tasks, user_choice_callback))
        
        # 等待所有任务完成或超时
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*processing_tasks, return_exceptions=True),
                timeout=300  # 5分钟超时
            )
        except asyncio.TimeoutError:
            print("⚠️ 部分任务超时，返回已完成的结果")
            results = [self.task_results.get(task.task_id, {"error": "timeout"}) for task in tasks]
        
        # 4. 汇总结果
        end_time = time.time()
        total_time = end_time - start_time
        
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_results = [r for r in results if not (isinstance(r, dict) and r.get("success"))]
        
        return {
            "success": True,
            "summary": {
                "total_papers": len(papers),
                "successful": len(successful_results),
                "failed": len(failed_results),
                "total_time": f"{total_time:.2f}s",
                "avg_time_per_paper": f"{total_time/len(papers):.2f}s"
            },
            "results": successful_results,
            "failed": failed_results,
            "processing_methods_used": {
                "fast": len([r for r in successful_results if r.get("method") == "fast_basic"]),
                "standard": len([r for r in successful_results if r.get("method") == "standard"]),
                "premium": len([r for r in successful_results if r.get("method") == "premium_mineru"])
            }
        }
    
    async def _process_single_paper(self, task: ProcessingTask) -> Dict:
        """处理单篇文献"""
        try:
            # 1. 下载PDF
            pdf_url = task.pdf_url
            if not pdf_url and task.doi:
                pdf_info = await self.research_rabbit.get_pdf_info(task.doi)
                if pdf_info:
                    pdf_url = pdf_info.get("url_for_pdf") or pdf_info.get("pdf_url")

            if not pdf_url:
                return {"error": "无可用PDF链接", "task_id": task.task_id, "title": task.title}

            self.task_status[task.task_id] = ProcessingStatus.DOWNLOADING
            self.task_progress[task.task_id] = 0.1
            
            pdf_content = await self._download_pdf_with_retry(pdf_url)
            if not pdf_content:
                return {"error": "PDF下载失败", "task_id": task.task_id}
            
            self.task_progress[task.task_id] = 0.3
            
            # 2. 根据方法选择处理方式
            if task.method == ProcessingMethod.FAST_BASIC:
                result = await self._process_pdf_fast(pdf_content, task)
            elif task.method == ProcessingMethod.STANDARD:
                result = await self._process_pdf_standard(pdf_content, task)
            elif task.method == ProcessingMethod.PREMIUM_MINERU:
                result = await self._process_pdf_premium(pdf_content, task)
            else:
                # 默认快速处理
                result = await self._process_pdf_fast(pdf_content, task)
            
            # 3. 保存结果
            self.task_status[task.task_id] = ProcessingStatus.COMPLETED
            self.task_progress[task.task_id] = 1.0
            self.task_results[task.task_id] = result
            
            return result
            
        except Exception as e:
            error_result = {
                "error": str(e),
                "task_id": task.task_id,
                "title": task.title,
                "success": False
            }
            self.task_status[task.task_id] = ProcessingStatus.FAILED
            self.task_results[task.task_id] = error_result
            return error_result
    
    async def _download_pdf_with_retry(self, pdf_url: str, max_retries: int = 3) -> Optional[bytes]:
        """带重试的PDF下载"""
        async with self.download_semaphore:
            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(pdf_url, timeout=30) as response:
                            if response.status == 200:
                                return await response.read()
                except Exception as e:
                    if attempt == max_retries - 1:
                        print(f"❌ PDF下载失败 (尝试 {attempt + 1}): {e}")
                        return None
                    await asyncio.sleep(2 ** attempt)  # 指数退避
            return None
    
    async def _process_pdf_fast(self, pdf_content: bytes, task: ProcessingTask) -> Dict:
        """快速PDF处理 (PyPDF2) - 1-2秒"""
        self.task_status[task.task_id] = ProcessingStatus.PROCESSING_FAST
        self.task_progress[task.task_id] = 0.5
        
        start_time = time.time()
        
        # 在线程池中运行CPU密集型操作
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.thread_executor,
            self._extract_text_pypdf2,
            pdf_content
        )
        
        processing_time = time.time() - start_time
        
        return {
            "success": True,
            "task_id": task.task_id,
            "title": task.title,
            "method": "fast_basic",
            "processing_time": f"{processing_time:.2f}s",
            "content": result.get("text", ""),
            "metadata": result.get("metadata", {}),
            "quality_score": 60,  # 快速处理质量较低
            "features": ["基础文本提取", "快速处理"]
        }
    
    async def _process_pdf_standard(self, pdf_content: bytes, task: ProcessingTask) -> Dict:
        """标准PDF处理 (pdfplumber) - 3-5秒"""
        self.task_status[task.task_id] = ProcessingStatus.PROCESSING_STANDARD
        self.task_progress[task.task_id] = 0.5
        
        start_time = time.time()
        
        # 在线程池中运行CPU密集型操作
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.thread_executor,
            self._extract_text_pdfplumber,
            pdf_content
        )
        
        processing_time = time.time() - start_time
        
        return {
            "success": True,
            "task_id": task.task_id,
            "title": task.title,
            "method": "standard",
            "processing_time": f"{processing_time:.2f}s",
            "content": result.get("text", ""),
            "metadata": result.get("metadata", {}),
            "tables": result.get("tables", []),
            "quality_score": 80,  # 标准质量
            "features": ["文本提取", "表格识别", "布局保持"]
        }
    
    async def _process_pdf_premium(self, pdf_content: bytes, task: ProcessingTask) -> Dict:
        """高质量PDF处理 (MinerU) - 30-60秒"""
        self.task_status[task.task_id] = ProcessingStatus.PROCESSING_PREMIUM
        self.task_progress[task.task_id] = 0.5
        
        start_time = time.time()
        
        # 保存临时文件
        temp_path = f"/tmp/temp_pdf_{task.task_id}.pdf"
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(pdf_content)
        
        # 使用现有的MinerU处理器
        result = await self.pdf_processor.process_pdf(temp_path)
        
        # 清理临时文件
        Path(temp_path).unlink(missing_ok=True)
        
        processing_time = time.time() - start_time
        
        if result.get("success"):
            return {
                "success": True,
                "task_id": task.task_id,
                "title": task.title,
                "method": "premium_mineru",
                "processing_time": f"{processing_time:.2f}s",
                "content": result.get("content", {}),
                "metadata": result.get("metadata", {}),
                "quality_score": 95,  # 最高质量
                "features": ["高质量OCR", "完整结构识别", "公式提取", "图表分析", "Markdown输出"]
            }
        else:
            # MinerU失败时降级到标准处理
            return await self._process_pdf_standard(pdf_content, task)
    
    def _extract_text_pypdf2(self, pdf_content: bytes) -> Dict:
        """PyPDF2文本提取 (同步函数)"""
        try:
            import io
            from PyPDF2 import PdfReader
            
            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)
            
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            return {
                "text": text,
                "metadata": {
                    "pages": len(reader.pages),
                    "method": "PyPDF2"
                }
            }
        except Exception as e:
            return {"text": "", "metadata": {"error": str(e)}}
    
    def _extract_text_pdfplumber(self, pdf_content: bytes) -> Dict:
        """pdfplumber文本提取 (同步函数)"""
        try:
            import io
            import pdfplumber
            
            pdf_file = io.BytesIO(pdf_content)
            text = ""
            tables = []
            
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    # 提取文本
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    
                    # 提取表格
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
            
            return {
                "text": text,
                "tables": tables,
                "metadata": {
                    "pages": len(pdf.pages),
                    "method": "pdfplumber",
                    "tables_found": len(tables)
                }
            }
        except Exception as e:
            return {"text": "", "tables": [], "metadata": {"error": str(e)}}
    
    async def _handle_user_choices(self, tasks: List[ProcessingTask], callback):
        """处理用户实时选择"""
        for task in tasks:
            # 等待快速处理完成
            while self.task_status.get(task.task_id) != ProcessingStatus.COMPLETED:
                if self.task_status.get(task.task_id) == ProcessingStatus.PROCESSING_FAST:
                    # 快速处理完成，询问用户是否需要升级
                    if task.task_id in self.task_results:
                        fast_result = self.task_results[task.task_id]
                        user_choice = await callback({
                            "task_id": task.task_id,
                            "title": task.title,
                            "fast_result_preview": fast_result.get("content", "")[:500],
                            "options": {
                                "keep_fast": "保持快速结果 (已完成)",
                                "upgrade_standard": "升级到标准处理 (+3-5秒, 更好质量)",
                                "upgrade_premium": "升级到高质量处理 (+30-60秒, 最佳质量)"
                            }
                        })
                        
                        if user_choice in ["upgrade_standard", "upgrade_premium"]:
                            # 重新处理
                            new_method = ProcessingMethod.STANDARD if user_choice == "upgrade_standard" else ProcessingMethod.PREMIUM_MINERU
                            task.method = new_method
                            asyncio.create_task(self._reprocess_with_method(task, new_method))
                
                await asyncio.sleep(0.5)
    
    async def _reprocess_with_method(self, task: ProcessingTask, method: ProcessingMethod):
        """使用新方法重新处理"""
        # 这里可以重新处理已下载的PDF
        pass
    
    async def get_processing_status(self, task_ids: List[str] = None) -> Dict:
        """获取处理状态"""
        if task_ids is None:
            task_ids = list(self.task_status.keys())
        
        return {
            task_id: {
                "status": self.task_status.get(task_id, "unknown").value,
                "progress": self.task_progress.get(task_id, 0.0),
                "result": self.task_results.get(task_id)
            }
            for task_id in task_ids
        }
    
    async def _download_worker(self, worker_name: str):
        """下载工作线程"""
        while True:
            try:
                # 从队列获取下载任务
                task = await self.download_queue.get()
                if task is None:  # 停止信号
                    break
                
                # 执行下载
                await self._process_single_paper(task)
                self.download_queue.task_done()
                
            except Exception as e:
                print(f"❌ 下载工作线程 {worker_name} 错误: {e}")
                await asyncio.sleep(1)
    
    async def _processing_worker(self, worker_name: str):
        """处理工作线程"""
        while True:
            try:
                # 从队列获取处理任务
                task = await self.processing_queue.get()
                if task is None:  # 停止信号
                    break
                
                # 执行处理
                # 这里可以添加额外的处理逻辑
                self.processing_queue.task_done()
                
            except Exception as e:
                print(f"❌ 处理工作线程 {worker_name} 错误: {e}")
                await asyncio.sleep(1)

# 全局处理管道实例
pipeline = LiteratureProcessingPipeline()
