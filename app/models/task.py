"""
任务和进度相关数据模型
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Float, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class TaskType(enum.Enum):
    LITERATURE_COLLECTION = "literature_collection"
    LITERATURE_SCREENING = "literature_screening" 
    STRUCTURE_EXTRACTION = "structure_extraction"
    EXPERIENCE_GENERATION = "experience_generation"
    MAIN_EXPERIENCE_UPDATE = "main_experience_update"
    QUESTION_ANALYSIS = "question_analysis"

class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    # 任务基础信息
    task_type = Column(String(50), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    # 任务配置
    config = Column(JSON)  # 任务配置参数
    input_data = Column(JSON)  # 输入数据
    
    # 执行状态
    status = Column(String(50), default="pending")
    progress_percentage = Column(Float, default=0.0)
    current_step = Column(String(200))
    
    # 执行结果
    result = Column(JSON)  # 任务结果
    error_message = Column(Text)  # 错误信息
    
    # 时间统计
    estimated_duration = Column(Integer)  # 预估耗时（秒）
    actual_duration = Column(Integer)  # 实际耗时（秒）
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    project = relationship("Project", back_populates="tasks")
    progress_logs = relationship("TaskProgress", back_populates="task")

class TaskProgress(Base):
    __tablename__ = "task_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    
    # 进度信息
    step_name = Column(String(200), nullable=False)
    step_description = Column(Text)
    progress_percentage = Column(Float, nullable=False)
    
    # 步骤结果
    step_result = Column(JSON)
    step_metrics = Column(JSON)  # 步骤指标（如处理文献数量等）
    
    # 时间信息
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # 关系
    task = relationship("Task", back_populates="progress_logs")