"""
智能交互系统的Pydantic数据模型
定义API请求和响应的数据结构
"""

from typing import Dict, List, Optional, Any, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field, validator


class InteractionStartRequest(BaseModel):
    """启动智能交互的请求模型"""
    user_input: str = Field(..., min_length=1, max_length=1000, description="用户输入内容")
    context_type: str = Field(..., description="交互类型: search, structuring, experience")
    project_id: int = Field(..., gt=0, description="项目ID")
    additional_context: Optional[Dict[str, Any]] = Field(default={}, description="额外上下文信息")

    @validator('context_type')
    def validate_context_type(cls, v):
        allowed_types = ['search', 'structuring', 'experience']
        if v not in allowed_types:
            raise ValueError(f'context_type必须是以下之一: {allowed_types}')
        return v

    @validator('user_input')
    def validate_user_input(cls, v):
        if not v.strip():
            raise ValueError('用户输入不能为空')
        return v.strip()


class ClarificationOptionModel(BaseModel):
    """澄清选项模型"""
    option_id: str = Field(..., description="选项唯一ID")
    title: str = Field(..., description="选项标题")
    description: str = Field(..., description="选项描述")
    icon: Optional[str] = Field(None, description="图标名称")
    estimated_time: Optional[str] = Field(None, description="预估处理时间")
    estimated_results: Optional[str] = Field(None, description="预估结果数量/类型")
    confidence_score: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="AI置信度")
    implications: List[str] = Field(default=[], description="选择此项的影响说明")
    is_recommended: bool = Field(False, description="是否为推荐项")
    metadata: Dict[str, Any] = Field(default={}, description="额外元数据")


class ClarificationCardModel(BaseModel):
    """澄清卡片模型"""
    session_id: str = Field(..., description="会话ID")
    stage: str = Field(..., description="当前阶段标识")
    question: str = Field(..., description="澄清问题")
    options: List[ClarificationOptionModel] = Field(..., description="选择项列表")
    recommended_option_id: str = Field(..., description="推荐选项ID")
    timeout_seconds: int = Field(5, ge=1, le=60, description="超时秒数")
    custom_input_allowed: bool = Field(True, description="是否允许自定义输入")
    context: Dict[str, Any] = Field(default={}, description="上下文信息")
    created_at: str = Field(..., description="创建时间(ISO格式)")


class InteractionStartResponse(BaseModel):
    """启动交互的响应模型"""
    success: bool = Field(..., description="是否成功")
    session_id: Optional[str] = Field(None, description="会话ID")
    requires_clarification: bool = Field(..., description="是否需要澄清")
    clarification_card: Optional[ClarificationCardModel] = Field(None, description="澄清卡片")
    direct_result: Optional[Dict[str, Any]] = Field(None, description="直接结果")
    error: Optional[str] = Field(None, description="错误信息")
    error_code: Optional[str] = Field(None, description="错误代码")


class SelectionRequest(BaseModel):
    """用户选择请求模型"""
    option_id: str = Field(..., description="选择的选项ID")
    selection_data: Optional[Dict[str, Any]] = Field(default={}, description="选择相关数据")
    client_timestamp: str = Field(..., description="客户端时间戳")

    @validator('client_timestamp')
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('client_timestamp必须是有效的ISO时间格式')


class TimeoutRequest(BaseModel):
    """超时请求模型"""
    timeout_timestamp: str = Field(..., description="超时时间戳")
    auto_selected_option_id: Optional[str] = Field(None, description="自动选择的选项ID")

    @validator('timeout_timestamp')
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('timeout_timestamp必须是有效的ISO时间格式')


class CustomInputRequest(BaseModel):
    """自定义输入请求模型"""
    custom_input: str = Field(..., min_length=1, max_length=500, description="用户自定义输入")
    context: Optional[Dict[str, Any]] = Field(default={}, description="输入上下文")
    client_timestamp: str = Field(..., description="客户端时间戳")

    @validator('custom_input')
    def validate_custom_input(cls, v):
        if not v.strip():
            raise ValueError('自定义输入不能为空')
        return v.strip()

    @validator('client_timestamp')
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('client_timestamp必须是有效的ISO时间格式')


class ProgressUpdateModel(BaseModel):
    """进度更新模型"""
    current_stage: str = Field(..., description="当前阶段")
    progress_percentage: float = Field(..., ge=0.0, le=100.0, description="进度百分比")
    estimated_remaining_time: Optional[int] = Field(None, description="预估剩余时间(秒)")


