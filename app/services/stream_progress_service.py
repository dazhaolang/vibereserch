"""
实时进度流服务 - 支持MCP服务器和Web前端的进度推送
"""

import asyncio
import json
import sys
import time
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator
from datetime import datetime
from loguru import logger
from dataclasses import dataclass, asdict
import uuid

@dataclass
class ProgressEvent:
    """进度事件数据结构"""
    id: str
    task_id: str
    task_name: str
    progress: int
    message: str
    timestamp: str
    status: str = "running"  # running, completed, failed, paused
    stage: str = "unknown"  # collection, structuring, experience, interaction
    sub_progress: Optional[Dict] = None  # 细粒度进度信息
    results_data: Optional[Dict] = None  # 阶段结果数据
    extra_data: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

@dataclass 
class LiteratureMetadata:
    """文献元数据结构"""
    id: int
    title: str
    authors: List[str]
    journal: str
    year: int
    doi: Optional[str]
    abstract: str
    keywords: List[str]
    citation_count: Optional[int] = None
    quality_score: Optional[float] = None
    pdf_available: bool = False
    
@dataclass
class WorkflowStage:
    """工作流阶段定义"""
    name: str
    display_name: str
    description: str
    estimated_duration: int  # 秒
    sub_steps: List[str]
    is_interactive: bool = False

