"""
用户相关的Pydantic模型
确保API请求响应的类型安全和一致性
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.models.user import MembershipType

# ============================================
# 枚举类型
# ============================================

class MembershipTypeEnum(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class ProjectStatusEnum(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class SecurityEventTypeEnum(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    FAILED_LOGIN = "failed_login"

class NotificationTypeEnum(str, Enum):
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    MEMBERSHIP_EXPIRING = "membership_expiring"
    MEMBERSHIP_EXPIRED = "membership_expired"
    SYSTEM_ALERT = "system_alert"
    PROJECT_SHARED = "project_shared"
    COMMENT_ADDED = "comment_added"

class NotificationStatusEnum(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"

# ============================================
# 请求模型
# ============================================

class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="用户邮箱")
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    full_name: Optional[str] = Field(None, max_length=200, description="真实姓名")
    institution: Optional[str] = Field(None, max_length=300, description="所属机构")
    research_field: Optional[str] = Field(None, description="研究领域")
    
    @field_validator("username", mode="before")
    def validate_username(cls, value):
        value_str = str(value).strip()
        if not value_str:
            raise ValueError("用户名不能为空")
        return value_str

    @field_validator("email", mode="before")
    def validate_email_domain(cls, value):
        value_str = str(value)
        # 可以添加特定的邮箱域名验证
        return value_str.lower()

class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="用户邮箱")
    password: str = Field(..., description="密码")

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=200)
    institution: Optional[str] = Field(None, max_length=300)
    research_field: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")

# ============================================
# 响应模型
# ============================================

class UserMembershipResponse(BaseModel):
    id: int
    user_id: int
    membership_type: MembershipTypeEnum
    monthly_literature_used: int
    monthly_queries_used: int
    total_projects: int
    subscription_start: Optional[datetime]
    subscription_end: Optional[datetime]
    auto_renewal: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    institution: Optional[str]
    research_field: Optional[str]
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    membership: Optional[UserMembershipResponse]

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: UserResponse

class UserListResponse(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    institution: Optional[str]
    research_field: Optional[str]
    membership_type: MembershipTypeEnum
    is_active: bool
    last_login: Optional[datetime]
    project_count: int = 0
    literature_count: int = 0
    
    class Config:
        from_attributes = True

class UserStatsResponse(BaseModel):
    user_id: int
    project_count: int
    literature_count: int
    completed_tasks: int
    total_tasks: int
    monthly_activity: int
    efficiency_score: float
    membership_info: UserMembershipResponse
    usage_stats: dict
    
    class Config:
        from_attributes = True

# ============================================
# 内部模型（用于服务间调用）
# ============================================

class UserInternal(BaseModel):
    """内部服务调用使用的用户模型"""
    id: int
    email: str
    username: str
    membership_type: MembershipTypeEnum
    is_active: bool
    is_verified: bool
    
    class Config:
        from_attributes = True

class MembershipLimits(BaseModel):
    """会员限制信息"""
    max_literature: int
    max_projects: int
    max_monthly_queries: int
    available_sources: List[str]
    api_rate_limit: int
    concurrent_requests: int
    
    @classmethod
    def get_limits(cls, membership_type: MembershipType) -> 'MembershipLimits':
        limits_config = {
            MembershipType.FREE: {
                'max_literature': 500,
                'max_projects': 3,
                'max_monthly_queries': 100,
                'available_sources': ['researchrabbit'],
                'api_rate_limit': 30,
                'concurrent_requests': 3
            },
            MembershipType.PREMIUM: {
                'max_literature': 2000,
                'max_projects': 10,
                'max_monthly_queries': 500,
                'available_sources': ['researchrabbit'],
                'api_rate_limit': 120,
                'concurrent_requests': 10
            },
            MembershipType.ENTERPRISE: {
                'max_literature': 10000,
                'max_projects': 50,
                'max_monthly_queries': 2000,
                'available_sources': ['researchrabbit'],
                'api_rate_limit': 300,
                'concurrent_requests': 50
            }
        }
        
        config = limits_config[membership_type]
        return cls(**config)
# ============================================
# 新增响应模型 (API对齐修复)
# ============================================

class UsageStatisticsResponse(BaseModel):
    """用户使用统计响应"""
    membership_type: str
    usage: dict
    limits: dict
    usage_percentage: dict
    
    class Config:
        from_attributes = True

class MembershipUpgradeResponse(BaseModel):
    """会员升级响应"""
    success: bool
    message: str
    new_membership_type: str
    
    class Config:
        from_attributes = True

class UserProfileUpdateResponse(BaseModel):
    """用户资料更新响应"""
    success: bool
    message: str
    
    class Config:
        from_attributes = True

class PasswordUpdateResponse(BaseModel):
    """密码更新响应"""
    success: bool
    message: str

    class Config:
        from_attributes = True

class SecurityEventResponse(BaseModel):
    """安全事件响应"""
    id: int
    user_id: int
    event_type: SecurityEventTypeEnum
    ip_address: str
    location: Optional[str] = None
    device_info: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    """通知响应"""
    id: int
    user_id: int
    type: NotificationTypeEnum
    title: str
    message: str
    status: NotificationStatusEnum
    action_url: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class NotificationUpdateRequest(BaseModel):
    """通知更新请求"""
    status: NotificationStatusEnum