class SelectionResponse(BaseModel):
    """选择处理响应模型"""
    success: bool = Field(..., description="是否成功")
    next_action: str = Field(..., description="下一步操作")
    next_clarification_card: Optional[ClarificationCardModel] = Field(None, description="下一轮澄清卡片")
    workflow_result: Optional[Dict[str, Any]] = Field(None, description="工作流结果")
    progress_update: Optional[ProgressUpdateModel] = Field(None, description="进度更新")
    error: Optional[str] = Field(None, description="错误信息")
    error_code: Optional[str] = Field(None, description="错误代码")

    @validator('next_action')
    def validate_next_action(cls, v):
        allowed_actions = ['continue_workflow', 'next_clarification', 'complete_interaction']
        if v not in allowed_actions:
            raise ValueError(f'next_action必须是以下之一: {allowed_actions}')
        return v


class TimeoutResponse(SelectionResponse):
    """超时响应模型（继承自SelectionResponse）"""
    auto_selected: bool = Field(True, description="标识为自动选择")
    selected_option: ClarificationOptionModel = Field(..., description="被自动选择的选项")


class CustomInputResponse(BaseModel):
    """自定义输入响应模型"""
    success: bool = Field(..., description="是否成功")
    input_processed: bool = Field(..., description="输入是否被成功处理")
    ai_interpretation: Optional[str] = Field(None, description="AI对输入的理解")
    generated_options: Optional[List[ClarificationOptionModel]] = Field(None, description="基于输入生成的新选项")
    next_action: str = Field(..., description="下一步操作")
    next_clarification_card: Optional[ClarificationCardModel] = Field(None, description="下一轮澄清卡片")
    workflow_result: Optional[Dict[str, Any]] = Field(None, description="工作流结果")
    error: Optional[str] = Field(None, description="错误信息")
    error_code: Optional[str] = Field(None, description="错误代码")


class InteractionHistoryItem(BaseModel):
    """交互历史项模型"""
    timestamp: str = Field(..., description="时间戳")
    stage: str = Field(..., description="阶段")
    user_action: str = Field(..., description="用户操作类型")
    action_data: Dict[str, Any] = Field(..., description="操作数据")
    ai_response: Dict[str, Any] = Field(..., description="AI响应")

    @validator('user_action')
    def validate_user_action(cls, v):
        allowed_actions = ['selection', 'custom_input', 'timeout']
        if v not in allowed_actions:
            raise ValueError(f'user_action必须是以下之一: {allowed_actions}')
        return v


class ClarificationResponse(BaseModel):
    """获取澄清卡片响应模型"""
    success: bool = Field(..., description="是否成功")
    clarification_cards: List[ClarificationCardModel] = Field(..., description="澄清卡片列表")
    current_stage: str = Field(..., description="当前阶段")
    interaction_history: List[InteractionHistoryItem] = Field(..., description="交互历史")
    error: Optional[str] = Field(None, description="错误信息")


class SessionStatistics(BaseModel):
    """会话统计模型"""
    total_rounds: int = Field(..., description="总轮次")
    user_selections: int = Field(..., description="用户主动选择次数")
    auto_selections: int = Field(..., description="自动选择次数")
    custom_inputs: int = Field(..., description="自定义输入次数")
    average_response_time: float = Field(..., description="平均响应时间(秒)")


class SessionInfo(BaseModel):
    """会话信息模型"""
    session_id: str = Field(..., description="会话ID")
    user_id: int = Field(..., description="用户ID")
    project_id: int = Field(..., description="项目ID")
    context_type: str = Field(..., description="交互类型")
    current_stage: str = Field(..., description="当前阶段")
    is_active: bool = Field(..., description="是否活跃")
    created_at: str = Field(..., description="创建时间")
    last_activity: str = Field(..., description="最后活动时间")
    timeout_at: Optional[str] = Field(None, description="会话超时时间")


class SessionStatusResponse(BaseModel):
    """会话状态响应模型"""
    success: bool = Field(..., description="是否成功")
    session: SessionInfo = Field(..., description="会话信息")
    statistics: SessionStatistics = Field(..., description="统计信息")
    error: Optional[str] = Field(None, description="错误信息")


class EndSessionRequest(BaseModel):
    """结束会话请求模型"""
    reason: Optional[str] = Field(None, description="结束原因")
    feedback: Optional[Dict[str, Any]] = Field(default={}, description="用户反馈")

    @validator('reason')
    def validate_reason(cls, v):
        if v is not None:
            allowed_reasons = ['user_cancelled', 'completed', 'timeout', 'error']
            if v not in allowed_reasons:
                raise ValueError(f'reason必须是以下之一: {allowed_reasons}')
        return v


class SessionSummary(BaseModel):
    """会话摘要模型"""
    session_id: str = Field(..., description="会话ID")
    total_duration: float = Field(..., description="总时长(秒)")
    rounds_completed: int = Field(..., description="完成轮次")
    final_result: Optional[Dict[str, Any]] = Field(None, description="最终结果")
    effectiveness_score: Optional[float] = Field(None, description="效果评分")


class EndSessionResponse(BaseModel):
    """结束会话响应模型"""
    success: bool = Field(..., description="是否成功")
    session_summary: SessionSummary = Field(..., description="会话摘要")
    cleanup_status: str = Field(..., description="清理状态")
    error: Optional[str] = Field(None, description="错误信息")

    @validator('cleanup_status')
    def validate_cleanup_status(cls, v):
        allowed_status = ['completed', 'partial', 'failed']
        if v not in allowed_status:
            raise ValueError(f'cleanup_status必须是以下之一: {allowed_status}')
        return v


# WebSocket事件模型
class WebSocketEvent(BaseModel):
    """WebSocket事件基础模型"""
    type: str = Field(..., description="事件类型")
    session_id: str = Field(..., description="会话ID")
    timestamp: int = Field(..., description="时间戳")


class ClarificationRequiredEvent(WebSocketEvent):
    """澄清卡片推送事件"""
    type: Literal["clarification_required"] = "clarification_required"
    clarification_card: ClarificationCardModel = Field(..., description="澄清卡片")


class OptionSelectedEvent(WebSocketEvent):
    """选择处理结果事件"""
    type: Literal["option_selected"] = "option_selected"
    selected_option: ClarificationOptionModel = Field(..., description="选择的选项")
    processing_result: SelectionResponse = Field(..., description="处理结果")


class AutoSelectedEvent(WebSocketEvent):
    """自动选择通知事件"""
    type: Literal["auto_selected"] = "auto_selected"
    selected_option: ClarificationOptionModel = Field(..., description="自动选择的选项")
    auto_selection_reason: str = Field(..., description="自动选择原因")
    processing_result: TimeoutResponse = Field(..., description="处理结果")


class InteractionCompletedEvent(WebSocketEvent):
    """交互完成事件"""
    type: Literal["interaction_completed"] = "interaction_completed"
    final_result: Dict[str, Any] = Field(..., description="最终结果")
    session_summary: SessionSummary = Field(..., description="会话摘要")
    next_action: str = Field(..., description="下一步操作")

    @validator('next_action')
    def validate_next_action(cls, v):
        allowed_actions = ['redirect', 'refresh', 'continue']
        if v not in allowed_actions:
            raise ValueError(f'next_action必须是以下之一: {allowed_actions}')
        return v


class ProgressUpdateEvent(WebSocketEvent):
    """进度更新事件"""
    type: Literal["progress_update"] = "progress_update"
    current_stage: str = Field(..., description="当前阶段")
    progress_percentage: float = Field(..., ge=0.0, le=100.0, description="进度百分比")
    stage_description: str = Field(..., description="阶段描述")
    estimated_remaining_time: Optional[int] = Field(None, description="预估剩余时间(秒)")


class ErrorEvent(WebSocketEvent):
    """错误通知事件"""
    type: Literal["error"] = "error"
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误信息")
    severity: str = Field(..., description="严重程度")
    recovery_action: Optional[str] = Field(None, description="恢复操作")

    @validator('severity')
    def validate_severity(cls, v):
        allowed_severity = ['low', 'medium', 'high', 'critical']
        if v not in allowed_severity:
            raise ValueError(f'severity必须是以下之一: {allowed_severity}')
        return v


class TimerSyncEvent(WebSocketEvent):
    """倒计时同步事件"""
    type: Literal["timer_sync"] = "timer_sync"
    remaining_seconds: int = Field(..., ge=0, description="剩余秒数")
    recommended_option_id: str = Field(..., description="推荐选项ID")
    timer_status: str = Field(..., description="计时器状态")

    @validator('timer_status')
    def validate_timer_status(cls, v):
        allowed_status = ['running', 'paused', 'stopped']
        if v not in allowed_status:
            raise ValueError(f'timer_status必须是以下之一: {allowed_status}')
        return v