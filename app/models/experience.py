"""
经验书和主经验相关数据模型 - MySQL版本
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, DECIMAL, Float, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class ExperienceBook(Base):
    __tablename__ = "experience_books"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # 基础信息
    title = Column(String(500), nullable=False)
    research_question = Column(Text, nullable=False)  # 原始研究问题
    
    # 迭代信息
    iteration_round = Column(Integer, default=1)
    total_literature_count = Column(Integer, default=0)
    current_batch_count = Column(Integer, default=0)
    
    # 内容
    content = Column(Text, nullable=False)  # 经验书内容
    summary = Column(Text)  # 内容摘要
    key_insights = Column(JSON)  # 关键洞察
    
    # 质量评估
    content_richness_score = Column(Float)  # 内容丰富度
    novelty_score = Column(Float)  # 新颖性评分
    information_gain = Column(Float)  # 信息增益
    
    # 状态
    is_final = Column(Boolean, default=False)
    status = Column(String(50), default="generating")  # generating, completed, archived
    
    # 向量嵌入已移动到Elasticsearch
    # content_embedding = 在ES中存储
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    project = relationship("Project", back_populates="experience_books")

class MainExperience(Base):
    __tablename__ = "main_experiences"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # 基础信息
    title = Column(String(500), nullable=False)
    research_domain = Column(String(200))  # 研究领域
    coverage_scope = Column(JSON)  # 覆盖范围（如制备方法列表）
    
    # 内容
    content = Column(Text, nullable=False)
    structured_knowledge = Column(JSON)  # 结构化知识表示
    methodology_summary = Column(JSON)  # 方法论总结
    
    # 统计信息
    source_literature_count = Column(Integer, default=0)
    last_update_round = Column(Integer, default=0)
    usage_count = Column(Integer, default=0)  # 被调用次数
    
    # 质量指标
    completeness_score = Column(Float)  # 完整性评分
    accuracy_score = Column(Float)  # 准确性评分
    usefulness_score = Column(Float)  # 实用性评分
    
    # 版本控制
    version = Column(String(20), default="1.0")
    is_current = Column(Boolean, default=True)
    
    # 向量嵌入已移动到Elasticsearch
    # content_embedding = 在ES中存储
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    project = relationship("Project", back_populates="main_experiences")