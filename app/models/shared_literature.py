"""
优化的文献存储架构设计 - MySQL版本
实现全局文献去重和共享存储
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, DECIMAL, Float, ForeignKey, Table, Index, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

# 用户文献引用关联表 (替代原来的project_literature_association)
user_literature_reference_association = Table(
    'user_literature_reference_associations',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('literature_reference_id', Integer, ForeignKey('user_literature_references.id'), primary_key=True),
    Column('added_at', TIMESTAMP, server_default=func.now()),
    Column('user_notes', Text),  # 用户对这篇文献的笔记
    Column('user_tags', JSON),   # 用户自定义标签
    mysql_engine='InnoDB',
    mysql_charset='utf8mb4'
)

class SharedLiterature(Base):
    """
    全局共享文献库 - 去重存储所有文献的处理结果
    """
    __tablename__ = "shared_literature"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 去重标识 - 用于检查是否已存在
    doi = Column(String(200), unique=True, index=True)  # DOI作为主要去重标识
    arxiv_id = Column(String(100), unique=True, index=True)  # ArXiv ID
    title_hash = Column(String(64), index=True)  # 标题哈希，用于无DOI文献去重
    content_hash = Column(String(64), unique=True, index=True)  # PDF内容哈希
    
    # 基础文献信息
    title = Column(Text, nullable=False)
    authors = Column(JSON)  # 作者列表
    abstract = Column(Text)
    keywords = Column(JSON)
    
    # 发表信息  
    journal = Column(String(500))
    publication_year = Column(Integer)
    volume = Column(String(50))
    issue = Column(String(50))
    pages = Column(String(100))
    
    # 来源信息
    source_platform = Column(String(100))
    source_url = Column(Text)
    pdf_url = Column(Text)
    
    # 质量评估
    citation_count = Column(Integer, default=0)
    impact_factor = Column(Float)
    quality_score = Column(Float)
    
    # ⭐ 关键：处理结果存储
    pdf_path = Column(String(500))  # PDF文件路径（全局共享）
    markdown_content = Column(Text)  # MinerU处理后的Markdown内容
    structured_data = Column(JSON)  # 结构化提取的数据
    processing_metadata = Column(JSON)  # 处理元数据（MinerU版本、处理时间等）
    
    # 处理状态
    is_downloaded = Column(Boolean, default=False)
    is_processed = Column(Boolean, default=False)
    processing_status = Column(String(50), default="pending")
    last_processed_at = Column(DateTime(timezone=True))
    
    # 向量嵌入已移动到Elasticsearch
    # title_embedding = 在ES中存储
    # abstract_embedding = 在ES中存储
    # content_embedding = 在ES中存储
    
    # 使用统计
    reference_count = Column(Integer, default=0)  # 被引用次数
    download_count = Column(Integer, default=0)   # 下载次数
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    references = relationship("UserLiteratureReference", back_populates="shared_literature")
    segments = relationship("SharedLiteratureSegment", back_populates="shared_literature")

    # 索引优化
    __table_args__ = (
        Index('idx_shared_lit_doi_hash', 'doi', 'content_hash'),
        Index('idx_shared_lit_title_year', 'title_hash', 'publication_year'),
        Index('idx_shared_lit_processing', 'processing_status', 'is_processed'),
    )

class UserLiteratureReference(Base):
    """
    用户文献引用表 - 存储用户对共享文献的引用
    """
    __tablename__ = "user_literature_references"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联信息
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shared_literature_id = Column(Integer, ForeignKey("shared_literature.id"), nullable=False)
    
    # 用户个性化信息
    user_title = Column(String(500))  # 用户自定义标题（如果需要）
    user_notes = Column(Text)         # 用户笔记
    user_tags = Column(JSON)          # 用户标签
    user_category = Column(String(200))  # 用户分类
    importance_score = Column(Float, default=0.5)  # 用户评价的重要性
    
    # 用户特定的处理状态
    reading_status = Column(String(50), default="unread")  # unread, reading, read, important
    user_rating = Column(Float)  # 用户评分
    
    # 关联项目信息（一个引用可以被多个项目使用）
    is_active = Column(Boolean, default=True)
    
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed = Column(DateTime(timezone=True))
    
    # 关系
    user = relationship("User")
    shared_literature = relationship("SharedLiterature", back_populates="references")
    projects = relationship("Project", secondary="user_literature_reference_associations", back_populates="literature_references")
    
    # 确保用户不会重复引用同一文献
    __table_args__ = (
        Index('idx_user_lit_unique', 'user_id', 'shared_literature_id', unique=True),
        Index('idx_user_lit_status', 'user_id', 'reading_status'),
    )

class SharedLiteratureSegment(Base):
    """
    共享文献段落表 - 存储MinerU处理后的结构化段落
    """
    __tablename__ = "shared_literature_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    shared_literature_id = Column(Integer, ForeignKey("shared_literature.id"), nullable=False)
    
    # 段落信息
    segment_type = Column(String(100))  # 段落类型：abstract, introduction, method, result, conclusion
    section_title = Column(String(500))
    content = Column(Text, nullable=False)
    markdown_content = Column(Text)  # Markdown格式内容
    
    # 位置信息
    page_number = Column(Integer)
    paragraph_index = Column(Integer)
    section_level = Column(Integer)  # 章节层级
    
    # 结构化数据
    structured_data = Column(JSON)
    extraction_confidence = Column(DECIMAL(5, 3))
    
    # 向量嵌入已移动到Elasticsearch
    # content_embedding = 在ES中存储
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    shared_literature = relationship("SharedLiterature", back_populates="segments")

# 更新Project模型以使用新的关联
class ProjectLiteratureReference(Base):
    """
    项目文献引用关系表
    """
    __tablename__ = "project_literature_references"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_literature_reference_id = Column(Integer, ForeignKey("user_literature_references.id"), nullable=False)
    
    # 项目特定信息
    added_to_project_at = Column(DateTime(timezone=True), server_default=func.now())
    project_notes = Column(Text)  # 项目特定笔记
    relevance_score = Column(Float, default=0.5)  # 与项目的相关性评分
    
    # 关系
    project = relationship("Project")
    literature_reference = relationship("UserLiteratureReference")
    
    __table_args__ = (
        Index('idx_proj_lit_ref_unique', 'project_id', 'user_literature_reference_id', unique=True),
    )

# 文献处理任务队列
class LiteratureProcessingTask(Base):
    """
    文献处理任务队列 - 管理PDF下载和处理任务
    """
    __tablename__ = "literature_processing_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    shared_literature_id = Column(Integer, ForeignKey("shared_literature.id"), nullable=False)
    
    # 任务信息
    task_type = Column(String(50), nullable=False)  # download, process, both
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    priority = Column(Integer, default=5)  # 1-10, 10最高优先级
    
    # 处理信息
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    processing_log = Column(JSON)
    
    # 资源使用
    cpu_time = Column(Float)  # CPU时间（秒）
    memory_usage = Column(Integer)  # 内存使用（MB）
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    shared_literature = relationship("SharedLiterature")
    
    __table_args__ = (
        Index('idx_task_status_priority', 'status', 'priority'),
        Index('idx_task_created', 'created_at'),
    )