"""
WebSocket API for real-time progress streaming
支持实时进度推送和任务状态更新
"""

import asyncio
import json
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.websockets import WebSocketState
from loguru import logger

from app.services.stream_progress_service import (
    stream_progress_service, 
    ws_progress_manager,
    ProgressEvent
)

router = APIRouter()

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.task_connections: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, task_id: str = None):
        """建立WebSocket连接"""
        await websocket.accept()
        
        # 全局连接池
        if "global" not in self.active_connections:
            self.active_connections["global"] = []
        self.active_connections["global"].append(websocket)
        
        # 任务特定连接池
        if task_id:
            if task_id not in self.task_connections:
                self.task_connections[task_id] = []
            self.task_connections[task_id].append(websocket)
            
            # 订阅任务进度更新
            await ws_progress_manager.add_websocket_subscriber(task_id, websocket)
            
        logger.info(f"WebSocket连接建立: task_id={task_id}, 总连接数={len(self.active_connections.get('global', []))}")
        
    async def disconnect(self, websocket: WebSocket, task_id: str = None):
        """断开WebSocket连接"""
        # 从全局连接池移除
        if "global" in self.active_connections:
            try:
                self.active_connections["global"].remove(websocket)
            except ValueError:
                pass
        
        # 从任务连接池移除
        if task_id and task_id in self.task_connections:
            try:
                self.task_connections[task_id].remove(websocket)
                if not self.task_connections[task_id]:
                    del self.task_connections[task_id]
            except ValueError:
                pass
            
            # 取消订阅
            await ws_progress_manager.remove_websocket_subscriber(task_id, websocket)
            
        logger.info(f"WebSocket连接断开: task_id={task_id}")
        
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """发送个人消息"""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(message)
        except Exception as e:
            logger.error(f"发送个人消息失败: {e}")
            
    async def send_to_task(self, task_id: str, message: str):
        """向特定任务的所有连接发送消息"""
        if task_id not in self.task_connections:
            return
            
        dead_connections = []
        for websocket in self.task_connections[task_id]:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message)
                else:
                    dead_connections.append(websocket)
            except Exception as e:
                logger.error(f"发送任务消息失败: {e}")
                dead_connections.append(websocket)
        
        # 清理死连接
        for dead_ws in dead_connections:
            await self.disconnect(dead_ws, task_id)
            
    async def broadcast(self, message: str):
        """广播消息给所有连接"""
        if "global" not in self.active_connections:
            return
            
        dead_connections = []
        for websocket in self.active_connections["global"]:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message)
                else:
                    dead_connections.append(websocket)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                dead_connections.append(websocket)
        
        # 清理死连接
        for dead_ws in dead_connections:
            await self.disconnect(dead_ws)

# 全局连接管理器
manager = ConnectionManager()

