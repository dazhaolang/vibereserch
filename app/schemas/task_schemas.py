"""Pydantic schemas for Task APIs"""

from typing import List, Optional, Dict
from datetime import datetime

from pydantic import BaseModel, Field


class TaskProgressSchema(BaseModel):
    step_name: str
    step_description: Optional[str]
    progress_percentage: float
    step_result: Optional[dict]
    step_metrics: Optional[dict]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskDetailResponse(BaseModel):
    id: int
    project_id: int
    task_type: str
    title: str
    description: Optional[str]
    config: Optional[dict]
    input_data: Optional[dict]
    status: str
    progress_percentage: float
    current_step: Optional[str]
    result: Optional[dict]
    error_message: Optional[str]
    token_usage: Optional[float]
    cost_estimate: Optional[float]
    cost_breakdown: Optional[dict]
    estimated_duration: Optional[int]
    actual_duration: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    progress_logs: List[TaskProgressSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: List[TaskDetailResponse]


class TaskRetryRequest(BaseModel):
    force: bool = False


class TaskCancelResponse(BaseModel):
    success: bool
    message: str


class TaskStatusBreakdown(BaseModel):
    status: str
    count: int


class TaskCostSummary(BaseModel):
    total_token_usage: float
    total_cost_estimate: float
    models: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class TaskStatisticsResponse(BaseModel):
    total_tasks: int
    status_breakdown: List[TaskStatusBreakdown] = Field(default_factory=list)
    running_tasks: List[int] = Field(default_factory=list)
    recent_tasks: List[TaskDetailResponse] = Field(default_factory=list)
    cost_summary: TaskCostSummary
