"""
大规模文献处理引擎 - 核心实现
支持200-500篇文献的高性能批量处理
"""

import asyncio
import time
import psutil
import multiprocessing
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger
import json
from enum import Enum

from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.services.multi_model_ai_service import MultiModelAIService
from app.services.pdf_processor import PDFProcessor
from app.services.stream_progress_service import StreamProgressService
from app.core.database import SessionLocal
from app.utils.async_limiter import AsyncLimiter


class ProcessingPhase(Enum):
    """处理阶段"""
    INITIALIZATION = "initialization"
    PDF_PROCESSING = "pdf_processing"
    AI_ANALYSIS = "ai_analysis"
    STRUCTURE_GENERATION = "structure_generation"
    DATABASE_OPERATIONS = "database_operations"
    COMPLETED = "completed"


@dataclass
class ProcessingMetrics:
    """处理指标"""
    start_time: float
    end_time: Optional[float] = None
    memory_peak: float = 0.0
    cpu_peak: float = 0.0
    tokens_used: int = 0
    api_calls: int = 0
    throughput: float = 0.0
    error_count: int = 0
    success_count: int = 0


class IntelligentResourceManager:
    """智能资源管理器"""

    def __init__(self):
        self.memory_monitor_interval = 5.0
        self.cpu_monitor_interval = 1.0
        self._monitoring_active = False
        self._current_metrics = ProcessingMetrics(start_time=time.time())

    async def calculate_optimal_concurrency(self,
                                          literature_count: int,
                                          processing_type: str = "comprehensive") -> Dict[str, Any]:
        """动态计算最优并发参数"""

        # 获取系统资源状态
        memory = psutil.virtual_memory()
        cpu_count = multiprocessing.cpu_count()
        available_memory_gb = memory.available / (1024**3)
        cpu_percent = psutil.cpu_percent(interval=1.0)

        logger.info(f"系统资源评估 - 可用内存: {available_memory_gb:.1f}GB, CPU使用率: {cpu_percent:.1f}%")

        # PDF处理：内存密集型，每个任务约500MB
        base_pdf_concurrent = min(
            int(available_memory_gb / 0.5),  # 基于内存
            cpu_count,                       # 基于CPU核心
            15                              # 最大安全限制
        )

        # AI调用：API限制为主，内存占用较少
        base_ai_concurrent = min(
            30,                             # API限制
            int(literature_count / 8),      # 基于文献数量
            base_pdf_concurrent * 2         # AI处理比PDF快
        )

        # 根据系统负载动态调整
        load_factor = self._calculate_load_factor(cpu_percent, memory.percent)

        pdf_concurrent = max(1, int(base_pdf_concurrent * load_factor))
        ai_concurrent = max(1, int(base_ai_concurrent * load_factor))

        # 批次大小基于并发数和内存情况
        optimal_batch_size = min(
            50,  # 最大批次
            max(10, pdf_concurrent * 3),  # 基于处理能力
            int(available_memory_gb * 2)  # 基于内存
        )

        # 估算处理时间
        estimated_duration = self._estimate_processing_time(
            literature_count, pdf_concurrent, ai_concurrent
        )

        config = {
            "pdf_processing_concurrent": pdf_concurrent,
            "ai_analysis_concurrent": ai_concurrent,
            "batch_size": optimal_batch_size,
            "memory_per_task_mb": 512,
            "estimated_duration_seconds": estimated_duration,
            "load_factor": load_factor,
            "system_info": {
                "available_memory_gb": available_memory_gb,
                "cpu_count": cpu_count,
                "cpu_utilization": cpu_percent,
                "memory_utilization": memory.percent
            }
        }

        logger.info(f"计算出最优配置: PDF并发={pdf_concurrent}, AI并发={ai_concurrent}, 批次大小={optimal_batch_size}")
        return config

    def _calculate_load_factor(self, cpu_percent: float, memory_percent: float) -> float:
        """计算负载调整因子"""
        if cpu_percent > 80 or memory_percent > 85:
            return 0.5  # 高负载，减少50%
        elif cpu_percent > 60 or memory_percent > 70:
            return 0.7  # 中等负载，减少30%
        elif cpu_percent < 30 and memory_percent < 50:
            return 1.2  # 低负载，增加20%
        else:
            return 1.0  # 正常负载

    def _estimate_processing_time(self, count: int, pdf_conc: int, ai_conc: int) -> int:
        """估算处理时间（秒）"""
        # PDF处理：平均每篇30秒，AI分析：平均每篇10秒
        pdf_time = (count * 30) / pdf_conc
        ai_time = (count * 10) / ai_conc

        # 考虑流水线并行，取较长时间的85%，加上初始化和收尾时间
        pipeline_time = max(pdf_time, ai_time) * 0.85 + 60
        return int(pipeline_time)

    async def start_monitoring(self, session_id: str):
        """开始资源监控"""
        self._monitoring_active = True
        self._current_metrics = ProcessingMetrics(start_time=time.time())

        # 启动后台监控任务
        asyncio.create_task(self._monitor_resources(session_id))

    async def _monitor_resources(self, session_id: str):
        """后台资源监控任务"""
        try:
            while self._monitoring_active:
                # 更新资源使用峰值
                memory = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent()

                self._current_metrics.memory_peak = max(
                    self._current_metrics.memory_peak,
                    memory.used / (1024**3)
                )
                self._current_metrics.cpu_peak = max(
                    self._current_metrics.cpu_peak,
                    cpu_percent
                )

                await asyncio.sleep(self.memory_monitor_interval)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"资源监控异常: {e}")

    def stop_monitoring(self) -> ProcessingMetrics:
        """停止监控并返回指标"""
        self._monitoring_active = False
        self._current_metrics.end_time = time.time()
        return self._current_metrics