@router.websocket("/ws/progress/{task_id}")
async def websocket_progress_endpoint(
    websocket: WebSocket, 
    task_id: str,
    token: str = Query(None, description="认证令牌")
):
    """
    任务进度WebSocket端点
    提供实时进度更新、文献元数据、Claude输出流
    """
    
    # WebSocket认证 (简化处理，生产环境需要更严格的认证)
    user = None
    if token:
        try:
            # 验证token并获取用户信息
            from app.core.security import get_current_user_from_token
            from app.core.database import get_db
            
            db = next(get_db())
            try:
                user = await get_current_user_from_token(token, db)
                if not user:
                    await websocket.close(code=4001, reason="Invalid token")
                    return
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"WebSocket认证失败: {e}")
            await websocket.close(code=4001, reason="Authentication failed")
            return
    else:
        # 没有提供token，拒绝连接
        await websocket.close(code=4001, reason="Token required")
        return
    
    await manager.connect(websocket, task_id)
    
    try:
        # 发送连接确认消息
        welcome_message = {
            "type": "connection_established",
            "task_id": task_id,
            "timestamp": stream_progress_service.active_tasks.get(task_id, {}).get("created_at"),
            "message": "WebSocket连接已建立"
        }
        await manager.send_personal_message(json.dumps(welcome_message, ensure_ascii=False), websocket)
        
        # 发送历史进度事件
        try:
            history = await stream_progress_service.get_task_history(task_id, limit=10)
            if history:
                history_message = {
                    "type": "history_events",
                    "task_id": task_id,
                    "events": history
                }
                await manager.send_personal_message(
                    json.dumps(history_message, ensure_ascii=False), 
                    websocket
                )
        except Exception as e:
            logger.error(f"发送历史事件失败: {e}")
        
        # 发送当前任务状态
        try:
            task_status = await stream_progress_service.get_task_status(task_id)
            if task_status:
                status_message = {
                    "type": "task_status",
                    "task_id": task_id,
                    "status": task_status
                }
                await manager.send_personal_message(
                    json.dumps(status_message, ensure_ascii=False),
                    websocket
                )
        except Exception as e:
            logger.error(f"发送任务状态失败: {e}")
        
        # 保持连接活跃
        while True:
            try:
                # 等待客户端消息或保持连接
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # 处理客户端消息
                try:
                    message = json.loads(data)
                    await handle_client_message(websocket, task_id, message)
                except json.JSONDecodeError:
                    logger.warning(f"无效JSON消息: {data}")
                    
            except asyncio.TimeoutError:
                # 发送心跳
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": stream_progress_service.active_tasks.get(task_id, {}).get("updated_at")
                }
                await manager.send_personal_message(
                    json.dumps(heartbeat, ensure_ascii=False), 
                    websocket
                )
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket客户端断开连接: {task_id}")
    except Exception as e:
        logger.error(f"WebSocket连接异常: {e}")
    finally:
        await manager.disconnect(websocket, task_id)

async def handle_client_message(websocket: WebSocket, task_id: str, message: dict):
    """处理客户端发送的消息"""
    
    message_type = message.get("type")
    
    if message_type == "request_status":
        # 请求任务状态
        try:
            task_status = await stream_progress_service.get_task_status(task_id)
            response = {
                "type": "status_response",
                "task_id": task_id,
                "status": task_status
            }
            await manager.send_personal_message(
                json.dumps(response, ensure_ascii=False),
                websocket
            )
        except Exception as e:
            logger.error(f"处理状态请求失败: {e}")
            
    elif message_type == "request_literature":
        # 请求文献元数据
        try:
            literature_metadata = await stream_progress_service.get_literature_metadata(task_id)
            response = {
                "type": "literature_metadata",
                "task_id": task_id,
                "literature": literature_metadata
            }
            await manager.send_personal_message(
                json.dumps(response, ensure_ascii=False),
                websocket
            )
        except Exception as e:
            logger.error(f"处理文献请求失败: {e}")
            
    elif message_type == "ping":
        # 心跳响应
        pong = {
            "type": "pong",
            "timestamp": message.get("timestamp")
        }
        await manager.send_personal_message(
            json.dumps(pong, ensure_ascii=False),
            websocket
        )
    
    else:
        logger.warning(f"未知消息类型: {message_type}")

