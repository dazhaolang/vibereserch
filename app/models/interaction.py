"""
智能交互系统数据模型
实现类似天工Skywork的澄清机制数据结构
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class InteractionSession(Base):
    """交互会话表 - 管理用户的智能交互会话"""
    __tablename__ = "interaction_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)

    # 交互类型：search(文献搜索), structuring(结构化处理), experience(经验生成)
    context_type = Column(String(50), nullable=False)
    current_stage = Column(String(100))

    # 交互历史记录
    interaction_history = Column(JSON, default=list)

    # 用户偏好设置
    user_preferences = Column(JSON, default=dict)

    # 会话状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime)  # 会话过期时间

    # 关联关系
    user = relationship("User")
    project = relationship("Project")
    clarification_cards = relationship("ClarificationCard", back_populates="session")


class ClarificationCard(Base):
    """澄清卡片表 - 存储AI生成的澄清选项"""
    __tablename__ = "clarification_cards"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey('interaction_sessions.session_id'), nullable=False)
    card_id = Column(String(255), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    # 澄清阶段和轮次
    stage = Column(String(100), nullable=False)
    round_number = Column(Integer, default=1)

    # 澄清问题和选项
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # AI动态生成的选择项列表
    recommended_option_id = Column(String(255))  # 推荐选项ID

    # 用户选择结果
    user_selection = Column(JSON)  # 用户选择的详细信息
    selection_time = Column(DateTime)
    resolution_type = Column(String(50))  # selection, custom_input, timeout
    is_auto_selected = Column(Boolean, default=False)

    # 超时设置
    timeout_seconds = Column(Integer, default=5)
    custom_input_allowed = Column(Boolean, default=True)

    # AI生成相关
    ai_generation_prompt = Column(Text)  # AI生成时使用的提示词
    generation_confidence = Column(Float, default=0.0)  # AI生成置信度

    # 上下文信息
    context = Column(JSON, default=dict)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)

    # 关联关系
    session = relationship("InteractionSession", back_populates="clarification_cards")


class InteractionAnalytics(Base):
    """交互分析表 - 收集用户交互行为数据"""
    __tablename__ = "interaction_analytics"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), ForeignKey('interaction_sessions.session_id'))
    user_id = Column(Integer, ForeignKey('users.id'))

    # 事件类型
    event_type = Column(String(100), nullable=False)  # start, select, timeout, custom_input, complete
    event_data = Column(JSON, default=dict)

    # 性能指标
    response_time_ms = Column(Integer)  # 用户响应时间(毫秒)
    ai_generation_time_ms = Column(Integer)  # AI生成时间(毫秒)

    # 用户行为
    user_confidence = Column(Float)  # 用户选择信心度(可选)
    interaction_quality_score = Column(Float)  # 交互质量评分

    created_at = Column(DateTime, default=datetime.utcnow)


# 导入缺失的Float类型
from sqlalchemy import Float