class FaultToleranceManager:
    """容错和恢复管理器"""

    def __init__(self):
        self.checkpoints = {}
        self.retry_delays = [1, 2, 4, 8, 16]  # 指数退避

    async def process_with_fault_tolerance(self,
                                         processing_func,
                                         literature_item: Literature,
                                         session_id: str,
                                         max_retries: int = 3) -> Dict[str, Any]:
        """带容错机制的处理执行"""

        checkpoint_key = f"{session_id}:lit:{literature_item.id if hasattr(literature_item, 'id') else 'batch'}"

        # 检查检查点
        if checkpoint_key in self.checkpoints:
            logger.debug(f"从检查点恢复: {getattr(literature_item, 'title', 'batch')[:50]}")
            return self.checkpoints[checkpoint_key]

        # 执行处理，带重试机制
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                result = await processing_func(literature_item)

                # 成功时保存检查点
                self.checkpoints[checkpoint_key] = result
                return result

            except Exception as e:
                last_exception = e

                if attempt == max_retries:
                    logger.error(f"处理最终失败: {getattr(literature_item, 'title', 'batch')[:50]} - {e}")
                    break

                # 等待重试
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                logger.warning(f"处理失败，{delay}秒后重试 (尝试 {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(delay)

        return {
            "success": False,
            "literature_id": getattr(literature_item, 'id', None),
            "title": getattr(literature_item, 'title', 'Unknown')[:100],
            "error": str(last_exception),
            "attempts": max_retries + 1,
            "fault_tolerant": True
        }

    async def graceful_degradation(self,
                                 failed_items: List[Literature],
                                 session_id: str) -> Dict[str, Any]:
        """优雅降级处理"""
        logger.info(f"启动优雅降级，处理 {len(failed_items)} 个失败项")

        simplified_results = []

        for item in failed_items:
            try:
                # 创建基本记录（仅使用现有信息）
                result = await self._create_basic_literature_record(item)
                simplified_results.append(result)

            except Exception as e:
                logger.error(f"降级处理也失败: {item.title[:50]} - {e}")
                simplified_results.append({
                    "success": False,
                    "literature_id": item.id,
                    "title": item.title[:100],
                    "degraded": True,
                    "error": str(e)
                })

        success_count = len([r for r in simplified_results if r.get("success", False)])

        return {
            "degradation_applied": True,
            "total_items": len(failed_items),
            "processed_count": success_count,
            "still_failed_count": len(failed_items) - success_count,
            "success_rate": success_count / len(failed_items) if failed_items else 0,
            "results": simplified_results
        }

    async def _create_basic_literature_record(self, literature: Literature) -> Dict[str, Any]:
        """创建基本文献记录"""
        # 使用现有的标题、摘要、作者信息创建简化段落
        segments = []

        if literature.title:
            segments.append({
                "segment_type": "title",
                "content": literature.title,
                "confidence": 0.9
            })

        if literature.abstract:
            segments.append({
                "segment_type": "abstract",
                "content": literature.abstract,
                "confidence": 0.8
            })

        if literature.authors:
            author_text = f"作者: {', '.join(literature.authors)}"
            segments.append({
                "segment_type": "authors",
                "content": author_text,
                "confidence": 0.9
            })

        return {
            "success": True,
            "literature_id": literature.id,
            "title": literature.title[:100],
            "segments_created": len(segments),
            "segments": segments,
            "processing_method": "degraded_basic_info",
            "degraded": True
        }


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self):
        self.progress_service = StreamProgressService()
        self.session_progress = {}

    async def update_progress(self, session_id: str, progress: int, message: str, details: Optional[Dict] = None):
        """更新处理进度"""
        try:
            self.session_progress[session_id] = {
                "progress": progress,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details or {}
            }

            # 通过WebSocket广播进度更新
            await self.progress_service.broadcast_task_update(0, {
                "type": "massive_processing_progress",
                "session_id": session_id,
                "progress": progress,
                "message": message,
                "details": details
            })

            logger.info(f"会话 {session_id} 进度: {progress}% - {message}")

        except Exception as e:
            logger.warning(f"进度更新失败: {e}")

    def get_progress(self, session_id: str) -> Optional[Dict]:
        """获取会话进度"""
        return self.session_progress.get(session_id)


