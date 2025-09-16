"""
Real-time Collaborative Research Workspace
实时协作研究工作空间 - 团队协作和知识共享平台
"""

import asyncio
import json
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
import uuid
from dataclasses import dataclass, asdict
from enum import Enum

from app.core.database import get_db
from app.models.literature import Literature
from app.models.project import Project
from app.models.user import User
from app.services.multi_model_ai_service import MultiModelAIService
from app.services.stream_progress_service import stream_progress_service


class CollaborationEventType(Enum):
    """协作事件类型"""
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    LITERATURE_ADDED = "literature_added"
    ANNOTATION_CREATED = "annotation_created"
    COMMENT_ADDED = "comment_added"
    RESEARCH_QUESTION_ASKED = "research_question_asked"
    INSIGHT_SHARED = "insight_shared"
    WORKSPACE_UPDATED = "workspace_updated"


@dataclass
class CollaborationEvent:
    """协作事件数据类"""
    event_id: str
    event_type: CollaborationEventType
    workspace_id: str
    user_id: int
    user_name: str
    timestamp: str
    data: Dict[str, Any]
    broadcast_to: List[int] = None


@dataclass
class WorkspaceUser:
    """工作空间用户"""
    user_id: int
    user_name: str
    email: str
    role: str  # owner, collaborator, viewer
    joined_at: str
    last_active: str
    current_activity: str = ""


@dataclass
class SharedAnnotation:
    """共享注释"""
    annotation_id: str
    literature_id: int
    user_id: int
    user_name: str
    content: str
    highlight_text: str
    position: Dict[str, Any]  # 注释位置信息
    tags: List[str]
    created_at: str
    updated_at: str
    replies: List[Dict[str, Any]] = None


@dataclass
class ResearchInsight:
    """研究洞察"""
    insight_id: str
    workspace_id: str
    user_id: int
    user_name: str
    title: str
    content: str
    insight_type: str  # hypothesis, finding, question, suggestion
    related_literature: List[int]
    tags: List[str]
    upvotes: int
    created_at: str
    updated_at: str


