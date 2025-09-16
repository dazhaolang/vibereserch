"""
团队协作相关数据模型
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class CollaborationRole(enum.Enum):
    OWNER = "owner"           # 项目所有者
    ADMIN = "admin"           # 管理员
    EDITOR = "editor"         # 编辑者
    VIEWER = "viewer"         # 查看者
    COMMENTATOR = "commentator" # 评论者

class InvitationStatus(enum.Enum):
    PENDING = "pending"       # 待接受
    ACCEPTED = "accepted"     # 已接受
    DECLINED = "declined"     # 已拒绝
    EXPIRED = "expired"       # 已过期

class Team(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # 团队设置
    is_public = Column(Boolean, default=False)  # 是否公开
    max_members = Column(Integer, default=50)   # 最大成员数
    
    # 创建者信息
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    creator = relationship("User", foreign_keys=[created_by])
    members = relationship("TeamMember", back_populates="team")
    projects = relationship("ProjectCollaboration", back_populates="team")

class TeamMember(Base):
    __tablename__ = "team_members"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 角色和权限
    role = Column(Enum(CollaborationRole), default=CollaborationRole.VIEWER)
    permissions = Column(JSON)  # 详细权限配置
    
    # 加入信息
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    invited_by = Column(Integer, ForeignKey("users.id"))
    
    # 状态
    is_active = Column(Boolean, default=True)
    last_activity = Column(DateTime(timezone=True))
    
    # 关系
    team = relationship("Team", back_populates="members")
    user = relationship("User", foreign_keys=[user_id], overlaps="inviter")
    inviter = relationship("User", foreign_keys=[invited_by], overlaps="user")

class ProjectCollaboration(Base):
    __tablename__ = "project_collaborations"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"))
    user_id = Column(Integer, ForeignKey("users.id"))  # 单个用户协作
    
    # 协作角色
    role = Column(Enum(CollaborationRole), default=CollaborationRole.VIEWER)
    permissions = Column(JSON)
    
    # 协作设置
    can_invite_others = Column(Boolean, default=False)
    can_modify_structure = Column(Boolean, default=False)
    can_delete_literature = Column(Boolean, default=False)
    can_export_data = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    project = relationship("Project")
    team = relationship("Team", back_populates="projects")
    user = relationship("User")

class CollaborationInvitation(Base):
    __tablename__ = "collaboration_invitations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 邀请信息
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    invitee_email = Column(String(255), nullable=False)
    invitee_id = Column(Integer, ForeignKey("users.id"))  # 如果用户已存在
    
    # 邀请目标
    project_id = Column(Integer, ForeignKey("projects.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    
    # 邀请详情
    role = Column(Enum(CollaborationRole), default=CollaborationRole.VIEWER)
    message = Column(Text)
    permissions = Column(JSON)
    
    # 状态和时间
    status = Column(Enum(InvitationStatus), default=InvitationStatus.PENDING)
    expires_at = Column(DateTime(timezone=True))
    responded_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    inviter = relationship("User", foreign_keys=[inviter_id], overlaps="invitee")
    invitee = relationship("User", foreign_keys=[invitee_id], overlaps="inviter")
    project = relationship("Project")
    team = relationship("Team")

class CollaborationComment(Base):
    __tablename__ = "collaboration_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 评论目标
    project_id = Column(Integer, ForeignKey("projects.id"))
    literature_id = Column(Integer, ForeignKey("literature.id"))
    experience_book_id = Column(Integer, ForeignKey("experience_books.id"))
    
    # 评论内容
    content = Column(Text, nullable=False)
    comment_type = Column(String(50), default="general")  # general, suggestion, question, issue
    
    # 作者信息
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 回复关系
    parent_comment_id = Column(Integer, ForeignKey("collaboration_comments.id"))
    thread_id = Column(Integer)  # 主题ID，用于组织讨论
    
    # 状态
    is_resolved = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    author = relationship("User")
    project = relationship("Project")
    literature = relationship("Literature")
    experience_book = relationship("ExperienceBook")
    parent_comment = relationship("CollaborationComment", remote_side=[id])
    replies = relationship("CollaborationComment", remote_side=[parent_comment_id], overlaps="parent_comment")

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 活动主体
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    
    # 活动内容
    action = Column(String(100), nullable=False)  # created, updated, deleted, commented等
    target_type = Column(String(50))  # project, literature, experience_book等
    target_id = Column(Integer)
    
    # 活动详情
    description = Column(Text)
    extra_data = Column(JSON)  # 额外的活动数据
    
    # 时间信息
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User")
    project = relationship("Project")
    team = relationship("Team")