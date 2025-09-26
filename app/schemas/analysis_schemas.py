"""
分析模块相关的数据模型
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from datetime import datetime

# 经验书响应模型
class ExperienceBookItem(BaseModel):
    """单个经验书项"""
    id: int
    title: str
    iteration_round: int
    content_summary: str
    quality_score: float
    created_at: str
    updated_at: Optional[str] = None

class ExperienceBooksResponse(BaseModel):
    """经验书列表响应模型"""
    experience_books: List[ExperienceBookItem]
    total_count: int

# 主经验响应模型  
class MainExperienceItem(BaseModel):
    """主经验项"""
    id: int
    experience_type: Optional[str] = None
    research_domain: Optional[str] = None
    title: str
    content: str
    version: str
    iteration_round: int
    confidence_score: float
    quality_score: Optional[float] = None
    completeness_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    usefulness_score: Optional[float] = None
    literature_count: int
    source_literature_count: Optional[int] = None
    status: str
    key_findings: Optional[List[str]] = None
    practical_guidelines: Optional[List[str]] = None
    source_books: List[Dict[str, Any]]
    created_at: str
    updated_at: Optional[str] = None
    is_current: bool

class MainExperienceResponse(BaseModel):
    """主经验响应模型"""
    main_experience: Optional[MainExperienceItem]
    message: Optional[str] = None