class DistributedBatchProcessor:
    """分布式批次处理器"""

    def __init__(self, resource_manager: IntelligentResourceManager):
        self.resource_manager = resource_manager
        self.progress_tracker = ProgressTracker()
        self.pdf_processor = PDFProcessor()
        self.ai_service = MultiModelAIService()

    async def process_literature_pipeline(self,
                                        literature_batch: List[Literature],
                                        processing_config: Dict[str, Any],
                                        session_id: str) -> Dict[str, Any]:
        """文献处理流水线"""

        logger.info(f"开始处理批次: {session_id}, 文献数量: {len(literature_batch)}")

        # 创建信号量池
        pdf_semaphore = asyncio.Semaphore(processing_config["pdf_processing_concurrent"])
        ai_semaphore = asyncio.Semaphore(processing_config["ai_analysis_concurrent"])

        # 初始化结果
        batch_results = {
            "session_id": session_id,
            "total_literature": len(literature_batch),
            "successful": 0,
            "failed": 0,
            "processing_details": [],
            "performance_metrics": {},
            "phase_results": {}
        }

        try:
            # 阶段1: 并行PDF处理
            await self.progress_tracker.update_progress(
                session_id, 10, "开始PDF处理阶段",
                {"phase": "pdf_processing", "total": len(literature_batch)}
            )

            pdf_results = await self._parallel_pdf_processing(
                literature_batch, pdf_semaphore, session_id
            )
            batch_results["phase_results"]["pdf_processing"] = pdf_results

            # 阶段2: 并行AI分析
            await self.progress_tracker.update_progress(
                session_id, 40, "开始AI分析阶段",
                {"phase": "ai_analysis", "pdf_completed": len([r for r in pdf_results if r["success"]])}
            )

            successful_pdf_results = [r for r in pdf_results if r["success"]]
            ai_results = await self._parallel_ai_analysis(
                successful_pdf_results, ai_semaphore, session_id
            )
            batch_results["phase_results"]["ai_analysis"] = ai_results

            # 阶段3: 结构化数据生成
            await self.progress_tracker.update_progress(
                session_id, 70, "生成结构化数据",
                {"phase": "structure_generation", "ai_completed": len([r for r in ai_results if r["success"]])}
            )

            successful_ai_results = [r for r in ai_results if r["success"]]
            structure_results = await self._parallel_structure_generation(
                successful_ai_results, ai_semaphore, session_id
            )
            batch_results["phase_results"]["structure_generation"] = structure_results

            # 阶段4: 批量数据库保存
            await self.progress_tracker.update_progress(
                session_id, 90, "保存处理结果",
                {"phase": "database_operations", "structures_completed": len(structure_results)}
            )

            save_results = await self._batch_database_operations(
                structure_results, session_id
            )
            batch_results["phase_results"]["database_operations"] = save_results

            # 统计最终结果
            batch_results["successful"] = len([r for r in save_results if r.get("success", False)])
            batch_results["failed"] = len(literature_batch) - batch_results["successful"]
            batch_results["processing_details"] = save_results

            await self.progress_tracker.update_progress(
                session_id, 100, "批次处理完成",
                {
                    "successful": batch_results["successful"],
                    "failed": batch_results["failed"],
                    "success_rate": batch_results["successful"] / len(literature_batch)
                }
            )

            return {"success": True, "results": batch_results}

        except Exception as e:
            logger.error(f"批次处理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "partial_results": batch_results
            }

    async def _parallel_pdf_processing(self,
                                     literature_batch: List[Literature],
                                     semaphore: asyncio.Semaphore,
                                     session_id: str) -> List[Dict[str, Any]]:
        """并行PDF处理"""

        async def process_single_pdf(literature: Literature):
            async with semaphore:
                try:
                    if not literature.pdf_path and not literature.pdf_url:
                        # 没有PDF的文献，跳过PDF处理
                        return {
                            "success": True,
                            "literature_id": literature.id,
                            "title": literature.title[:100],
                            "pdf_processed": False,
                            "content": {"text_content": literature.abstract or ""},
                            "processing_method": "abstract_only"
                        }

                    # 处理PDF
                    pdf_path = literature.pdf_path or literature.pdf_url
                    result = await self.pdf_processor.process_pdf(pdf_path)

                    if result["success"]:
                        return {
                            "success": True,
                            "literature_id": literature.id,
                            "title": literature.title[:100],
                            "pdf_processed": True,
                            "content": result["content"],
                            "processing_method": "pdf_extraction",
                            "metadata": result.get("metadata", {})
                        }
                    else:
                        # PDF处理失败，使用摘要
                        return {
                            "success": True,
                            "literature_id": literature.id,
                            "title": literature.title[:100],
                            "pdf_processed": False,
                            "content": {"text_content": literature.abstract or ""},
                            "processing_method": "fallback_abstract",
                            "pdf_error": result.get("error", "Unknown error")
                        }

                except Exception as e:
                    logger.error(f"PDF处理异常: {literature.title[:50]} - {e}")
                    return {
                        "success": False,
                        "literature_id": literature.id,
                        "title": literature.title[:100],
                        "error": str(e),
                        "processing_method": "pdf_processing"
                    }

        # 并行执行PDF处理任务
        tasks = [process_single_pdf(lit) for lit in literature_batch]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _parallel_ai_analysis(self,
                                  pdf_results: List[Dict],
                                  semaphore: asyncio.Semaphore,
                                  session_id: str) -> List[Dict[str, Any]]:
        """并行AI分析"""

        async def analyze_single_literature(pdf_result: Dict):
            async with semaphore:
                try:
                    literature_id = pdf_result["literature_id"]
                    content = pdf_result["content"]["text_content"]

                    if not content.strip():
                        return {
                            "success": False,
                            "literature_id": literature_id,
                            "title": pdf_result.get("title", ""),
                            "error": "没有可分析的内容",
                            "processing_method": "ai_analysis"
                        }

                    # 使用多模型AI服务进行分析
                    analysis_result = await self.ai_service.analyze_literature_with_multiple_models(
                        content[:4000],  # 限制长度避免token超限
                        analysis_type="comprehensive",
                        use_ensemble=True
                    )

                    if analysis_result["success"]:
                        return {
                            "success": True,
                            "literature_id": literature_id,
                            "title": pdf_result.get("title", ""),
                            "ai_analysis": analysis_result,
                            "original_content": content[:1000],  # 保存部分原始内容用于结构化
                            "processing_method": "ai_comprehensive_analysis"
                        }
                    else:
                        return {
                            "success": False,
                            "literature_id": literature_id,
                            "title": pdf_result.get("title", ""),
                            "error": analysis_result.get("error", "AI分析失败"),
                            "processing_method": "ai_analysis"
                        }

                except Exception as e:
                    logger.error(f"AI分析异常: {pdf_result.get('title', '')[:50]} - {e}")
                    return {
                        "success": False,
                        "literature_id": pdf_result["literature_id"],
                        "title": pdf_result.get("title", ""),
                        "error": str(e),
                        "processing_method": "ai_analysis"
                    }

        tasks = [analyze_single_literature(result) for result in pdf_results]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _parallel_structure_generation(self,
                                           ai_results: List[Dict],
                                           semaphore: asyncio.Semaphore,
                                           session_id: str) -> List[Dict[str, Any]]:
        """并行结构化数据生成"""

        async def generate_structure(ai_result: Dict):
            async with semaphore:
                try:
                    literature_id = ai_result["literature_id"]
                    analysis = ai_result["ai_analysis"]

                    # 从AI分析结果中提取结构化段落
                    segments = []

                    if "ensemble_result" in analysis:
                        content = analysis["ensemble_result"]["content"]

                        # 简单的段落分割和分类
                        paragraphs = content.split('\n\n')

                        for i, paragraph in enumerate(paragraphs):
                            if len(paragraph.strip()) > 50:  # 过滤短段落
                                segments.append({
                                    "segment_type": self._classify_segment_type(paragraph),
                                    "content": paragraph.strip(),
                                    "order": i,
                                    "confidence": analysis["ensemble_result"].get("confidence", 0.8),
                                    "source": "ai_analysis_segmentation"
                                })

                    # 如果没有足够的段落，使用原始内容
                    if len(segments) < 2 and "original_content" in ai_result:
                        segments.append({
                            "segment_type": "summary",
                            "content": ai_result["original_content"],
                            "order": 0,
                            "confidence": 0.6,
                            "source": "original_content_fallback"
                        })

                    return {
                        "success": True,
                        "literature_id": literature_id,
                        "title": ai_result.get("title", ""),
                        "segments": segments,
                        "processing_method": "structure_generation",
                        "segment_count": len(segments)
                    }

                except Exception as e:
                    logger.error(f"结构化生成异常: {ai_result.get('title', '')[:50]} - {e}")
                    return {
                        "success": False,
                        "literature_id": ai_result["literature_id"],
                        "title": ai_result.get("title", ""),
                        "error": str(e),
                        "processing_method": "structure_generation"
                    }

        tasks = [generate_structure(result) for result in ai_results]
        return await asyncio.gather(*tasks, return_exceptions=False)

    def _classify_segment_type(self, paragraph: str) -> str:
        """简单的段落类型分类"""
        paragraph_lower = paragraph.lower()

        if any(keyword in paragraph_lower for keyword in ["method", "approach", "technique", "methodology"]):
            return "methodology"
        elif any(keyword in paragraph_lower for keyword in ["result", "finding", "outcome", "conclusion"]):
            return "results"
        elif any(keyword in paragraph_lower for keyword in ["introduction", "background", "overview"]):
            return "introduction"
        elif any(keyword in paragraph_lower for keyword in ["discussion", "analysis", "interpretation"]):
            return "discussion"
        else:
            return "general"

    async def _batch_database_operations(self,
                                       structure_results: List[Dict],
                                       session_id: str) -> List[Dict[str, Any]]:
        """批量数据库操作"""

        db = SessionLocal()
        final_results = []

        try:
            for result in structure_results:
                try:
                    if not result["success"]:
                        final_results.append(result)
                        continue

                    literature_id = result["literature_id"]
                    segments = result["segments"]

                    # 获取文献对象
                    literature = db.query(Literature).filter(Literature.id == literature_id).first()
                    if not literature:
                        final_results.append({
                            "success": False,
                            "literature_id": literature_id,
                            "error": "文献不存在",
                            "processing_method": "database_operations"
                        })
                        continue

                    # 删除旧的段落（如果存在）
                    db.query(LiteratureSegment).filter(
                        LiteratureSegment.literature_id == literature_id
                    ).delete()

                    # 创建新的段落
                    segment_objects = []
                    for segment_data in segments:
                        segment = LiteratureSegment(
                            literature_id=literature_id,
                            segment_type=segment_data["segment_type"],
                            content=segment_data["content"],
                            order=segment_data.get("order", 0),
                            extraction_confidence=segment_data.get("confidence", 0.8),
                            structured_data={
                                "source": segment_data.get("source", "massive_processing"),
                                "session_id": session_id,
                                "processing_timestamp": datetime.utcnow().isoformat()
                            }
                        )
                        segment_objects.append(segment)
                        db.add(segment)

                    # 更新文献状态
                    literature.is_parsed = True
                    literature.parsing_status = "completed"
                    literature.parsed_content = " ".join([s["content"] for s in segments])

                    db.commit()

                    final_results.append({
                        "success": True,
                        "literature_id": literature_id,
                        "title": result.get("title", ""),
                        "segments_created": len(segment_objects),
                        "processing_method": "database_operations_success"
                    })

                except Exception as e:
                    db.rollback()
                    logger.error(f"数据库操作失败: {result.get('title', '')[:50]} - {e}")
                    final_results.append({
                        "success": False,
                        "literature_id": result.get("literature_id"),
                        "title": result.get("title", ""),
                        "error": str(e),
                        "processing_method": "database_operations"
                    })

        finally:
            db.close()

        return final_results


