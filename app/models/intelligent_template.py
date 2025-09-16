"""
智能模板数据模型
支持用户友好的模板配置和双重提示词系统
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class TemplateDiscovery(Base):
    """模板发现记录 - 记录AI从文献中发现的研究模式"""
    __tablename__ = "template_discoveries"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # 发现结果
    field_name = Column(String(200))  # AI识别的研究领域名称
    research_discovery = Column(JSON)  # 完整的研究发现结果
    extraction_strategy = Column(JSON)  # 生成的提取策略
    
    # 样本文献信息
    representative_literature_ids = Column(JSON)  # 使用的代表性文献ID列表
    total_literature_analyzed = Column(Integer)  # 分析的文献总数
    
    # 质量指标
    discovery_confidence = Column(Float, default=0.0)  # AI发现的置信度
    user_validation_score = Column(Float)  # 用户验证评分
    
    # 状态
    status = Column(String(50), default="generated")  # generated, user_reviewed, active, archived
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    project = relationship("Project", back_populates="template_discoveries")
    prompt_templates = relationship("PromptTemplate", back_populates="discovery")


class PromptTemplate(Base):
    """双重提示词模板 - 用户友好版本 + 技术执行版本"""
    __tablename__ = "prompt_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    discovery_id = Column(Integer, ForeignKey("template_discoveries.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # 基本信息
    section_name = Column(String(200), nullable=False)  # 板块名称
    display_order = Column(Integer, default=0)  # 显示顺序
    
    # 用户友好版本
    display_title = Column(String(300))  # 用户看到的标题
    user_description = Column(Text)  # 用户理解的说明
    user_examples = Column(JSON)  # 示例列表
    is_user_configurable = Column(Boolean, default=True)  # 用户是否可以配置
    
    # 技术执行版本
    system_prompt = Column(Text, nullable=False)  # AI执行的详细提示词
    extraction_rules = Column(JSON)  # 具体提取规则
    output_format = Column(Text)  # 期望输出格式
    fallback_instructions = Column(Text)  # 无内容时的处理方式
    
    # 用户定制
    user_modifications = Column(JSON)  # 用户的修改记录
    custom_instructions = Column(Text)  # 用户自定义指令
    
    # 性能统计
    usage_count = Column(Integer, default=0)  # 使用次数
    success_rate = Column(Float, default=0.0)  # 成功率
    avg_extraction_quality = Column(Float, default=0.0)  # 平均提取质量
    
    # 状态
    is_active = Column(Boolean, default=True)
    version = Column(String(20), default="1.0")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    discovery = relationship("TemplateDiscovery", back_populates="prompt_templates")
    project = relationship("Project", back_populates="prompt_templates")
    user_feedbacks = relationship("PromptFeedback", back_populates="prompt_template")


class PromptFeedback(Base):
    """用户对提示词的反馈"""
    __tablename__ = "prompt_feedbacks"
    
    id = Column(Integer, primary_key=True, index=True)
    prompt_template_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 反馈内容
    feedback_type = Column(String(50), nullable=False)  # improvement, complaint, suggestion
    rating = Column(Integer)  # 1-5 评分
    feedback_text = Column(Text)  # 具体反馈内容
    suggested_changes = Column(JSON)  # 建议的修改
    
    # 处理状态
    status = Column(String(50), default="pending")  # pending, reviewed, implemented, rejected
    admin_response = Column(Text)  # 管理员回复
    implemented_changes = Column(JSON)  # 已实施的改动
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    prompt_template = relationship("PromptTemplate", back_populates="user_feedbacks")
    user = relationship("User")


class ExtractionResult(Base):
    """基于智能模板的提取结果"""
    __tablename__ = "extraction_results"
    
    id = Column(Integer, primary_key=True, index=True)
    literature_id = Column(Integer, ForeignKey("literature.id"), nullable=False)
    prompt_template_id = Column(Integer, ForeignKey("prompt_templates.id"), nullable=False)
    
    # 提取结果
    extracted_content = Column(JSON)  # 提取的结构化内容
    extraction_confidence = Column(Float, default=0.0)  # 提取置信度
    processing_time = Column(Float)  # 处理时间（秒）
    
    # 质量评估
    content_completeness = Column(Float, default=0.0)  # 内容完整性
    data_accuracy = Column(Float, default=0.0)  # 数据准确性
    format_compliance = Column(Float, default=0.0)  # 格式合规性
    
    # 元数据
    extraction_method = Column(String(100), default="intelligent_template")
    model_used = Column(String(100))  # 使用的AI模型
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    literature = relationship("Literature")
    prompt_template = relationship("PromptTemplate")