@router.websocket("/ws/project/{project_id}/status")
async def websocket_project_status_endpoint(
    websocket: WebSocket, 
    project_id: str,
    token: str = Query(None, description="认证令牌")
):
    """
    项目状态WebSocket端点
    提供项目级别的状态更新和通知
    """
    
    # WebSocket认证 (简化处理，生产环境需要更严格的认证)
    user = None
    if token:
        try:
            # 验证token并获取用户信息
            from app.core.security import get_current_user_from_token
            from app.core.database import get_db
            
            db = next(get_db())
            try:
                user = await get_current_user_from_token(token, db)
                if not user:
                    await websocket.close(code=4001, reason="Invalid token")
                    return
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"WebSocket认证失败: {e}")
            await websocket.close(code=4001, reason="Authentication failed")
            return
    else:
        # 没有提供token，拒绝连接
        await websocket.close(code=4001, reason="Token required")
        return
    
    # 为项目创建连接标识符
    connection_id = f"project_{project_id}"
    await manager.connect(websocket, connection_id)
    
    try:
        # 发送连接确认消息
        welcome_message = {
            "type": "connection_established",
            "project_id": project_id,
            "timestamp": stream_progress_service.get_current_timestamp(),
            "message": "项目状态WebSocket连接已建立"
        }
        await manager.send_personal_message(json.dumps(welcome_message, ensure_ascii=False), websocket)
        
        # 发送当前项目状态
        try:
            # 这里可以获取项目相关的活动任务
            project_tasks = await stream_progress_service.get_project_active_tasks(project_id)
            status_message = {
                "type": "project_status",
                "project_id": project_id,
                "active_tasks": project_tasks,
                "status": "connected"
            }
            await manager.send_personal_message(
                json.dumps(status_message, ensure_ascii=False),
                websocket
            )
        except Exception as e:
            logger.error(f"发送项目状态失败: {e}")
        
        # 保持连接活跃
        while True:
            try:
                # 等待客户端消息或保持连接
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # 处理客户端消息
                try:
                    message = json.loads(data)
                    await handle_project_client_message(websocket, project_id, message)
                except json.JSONDecodeError:
                    logger.warning(f"无效JSON消息: {data}")
                    
            except asyncio.TimeoutError:
                # 发送心跳
                heartbeat = {
                    "type": "heartbeat",
                    "project_id": project_id,
                    "timestamp": stream_progress_service.get_current_timestamp()
                }
                await manager.send_personal_message(
                    json.dumps(heartbeat, ensure_ascii=False), 
                    websocket
                )
                
    except WebSocketDisconnect:
        logger.info(f"项目WebSocket客户端断开连接: project_id={project_id}")
    except Exception as e:
        logger.error(f"项目WebSocket连接异常: {e}")
    finally:
        await manager.disconnect(websocket, connection_id)

async def handle_project_client_message(websocket: WebSocket, project_id: str, message: dict):
    """处理项目WebSocket客户端发送的消息"""
    
    message_type = message.get("type")
    
    if message_type == "request_project_status":
        # 请求项目状态
        try:
            project_tasks = await stream_progress_service.get_project_active_tasks(project_id)
            response = {
                "type": "project_status_response",
                "project_id": project_id,
                "active_tasks": project_tasks,
                "status": "active" if project_tasks else "idle"
            }
            await manager.send_personal_message(
                json.dumps(response, ensure_ascii=False),
                websocket
            )
        except Exception as e:
            logger.error(f"处理项目状态请求失败: {e}")
            
    elif message_type == "ping":
        # 心跳响应
        pong = {
            "type": "pong",
            "project_id": project_id,
            "timestamp": message.get("timestamp")
        }
        await manager.send_personal_message(
            json.dumps(pong, ensure_ascii=False),
            websocket
        )
    
    else:
        logger.warning(f"未知项目消息类型: {message_type}")

@router.websocket("/ws/global")
async def websocket_global_endpoint(
    websocket: WebSocket,
    token: str = Query(None, description="认证令牌")
):
    """
    全局WebSocket端点
    用于系统级通知和管理
    """
    
    await manager.connect(websocket)
    
    try:
        # 发送连接确认
        welcome = {
            "type": "global_connection_established",
            "message": "全局WebSocket连接已建立"
        }
        await manager.send_personal_message(json.dumps(welcome, ensure_ascii=False), websocket)
        
        # 发送活动任务列表
        active_tasks = await stream_progress_service.get_all_active_tasks()
        tasks_message = {
            "type": "active_tasks",
            "tasks": active_tasks
        }
        await manager.send_personal_message(
            json.dumps(tasks_message, ensure_ascii=False),
            websocket
        )
        
        # 保持连接
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                message = json.loads(data)
                
                # 处理全局消息
                if message.get("type") == "subscribe_task":
                    task_id = message.get("task_id")
                    if task_id:
                        await ws_progress_manager.add_websocket_subscriber(task_id, websocket)
                        
            except asyncio.TimeoutError:
                # 全局心跳
                heartbeat = {
                    "type": "global_heartbeat",
                    "active_tasks_count": len(await stream_progress_service.get_all_active_tasks())
                }
                await manager.send_personal_message(
                    json.dumps(heartbeat, ensure_ascii=False),
                    websocket
                )
                
    except WebSocketDisconnect:
        logger.info("全局WebSocket客户端断开连接")
    except Exception as e:
        logger.error(f"全局WebSocket连接异常: {e}")
    finally:
        await manager.disconnect(websocket)