class MassiveLiteratureProcessor:
    """大规模文献处理引擎主控制器"""

    def __init__(self):
        self.resource_manager = IntelligentResourceManager()
        self.fault_manager = FaultToleranceManager()
        self.progress_tracker = ProgressTracker()

    async def process_massive_literature(self,
                                       literature_list: List[Literature],
                                       target_count: int = 200,
                                       processing_config: Optional[Dict] = None) -> Dict[str, Any]:
        """大规模文献处理主入口"""

        session_id = f"massive_{int(time.time())}_{len(literature_list)}"

        try:
            logger.info(f"启动大规模处理会话: {session_id}, 目标文献数: {target_count}")

            # 1. 限制和预处理
            actual_literature = literature_list[:target_count]

            await self.progress_tracker.update_progress(
                session_id, 5, f"初始化处理，文献数量: {len(actual_literature)}"
            )

            # 2. 计算最优配置
            optimal_config = await self.resource_manager.calculate_optimal_concurrency(
                len(actual_literature), "comprehensive"
            )

            # 3. 启动资源监控
            await self.resource_manager.start_monitoring(session_id)

            # 4. 分批处理策略
            batch_size = optimal_config["batch_size"]
            literature_batches = [
                actual_literature[i:i + batch_size]
                for i in range(0, len(actual_literature), batch_size)
            ]

            logger.info(f"分批策略: {len(literature_batches)} 个批次, 每批 {batch_size} 篇")

            await self.progress_tracker.update_progress(
                session_id, 10, f"开始分批处理，共 {len(literature_batches)} 个批次",
                {"batches": len(literature_batches), "batch_size": batch_size}
            )

            # 5. 初始化总体结果
            overall_results = {
                "session_id": session_id,
                "total_literature": len(actual_literature),
                "total_batches": len(literature_batches),
                "successful": 0,
                "failed": 0,
                "batch_results": [],
                "failed_literature": [],
                "performance_summary": {},
                "processing_time": 0,
                "configuration": optimal_config
            }

            start_time = time.time()

            # 6. 批次并行处理（控制并发度避免过载）
            batch_processor = DistributedBatchProcessor(self.resource_manager)
            batch_semaphore = asyncio.Semaphore(2)  # 最多同时处理2个批次

            async def process_single_batch(batch_idx: int, batch: List[Literature]):
                async with batch_semaphore:
                    batch_session_id = f"{session_id}_batch_{batch_idx}"
                    logger.info(f"开始处理批次 {batch_idx + 1}/{len(literature_batches)}")

                    return await self.fault_manager.process_with_fault_tolerance(
                        lambda _: batch_processor.process_literature_pipeline(
                            batch, optimal_config, batch_session_id
                        ),
                        batch,  # 传递批次作为"文献"参数
                        batch_session_id
                    )

            # 并行执行所有批次
            batch_tasks = [
                process_single_batch(i, batch)
                for i, batch in enumerate(literature_batches)
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 7. 汇总批次结果
            failed_literature_items = []

            for i, batch_result in enumerate(batch_results):
                if isinstance(batch_result, Exception):
                    logger.error(f"批次 {i} 处理异常: {batch_result}")
                    failed_literature_items.extend(literature_batches[i])
                    continue

                if batch_result.get("success") and "results" in batch_result:
                    result_data = batch_result["results"]
                    overall_results["successful"] += result_data["successful"]
                    overall_results["failed"] += result_data["failed"]
                    overall_results["batch_results"].append(result_data)
                else:
                    failed_literature_items.extend(literature_batches[i])

            # 8. 优雅降级处理失败项
            if failed_literature_items:
                await self.progress_tracker.update_progress(
                    session_id, 85, f"对 {len(failed_literature_items)} 个失败项启动降级处理"
                )

                degradation_result = await self.fault_manager.graceful_degradation(
                    failed_literature_items, session_id
                )

                overall_results["degradation_result"] = degradation_result
                overall_results["successful"] += degradation_result["processed_count"]
                overall_results["failed_literature"] = [
                    r for r in degradation_result["results"] if not r.get("success", False)
                ]

            # 9. 完成处理和性能总结
            overall_results["processing_time"] = time.time() - start_time

            # 停止资源监控
            final_metrics = self.resource_manager.stop_monitoring()
            final_metrics.success_count = overall_results["successful"]
            final_metrics.error_count = overall_results["failed"]
            final_metrics.throughput = overall_results["successful"] / overall_results["processing_time"] if overall_results["processing_time"] > 0 else 0

            overall_results["performance_summary"] = {
                "memory_peak": final_metrics.memory_peak,
                "cpu_peak": final_metrics.cpu_peak,
                "tokens_used": final_metrics.tokens_used,
                "api_calls": final_metrics.api_calls,
                "throughput": final_metrics.throughput,
                "processing_time": overall_results["processing_time"]
            }

            # 10. 最终进度更新
            success_rate = overall_results["successful"] / overall_results["total_literature"]

            await self.progress_tracker.update_progress(
                session_id, 100, "大规模处理完成",
                {
                    "successful": overall_results["successful"],
                    "failed": overall_results["failed"],
                    "success_rate": success_rate,
                    "throughput": final_metrics.throughput
                }
            )

            logger.info(f"大规模处理完成: {session_id}")
            logger.info(f"处理结果: {overall_results['successful']}/{overall_results['total_literature']} 成功 ({success_rate:.1%})")
            logger.info(f"处理时间: {overall_results['processing_time']:.1f} 秒")
            logger.info(f"处理效率: {final_metrics.throughput:.2f} 篇/秒")

            return {
                "success": True,
                "results": overall_results,
                "recommendations": self._generate_recommendations(overall_results)
            }

        except Exception as e:
            logger.error(f"大规模处理引擎异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id,
                "partial_results": locals().get("overall_results", {})
            }

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        recommendations = []

        success_rate = results["successful"] / results["total_literature"]
        processing_time = results["processing_time"]
        throughput = results["performance_summary"].get("throughput", 0)

        # 成功率分析
        if success_rate >= 0.95:
            recommendations.append("✅ 处理成功率优秀 (≥95%)")
        elif success_rate >= 0.85:
            recommendations.append("✅ 处理成功率良好 (≥85%)")
        elif success_rate >= 0.7:
            recommendations.append("⚠️ 处理成功率中等，建议检查网络连接和API配置")
        else:
            recommendations.append("❌ 处理成功率较低，需要检查系统配置和资源分配")

        # 性能分析
        if throughput >= 1.0:
            recommendations.append(f"✅ 处理效率优秀: {throughput:.2f} 篇/秒")
        elif throughput >= 0.5:
            recommendations.append(f"✅ 处理效率良好: {throughput:.2f} 篇/秒")
        else:
            recommendations.append(f"⚠️ 处理效率较低: {throughput:.2f} 篇/秒，建议增加系统资源")

        # 内存和CPU使用分析
        memory_peak = results["performance_summary"].get("memory_peak", 0)
        cpu_peak = results["performance_summary"].get("cpu_peak", 0)

        if memory_peak > 12:  # >12GB
            recommendations.append("⚠️ 内存使用较高，建议优化批次大小或增加内存")

        if cpu_peak > 80:  # >80%
            recommendations.append("⚠️ CPU使用率较高，建议降低并发数或增加CPU资源")

        # 降级处理分析
        if results.get("degradation_result"):
            degraded_count = results["degradation_result"]["processed_count"]
            recommendations.append(f"ℹ️ 有 {degraded_count} 篇文献使用了降级处理，建议检查原始处理失败原因")

        # 总体建议
        recommendations.append(f"📊 本次处理统计: 总计 {results['total_literature']} 篇，成功 {results['successful']} 篇，用时 {processing_time:.1f} 秒")

        return recommendations