class StreamProgressService:
    """实时进度流服务"""
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict] = {}
        self.subscribers: Dict[str, List[Callable]] = {}  # task_id -> [callback_functions]
        self.event_history: Dict[str, List[ProgressEvent]] = {}
        self.max_history_per_task = 50
        self.websocket_broadcast = None  # WebSocket广播函数，由WebSocket模块设置
        
        # 定义工作流阶段
        self.workflow_stages = {
            "collection": WorkflowStage(
                name="collection",
                display_name="文献采集",
                description="搜索和采集相关科研文献",
                estimated_duration=180,  # 3分钟
                sub_steps=[
                    "初始化搜索参数",
                    "连接ResearchRabbit API", 
                    "执行文献搜索",
                    "质量筛选和排序",
                    "下载文献元数据",
                    "保存到数据库"
                ]
            ),
            "structuring": WorkflowStage(
                name="structuring", 
                display_name="轻结构化处理",
                description="将文献转换为结构化数据",
                estimated_duration=300,  # 5分钟
                sub_steps=[
                    "生成模板",
                    "PDF文本提取", 
                    "AI结构化分析",
                    "数据验证",
                    "保存结构化结果"
                ]
            ),
            "experience": WorkflowStage(
                name="experience",
                display_name="经验生成", 
                description="基于文献生成研究经验",
                estimated_duration=240,  # 4分钟
                sub_steps=[
                    "迭代轮次1",
                    "迭代轮次2", 
                    "迭代轮次3",
                    "经验汇总",
                    "质量评估"
                ]
            ),
            "interaction": WorkflowStage(
                name="interaction",
                display_name="智能交互",
                description="Claude Code处理用户问题", 
                estimated_duration=120,  # 2分钟
                sub_steps=[
                    "问题分析",
                    "知识检索",
                    "答案生成", 
                    "结果验证"
                ],
                is_interactive=True
            )
        }
    
    async def create_workflow_task(
        self, 
        task_id: str, 
        task_name: str, 
        workflow_stages: List[str],
        initial_data: Optional[Dict] = None
    ) -> str:
        """创建完整工作流任务"""
        stream_id = str(uuid.uuid4())
        
        total_duration = sum(self.workflow_stages[stage].estimated_duration for stage in workflow_stages)
        
        self.active_tasks[task_id] = {
            "stream_id": stream_id,
            "task_name": task_name,
            "workflow_stages": workflow_stages,
            "current_stage": 0,
            "current_step": 0,
            "total_duration": total_duration,
            "status": "pending",
            "stage_results": {},  # 每个阶段的结果
            "literature_metadata": [],  # 文献元数据
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            **(initial_data or {})
        }
        
        self.subscribers[task_id] = []
        self.event_history[task_id] = []
        
        logger.info(f"Created workflow task: {task_id} - {task_name} with stages: {workflow_stages}")
        return stream_id
    
    async def update_stage_progress(
        self, 
        task_id: str, 
        stage: str,
        step_progress: int, 
        message: str,
        sub_progress: Optional[Dict] = None,
        results_data: Optional[Dict] = None,
        status: str = "running"
    ) -> ProgressEvent:
        """更新阶段内的细粒度进度"""
        
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return None
        
        task_data = self.active_tasks[task_id]
        stage_info = self.workflow_stages.get(stage, self.workflow_stages["collection"])
        
        # 计算总体进度
        stages = task_data["workflow_stages"]
        current_stage_index = stages.index(stage) if stage in stages else 0
        
        # 每个阶段占总进度的权重
        stage_weight = 100 / len(stages)
        overall_progress = int(current_stage_index * stage_weight + (step_progress / 100) * stage_weight)
        
        # 创建详细的子进度信息
        detailed_sub_progress = {
            "stage": stage,
            "stage_display_name": stage_info.display_name,
            "step_progress": step_progress,
            "current_step": message,
            "total_steps": len(stage_info.sub_steps),
            "completed_steps": int((step_progress / 100) * len(stage_info.sub_steps)),
            **(sub_progress or {})
        }
        
        # 创建进度事件
        event = ProgressEvent(
            id=str(uuid.uuid4()),
            task_id=task_id,
            task_name=task_data["task_name"],
            progress=overall_progress,
            message=message,
            timestamp=datetime.now().isoformat(),
            status=status,
            stage=stage,
            sub_progress=detailed_sub_progress,
            results_data=results_data
        )
        
        # 更新任务状态
        task_data.update({
            "current_stage": current_stage_index,
            "current_step": step_progress,
            "status": status,
            "updated_at": event.timestamp,
            "last_message": message
        })
        
        # 保存阶段结果
        if results_data:
            if "stage_results" not in task_data:
                task_data["stage_results"] = {}
            task_data["stage_results"][stage] = results_data
            
            # 特别处理文献元数据
            if stage == "collection" and "literature_list" in results_data:
                task_data["literature_metadata"] = results_data["literature_list"]
        
        # 保存到历史记录并通知订阅者
        if task_id in self.event_history:
            self.event_history[task_id].append(event)
            if len(self.event_history[task_id]) > self.max_history_per_task:
                self.event_history[task_id] = self.event_history[task_id][-self.max_history_per_task:]
        
        await self._notify_subscribers(task_id, event)
        await self._send_to_stderr(event)
        
        return event
    
    async def complete_stage(
        self, 
        task_id: str, 
        stage: str,
        results_data: Dict,
        final_message: str = None
    ) -> ProgressEvent:
        """完成一个阶段"""
        message = final_message or f"{self.workflow_stages[stage].display_name}完成"
        return await self.update_stage_progress(
            task_id, stage, 100, message, 
            results_data=results_data, 
            status="stage_completed"
        )
    
    async def get_literature_metadata(self, task_id: str) -> List[Dict]:
        """获取文献元数据列表"""
        if task_id not in self.active_tasks:
            return []
        
        return self.active_tasks[task_id].get("literature_metadata", [])
    
    async def update_literature_citations(
        self, 
        task_id: str, 
        literature_id: int, 
        citations: Dict
    ):
        """更新文献引用信息（懒加载）"""
        if task_id in self.active_tasks:
            literature_list = self.active_tasks[task_id].get("literature_metadata", [])
            for lit in literature_list:
                if lit.get("id") == literature_id:
                    lit.update({
                        "citations": citations.get("citations", []),
                        "references": citations.get("references", []),
                        "citation_graph": citations.get("citation_graph", {}),
                        "citations_loaded": True
                    })
                    break
        
    async def create_task_stream(self, task_id: str, task_name: str, estimated_steps: int = 100) -> str:
        """创建任务进度流"""
        stream_id = str(uuid.uuid4())
        
        self.active_tasks[task_id] = {
            "stream_id": stream_id,
            "task_name": task_name,
            "estimated_steps": estimated_steps,
            "current_step": 0,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.subscribers[task_id] = []
        self.event_history[task_id] = []
        
        logger.info(f"Created task stream: {task_id} - {task_name}")
        return stream_id
    
    async def update_progress(
        self, 
        task_id: str, 
        progress: int, 
        message: str, 
        status: str = "running",
        extra_data: Optional[Dict] = None
    ) -> ProgressEvent:
        """更新任务进度"""
        
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found, creating new stream")
            await self.create_task_stream(task_id, "Unknown Task")
        
        # 创建进度事件
        event = ProgressEvent(
            id=str(uuid.uuid4()),
            task_id=task_id,
            task_name=self.active_tasks[task_id]["task_name"],
            progress=min(100, max(0, progress)),
            message=message,
            timestamp=datetime.now().isoformat(),
            status=status,
            extra_data=extra_data
        )
        
        # 更新任务状态
        self.active_tasks[task_id].update({
            "current_step": progress,
            "status": status,
            "updated_at": event.timestamp,
            "last_message": message
        })
        
        # 保存到历史记录
        if task_id in self.event_history:
            self.event_history[task_id].append(event)
            # 限制历史记录数量
            if len(self.event_history[task_id]) > self.max_history_per_task:
                self.event_history[task_id] = self.event_history[task_id][-self.max_history_per_task:]
        
        # 通知订阅者
        await self._notify_subscribers(task_id, event)
        
        # 发送到stderr供Claude Code查看
        await self._send_to_stderr(event)
        
        return event

    async def broadcast_task_update(self, task_id: int, update_data: dict):
        """广播任务更新 - 兼容新的异步任务架构"""
        task_id_str = str(task_id)
        
        message_type = update_data.get("type", "progress")
        progress = update_data.get("progress", 0)
        current_step = update_data.get("current_step", "处理中...")
        
        # 根据消息类型确定状态
        if message_type == "task_started":
            status = "running"
        elif message_type == "task_completed":
            status = "completed"
        elif message_type == "task_failed":
            status = "failed"
        else:
            status = "running"
        
        # 如果任务不存在，先创建
        if task_id_str not in self.active_tasks:
            await self.create_task_stream(task_id_str, f"Task {task_id}", 100)
        
        # 更新进度
        await self.update_progress(
            task_id_str,
            progress,
            current_step,
            status,
            update_data
        )
    
    async def broadcast_project_update(self, project_id: int, update_data: dict):
        """广播项目更新 - 用于索引构建等项目级别的任务"""
        project_task_id = f"project_{project_id}"
        
        message_type = update_data.get("type", "progress")
        progress = update_data.get("progress", 0)
        
        if message_type == "indexing_started":
            current_step = "开始构建索引..."
            status = "running"
            # 创建项目级别的任务流
            await self.create_task_stream(project_task_id, f"项目 {project_id} 索引构建", 100)
        elif message_type == "indexing_progress":
            current_step = f"索引构建中 ({progress}%)"
            status = "running"
        elif message_type == "indexing_completed":
            current_step = "索引构建完成"
            status = "completed"
            progress = 100
        elif message_type == "indexing_failed":
            current_step = f"索引构建失败: {update_data.get('error', '未知错误')}"
            status = "failed"
        else:
            current_step = "处理中..."
            status = "running"
        
        # 如果任务不存在，先创建
        if project_task_id not in self.active_tasks:
            await self.create_task_stream(project_task_id, f"项目 {project_id} 索引构建", 100)
        
        # 更新进度
        await self.update_progress(
            project_task_id,
            progress,
            current_step,
            status,
            update_data
        )
    
    async def subscribe_to_task(self, task_id: str, callback: Callable[[ProgressEvent], None]):
        """订阅任务进度更新"""
        if task_id not in self.subscribers:
            self.subscribers[task_id] = []
        
        self.subscribers[task_id].append(callback)
        logger.info(f"Added subscriber to task {task_id}")
    
    async def unsubscribe_from_task(self, task_id: str, callback: Callable):
        """取消订阅任务进度"""
        if task_id in self.subscribers and callback in self.subscribers[task_id]:
            self.subscribers[task_id].remove(callback)
            logger.info(f"Removed subscriber from task {task_id}")
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self.active_tasks.get(task_id)
    
    async def get_task_history(self, task_id: str, limit: int = 20) -> List[Dict]:
        """获取任务历史事件"""
        if task_id not in self.event_history:
            return []
        
        events = self.event_history[task_id][-limit:]
        return [event.to_dict() for event in events]
    
    async def complete_task(self, task_id: str, final_message: str = "任务完成") -> ProgressEvent:
        """完成任务"""
        return await self.update_progress(task_id, 100, final_message, "completed")
    
    async def fail_task(self, task_id: str, error_message: str) -> ProgressEvent:
        """任务失败"""
        return await self.update_progress(task_id, -1, f"任务失败: {error_message}", "failed")
    
    async def pause_task(self, task_id: str, pause_message: str = "任务暂停") -> ProgressEvent:
        """暂停任务"""
        current_progress = self.active_tasks.get(task_id, {}).get("current_step", 0)
        return await self.update_progress(task_id, current_progress, pause_message, "paused")
    
    async def resume_task(self, task_id: str, resume_message: str = "任务恢复") -> ProgressEvent:
        """恢复任务"""
        current_progress = self.active_tasks.get(task_id, {}).get("current_step", 0)
        return await self.update_progress(task_id, current_progress, resume_message, "running")
    
    async def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """清理已完成的旧任务"""
        current_time = datetime.now()
        to_remove = []
        
        for task_id, task_data in self.active_tasks.items():
            if task_data["status"] in ["completed", "failed"]:
                updated_time = datetime.fromisoformat(task_data["updated_at"])
                age_hours = (current_time - updated_time).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.active_tasks[task_id]
            if task_id in self.subscribers:
                del self.subscribers[task_id]
            if task_id in self.event_history:
                del self.event_history[task_id]
            
            logger.info(f"Cleaned up old task: {task_id}")
    
    async def get_all_active_tasks(self) -> Dict[str, Dict]:
        """获取所有活动任务"""
        return {
            task_id: task_data 
            for task_id, task_data in self.active_tasks.items() 
            if task_data["status"] in ["pending", "running", "paused"]
        }
    
    async def _notify_subscribers(self, task_id: str, event: ProgressEvent):
        """通知订阅者"""
        if task_id in self.subscribers:
            for callback in self.subscribers[task_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"Error notifying subscriber: {e}")
        
        # 广播到WebSocket连接（如果已配置）
        if hasattr(self, 'websocket_broadcast') and self.websocket_broadcast:
            try:
                await self.websocket_broadcast(event)
            except Exception as e:
                logger.error(f"WebSocket broadcast failed: {e}")
    
    async def _send_to_stderr(self, event: ProgressEvent):
        """发送详细进度到stderr供Claude Code查看"""
        try:
            stage_info = self.workflow_stages.get(event.stage, self.workflow_stages["collection"])
            
            if event.status == "failed":
                progress_msg = f"[❌ ERROR] {event.stage.upper()}: {event.message}"
            elif event.status == "stage_completed":
                progress_msg = f"[✅ COMPLETED] {stage_info.display_name}: {event.message}"
            elif event.status == "running":
                # 细粒度进度信息
                sub_progress = event.sub_progress or {}
                step_progress = sub_progress.get("step_progress", 0)
                completed_steps = sub_progress.get("completed_steps", 0)
                total_steps = sub_progress.get("total_steps", 1)
                
                # 特殊处理不同阶段
                if event.stage == "collection":
                    if "literature_found" in sub_progress:
                        found = sub_progress["literature_found"]
                        target = sub_progress.get("target_count", "未知")
                        progress_msg = f"[📚 COLLECTING] 文献采集: 已找到 {found} 篇，目标 {target} 篇 ({step_progress}%)"
                    else:
                        progress_msg = f"[📚 COLLECTING] {event.message} ({step_progress}% - {completed_steps}/{total_steps})"
                        
                elif event.stage == "structuring":
                    if "processed_count" in sub_progress and "total_count" in sub_progress:
                        processed = sub_progress["processed_count"]
                        total = sub_progress["total_count"]
                        progress_msg = f"[⚙️ STRUCTURING] 轻结构化: 已完成 {processed}/{total} 篇 ({step_progress}%)"
                    else:
                        progress_msg = f"[⚙️ STRUCTURING] {event.message} ({step_progress}%)"
                        
                elif event.stage == "experience":
                    if "iteration_round" in sub_progress:
                        iteration = sub_progress["iteration_round"]
                        info_gain = sub_progress.get("information_gain", 0)
                        progress_msg = f"[🧠 EXPERIENCE] 经验生成: 第 {iteration} 轮, 信息增益 {info_gain:.1%} ({step_progress}%)"
                    else:
                        progress_msg = f"[🧠 EXPERIENCE] {event.message} ({step_progress}%)"
                        
                elif event.stage == "interaction":
                    if "claude_thinking" in sub_progress:
                        thinking = sub_progress["claude_thinking"][:100] + "..." if len(sub_progress["claude_thinking"]) > 100 else sub_progress["claude_thinking"]
                        progress_msg = f"[🤔 CLAUDE] {thinking}"
                    else:
                        progress_msg = f"[🤔 INTERACTION] {event.message} ({step_progress}%)"
                else:
                    progress_msg = f"[🔄 {event.stage.upper()}] {event.message} ({step_progress}%)"
            else:
                progress_msg = f"[📊 {event.stage.upper()}] {event.message}"
            
            # 如果有结果数据，追加关键信息
            if event.results_data:
                if event.stage == "collection" and "literature_list" in event.results_data:
                    count = len(event.results_data["literature_list"])
                    progress_msg += f" | 📄 {count} 篇文献已加载"
                elif event.stage == "structuring" and "success_count" in event.results_data:
                    success = event.results_data["success_count"]
                    failed = event.results_data.get("failed_count", 0)
                    progress_msg += f" | ✅ {success} 成功, ❌ {failed} 失败"
                elif event.stage == "experience" and "experience_quality" in event.results_data:
                    quality = event.results_data["experience_quality"]
                    progress_msg += f" | 📈 质量评分: {quality:.1f}/10"
            
            print(progress_msg, file=sys.stderr, flush=True)
            
        except Exception as e:
            logger.error(f"Error sending to stderr: {e}")
            print(f"[❌ SYSTEM] Progress reporting error: {str(e)}", file=sys.stderr, flush=True)

    def get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().isoformat()
    
    async def get_project_active_tasks(self, project_id: str) -> List[Dict]:
        """获取项目相关的活动任务"""
        project_tasks = []
        for task_id, task_data in self.active_tasks.items():
            # 如果任务数据中包含project_id信息，匹配该项目
            if task_data.get("project_id") == project_id:
                project_tasks.append({
                    "task_id": task_id,
                    "task_name": task_data.get("task_name", "Unknown Task"),
                    "status": task_data.get("status", "unknown"),
                    "stage": task_data.get("current_stage", "unknown"),
                    "progress": task_data.get("progress", 0),
                    "created_at": task_data.get("created_at", ""),
                    "updated_at": task_data.get("updated_at", "")
                })
        return project_tasks

class MCPProgressCallback:
    """MCP进度回调适配器"""
    
    def __init__(self, stream_service: StreamProgressService, task_id: str):
        self.stream_service = stream_service
        self.task_id = task_id
        
    async def __call__(self, message: str, progress: int, extra_data: Optional[Dict] = None):
        """进度回调函数"""
        await self.stream_service.update_progress(
            self.task_id, 
            progress, 
            message, 
            extra_data=extra_data
        )

# 全局实例
stream_progress_service = StreamProgressService()

def create_mcp_progress_callback(task_id: str) -> MCPProgressCallback:
    """创建MCP进度回调"""
    return MCPProgressCallback(stream_progress_service, task_id)

async def start_background_cleanup():
    """启动后台清理任务"""
    while True:
        try:
            await stream_progress_service.cleanup_completed_tasks()
            await asyncio.sleep(3600)  # 每小时清理一次
        except Exception as e:
            logger.error(f"Background cleanup error: {e}")
            await asyncio.sleep(3600)

# WebSocket连接管理
class WSProgressManager:
    """WebSocket进度管理器"""
    
    def __init__(self, stream_service: StreamProgressService):
        self.stream_service = stream_service
        self.websocket_connections: Dict[str, List] = {}  # task_id -> [websockets]
    
    async def add_websocket_subscriber(self, task_id: str, websocket):
        """添加WebSocket订阅者"""
        if task_id not in self.websocket_connections:
            self.websocket_connections[task_id] = []
        
        self.websocket_connections[task_id].append(websocket)
        
        # 创建回调函数
        async def websocket_callback(event: ProgressEvent):
            try:
                await websocket.send_text(event.to_json())
            except Exception as e:
                logger.error(f"WebSocket send error: {e}")
                # 移除失效的连接
                if websocket in self.websocket_connections.get(task_id, []):
                    self.websocket_connections[task_id].remove(websocket)
        
        # 订阅进度更新
        await self.stream_service.subscribe_to_task(task_id, websocket_callback)
        
        # 发送历史事件
        history = await self.stream_service.get_task_history(task_id, 5)
        for event_dict in history:
            try:
                await websocket.send_text(json.dumps(event_dict, ensure_ascii=False))
            except:
                pass
    
    async def remove_websocket_subscriber(self, task_id: str, websocket):
        """移除WebSocket订阅者"""
        if task_id in self.websocket_connections:
            if websocket in self.websocket_connections[task_id]:
                self.websocket_connections[task_id].remove(websocket)

# 创建全局WebSocket管理器
ws_progress_manager = WSProgressManager(stream_progress_service)