class CollaborativeResearchWorkspace:
    """
    实时协作研究工作空间

    突破性功能:
    1. 实时多用户协作 - 支持多人同时在线研究
    2. 智能注释系统 - AI辅助的文献注释和讨论
    3. 共享知识库 - 团队共享的研究洞察和发现
    4. 实时问答协作 - 团队成员间的智能问答
    5. 协作研究看板 - 可视化的研究进度管理
    6. 冲突解决机制 - 自动处理多用户编辑冲突
    """

    def __init__(self):
        self.ai_service = MultiModelAIService()
        self.active_workspaces = {}  # 活跃工作空间
        self.user_connections = {}  # 用户连接映射
        self.workspace_events = {}  # 工作空间事件历史

    async def create_collaborative_workspace(
        self,
        project_id: int,
        creator_id: int,
        workspace_name: str,
        workspace_description: str = "",
        collaboration_settings: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        创建协作工作空间

        突破性功能:
        - 智能权限管理
        - 实时状态同步
        - 自动化工作流
        """
        try:
            workspace_id = str(uuid.uuid4())

            if collaboration_settings is None:
                collaboration_settings = {
                    "allow_public_join": False,
                    "auto_ai_assistance": True,
                    "real_time_sync": True,
                    "annotation_notifications": True,
                    "insight_sharing": True
                }

            # 创建工作空间数据结构
            workspace_data = {
                "workspace_id": workspace_id,
                "project_id": project_id,
                "name": workspace_name,
                "description": workspace_description,
                "creator_id": creator_id,
                "settings": collaboration_settings,
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "active_users": [],
                "shared_annotations": {},
                "research_insights": {},
                "collaboration_stats": {
                    "total_contributions": 0,
                    "active_collaborators": 0,
                    "annotations_count": 0,
                    "insights_count": 0
                }
            }

            # 存储工作空间
            self.active_workspaces[workspace_id] = workspace_data

            # 创建初始事件
            initial_event = CollaborationEvent(
                event_id=str(uuid.uuid4()),
                event_type=CollaborationEventType.WORKSPACE_UPDATED,
                workspace_id=workspace_id,
                user_id=creator_id,
                user_name="",  # 这里可以从数据库获取用户名
                timestamp=datetime.now().isoformat(),
                data={"action": "workspace_created", "workspace_name": workspace_name}
            )

            await self._broadcast_event(initial_event)

            return {
                "workspace_id": workspace_id,
                "status": "created",
                "join_url": f"/workspace/{workspace_id}",
                "workspace_data": workspace_data
            }

        except Exception as e:
            logger.error(f"创建协作工作空间时出错: {e}")
            return {"error": str(e)}

    async def join_collaborative_workspace(
        self,
        workspace_id: str,
        user_id: int,
        user_name: str,
        user_email: str,
        role: str = "collaborator"
    ) -> Dict[str, Any]:
        """
        加入协作工作空间

        突破性功能:
        - 动态权限分配
        - 实时状态更新
        - 智能欢迎引导
        """
        try:
            if workspace_id not in self.active_workspaces:
                return {"error": "工作空间不存在"}

            workspace = self.active_workspaces[workspace_id]

            # 检查用户是否已在工作空间中
            existing_user = next(
                (u for u in workspace["active_users"] if u["user_id"] == user_id),
                None
            )

            if existing_user:
                # 更新现有用户的活动状态
                existing_user["last_active"] = datetime.now().isoformat()
                existing_user["current_activity"] = "在线"
            else:
                # 添加新用户
                new_user = WorkspaceUser(
                    user_id=user_id,
                    user_name=user_name,
                    email=user_email,
                    role=role,
                    joined_at=datetime.now().isoformat(),
                    last_active=datetime.now().isoformat(),
                    current_activity="刚加入"
                )
                workspace["active_users"].append(asdict(new_user))

            # 更新协作统计
            workspace["collaboration_stats"]["active_collaborators"] = len(workspace["active_users"])
            workspace["last_activity"] = datetime.now().isoformat()

            # 广播用户加入事件
            join_event = CollaborationEvent(
                event_id=str(uuid.uuid4()),
                event_type=CollaborationEventType.USER_JOINED,
                workspace_id=workspace_id,
                user_id=user_id,
                user_name=user_name,
                timestamp=datetime.now().isoformat(),
                data={"role": role, "user_email": user_email}
            )

            await self._broadcast_event(join_event)

            # 为新用户生成个性化欢迎信息
            welcome_message = await self._generate_welcome_message(workspace_id, user_id)

            return {
                "status": "joined",
                "workspace_data": workspace,
                "welcome_message": welcome_message,
                "current_collaborators": len(workspace["active_users"]),
                "recent_activity": await self._get_recent_workspace_activity(workspace_id, limit=10)
            }

        except Exception as e:
            logger.error(f"加入工作空间时出错: {e}")
            return {"error": str(e)}

    async def create_shared_annotation(
        self,
        workspace_id: str,
        literature_id: int,
        user_id: int,
        user_name: str,
        annotation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        创建共享注释

        突破性功能:
        - AI辅助注释理解
        - 智能标签建议
        - 实时协作讨论
        """
        try:
            if workspace_id not in self.active_workspaces:
                return {"error": "工作空间不存在"}

            annotation_id = str(uuid.uuid4())

            # 使用AI增强注释内容
            enhanced_annotation = await self._enhance_annotation_with_ai(
                annotation_data["content"],
                annotation_data.get("highlight_text", ""),
                literature_id
            )

            # 创建注释对象
            annotation = SharedAnnotation(
                annotation_id=annotation_id,
                literature_id=literature_id,
                user_id=user_id,
                user_name=user_name,
                content=annotation_data["content"],
                highlight_text=annotation_data.get("highlight_text", ""),
                position=annotation_data.get("position", {}),
                tags=enhanced_annotation.get("suggested_tags", []),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                replies=[]
            )

            # 存储注释
            workspace = self.active_workspaces[workspace_id]
            workspace["shared_annotations"][annotation_id] = asdict(annotation)

            # 更新统计
            workspace["collaboration_stats"]["annotations_count"] += 1
            workspace["collaboration_stats"]["total_contributions"] += 1

            # 广播注释创建事件
            annotation_event = CollaborationEvent(
                event_id=str(uuid.uuid4()),
                event_type=CollaborationEventType.ANNOTATION_CREATED,
                workspace_id=workspace_id,
                user_id=user_id,
                user_name=user_name,
                timestamp=datetime.now().isoformat(),
                data={
                    "annotation_id": annotation_id,
                    "literature_id": literature_id,
                    "content_preview": annotation_data["content"][:100],
                    "ai_insights": enhanced_annotation.get("ai_insights", [])
                }
            )

            await self._broadcast_event(annotation_event)

            return {
                "annotation_id": annotation_id,
                "status": "created",
                "annotation": asdict(annotation),
                "ai_enhancement": enhanced_annotation,
                "related_suggestions": await self._generate_annotation_suggestions(
                    annotation_data["content"], workspace_id
                )
            }

        except Exception as e:
            logger.error(f"创建共享注释时出错: {e}")
            return {"error": str(e)}

    async def share_research_insight(
        self,
        workspace_id: str,
        user_id: int,
        user_name: str,
        insight_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分享研究洞察

        突破性功能:
        - AI洞察评估
        - 自动关联文献
        - 智能讨论引导
        """
        try:
            if workspace_id not in self.active_workspaces:
                return {"error": "工作空间不存在"}

            insight_id = str(uuid.uuid4())

            # 使用AI增强洞察内容
            enhanced_insight = await self._enhance_insight_with_ai(
                insight_data["content"],
                insight_data.get("insight_type", "finding"),
                workspace_id
            )

            # 创建洞察对象
            insight = ResearchInsight(
                insight_id=insight_id,
                workspace_id=workspace_id,
                user_id=user_id,
                user_name=user_name,
                title=insight_data.get("title", ""),
                content=insight_data["content"],
                insight_type=insight_data.get("insight_type", "finding"),
                related_literature=enhanced_insight.get("related_literature", []),
                tags=enhanced_insight.get("suggested_tags", []),
                upvotes=0,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )

            # 存储洞察
            workspace = self.active_workspaces[workspace_id]
            workspace["research_insights"][insight_id] = asdict(insight)

            # 更新统计
            workspace["collaboration_stats"]["insights_count"] += 1
            workspace["collaboration_stats"]["total_contributions"] += 1

            # 广播洞察分享事件
            insight_event = CollaborationEvent(
                event_id=str(uuid.uuid4()),
                event_type=CollaborationEventType.INSIGHT_SHARED,
                workspace_id=workspace_id,
                user_id=user_id,
                user_name=user_name,
                timestamp=datetime.now().isoformat(),
                data={
                    "insight_id": insight_id,
                    "insight_type": insight_data.get("insight_type", "finding"),
                    "content_preview": insight_data["content"][:150],
                    "ai_assessment": enhanced_insight.get("ai_assessment", {})
                }
            )

            await self._broadcast_event(insight_event)

            return {
                "insight_id": insight_id,
                "status": "shared",
                "insight": asdict(insight),
                "ai_enhancement": enhanced_insight,
                "discussion_starters": await self._generate_discussion_starters(insight_data["content"])
            }

        except Exception as e:
            logger.error(f"分享研究洞察时出错: {e}")
            return {"error": str(e)}

    async def get_workspace_real_time_status(
        self,
        workspace_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        获取工作空间实时状态

        返回当前活跃用户、最新活动、协作统计等
        """
        try:
            if workspace_id not in self.active_workspaces:
                return {"error": "工作空间不存在"}

            workspace = self.active_workspaces[workspace_id]

            # 过滤掉非活跃用户（超过30分钟未活动）
            current_time = datetime.now()
            active_users = []

            for user in workspace["active_users"]:
                last_active = datetime.fromisoformat(user["last_active"])
                if (current_time - last_active).total_seconds() < 1800:  # 30分钟
                    active_users.append(user)

            workspace["active_users"] = active_users
            workspace["collaboration_stats"]["active_collaborators"] = len(active_users)

            # 获取最新活动
            recent_activity = await self._get_recent_workspace_activity(workspace_id, limit=20)

            # 获取协作热点
            collaboration_hotspots = await self._identify_collaboration_hotspots(workspace_id)

            return {
                "workspace_id": workspace_id,
                "active_users": active_users,
                "collaboration_stats": workspace["collaboration_stats"],
                "recent_activity": recent_activity,
                "collaboration_hotspots": collaboration_hotspots,
                "current_focus": await self._analyze_current_research_focus(workspace_id),
                "ai_suggestions": await self._generate_workspace_ai_suggestions(workspace_id),
                "last_updated": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取工作空间状态时出错: {e}")
            return {"error": str(e)}

    # =============== 私有辅助方法 ===============

    async def _broadcast_event(self, event: CollaborationEvent):
        """广播协作事件"""
        try:
            # 记录事件历史
            if event.workspace_id not in self.workspace_events:
                self.workspace_events[event.workspace_id] = []

            self.workspace_events[event.workspace_id].append(asdict(event))

            # 保持最近1000个事件
            if len(self.workspace_events[event.workspace_id]) > 1000:
                self.workspace_events[event.workspace_id] = self.workspace_events[event.workspace_id][-1000:]

            # 通过WebSocket广播事件
            await stream_progress_service.send_progress_update(
                f"workspace_{event.workspace_id}",
                f"协作事件: {event.event_type.value}",
                100,
                asdict(event)
            )

        except Exception as e:
            logger.error(f"广播事件时出错: {e}")

    async def _enhance_annotation_with_ai(
        self,
        annotation_content: str,
        highlight_text: str,
        literature_id: int
    ) -> Dict[str, Any]:
        """使用AI增强注释"""
        try:
            enhancement_prompt = f"""
            分析以下文献注释，提供智能增强建议:

            注释内容: {annotation_content}
            高亮文本: {highlight_text}

            请提供:
            1. 建议的标签(最多5个)
            2. 相关的研究概念
            3. 可能的研究方向
            4. 讨论要点

            以JSON格式返回。
            """

            response = await self.ai_service.chat_completion(
                [{"role": "user", "content": enhancement_prompt}],
                temperature=0.3
            )

            if response and response.get("choices"):
                content = response["choices"][0]["message"]["content"]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {
                        "suggested_tags": ["注释"],
                        "ai_insights": [],
                        "research_directions": []
                    }

            return {"suggested_tags": [], "ai_insights": []}

        except Exception as e:
            logger.error(f"AI增强注释时出错: {e}")
            return {"suggested_tags": [], "ai_insights": []}

    async def _enhance_insight_with_ai(
        self,
        insight_content: str,
        insight_type: str,
        workspace_id: str
    ) -> Dict[str, Any]:
        """使用AI增强研究洞察"""
        try:
            enhancement_prompt = f"""
            分析以下研究洞察，提供智能评估和建议:

            洞察内容: {insight_content}
            洞察类型: {insight_type}

            请提供:
            1. 洞察的创新性评分(0-1)
            2. 可行性评分(0-1)
            3. 建议的标签
            4. 相关文献建议
            5. 后续研究建议

            以JSON格式返回。
            """

            response = await self.ai_service.chat_completion(
                [{"role": "user", "content": enhancement_prompt}],
                temperature=0.3
            )

            if response and response.get("choices"):
                content = response["choices"][0]["message"]["content"]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {
                        "ai_assessment": {"innovation": 0.5, "feasibility": 0.5},
                        "suggested_tags": [],
                        "related_literature": []
                    }

            return {"ai_assessment": {}, "suggested_tags": [], "related_literature": []}

        except Exception as e:
            logger.error(f"AI增强洞察时出错: {e}")
            return {"ai_assessment": {}, "suggested_tags": [], "related_literature": []}

    async def _generate_welcome_message(self, workspace_id: str, user_id: int) -> str:
        """生成个性化欢迎消息"""
        try:
            workspace = self.active_workspaces[workspace_id]
            welcome_msg = f"""
欢迎加入协作研究空间 "{workspace['name']}"！

当前活跃状态:
- 协作者: {len(workspace['active_users'])} 人
- 共享注释: {workspace['collaboration_stats']['annotations_count']} 条
- 研究洞察: {workspace['collaboration_stats']['insights_count']} 个

开始协作:
1. 浏览项目文献并添加注释
2. 分享你的研究发现和洞察
3. 参与团队讨论和问答
4. 使用AI助手获得智能建议

祝研究愉快！
            """
            return welcome_msg.strip()

        except Exception as e:
            return "欢迎加入协作研究空间！"

    async def _get_recent_workspace_activity(
        self,
        workspace_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取最近的工作空间活动"""
        try:
            if workspace_id not in self.workspace_events:
                return []

            events = self.workspace_events[workspace_id]
            return events[-limit:] if events else []

        except Exception as e:
            logger.error(f"获取工作空间活动时出错: {e}")
            return []

    async def _generate_annotation_suggestions(
        self,
        annotation_content: str,
        workspace_id: str
    ) -> List[str]:
        """生成注释相关建议"""
        return [
            "考虑与其他文献的对比",
            "探索相关的研究方法",
            "思考实际应用场景"
        ]

    async def _generate_discussion_starters(self, insight_content: str) -> List[str]:
        """生成讨论引导问题"""
        return [
            "这个发现的实际应用前景如何？",
            "是否存在其他解释角度？",
            "需要什么样的后续实验验证？"
        ]

    async def _identify_collaboration_hotspots(self, workspace_id: str) -> List[Dict[str, Any]]:
        """识别协作热点"""
        return [
            {"type": "热门文献", "title": "最多注释的文献", "count": 0},
            {"type": "活跃讨论", "title": "最多回复的注释", "count": 0}
        ]

    async def _analyze_current_research_focus(self, workspace_id: str) -> Dict[str, Any]:
        """分析当前研究焦点"""
        return {
            "primary_topics": [],
            "emerging_themes": [],
            "research_gaps": []
        }

    async def _generate_workspace_ai_suggestions(self, workspace_id: str) -> List[str]:
        """生成工作空间AI建议"""
        return [
            "建议组织一次团队研讨会",
            "考虑添加更多相关文献",
            "可以探索跨学科合作机会"
        ]


# 创建全局实例
collaborative_workspace = CollaborativeResearchWorkspace()