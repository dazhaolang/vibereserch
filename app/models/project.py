"""
项目相关数据模型 - MySQL版本
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Table, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

# 项目文献关联表
project_literature_association = Table(
    'project_literature_associations',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id'), primary_key=True),
    Column('literature_id', Integer, ForeignKey('literature.id'), primary_key=True),
    Column('added_at', TIMESTAMP, server_default=func.now()),
    mysql_engine='InnoDB',
    mysql_charset='utf8mb4'
)

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)

    # 研究方向和关键词
    research_direction = Column(String(500))
    keywords = Column(JSON)  # 存储关键词列表
    research_categories = Column(JSON)  # 研究分类层级
    research_field = Column(String(200), index=True)  # 研究领域

    # 项目状态
    status = Column(String(50), default="active")  # active, completed, archived

    # 文献采集配置
    literature_sources = Column(JSON)  # 文献来源配置
    max_literature_count = Column(Integer, default=1000)

    # 轻结构化配置
    structure_template = Column(JSON)  # 轻结构化模板
    extraction_prompts = Column(JSON)  # 提取提示词

    # 用户关联
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 公共/私有设置
    is_public = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    owner = relationship("User", back_populates="projects")
    literature = relationship("Literature", secondary=project_literature_association, back_populates="projects")
    literature_references = relationship("UserLiteratureReference", secondary="user_literature_reference_associations", back_populates="projects")
    tasks = relationship("Task", back_populates="project")
    experience_books = relationship("ExperienceBook", back_populates="project")
    main_experiences = relationship("MainExperience", back_populates="project")
    template_discoveries = relationship("TemplateDiscovery", back_populates="project")
    prompt_templates = relationship("PromptTemplate", back_populates="project")

    # 索引配置 - MySQL
    __table_args__ = (
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'},
    )