@router.get("/ws/tasks")
async def get_active_websocket_tasks():
    """获取当前活动的WebSocket任务"""
    return {
        "active_connections": len(manager.active_connections.get("global", [])),
        "task_connections": {
            task_id: len(connections) 
            for task_id, connections in manager.task_connections.items()
        },
        "active_tasks": await stream_progress_service.get_all_active_tasks()
    }

# 在stream_progress_service中集成WebSocket通知
async def broadcast_progress_event(event: ProgressEvent):
    """广播进度事件到WebSocket客户端"""
    try:
        message = {
            "type": "progress_event",
            "event": event.to_dict()
        }
        message_str = json.dumps(message, ensure_ascii=False)
        
        # 向任务特定连接发送
        await manager.send_to_task(event.task_id, message_str)
        
    except Exception as e:
        logger.error(f"广播进度事件失败: {e}")

# 注册广播函数到进度服务
stream_progress_service.websocket_broadcast = broadcast_progress_event

@router.websocket("/ws/intelligent-interaction/{session_id}")
async def websocket_intelligent_interaction_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(None, description="认证令牌")
):
    """
    智能交互WebSocket端点
    提供实时智能交互事件推送和状态同步
    """

    # WebSocket认证
    user = None
    if token:
        try:
            from app.core.security import get_current_user_from_token
            from app.core.database import get_db

            db = next(get_db())
            try:
                user = await get_current_user_from_token(token, db)
                if not user:
                    await websocket.close(code=4001, reason="Invalid token")
                    return
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"智能交互WebSocket认证失败: {e}")
            await websocket.close(code=4001, reason="Authentication failed")
            return
    else:
        await websocket.close(code=4001, reason="Token required")
        return

    # 验证会话存在和权限
    try:
        from app.core.database import get_db
        from app.models.interaction import InteractionSession

        db = next(get_db())
        try:
            session = db.query(InteractionSession).filter(
                InteractionSession.session_id == session_id,
                InteractionSession.user_id == user.id,
                InteractionSession.is_active == True
            ).first()

            if not session:
                await websocket.close(code=4003, reason="Session not found or access denied")
                return
        finally:
            db.close()
    except Exception as e:
        logger.error(f"会话验证失败: {e}")
        await websocket.close(code=4000, reason="Session validation failed")
        return

    # 建立连接
    connection_id = f"intelligent_interaction_{session_id}"
    await manager.connect(websocket, connection_id)

    try:
        # 发送连接确认消息
        welcome_message = {
            "type": "connection_established",
            "session_id": session_id,
            "timestamp": stream_progress_service.get_current_timestamp(),
            "message": "智能交互WebSocket连接已建立"
        }
        await manager.send_personal_message(json.dumps(welcome_message, ensure_ascii=False), websocket)

        # 发送会话当前状态
        try:
            from app.services.intelligent_interaction_engine import intelligent_interaction_engine
            session_status = await intelligent_interaction_engine.get_session_status(session_id)

            if session_status:
                status_message = {
                    "type": "session_status",
                    "session_id": session_id,
                    "status": session_status
                }
                await manager.send_personal_message(
                    json.dumps(status_message, ensure_ascii=False),
                    websocket
                )
        except Exception as e:
            logger.error(f"发送会话状态失败: {e}")

        # 保持连接活跃
        while True:
            try:
                # 等待客户端消息或保持连接
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # 处理客户端消息
                try:
                    message = json.loads(data)
                    await handle_intelligent_interaction_message(websocket, session_id, message)
                except json.JSONDecodeError:
                    logger.warning(f"无效JSON消息: {data}")

            except asyncio.TimeoutError:
                # 发送心跳
                heartbeat = {
                    "type": "heartbeat",
                    "session_id": session_id,
                    "timestamp": stream_progress_service.get_current_timestamp()
                }
                await manager.send_personal_message(
                    json.dumps(heartbeat, ensure_ascii=False),
                    websocket
                )

    except WebSocketDisconnect:
        logger.info(f"智能交互WebSocket客户端断开连接: session_id={session_id}")
    except Exception as e:
        logger.error(f"智能交互WebSocket连接异常: {e}")
    finally:
        await manager.disconnect(websocket, connection_id)

async def handle_intelligent_interaction_message(websocket: WebSocket, session_id: str, message: dict):
    """处理智能交互WebSocket客户端发送的消息"""

    message_type = message.get("type")

    if message_type == "request_session_status":
        # 请求会话状态
        try:
            from app.services.intelligent_interaction_engine import intelligent_interaction_engine
            session_status = await intelligent_interaction_engine.get_session_status(session_id)

            response = {
                "type": "session_status_response",
                "session_id": session_id,
                "status": session_status
            }
            await manager.send_personal_message(
                json.dumps(response, ensure_ascii=False),
                websocket
            )
        except Exception as e:
            logger.error(f"处理会话状态请求失败: {e}")

    elif message_type == "request_current_card":
        # 请求当前澄清卡片
        try:
            from app.services.intelligent_interaction_engine import intelligent_interaction_engine
            current_card = await intelligent_interaction_engine.get_current_clarification_card(session_id)

            response = {
                "type": "current_card_response",
                "session_id": session_id,
                "clarification_card": current_card.dict() if current_card else None
            }
            await manager.send_personal_message(
                json.dumps(response, ensure_ascii=False),
                websocket
            )
        except Exception as e:
            logger.error(f"处理澄清卡片请求失败: {e}")

    elif message_type == "timer_sync":
        # 计时器同步请求
        try:
            from app.services.intelligent_interaction_engine import intelligent_interaction_engine
            timer_status = await intelligent_interaction_engine.get_timer_status(session_id)

            response = {
                "type": "timer_sync",
                "session_id": session_id,
                "remaining_seconds": timer_status.get("remaining_seconds", 0),
                "recommended_option_id": timer_status.get("recommended_option_id"),
                "timer_status": timer_status.get("status", "stopped"),
                "timestamp": timer_status.get("timestamp")
            }
            await manager.send_personal_message(
                json.dumps(response, ensure_ascii=False),
                websocket
            )
        except Exception as e:
            logger.error(f"处理计时器同步失败: {e}")

    elif message_type == "ping":
        # 心跳响应
        pong = {
            "type": "pong",
            "session_id": session_id,
            "timestamp": message.get("timestamp")
        }
        await manager.send_personal_message(
            json.dumps(pong, ensure_ascii=False),
            websocket
        )

    else:
        logger.warning(f"未知智能交互消息类型: {message_type}")

# 智能交互事件广播函数
async def broadcast_intelligent_interaction_event(session_id: str, event_data: dict):
    """广播智能交互事件到WebSocket客户端"""
    try:
        message = {
            "type": "intelligent_interaction_event",
            "session_id": session_id,
            "event": event_data
        }
        message_str = json.dumps(message, ensure_ascii=False)

        # 向智能交互会话特定连接发送
        connection_id = f"intelligent_interaction_{session_id}"
        await manager.send_to_task(connection_id, message_str)

    except Exception as e:
        logger.error(f"广播智能交互事件失败: {e}")

# 注册智能交互广播函数
try:
    from app.services.intelligent_interaction_engine import intelligent_interaction_engine
    intelligent_interaction_engine.websocket_broadcast = broadcast_intelligent_interaction_event
except ImportError:
    logger.warning("智能交互引擎尚未可用，跳过WebSocket集成")