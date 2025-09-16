"""
Collaborative Workspace API - 实时协作工作空间API接口
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import json

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.collaborative_workspace import collaborative_workspace, CollaborationEventType
from app.services.stream_progress_service import stream_progress_service


router = APIRouter()


# =============== Pydantic Models ===============

class CreateWorkspaceRequest(BaseModel):
    """创建工作空间请求"""
    project_id: int = Field(..., description="项目ID")
    workspace_name: str = Field(..., description="工作空间名称")
    workspace_description: str = Field("", description="工作空间描述")
    collaboration_settings: Optional[Dict[str, Any]] = Field(None, description="协作设置")


class CreateWorkspaceResponse(BaseModel):
    """创建工作空间响应"""
    workspace_id: str
    status: str
    join_url: str
    workspace_data: Dict[str, Any]


class JoinWorkspaceRequest(BaseModel):
    """加入工作空间请求"""
    workspace_id: str = Field(..., description="工作空间ID")
    role: str = Field("collaborator", description="用户角色")


class JoinWorkspaceResponse(BaseModel):
    """加入工作空间响应"""
    status: str
    workspace_data: Dict[str, Any]
    welcome_message: str
    current_collaborators: int
    recent_activity: List[Dict[str, Any]]


class CreateAnnotationRequest(BaseModel):
    """创建注释请求"""
    workspace_id: str = Field(..., description="工作空间ID")
    literature_id: int = Field(..., description="文献ID")
    annotation_data: Dict[str, Any] = Field(..., description="注释数据")


class CreateAnnotationResponse(BaseModel):
    """创建注释响应"""
    annotation_id: str
    status: str
    annotation: Dict[str, Any]
    ai_enhancement: Dict[str, Any]
    related_suggestions: List[str]


class ShareInsightRequest(BaseModel):
    """分享洞察请求"""
    workspace_id: str = Field(..., description="工作空间ID")
    insight_data: Dict[str, Any] = Field(..., description="洞察数据")


class ShareInsightResponse(BaseModel):
    """分享洞察响应"""
    insight_id: str
    status: str
    insight: Dict[str, Any]
    ai_enhancement: Dict[str, Any]
    discussion_starters: List[str]


class WorkspaceStatusResponse(BaseModel):
    """工作空间状态响应"""
    workspace_id: str
    active_users: List[Dict[str, Any]]
    collaboration_stats: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]
    collaboration_hotspots: List[Dict[str, Any]]
    current_focus: Dict[str, Any]
    ai_suggestions: List[str]
    last_updated: str


# =============== API Endpoints ===============

@router.post("/collaborative-workspace/create", response_model=CreateWorkspaceResponse)
async def create_collaborative_workspace(
    request: CreateWorkspaceRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建协作工作空间

    突破性功能:
    - 智能权限管理
    - 实时状态同步
    - 自动化工作流
    """
    try:
        # 执行工作空间创建
        result = await collaborative_workspace.create_collaborative_workspace(
            project_id=request.project_id,
            creator_id=current_user.id,
            workspace_name=request.workspace_name,
            workspace_description=request.workspace_description,
            collaboration_settings=request.collaboration_settings
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return CreateWorkspaceResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建协作工作空间失败: {str(e)}")


@router.post("/collaborative-workspace/join", response_model=JoinWorkspaceResponse)
async def join_collaborative_workspace(
    request: JoinWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    加入协作工作空间

    突破性功能:
    - 动态权限分配
    - 实时状态更新
    - 智能欢迎引导
    """
    try:
        # 执行加入工作空间
        result = await collaborative_workspace.join_collaborative_workspace(
            workspace_id=request.workspace_id,
            user_id=current_user.id,
            user_name=current_user.name,
            user_email=current_user.email,
            role=request.role
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return JoinWorkspaceResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加入协作工作空间失败: {str(e)}")


@router.post("/collaborative-workspace/annotations", response_model=CreateAnnotationResponse)
async def create_shared_annotation(
    request: CreateAnnotationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建共享注释

    突破性功能:
    - AI辅助注释理解
    - 智能标签建议
    - 实时协作讨论
    """
    try:
        # 执行注释创建
        result = await collaborative_workspace.create_shared_annotation(
            workspace_id=request.workspace_id,
            literature_id=request.literature_id,
            user_id=current_user.id,
            user_name=current_user.name,
            annotation_data=request.annotation_data
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return CreateAnnotationResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建共享注释失败: {str(e)}")


@router.post("/collaborative-workspace/insights", response_model=ShareInsightResponse)
async def share_research_insight(
    request: ShareInsightRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    分享研究洞察

    突破性功能:
    - AI洞察评估
    - 自动关联文献
    - 智能讨论引导
    """
    try:
        # 执行洞察分享
        result = await collaborative_workspace.share_research_insight(
            workspace_id=request.workspace_id,
            user_id=current_user.id,
            user_name=current_user.name,
            insight_data=request.insight_data
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return ShareInsightResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分享研究洞察失败: {str(e)}")


@router.get("/collaborative-workspace/{workspace_id}/status", response_model=WorkspaceStatusResponse)
async def get_workspace_status(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取工作空间实时状态

    返回当前活跃用户、最新活动、协作统计等
    """
    try:
        result = await collaborative_workspace.get_workspace_real_time_status(
            workspace_id=workspace_id,
            user_id=current_user.id
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return WorkspaceStatusResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取工作空间状态失败: {str(e)}")


@router.get("/collaborative-workspace/{workspace_id}/annotations")
async def get_workspace_annotations(
    workspace_id: str,
    literature_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取工作空间注释"""
    try:
        if workspace_id not in collaborative_workspace.active_workspaces:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        workspace = collaborative_workspace.active_workspaces[workspace_id]
        annotations = workspace.get("shared_annotations", {})

        # 如果指定了文献ID，则筛选
        if literature_id:
            filtered_annotations = {
                k: v for k, v in annotations.items()
                if v.get("literature_id") == literature_id
            }
            annotations = filtered_annotations

        return {
            "workspace_id": workspace_id,
            "literature_id": literature_id,
            "annotations": annotations,
            "total_count": len(annotations)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取注释失败: {str(e)}")


@router.get("/collaborative-workspace/{workspace_id}/insights")
async def get_workspace_insights(
    workspace_id: str,
    insight_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取工作空间研究洞察"""
    try:
        if workspace_id not in collaborative_workspace.active_workspaces:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        workspace = collaborative_workspace.active_workspaces[workspace_id]
        insights = workspace.get("research_insights", {})

        # 如果指定了洞察类型，则筛选
        if insight_type:
            filtered_insights = {
                k: v for k, v in insights.items()
                if v.get("insight_type") == insight_type
            }
            insights = filtered_insights

        return {
            "workspace_id": workspace_id,
            "insight_type": insight_type,
            "insights": insights,
            "total_count": len(insights),
            "insight_types": ["hypothesis", "finding", "question", "suggestion"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取洞察失败: {str(e)}")


@router.delete("/collaborative-workspace/{workspace_id}/leave")
async def leave_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """离开工作空间"""
    try:
        if workspace_id not in collaborative_workspace.active_workspaces:
            raise HTTPException(status_code=404, detail="工作空间不存在")

        workspace = collaborative_workspace.active_workspaces[workspace_id]

        # 移除用户
        workspace["active_users"] = [
            user for user in workspace["active_users"]
            if user["user_id"] != current_user.id
        ]

        # 更新统计
        workspace["collaboration_stats"]["active_collaborators"] = len(workspace["active_users"])

        return {
            "status": "left",
            "workspace_id": workspace_id,
            "remaining_collaborators": len(workspace["active_users"])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"离开工作空间失败: {str(e)}")


@router.get("/collaborative-workspace/features")
async def get_collaboration_features():
    """获取协作功能说明"""
    return {
        "real_time_collaboration": {
            "description": "实时多用户协作研究",
            "features": [
                "实时用户状态同步",
                "多人同时在线编辑",
                "即时消息通知",
                "活动状态跟踪"
            ]
        },
        "intelligent_annotations": {
            "description": "AI辅助的智能注释系统",
            "features": [
                "AI增强注释理解",
                "智能标签建议",
                "相关文献推荐",
                "讨论引导生成"
            ]
        },
        "shared_knowledge_base": {
            "description": "团队共享的知识库",
            "features": [
                "研究洞察共享",
                "知识点整理",
                "团队发现汇总",
                "集体智慧积累"
            ]
        },
        "collaborative_qa": {
            "description": "团队协作问答",
            "features": [
                "实时问答互动",
                "AI辅助回答",
                "专家知识整合",
                "问题跟踪管理"
            ]
        },
        "research_dashboard": {
            "description": "协作研究看板",
            "features": [
                "研究进度可视化",
                "任务分配管理",
                "里程碑跟踪",
                "团队贡献统计"
            ]
        },
        "conflict_resolution": {
            "description": "智能冲突解决",
            "features": [
                "编辑冲突检测",
                "自动合并建议",
                "版本控制",
                "回滚机制"
            ]
        }
    }


# =============== WebSocket Endpoints ===============

@router.websocket("/collaborative-workspace/{workspace_id}/ws")
async def workspace_websocket_endpoint(
    websocket: WebSocket,
    workspace_id: str
):
    """
    工作空间WebSocket连接

    用于实时协作通信
    """
    await websocket.accept()

    try:
        # 注册WebSocket连接
        if workspace_id not in collaborative_workspace.user_connections:
            collaborative_workspace.user_connections[workspace_id] = []

        collaborative_workspace.user_connections[workspace_id].append(websocket)

        # 保持连接并处理消息
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # 处理不同类型的实时消息
            if message.get("type") == "user_activity":
                # 更新用户活动状态
                await collaborative_workspace._broadcast_event_to_workspace(
                    workspace_id,
                    {
                        "type": "user_activity_update",
                        "user_id": message.get("user_id"),
                        "activity": message.get("activity"),
                        "timestamp": message.get("timestamp")
                    }
                )

            elif message.get("type") == "typing_indicator":
                # 广播输入状态
                await collaborative_workspace._broadcast_event_to_workspace(
                    workspace_id,
                    {
                        "type": "typing_indicator",
                        "user_id": message.get("user_id"),
                        "is_typing": message.get("is_typing"),
                        "location": message.get("location")
                    }
                )

            # 回声确认
            await websocket.send_text(json.dumps({"status": "received"}))

    except WebSocketDisconnect:
        # 移除断开的连接
        if workspace_id in collaborative_workspace.user_connections:
            collaborative_workspace.user_connections[workspace_id] = [
                conn for conn in collaborative_workspace.user_connections[workspace_id]
                if conn != websocket
            ]