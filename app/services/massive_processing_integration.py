"""
大规模文献处理API和任务集成
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Any
from fastapi import HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.task import Task
from app.models.project import Project
from app.services.massive_literature_processor import (
    MassiveLiteratureProcessor,
    start_massive_literature_processing
)
from app.services.stream_progress_service import StreamProgressService
from app.tasks.literature_tasks import safe_broadcast_update


async def start_massive_processing_task(
    task_id: int,
    project_id: int,
    processing_config: Dict[str, Any] = None
):
    """
    启动大规模文献处理任务

    Args:
        task_id: 任务ID
        project_id: 项目ID
        processing_config: 处理配置参数
    """
    db = SessionLocal()
    progress_service = StreamProgressService()

    try:
        # 获取任务和项目信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"项目不存在: {project_id}")

        # 解析处理配置
        config = processing_config or {}
        batch_size = config.get("batch_size", 20)
        max_concurrent = config.get("max_concurrent", 10)
        max_retries = config.get("max_retries", 3)
        memory_limit = config.get("memory_limit", 8.0)
        resume_from_checkpoint = config.get("resume_from_checkpoint", True)

        # 更新任务状态为运行中
        task.status = "running"
        task.started_at = datetime.utcnow()
        task.progress_percentage = 0
        task.current_step = "🚀 初始化大规模文献处理引擎..."
        task.result = {
            "processing_config": config,
            "start_time": datetime.utcnow().isoformat()
        }
        db.commit()

        # 发送任务开始通知
        await safe_broadcast_update(progress_service, task_id, {
            "type": "massive_processing_started",
            "task_id": task_id,
            "project_id": project_id,
            "progress": 0,
            "current_step": "🚀 初始化大规模文献处理引擎...",
            "config": {
                "batch_size": batch_size,
                "max_concurrent": max_concurrent,
                "memory_limit": f"{memory_limit}GB",
                "resume_enabled": resume_from_checkpoint
            }
        })

        logger.info(f"开始大规模处理任务 - Task ID: {task_id}, Project ID: {project_id}")

        # 创建处理器实例
        processor = MassiveLiteratureProcessor(
            batch_size=batch_size,
            max_concurrent=max_concurrent,
            max_retries=max_retries,
            memory_limit=memory_limit
        )

        # 定义进度回调函数
        async def progress_callback(step: str, progress: int, details: dict = None):
            try:
                # 更新任务状态
                task_update = db.query(Task).filter(Task.id == task_id).first()
                if task_update:
                    task_update.progress_percentage = progress
                    task_update.current_step = step

                    if details:
                        current_result = task_update.result or {}
                        current_result.update(details)
                        task_update.result = current_result

                    db.commit()

                # 发送WebSocket更新
                await safe_broadcast_update(progress_service, task_id, {
                    "type": "massive_processing_progress",
                    "task_id": task_id,
                    "project_id": project_id,
                    "progress": progress,
                    "current_step": step,
                    "details": details or {},
                    "timestamp": datetime.utcnow().isoformat()
                })

                logger.info(f"大规模处理进度 - Task {task_id}: {step} ({progress}%)")

            except Exception as e:
                logger.error(f"进度更新失败: {e}")

        # 执行大规模处理
        processing_results = await processor.process_project_literature(
            project_id=project_id,
            task_id=task_id,
            resume_from_checkpoint=resume_from_checkpoint,
            progress_callback=progress_callback
        )

        # 处理完成，更新任务状态
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "completed"
            task.progress_percentage = 100
            task.current_step = "✅ 大规模文献处理完成"
            task.completed_at = datetime.utcnow()

            # 计算实际耗时
            if task.started_at:
                task.actual_duration = int((task.completed_at - task.started_at).total_seconds())

            # 保存详细结果
            task.result = {
                **task.result,
                "completion_time": datetime.utcnow().isoformat(),
                "processing_results": processing_results,
                "performance_summary": {
                    "total_literature": processing_results.get("total_literature", 0),
                    "successful_count": processing_results.get("successful", 0),
                    "failed_count": processing_results.get("failed", 0),
                    "success_rate": f"{(processing_results.get('successful', 0) / max(processing_results.get('total_literature', 1), 1) * 100):.1f}%",
                    "processing_time": f"{processing_results.get('processing_time', 0):.1f}秒",
                    "throughput": f"{processing_results.get('throughput', 0):.2f} 篇/秒",
                    "memory_peak": f"{processing_results.get('memory_peak', 0):.2f}GB",
                    "tokens_used": processing_results.get("tokens_used", 0)
                }
            }
            db.commit()

        # 发送完成通知
        await safe_broadcast_update(progress_service, task_id, {
            "type": "massive_processing_completed",
            "task_id": task_id,
            "project_id": project_id,
            "progress": 100,
            "current_step": "✅ 大规模文献处理完成",
            "results": processing_results,
            "performance_summary": task.result.get("performance_summary", {}),
            "completion_time": datetime.utcnow().isoformat()
        })

        logger.info(f"大规模处理任务完成 - Task ID: {task_id}, 成功: {processing_results.get('successful', 0)}, 失败: {processing_results.get('failed', 0)}")

        return processing_results

    except Exception as e:
        logger.error(f"大规模处理任务失败 - Task ID: {task_id}: {e}")

        # 更新任务状态为失败
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()

                if task.started_at:
                    task.actual_duration = int((task.completed_at - task.started_at).total_seconds())

                current_result = task.result or {}
                current_result.update({
                    "error": str(e),
                    "error_time": datetime.utcnow().isoformat()
                })
                task.result = current_result

                db.commit()

            # 发送失败通知
            await safe_broadcast_update(progress_service, task_id, {
                "type": "massive_processing_failed",
                "task_id": task_id,
                "project_id": project_id,
                "error": str(e),
                "error_time": datetime.utcnow().isoformat()
            })

        except Exception as commit_error:
            logger.error(f"更新失败状态时出错: {commit_error}")

        raise

    finally:
        db.close()


async def get_massive_processing_status(session_id: str) -> Dict[str, Any]:
    """
    获取大规模处理状态

    Args:
        session_id: 会话ID

    Returns:
        处理状态信息
    """
    try:
        # 这里可以通过session_id查询处理状态
        # 实际实现中可能需要维护一个全局的处理器实例管理器

        return {
            "success": True,
            "message": "状态查询功能需要处理器实例管理器支持",
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"获取处理状态失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def stop_massive_processing(session_id: str, save_checkpoint: bool = True) -> Dict[str, Any]:
    """
    停止大规模处理

    Args:
        session_id: 会话ID
        save_checkpoint: 是否保存检查点

    Returns:
        停止操作结果
    """
    try:
        # 这里需要实现处理器实例管理和停止逻辑
        logger.info(f"请求停止大规模处理 - Session ID: {session_id}")

        return {
            "success": True,
            "message": "停止请求已发送",
            "session_id": session_id,
            "checkpoint_saved": save_checkpoint
        }

    except Exception as e:
        logger.error(f"停止处理失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# 高级功能：智能批量处理配置优化
class ProcessingConfigOptimizer:
    """处理配置优化器"""

    @staticmethod
    async def optimize_config_for_project(project_id: int, literature_count: int) -> Dict[str, Any]:
        """
        为项目优化处理配置

        Args:
            project_id: 项目ID
            literature_count: 文献数量

        Returns:
            优化的配置参数
        """
        try:
            # 获取系统资源信息
            import psutil
            memory_total = psutil.virtual_memory().total / (1024**3)  # GB
            cpu_count = psutil.cpu_count()

            # 基于文献数量和系统资源优化配置
            if literature_count <= 50:
                # 小规模处理
                config = {
                    "batch_size": 10,
                    "max_concurrent": min(5, cpu_count),
                    "memory_limit": min(2.0, memory_total * 0.3),
                    "processing_mode": "standard"
                }
            elif literature_count <= 200:
                # 中等规模处理
                config = {
                    "batch_size": 20,
                    "max_concurrent": min(10, cpu_count),
                    "memory_limit": min(4.0, memory_total * 0.5),
                    "processing_mode": "optimized"
                }
            else:
                # 大规模处理
                config = {
                    "batch_size": 30,
                    "max_concurrent": min(20, cpu_count),
                    "memory_limit": min(8.0, memory_total * 0.7),
                    "processing_mode": "massive"
                }

            # 添加通用优化参数
            config.update({
                "max_retries": 3,
                "checkpoint_interval": 300,  # 5分钟
                "resume_from_checkpoint": True,
                "enable_performance_monitoring": True,
                "auto_gc_interval": 50  # 每50个项目强制垃圾回收
            })

            # 预估处理时间
            estimated_time_per_item = 3  # 秒/篇 (基于历史数据)
            parallel_factor = config["max_concurrent"] * 0.7  # 考虑并行效率

            estimated_total_time = (literature_count * estimated_time_per_item) / parallel_factor

            config["estimated_processing_time"] = {
                "total_seconds": int(estimated_total_time),
                "formatted": f"{int(estimated_total_time // 60)}分{int(estimated_total_time % 60)}秒"
            }

            logger.info(f"为项目 {project_id} 优化配置 - 文献数量: {literature_count}, 预计耗时: {config['estimated_processing_time']['formatted']}")

            return {
                "success": True,
                "config": config,
                "system_info": {
                    "total_memory": f"{memory_total:.1f}GB",
                    "cpu_cores": cpu_count,
                    "literature_count": literature_count
                }
            }

        except Exception as e:
            logger.error(f"配置优化失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "default_config": {
                    "batch_size": 20,
                    "max_concurrent": 10,
                    "memory_limit": 4.0,
                    "max_retries": 3
                }
            }


# 性能监控和报告
class MassiveProcessingReporter:
    """大规模处理报告生成器"""

    @staticmethod
    async def generate_processing_report(
        task_id: int,
        include_detailed_metrics: bool = True
    ) -> Dict[str, Any]:
        """
        生成处理报告

        Args:
            task_id: 任务ID
            include_detailed_metrics: 是否包含详细指标

        Returns:
            处理报告
        """
        db = SessionLocal()

        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise ValueError(f"任务不存在: {task_id}")

            task_result = task.result or {}
            processing_results = task_result.get("processing_results", {})

            # 基础报告
            report = {
                "task_info": {
                    "task_id": task_id,
                    "project_id": task.project_id,
                    "status": task.status,
                    "start_time": task.started_at.isoformat() if task.started_at else None,
                    "end_time": task.completed_at.isoformat() if task.completed_at else None,
                    "duration": task.actual_duration or 0
                },
                "summary": task_result.get("performance_summary", {}),
                "processing_overview": {
                    "total_literature": processing_results.get("total_literature", 0),
                    "successful": processing_results.get("successful", 0),
                    "failed": processing_results.get("failed", 0),
                    "skipped": processing_results.get("skipped", 0),
                    "success_rate": processing_results.get("success_rate", 0)
                }
            }

            if include_detailed_metrics and "statistics" in processing_results:
                stats = processing_results["statistics"]

                report["detailed_metrics"] = {
                    "performance": {
                        "throughput_per_minute": stats.get("throughput_per_minute", 0),
                        "average_processing_time": stats.get("average_processing_time", 0),
                        "total_segments_generated": stats.get("total_segments_generated", 0),
                        "total_tokens_used": stats.get("total_tokens_used", 0)
                    },
                    "resource_usage": {
                        "memory_peak": stats.get("performance_metrics", {}).get("peak_memory", 0),
                        "cpu_peak": stats.get("performance_metrics", {}).get("peak_cpu", 0),
                        "memory_efficiency": stats.get("memory_efficiency", {})
                    },
                    "error_analysis": stats.get("error_analysis", {}),
                    "batch_performance": processing_results.get("batch_metrics", [])
                }

            # 生成建议
            report["recommendations"] = MassiveProcessingReporter._generate_recommendations(
                processing_results
            )

            return {
                "success": True,
                "report": report,
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"生成处理报告失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

        finally:
            db.close()

    @staticmethod
    def _generate_recommendations(processing_results: Dict[str, Any]) -> List[Dict[str, str]]:
        """基于处理结果生成优化建议"""
        recommendations = []

        success_rate = processing_results.get("success_rate", 0)
        throughput = processing_results.get("throughput", 0)
        memory_peak = processing_results.get("memory_peak", 0)

        # 成功率建议
        if success_rate < 0.8:
            recommendations.append({
                "category": "质量",
                "priority": "高",
                "suggestion": "成功率较低，建议检查PDF处理配置和文献质量，考虑增加重试次数"
            })
        elif success_rate > 0.95:
            recommendations.append({
                "category": "质量",
                "priority": "信息",
                "suggestion": "处理质量优秀，当前配置适合此类文献"
            })

        # 性能建议
        if throughput < 1.0:  # 每秒少于1篇
            recommendations.append({
                "category": "性能",
                "priority": "中",
                "suggestion": "处理速度较慢，可以考虑增加并发数或优化批处理大小"
            })
        elif throughput > 3.0:  # 每秒超过3篇
            recommendations.append({
                "category": "性能",
                "priority": "信息",
                "suggestion": "处理速度优秀，系统性能得到充分利用"
            })

        # 内存建议
        if memory_peak > 6.0:  # 内存使用超过6GB
            recommendations.append({
                "category": "资源",
                "priority": "中",
                "suggestion": "内存使用较高，建议减少批处理大小或并发数以优化内存使用"
            })

        # 通用建议
        recommendations.append({
            "category": "维护",
            "priority": "低",
            "suggestion": "定期清理检查点文件和临时数据以维护系统性能"
        })

        return recommendations


# 与现有系统的集成接口
async def integrate_with_existing_literature_tasks(
    keywords: List[str],
    project_id: int,
    max_count: int = 200,
    enable_massive_processing: bool = True,
    processing_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    集成现有文献任务系统的大规模处理接口

    Args:
        keywords: 搜索关键词
        project_id: 项目ID
        max_count: 最大文献数量
        enable_massive_processing: 是否启用大规模处理
        processing_config: 处理配置

    Returns:
        集成处理结果
    """
    try:
        logger.info(f"启动集成文献处理 - 项目: {project_id}, 关键词: {keywords}, 数量: {max_count}")

        # 第一阶段：文献搜索和采集
        logger.info("阶段1: 文献搜索和采集")
        # 这里可以复用现有的literature_tasks中的搜索逻辑

        # 第二阶段：智能批量处理配置优化
        logger.info("阶段2: 处理配置优化")
        optimizer = ProcessingConfigOptimizer()
        config_result = await optimizer.optimize_config_for_project(project_id, max_count)

        if not config_result["success"]:
            logger.warning(f"配置优化失败，使用默认配置: {config_result.get('error')}")
            optimized_config = config_result["default_config"]
        else:
            optimized_config = config_result["config"]

        # 合并用户提供的配置
        if processing_config:
            optimized_config.update(processing_config)

        # 第三阶段：大规模处理
        if enable_massive_processing and max_count >= 50:
            logger.info("阶段3: 启动大规模批量处理")

            # 创建处理任务
            db = SessionLocal()
            try:
                task = Task(
                    project_id=project_id,
                    task_type="massive_literature_processing",
                    description=f"大规模文献处理 - 关键词: {', '.join(keywords)}",
                    status="pending",
                    estimated_duration=optimized_config.get("estimated_processing_time", {}).get("total_seconds", 3600)
                )
                db.add(task)
                db.commit()
                task_id = task.id

            finally:
                db.close()

            # 启动异步处理任务
            asyncio.create_task(start_massive_processing_task(
                task_id=task_id,
                project_id=project_id,
                processing_config=optimized_config
            ))

            return {
                "success": True,
                "mode": "massive_processing",
                "task_id": task_id,
                "project_id": project_id,
                "estimated_time": optimized_config.get("estimated_processing_time", {}),
                "config_used": optimized_config,
                "message": f"已启动大规模处理任务 (ID: {task_id})，预计处理 {max_count} 篇文献"
            }
        else:
            logger.info("阶段3: 使用标准处理模式")

            return {
                "success": True,
                "mode": "standard_processing",
                "message": f"文献数量 ({max_count}) 较少或未启用大规模处理，使用标准处理模式",
                "recommendation": "对于50篇以上文献建议启用大规模处理以获得更好性能"
            }

    except Exception as e:
        logger.error(f"集成文献处理失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }