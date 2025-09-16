"""
进度可视化服务 - 实时任务进度跟踪和可视化
提供WebSocket实时更新、任务状态管理、进度统计
"""

import asyncio
import json
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
import uuid

from app.core.config import settings
from app.models.task import Task, TaskProgress, TaskType, TaskStatus
from app.models.project import Project
from app.models.user import User


class ProgressVisualizationService:
    """进度可视化服务"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # WebSocket连接管理
        self.active_connections: Dict[str, Any] = {}  # user_id -> websocket
        
        # 任务进度缓存
        self.progress_cache: Dict[int, Dict] = {}  # task_id -> progress_data
        
        # 进度更新回调
        self.progress_callbacks: Dict[int, List[Callable]] = {}  # task_id -> [callbacks]
        
        # 任务类型配置
        self.task_type_configs = {
            TaskType.LITERATURE_COLLECTION: {
                "name": "文献采集",
                "icon": "📚",
                "color": "#3B82F6",
                "stages": [
                    {"name": "初始化", "weight": 5},
                    {"name": "多源采集", "weight": 30},
                    {"name": "去重处理", "weight": 15},
                    {"name": "AI初筛", "weight": 35},
                    {"name": "最终整理", "weight": 15}
                ]
            },
            TaskType.LITERATURE_PROCESSING: {
                "name": "文献处理",
                "icon": "⚙️",
                "color": "#10B981",
                "stages": [
                    {"name": "PDF解析", "weight": 25},
                    {"name": "内容提取", "weight": 30},
                    {"name": "结构化处理", "weight": 35},
                    {"name": "质量评估", "weight": 10}
                ]
            },
            TaskType.EXPERIENCE_GENERATION: {
                "name": "经验增强",
                "icon": "🧠",
                "color": "#8B5CF6",
                "stages": [
                    {"name": "文献分组", "weight": 10},
                    {"name": "迭代生成", "weight": 70},
                    {"name": "质量评估", "weight": 15},
                    {"name": "结果保存", "weight": 5}
                ]
            },
            TaskType.MAIN_EXPERIENCE_CREATION: {
                "name": "主经验创建",
                "icon": "🏗️",
                "color": "#F59E0B",
                "stages": [
                    {"name": "分析文献", "weight": 20},
                    {"name": "创建主经验", "weight": 60},
                    {"name": "关联建立", "weight": 15},
                    {"name": "保存完成", "weight": 5}
                ]
            },
            TaskType.ANALYSIS: {
                "name": "智能分析",
                "icon": "🔍",
                "color": "#EF4444",
                "stages": [
                    {"name": "问题分析", "weight": 15},
                    {"name": "检索匹配", "weight": 25},
                    {"name": "AI生成", "weight": 45},
                    {"name": "结果优化", "weight": 15}
                ]
            }
        }
    
    async def create_task_with_progress(
        self,
        project: Project,
        task_type: TaskType,
        title: str,
        description: str = None,
        metadata: Dict = None
    ) -> Task:
        """
        创建带进度跟踪的任务
        
        Args:
            project: 项目对象
            task_type: 任务类型
            title: 任务标题
            description: 任务描述
            metadata: 任务元数据
            
        Returns:
            创建的任务对象
        """
        try:
            logger.info(f"创建任务: {title} - 类型: {task_type.value}")
            
            # 创建任务
            task = Task(
                project_id=project.id,
                task_type=task_type,
                title=title,
                description=description or f"{task_type.value}任务",
                status=TaskStatus.PENDING,
                metadata=metadata or {},
                created_at=datetime.utcnow()
            )
            
            self.db.add(task)
            self.db.flush()  # 获取task.id
            
            # 初始化进度记录
            initial_progress = TaskProgress(
                task_id=task.id,
                stage_name="初始化",
                progress_percentage=0.0,
                current_step="任务已创建",
                metadata={"created_at": datetime.utcnow().isoformat()}
            )
            
            self.db.add(initial_progress)
            self.db.commit()
            
            # 初始化进度缓存
            self.progress_cache[task.id] = {
                "task_id": task.id,
                "task_type": task_type.value,
                "title": title,
                "status": TaskStatus.PENDING.value,
                "progress_percentage": 0.0,
                "current_stage": "初始化",
                "current_step": "任务已创建",
                "stages": self.task_type_configs.get(task_type, {}).get("stages", []),
                "start_time": datetime.utcnow().isoformat(),
                "estimated_duration": None,
                "metadata": metadata or {}
            }
            
            # 通知WebSocket连接
            await self._notify_progress_update(project.owner_id, task.id)
            
            return task
            
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            self.db.rollback()
            raise
    
    async def update_task_progress(
        self,
        task_id: int,
        stage_name: str,
        progress_percentage: float,
        current_step: str = None,
        metadata: Dict = None
    ):
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            stage_name: 当前阶段名称
            progress_percentage: 进度百分比 (0-100)
            current_step: 当前步骤描述
            metadata: 额外元数据
        """
        try:
            # 获取任务
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return
            
            # 创建进度记录
            progress_record = TaskProgress(
                task_id=task_id,
                stage_name=stage_name,
                progress_percentage=progress_percentage,
                current_step=current_step or stage_name,
                metadata=metadata or {}
            )
            
            self.db.add(progress_record)
            
            # 更新任务状态
            if progress_percentage >= 100.0:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
            elif progress_percentage > 0:
                task.status = TaskStatus.RUNNING
            
            # 更新进度缓存
            if task_id in self.progress_cache:
                cache_data = self.progress_cache[task_id]
                cache_data.update({
                    "progress_percentage": progress_percentage,
                    "current_stage": stage_name,
                    "current_step": current_step or stage_name,
                    "status": task.status.value,
                    "last_update": datetime.utcnow().isoformat()
                })
                
                if metadata:
                    cache_data["metadata"].update(metadata)
                
                # 计算预估剩余时间
                if progress_percentage > 0:
                    cache_data["estimated_duration"] = self._calculate_estimated_duration(
                        cache_data, progress_percentage
                    )
            
            self.db.commit()
            
            # 通知进度更新
            project = self.db.query(Project).filter(Project.id == task.project_id).first()
            if project:
                await self._notify_progress_update(project.owner_id, task_id)
            
            # 调用注册的回调函数
            if task_id in self.progress_callbacks:
                for callback in self.progress_callbacks[task_id]:
                    try:
                        await callback(task_id, progress_percentage, stage_name, metadata)
                    except Exception as e:
                        logger.error(f"进度回调执行失败: {e}")
            
        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")
            self.db.rollback()
    
    async def get_task_progress_summary(self, project_id: int) -> Dict:
        """
        获取项目任务进度汇总
        
        Args:
            project_id: 项目ID
            
        Returns:
            进度汇总信息
        """
        try:
            # 获取项目所有任务
            tasks = self.db.query(Task).filter(
                Task.project_id == project_id
            ).order_by(desc(Task.created_at)).all()
            
            if not tasks:
                return {
                    "project_id": project_id,
                    "total_tasks": 0,
                    "active_tasks": 0,
                    "completed_tasks": 0,
                    "overall_progress": 0.0,
                    "tasks": []
                }
            
            # 统计任务状态
            total_tasks = len(tasks)
            completed_tasks = sum(1 for task in tasks if task.status == TaskStatus.COMPLETED)
            active_tasks = sum(1 for task in tasks if task.status == TaskStatus.RUNNING)
            
            # 计算整体进度
            total_progress = 0.0
            task_summaries = []
            
            for task in tasks:
                # 获取最新进度
                latest_progress = self.db.query(TaskProgress).filter(
                    TaskProgress.task_id == task.id
                ).order_by(desc(TaskProgress.created_at)).first()
                
                progress_percentage = latest_progress.progress_percentage if latest_progress else 0.0
                total_progress += progress_percentage
                
                # 获取任务配置
                task_config = self.task_type_configs.get(task.task_type, {})
                
                task_summary = {
                    "task_id": task.id,
                    "title": task.title,
                    "task_type": task.task_type.value,
                    "status": task.status.value,
                    "progress_percentage": progress_percentage,
                    "current_stage": latest_progress.stage_name if latest_progress else "待开始",
                    "current_step": latest_progress.current_step if latest_progress else "",
                    "created_at": task.created_at.isoformat(),
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "config": {
                        "name": task_config.get("name", task.task_type.value),
                        "icon": task_config.get("icon", "📋"),
                        "color": task_config.get("color", "#6B7280")
                    }
                }
                
                # 添加缓存数据
                if task.id in self.progress_cache:
                    cache_data = self.progress_cache[task.id]
                    task_summary.update({
                        "estimated_duration": cache_data.get("estimated_duration"),
                        "stages": cache_data.get("stages", [])
                    })
                
                task_summaries.append(task_summary)
            
            overall_progress = total_progress / total_tasks if total_tasks > 0 else 0.0
            
            return {
                "project_id": project_id,
                "total_tasks": total_tasks,
                "active_tasks": active_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": total_tasks - completed_tasks - active_tasks,
                "overall_progress": round(overall_progress, 1),
                "tasks": task_summaries,
                "last_update": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取任务进度汇总失败: {e}")
            return {"project_id": project_id, "error": str(e)}
    
    async def get_detailed_task_progress(self, task_id: int) -> Dict:
        """
        获取详细的任务进度信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            详细进度信息
        """
        try:
            # 获取任务基本信息
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return {"error": "任务不存在"}
            
            # 获取所有进度记录
            progress_records = self.db.query(TaskProgress).filter(
                TaskProgress.task_id == task_id
            ).order_by(TaskProgress.created_at).all()
            
            # 获取任务配置
            task_config = self.task_type_configs.get(task.task_type, {})
            
            # 构建详细信息
            detailed_info = {
                "task_id": task_id,
                "title": task.title,
                "description": task.description,
                "task_type": task.task_type.value,
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "config": {
                    "name": task_config.get("name", task.task_type.value),
                    "icon": task_config.get("icon", "📋"),
                    "color": task_config.get("color", "#6B7280"),
                    "stages": task_config.get("stages", [])
                },
                "progress_history": [],
                "current_progress": 0.0,
                "current_stage": "待开始",
                "current_step": "",
                "metadata": task.metadata or {}
            }
            
            # 处理进度历史
            for record in progress_records:
                progress_entry = {
                    "timestamp": record.created_at.isoformat(),
                    "stage_name": record.stage_name,
                    "progress_percentage": record.progress_percentage,
                    "current_step": record.current_step,
                    "metadata": record.metadata or {}
                }
                detailed_info["progress_history"].append(progress_entry)
            
            # 设置当前进度
            if progress_records:
                latest_record = progress_records[-1]
                detailed_info.update({
                    "current_progress": latest_record.progress_percentage,
                    "current_stage": latest_record.stage_name,
                    "current_step": latest_record.current_step
                })
            
            # 添加缓存数据
            if task_id in self.progress_cache:
                cache_data = self.progress_cache[task_id]
                detailed_info.update({
                    "estimated_duration": cache_data.get("estimated_duration"),
                    "performance_metrics": cache_data.get("performance_metrics", {})
                })
            
            return detailed_info
            
        except Exception as e:
            logger.error(f"获取详细任务进度失败: {e}")
            return {"error": str(e)}
    
    async def register_progress_callback(self, task_id: int, callback: Callable):
        """
        注册进度更新回调函数
        
        Args:
            task_id: 任务ID
            callback: 回调函数 async def callback(task_id, progress, stage, metadata)
        """
        if task_id not in self.progress_callbacks:
            self.progress_callbacks[task_id] = []
        
        self.progress_callbacks[task_id].append(callback)
        logger.info(f"为任务 {task_id} 注册进度回调")
    
    async def unregister_progress_callback(self, task_id: int, callback: Callable):
        """移除进度更新回调函数"""
        if task_id in self.progress_callbacks:
            try:
                self.progress_callbacks[task_id].remove(callback)
                if not self.progress_callbacks[task_id]:
                    del self.progress_callbacks[task_id]
            except ValueError:
                pass
    
    async def add_websocket_connection(self, user_id: int, websocket):
        """添加WebSocket连接"""
        self.active_connections[str(user_id)] = websocket
        logger.info(f"用户 {user_id} WebSocket连接已建立")
    
    async def remove_websocket_connection(self, user_id: int):
        """移除WebSocket连接"""
        user_key = str(user_id)
        if user_key in self.active_connections:
            del self.active_connections[user_key]
            logger.info(f"用户 {user_id} WebSocket连接已移除")
    
    async def _notify_progress_update(self, user_id: int, task_id: int):
        """通知进度更新"""
        try:
            user_key = str(user_id)
            if user_key in self.active_connections:
                websocket = self.active_connections[user_key]
                
                # 获取当前进度数据
                progress_data = self.progress_cache.get(task_id, {})
                
                # 构建通知消息
                notification = {
                    "type": "progress_update",
                    "task_id": task_id,
                    "data": progress_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # 发送WebSocket消息
                await websocket.send_text(json.dumps(notification, ensure_ascii=False))
                
        except Exception as e:
            logger.error(f"WebSocket通知失败: {e}")
            # 移除无效连接
            await self.remove_websocket_connection(user_id)
    
    def _calculate_estimated_duration(self, cache_data: Dict, current_progress: float) -> Optional[str]:
        """计算预估剩余时间"""
        try:
            start_time_str = cache_data.get("start_time")
            if not start_time_str or current_progress <= 0:
                return None
            
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            elapsed_time = datetime.utcnow() - start_time.replace(tzinfo=None)
            
            if current_progress >= 100:
                return "已完成"
            
            # 计算预估总时间
            estimated_total_seconds = (elapsed_time.total_seconds() / current_progress) * 100
            remaining_seconds = estimated_total_seconds - elapsed_time.total_seconds()
            
            if remaining_seconds <= 0:
                return "即将完成"
            
            # 格式化时间
            if remaining_seconds < 60:
                return f"{int(remaining_seconds)}秒"
            elif remaining_seconds < 3600:
                return f"{int(remaining_seconds / 60)}分钟"
            else:
                hours = int(remaining_seconds / 3600)
                minutes = int((remaining_seconds % 3600) / 60)
                return f"{hours}小时{minutes}分钟"
                
        except Exception as e:
            logger.error(f"计算预估时间失败: {e}")
            return None
    
    async def get_user_task_statistics(self, user_id: int) -> Dict:
        """
        获取用户任务统计信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户任务统计
        """
        try:
            # 获取用户所有项目的任务
            user_projects = self.db.query(Project).filter(Project.owner_id == user_id).all()
            project_ids = [p.id for p in user_projects]
            
            if not project_ids:
                return {
                    "user_id": user_id,
                    "total_tasks": 0,
                    "task_statistics": {},
                    "recent_activities": []
                }
            
            # 获取所有任务
            all_tasks = self.db.query(Task).filter(
                Task.project_id.in_(project_ids)
            ).all()
            
            # 按类型统计
            task_type_stats = {}
            status_stats = {status.value: 0 for status in TaskStatus}
            
            for task in all_tasks:
                task_type = task.task_type.value
                if task_type not in task_type_stats:
                    task_type_stats[task_type] = {
                        "total": 0,
                        "completed": 0,
                        "running": 0,
                        "failed": 0
                    }
                
                task_type_stats[task_type]["total"] += 1
                status_stats[task.status.value] += 1
                
                if task.status == TaskStatus.COMPLETED:
                    task_type_stats[task_type]["completed"] += 1
                elif task.status == TaskStatus.RUNNING:
                    task_type_stats[task_type]["running"] += 1
                elif task.status == TaskStatus.FAILED:
                    task_type_stats[task_type]["failed"] += 1
            
            # 获取最近活动
            recent_tasks = self.db.query(Task).filter(
                Task.project_id.in_(project_ids)
            ).order_by(desc(Task.created_at)).limit(10).all()
            
            recent_activities = []
            for task in recent_tasks:
                latest_progress = self.db.query(TaskProgress).filter(
                    TaskProgress.task_id == task.id
                ).order_by(desc(TaskProgress.created_at)).first()
                
                activity = {
                    "task_id": task.id,
                    "title": task.title,
                    "task_type": task.task_type.value,
                    "status": task.status.value,
                    "progress": latest_progress.progress_percentage if latest_progress else 0.0,
                    "created_at": task.created_at.isoformat(),
                    "project_name": next((p.name for p in user_projects if p.id == task.project_id), "未知项目")
                }
                recent_activities.append(activity)
            
            return {
                "user_id": user_id,
                "total_tasks": len(all_tasks),
                "task_type_statistics": task_type_stats,
                "status_statistics": status_stats,
                "recent_activities": recent_activities,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取用户任务统计失败: {e}")
            return {"user_id": user_id, "error": str(e)}
    
    async def cleanup_completed_tasks(self, days_old: int = 30):
        """
        清理旧的已完成任务进度记录
        
        Args:
            days_old: 保留天数
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # 删除旧的进度记录
            deleted_count = self.db.query(TaskProgress).filter(
                and_(
                    TaskProgress.created_at < cutoff_date,
                    TaskProgress.task.has(Task.status == TaskStatus.COMPLETED)
                )
            ).delete(synchronize_session=False)
            
            self.db.commit()
            
            logger.info(f"清理了 {deleted_count} 条旧的任务进度记录")
            
        except Exception as e:
            logger.error(f"清理任务记录失败: {e}")
            self.db.rollback()


# 创建进度更新装饰器
def with_progress_tracking(service_instance, task_id: int):
    """进度跟踪装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 注册进度回调
            async def progress_callback(stage: str, progress: float, metadata: Dict = None):
                await service_instance.update_task_progress(
                    task_id, stage, progress, metadata=metadata
                )
            
            # 将progress_callback添加到kwargs中
            kwargs['progress_callback'] = progress_callback
            
            try:
                # 执行原函数
                result = await func(*args, **kwargs)
                
                # 如果成功，设置为100%完成
                if result.get("success", True):
                    await progress_callback("完成", 100.0, {"result": "success"})
                else:
                    await service_instance.update_task_progress(
                        task_id, "失败", -1, metadata={"error": result.get("error", "未知错误")}
                    )
                
                return result
                
            except Exception as e:
                # 如果失败，标记任务失败
                await service_instance.update_task_progress(
                    task_id, "失败", -1, metadata={"error": str(e)}
                )
                raise
        
        return wrapper
    return decorator