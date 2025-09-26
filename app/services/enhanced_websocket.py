"""
增强的WebSocket实时通信服务
支持房间、频道、心跳检测、消息重传等高级功能
"""

import asyncio
import json
import time
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from datetime import datetime, timedelta
import hashlib


class MessageType(Enum):
    """消息类型枚举"""
    SYSTEM = "system"
    PROGRESS = "progress"
    NOTIFICATION = "notification"
    CHAT = "chat"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    DATA = "data"
    COMMAND = "command"


class ChannelType(Enum):
    """频道类型枚举"""
    GLOBAL = "global"
    PROJECT = "project"
    TASK = "task"
    USER = "user"
    COLLABORATION = "collaboration"


@dataclass
class WebSocketMessage:
    """WebSocket消息数据类"""
    type: MessageType
    channel: str
    data: Any
    timestamp: float = None
    message_id: str = None
    sender_id: Optional[str] = None
    require_ack: bool = False

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.message_id is None:
            # 生成唯一消息ID
            content = f"{self.type.value}_{self.channel}_{self.timestamp}"
            self.message_id = hashlib.md5(content.encode()).hexdigest()[:12]

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps({
            "type": self.type.value,
            "channel": self.channel,
            "data": self.data,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "require_ack": self.require_ack
        })


@dataclass
class WebSocketClient:
    """WebSocket客户端信息"""
    client_id: str
    websocket: WebSocket
    user_id: Optional[int] = None
    channels: Set[str] = None
    last_heartbeat: float = None
    connected_at: float = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.channels is None:
            self.channels = set()
        if self.connected_at is None:
            self.connected_at = time.time()
        if self.last_heartbeat is None:
            self.last_heartbeat = time.time()
        if self.metadata is None:
            self.metadata = {}


class EnhancedWebSocketManager:
    """增强的WebSocket管理器"""

    def __init__(self):
        # 客户端管理
        self.clients: Dict[str, WebSocketClient] = {}
        # 频道订阅管理
        self.channels: Dict[str, Set[str]] = {}
        # 用户到客户端映射
        self.user_clients: Dict[int, Set[str]] = {}
        # 消息队列（用于离线消息）
        self.message_queue: Dict[str, List[WebSocketMessage]] = {}
        # 消息确认跟踪
        self.pending_acks: Dict[str, WebSocketMessage] = {}
        # 心跳配置
        self.heartbeat_interval = 30  # 秒
        self.heartbeat_timeout = 60  # 秒
        # 启动心跳检查任务
        self._heartbeat_task = None

    async def connect_client(
        self,
        websocket: WebSocket,
        client_id: str,
        user_id: Optional[int] = None,
        initial_channels: List[str] = None
    ) -> WebSocketClient:
        """连接客户端"""
        await websocket.accept()

        # 创建客户端实例
        client = WebSocketClient(
            client_id=client_id,
            websocket=websocket,
            user_id=user_id
        )

        # 注册客户端
        self.clients[client_id] = client

        # 注册用户映射
        if user_id:
            if user_id not in self.user_clients:
                self.user_clients[user_id] = set()
            self.user_clients[user_id].add(client_id)

        # 订阅初始频道
        if initial_channels:
            for channel in initial_channels:
                await self.subscribe_channel(client_id, channel)
        else:
            # 默认订阅全局频道
            await self.subscribe_channel(client_id, "global")

        # 发送连接成功消息
        await self.send_to_client(
            client_id,
            WebSocketMessage(
                type=MessageType.SYSTEM,
                channel="system",
                data={
                    "event": "connected",
                    "client_id": client_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        )

        # 发送离线消息
        await self._deliver_queued_messages(client_id)

        logger.info(f"WebSocket客户端连接: client_id={client_id}, user_id={user_id}")
        return client

    async def disconnect_client(self, client_id: str):
        """断开客户端连接"""
        if client_id not in self.clients:
            return

        client = self.clients[client_id]

        # 从所有频道取消订阅
        for channel in list(client.channels):
            await self.unsubscribe_channel(client_id, channel)

        # 移除用户映射
        if client.user_id and client.user_id in self.user_clients:
            self.user_clients[client.user_id].discard(client_id)
            if not self.user_clients[client.user_id]:
                del self.user_clients[client.user_id]

        # 移除客户端
        del self.clients[client_id]

        logger.info(f"WebSocket客户端断开: client_id={client_id}")

    async def subscribe_channel(self, client_id: str, channel: str):
        """订阅频道"""
        if client_id not in self.clients:
            return False

        client = self.clients[client_id]
        client.channels.add(channel)

        if channel not in self.channels:
            self.channels[channel] = set()
        self.channels[channel].add(client_id)

        logger.debug(f"客户端 {client_id} 订阅频道 {channel}")
        return True

    async def unsubscribe_channel(self, client_id: str, channel: str):
        """取消订阅频道"""
        if client_id not in self.clients:
            return False

        client = self.clients[client_id]
        client.channels.discard(channel)

        if channel in self.channels:
            self.channels[channel].discard(client_id)
            if not self.channels[channel]:
                del self.channels[channel]

        logger.debug(f"客户端 {client_id} 取消订阅频道 {channel}")
        return True

    async def send_to_client(self, client_id: str, message: WebSocketMessage) -> bool:
        """发送消息给特定客户端"""
        if client_id not in self.clients:
            # 客户端离线，加入队列
            await self._queue_message(client_id, message)
            return False

        client = self.clients[client_id]
        try:
            await client.websocket.send_text(message.to_json())

            # 如果需要确认，添加到待确认列表
            if message.require_ack:
                self.pending_acks[message.message_id] = message

            return True
        except Exception as e:
            logger.error(f"发送消息失败 client_id={client_id}: {e}")
            # 客户端可能已断开，清理连接
            await self.disconnect_client(client_id)
            # 消息加入队列
            await self._queue_message(client_id, message)
            return False

    async def send_to_channel(self, channel: str, message: WebSocketMessage):
        """发送消息给频道所有订阅者"""
        if channel not in self.channels:
            logger.debug(f"频道 {channel} 没有订阅者")
            return 0

        message.channel = channel
        success_count = 0
        failed_clients = []

        for client_id in self.channels[channel].copy():
            if await self.send_to_client(client_id, message):
                success_count += 1
            else:
                failed_clients.append(client_id)

        # 清理失败的客户端
        for client_id in failed_clients:
            await self.disconnect_client(client_id)

        return success_count

    async def send_to_user(self, user_id: int, message: WebSocketMessage) -> int:
        """发送消息给特定用户的所有客户端"""
        if user_id not in self.user_clients:
            # 用户离线，消息可以加入队列
            return 0

        success_count = 0
        for client_id in self.user_clients[user_id].copy():
            if await self.send_to_client(client_id, message):
                success_count += 1

        return success_count

    async def broadcast(self, message: WebSocketMessage):
        """广播消息给所有连接的客户端"""
        return await self.send_to_channel("global", message)

    async def handle_client_message(self, client_id: str, raw_message: str):
        """处理客户端发来的消息"""
        try:
            data = json.loads(raw_message)
            message_type = data.get("type", "data")

            # 处理心跳
            if message_type == "heartbeat":
                await self._handle_heartbeat(client_id)
                return

            # 处理消息确认
            if message_type == "ack":
                await self._handle_ack(data.get("message_id"))
                return

            # 处理订阅请求
            if message_type == "subscribe":
                channels = data.get("channels", [])
                for channel in channels:
                    await self.subscribe_channel(client_id, channel)
                return

            # 处理取消订阅
            if message_type == "unsubscribe":
                channels = data.get("channels", [])
                for channel in channels:
                    await self.unsubscribe_channel(client_id, channel)
                return

            # 转发消息到指定频道
            if message_type == "message":
                target_channel = data.get("channel", "global")
                forward_message = WebSocketMessage(
                    type=MessageType.CHAT,
                    channel=target_channel,
                    data=data.get("data"),
                    sender_id=client_id
                )
                await self.send_to_channel(target_channel, forward_message)

        except json.JSONDecodeError:
            logger.error(f"无效的JSON消息: {raw_message}")
        except Exception as e:
            logger.error(f"处理客户端消息失败: {e}")

    async def _handle_heartbeat(self, client_id: str):
        """处理心跳消息"""
        if client_id in self.clients:
            self.clients[client_id].last_heartbeat = time.time()
            # 回复心跳
            await self.send_to_client(
                client_id,
                WebSocketMessage(
                    type=MessageType.HEARTBEAT,
                    channel="system",
                    data={"status": "alive"}
                )
            )

    async def _handle_ack(self, message_id: str):
        """处理消息确认"""
        if message_id in self.pending_acks:
            del self.pending_acks[message_id]
            logger.debug(f"消息 {message_id} 已确认")

    async def _queue_message(self, client_id: str, message: WebSocketMessage):
        """将消息加入离线队列"""
        if client_id not in self.message_queue:
            self.message_queue[client_id] = []

        # 限制队列大小
        max_queue_size = 100
        if len(self.message_queue[client_id]) >= max_queue_size:
            self.message_queue[client_id].pop(0)

        self.message_queue[client_id].append(message)

    async def _deliver_queued_messages(self, client_id: str):
        """发送离线消息"""
        if client_id not in self.message_queue:
            return

        messages = self.message_queue[client_id]
        del self.message_queue[client_id]

        for message in messages:
            await self.send_to_client(client_id, message)

    async def check_heartbeats(self):
        """检查客户端心跳"""
        while True:
            try:
                current_time = time.time()
                disconnected_clients = []

                for client_id, client in self.clients.items():
                    if current_time - client.last_heartbeat > self.heartbeat_timeout:
                        logger.warning(f"客户端 {client_id} 心跳超时")
                        disconnected_clients.append(client_id)

                # 断开超时的客户端
                for client_id in disconnected_clients:
                    await self.disconnect_client(client_id)

                await asyncio.sleep(self.heartbeat_interval)

            except Exception as e:
                logger.error(f"心跳检查失败: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    async def start_heartbeat_monitor(self):
        """启动心跳监控"""
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self.check_heartbeats())
            logger.info("心跳监控已启动")

    async def stop_heartbeat_monitor(self):
        """停止心跳监控"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
            logger.info("心跳监控已停止")

    def get_stats(self) -> Dict[str, Any]:
        """获取WebSocket统计信息"""
        return {
            "total_clients": len(self.clients),
            "total_channels": len(self.channels),
            "total_users": len(self.user_clients),
            "pending_acks": len(self.pending_acks),
            "queued_messages": sum(len(msgs) for msgs in self.message_queue.values()),
            "channels": {
                channel: len(subscribers)
                for channel, subscribers in self.channels.items()
            }
        }


# 全局WebSocket管理器实例
enhanced_ws_manager = EnhancedWebSocketManager()


# 辅助函数
async def notify_task_progress(
    task_id: str,
    progress: int,
    status: str,
    message: str,
    details: Optional[Dict] = None
):
    """通知任务进度"""
    await enhanced_ws_manager.send_to_channel(
        f"task:{task_id}",
        WebSocketMessage(
            type=MessageType.PROGRESS,
            channel=f"task:{task_id}",
            data={
                "task_id": task_id,
                "progress": progress,
                "status": status,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    )


async def notify_project_update(
    project_id: int,
    event: str,
    data: Dict
):
    """通知项目更新"""
    await enhanced_ws_manager.send_to_channel(
        f"project:{project_id}",
        WebSocketMessage(
            type=MessageType.NOTIFICATION,
            channel=f"project:{project_id}",
            data={
                "project_id": project_id,
                "event": event,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    )


async def broadcast_system_notification(
    title: str,
    message: str,
    level: str = "info"
):
    """广播系统通知"""
    await enhanced_ws_manager.broadcast(
        WebSocketMessage(
            type=MessageType.NOTIFICATION,
            channel="global",
            data={
                "title": title,
                "message": message,
                "level": level,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    )