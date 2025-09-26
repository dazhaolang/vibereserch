"""
用户相关数据模型 - MySQL版本
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, Text, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
import enum
from app.core.database import Base

class MembershipType(enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class SecurityEventType(enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    FAILED_LOGIN = "failed_login"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    institution = Column(String(300))  # 所属机构
    research_field = Column(Text)  # 研究领域
    avatar_url = Column(String(500))  # 头像URL

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    # 关系
    membership = relationship("UserMembership", back_populates="user", uselist=False)
    projects = relationship("Project", back_populates="owner")

    # 索引配置 - MySQL
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

class UserMembership(Base):
    __tablename__ = "user_memberships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    membership_type = Column(Enum(MembershipType), default=MembershipType.FREE)

    # 使用统计
    monthly_literature_used = Column(Integer, default=0)
    monthly_queries_used = Column(Integer, default=0)
    total_projects = Column(Integer, default=0)

    # 订阅信息
    subscription_start = Column(DateTime(timezone=True))
    subscription_end = Column(DateTime(timezone=True))
    auto_renewal = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    user = relationship("User", back_populates="membership")

    # 索引配置 - MySQL
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    ip_address = Column(String(45), nullable=False)  # IPv6 support
    location = Column(String(255))  # Geographic location
    device_info = Column(String(500))  # Device type info
    user_agent = Column(Text)  # Browser/client info
    event_metadata = Column("metadata", JSON)  # Additional event data

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship(
        "User",
        backref=backref("security_events", cascade="all, delete-orphan"),
    )

    # 索引配置 - MySQL
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )


class NotificationType(enum.Enum):
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    MEMBERSHIP_EXPIRING = "membership_expiring"
    MEMBERSHIP_EXPIRED = "membership_expired"
    SYSTEM_ALERT = "system_alert"
    PROJECT_SHARED = "project_shared"
    COMMENT_ADDED = "comment_added"


class NotificationStatus(enum.Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.UNREAD, nullable=False)
    action_url = Column(String(500))  # Optional URL for action button
    metadata_payload = Column("metadata", JSON)  # Additional data like task_id, project_id etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    read_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", backref="notifications")

    # 索引配置 - MySQL
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )
