"""
文献相关数据模型 - MySQL版本
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, Float, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.project import project_literature_association

class Literature(Base):
    __tablename__ = "literature"

    id = Column(Integer, primary_key=True, index=True)

    # 基础信息
    title = Column(Text, nullable=False)
    authors = Column(JSON)  # 作者列表
    abstract = Column(Text)
    keywords = Column(JSON)  # 关键词列表

    # 发表信息
    journal = Column(String(500))
    publication_year = Column(Integer, index=True)
    volume = Column(String(50))
    issue = Column(String(50))
    pages = Column(String(100))
    doi = Column(String(200), unique=True, index=True)

    # 来源信息
    source_platform = Column(String(100), index=True)  # Google Scholar, Semantic Scholar等
    source_url = Column(Text)
    pdf_url = Column(Text)

    # 文献质量评估
    citation_count = Column(Integer, default=0)
    impact_factor = Column(DECIMAL(10, 3))
    quality_score = Column(DECIMAL(5, 3), index=True)  # 综合质量评分
    reliability_score = Column(DECIMAL(3, 2), default=0.5)  # 可靠性评分 (0-1)
    source_reliability = Column(String(50), default="unknown")  # 来源可靠性等级: high, medium, low, unknown

    # 分类和标签 - 用于批量操作
    tags = Column(JSON)  # 标签列表
    category = Column(String(200), index=True)  # 文献分类

    # 处理状态
    is_downloaded = Column(Boolean, default=False)
    is_parsed = Column(Boolean, default=False)
    parsing_status = Column(String(50), default="pending")
    status = Column(String(50), default="pending", index=True)  # 处理状态
    parsed_content = Column(Text)  # 解析后的内容
    pdf_path = Column(String(500))  # PDF文件路径

    # 文件信息
    file_path = Column(String(500))
    file_size = Column(Integer)
    file_hash = Column(String(100))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    segments = relationship("LiteratureSegment", back_populates="literature", cascade="all, delete-orphan")
    projects = relationship("Project", secondary=project_literature_association, back_populates="literature")

    # 索引配置 - MySQL全文索引
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )

class LiteratureSegment(Base):
    __tablename__ = "literature_segments"

    id = Column(Integer, primary_key=True, index=True)
    literature_id = Column(Integer, ForeignKey("literature.id"), nullable=False, index=True)

    # 分段信息
    segment_type = Column(String(100), index=True)  # 分段类型：制备、表征、机理等
    section_title = Column(String(500))  # 章节标题
    content = Column(Text, nullable=False)  # 轻结构化内容
    original_text = Column(Text)  # 原始文本（仅用于内部处理）

    # 位置信息
    page_number = Column(Integer)
    paragraph_index = Column(Integer)

    # 结构化元数据
    structured_data = Column(JSON)  # 结构化提取的数据
    extraction_confidence = Column(DECIMAL(5, 3))  # 提取置信度

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    literature = relationship("Literature", back_populates="segments")

    # 索引配置 - MySQL全文索引
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )