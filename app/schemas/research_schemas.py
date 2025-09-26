"""Schemas for research mode API"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResearchQueryRequest(BaseModel):
    project_id: int
    query: str
    mode: str = Field(..., pattern="^(rag|deep|auto)$")
    max_literature_count: int = 10
    context_literature_ids: Optional[List[int]] = None
    processing_method: Optional[str] = None
    keywords: Optional[List[str]] = None
    auto_config: Optional[Dict[str, Any]] = None
    agent: Optional[str] = Field(default=None, description="自动模式使用的调度智能体，例如 claude/codex/gemini")


class ResearchQueryResponse(BaseModel):
    mode: str
    payload: Dict[str, Any]


class ResearchAnalysisRequest(BaseModel):
    query: str
    project_id: int
    context: Optional[Dict[str, Any]] = None


class ResearchAnalysisResponse(BaseModel):
    recommended_mode: str = Field(..., description="推荐的研究模式 (rag|deep|auto)")
    sub_questions: List[str] = Field(default_factory=list, description="拆解的子问题列表")
    complexity_score: float = Field(default=0.5, description="问题复杂度评分 (0-1)")
    estimated_resources: Dict[str, Any] = Field(default_factory=dict, description="预估资源需求")
    reasoning: str = Field(default="", description="推荐理由")
    suggested_keywords: List[str] = Field(default_factory=list, description="建议的搜索关键词")
    processing_suggestions: Dict[str, Any] = Field(default_factory=dict, description="处理建议配置")


class ResearchResult(BaseModel):
    id: int
    task_id: int
    project_id: int
    mode: str
    query: str
    status: str
    progress: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    main_answer: Optional[str] = None
    literature_sources: Optional[List[Dict[str, Any]]] = None
    experience_books: Optional[List[Dict[str, Any]]] = None
    experiment_suggestions: Optional[List[Dict[str, Any]]] = None
    confidence_metrics: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResearchResultResponse(ResearchResult):
    pass


class ResearchHistoryResponse(BaseModel):
    items: List[ResearchResult]
    total: int
    page: int
    size: int


class ResearchTaskStatusResponse(BaseModel):
    status: str
    progress: float
    message: Optional[str] = None
    estimated_time: Optional[int] = None
