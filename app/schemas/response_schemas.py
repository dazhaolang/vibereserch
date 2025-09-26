"""
通用响应Schema定义
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime

class StandardResponse(BaseModel):
    """标准响应格式"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PaginatedResponse(BaseModel):
    """分页响应格式"""
    total: int
    page: int
    page_size: int
    total_pages: int
    data: list

class ErrorResponse(BaseModel):
    """错误响应格式"""
    success: bool = False
    message: str
    error_code: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: datetime
    version: Optional[str] = None
    services: Optional[Dict[str, str]] = None
