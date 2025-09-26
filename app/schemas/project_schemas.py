"""
项目相关的Schema定义
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ProjectBase(BaseModel):
    """项目基础模型"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class ProjectCreateRequest(ProjectBase):
    """创建项目请求"""
    tags: Optional[List[str]] = []
    is_public: bool = False

class ProjectUpdateRequest(BaseModel):
    """更新项目请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None

class ProjectResponse(ProjectBase):
    """项目响应"""
    id: int
    owner_id: int
    tags: List[str]
    is_public: bool
    literature_count: int
    task_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProjectListResponse(BaseModel):
    """项目列表响应"""
    total: int
    items: List[ProjectResponse]
    page: int
    page_size: int

class ProjectStatistics(BaseModel):
    """项目统计信息"""
    total_literature: int
    total_tasks: int
    completed_tasks: int
    active_tasks: int
    total_experience: int
    storage_used_mb: float
    last_activity: Optional[datetime]