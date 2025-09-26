"""
分析和问答API路由 - 简化版本用于测试
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from loguru import logger

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.project import Project
from app.models.literature import Literature
from app.core.exceptions import NotFoundError
from app.services.task_service import TaskService

router = APIRouter()

# ============================================
# 请求模型定义
# ============================================

class QuestionRequest(BaseModel):
    """问答请求模型"""
    project_id: int = Field(..., description="项目ID")
    question: str = Field(..., min_length=1, max_length=1000, description="问题内容")
    use_main_experience: bool = Field(default=False, description="是否使用主经验回答")
    context: Optional[Dict[str, Any]] = None

class ExperienceGenerationRequest(BaseModel):
    """经验生成请求模型"""
    project_id: int = Field(..., description="项目ID")
    processing_method: str = Field(default="enhanced", description="处理方式")
    research_question: Optional[str] = Field(default="通用研究问题", description="研究问题")

class IdeaGenerationRequest(BaseModel):
    """创新想法生成请求模型"""
    project_id: int = Field(..., description="项目ID")
    research_domain: str = Field(..., min_length=1, description="研究领域")
    innovation_direction: str = Field(..., min_length=1, description="创新方向")

# ============================================
# 响应模型定义
# ============================================

class QuestionResponse(BaseModel):
    """问答响应模型"""
    answer: str = Field(..., description="回答内容")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    sources: List[Dict] = Field(default=[], description="信息来源")
    related_literature: List[int] = Field(default=[], description="相关文献ID")
    processing_time: float = Field(..., description="处理时间")

class IdeaResponse(BaseModel):
    """创新想法响应模型"""
    ideas: List[Dict] = Field(..., description="创新想法列表")
    evaluation: Dict = Field(..., description="评估结果")
    recommendations: List[str] = Field(default=[], description="推荐建议")

# ============================================
# API端点实现
# ============================================

@router.post("/ask-question", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """智能问答功能"""
    
    # 验证项目存在和所有权
    project = db.query(Project).filter_by(
        id=request.project_id, 
        owner_id=current_user.id
    ).first()
    
    if not project:
        raise NotFoundError("项目", request.project_id)
    
    # 简化实现，返回测试数据
    return QuestionResponse(
        answer=f"针对问题 '{request.question}' 的回答：这是一个测试回答。项目ID: {request.project_id}",
        confidence=0.8,
        sources=[{"type": "test", "content": "测试数据源"}],
        related_literature=[],
        processing_time=0.5
    )

@router.post("/generate-experience")
async def generate_experience(
    request: ExperienceGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """启动经验生成任务"""
    
    try:
        # 验证项目存在和所有权
        project = db.query(Project).filter(
            Project.id == request.project_id,
            Project.owner_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail=f"项目 {request.project_id} 不存在")
        
        # 检查文献数量 - 使用正确的关联查询
        try:
            literature_count = db.query(Literature).filter(
                Literature.projects.any(id=request.project_id)
            ).count()
        except Exception as e:
            # 如果关联查询失败，使用简单查询
            print(f"文献查询失败: {e}")
            literature_count = 0
        
        # 模拟经验生成任务（实际环境中会启动Celery任务）
        if literature_count == 0:
            return {
                "success": True,
                "message": "项目暂无文献，无法生成经验",
                "project_id": request.project_id,
                "literature_count": literature_count,
                "status": "skipped"
            }
        
        # 使用统一任务服务创建任务并调度
        try:
            task_service = TaskService(db)
            task = task_service.create_experience_task(
                owner_id=current_user.id,
                project_id=request.project_id,
                research_question=request.research_question or "通用研究问题",
                processing_method=request.processing_method or "standard",
            )
        except Exception as exc:
            logger.error(f"创建经验生成任务失败: {exc}")
            raise HTTPException(status_code=500, detail="经验生成任务启动失败")

        return {
            "success": True,
            "message": "经验生成任务已启动",
            "project_id": request.project_id,
            "literature_count": literature_count,
            "task_id": task.id,
            "status": "processing",
            "processing_method": request.processing_method or "standard",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"经验生成失败: {e}")
        return {
            "success": False,
            "message": f"经验生成失败: {str(e)}",
            "project_id": request.project_id,
            "status": "failed"
        }

@router.post("/generate-main-experience")
async def generate_main_experience(
    project_id: int,
    research_domain: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """启动主经验生成任务"""
    
    # 验证项目存在和所有权
    project = db.query(Project).filter_by(
        id=project_id, 
        owner_id=current_user.id
    ).first()
    
    if not project:
        raise NotFoundError("项目", project_id)
    
    return {
        "message": "主经验生成功能测试成功",
        "project_id": project_id,
        "research_domain": research_domain,
        "status": "completed"
    }

@router.post("/generate-ideas", response_model=IdeaResponse)
async def generate_ideas(
    request: IdeaGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """生成科研创新想法"""
    
    # 验证项目存在和所有权
    project = db.query(Project).filter_by(
        id=request.project_id, 
        owner_id=current_user.id
    ).first()
    
    if not project:
        raise NotFoundError("项目", request.project_id)
    
    return IdeaResponse(
        ideas=[
            {"id": 1, "title": f"{request.research_domain}相关创新想法1", "description": f"基于{request.innovation_direction}的想法"},
            {"id": 2, "title": f"{request.research_domain}相关创新想法2", "description": f"进一步的{request.innovation_direction}研究"}
        ],
        evaluation={"feasibility": 0.8, "novelty": 0.9, "impact": 0.7},
        recommendations=["建议进行深入研究", "考虑实验验证", "寻找合作机会"]
    )

@router.get("/project/{project_id}/experience-books")
async def get_experience_books(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取项目的经验书列表"""
    
    # 验证项目存在和所有权
    project = db.query(Project).filter_by(
        id=project_id, 
        owner_id=current_user.id
    ).first()
    
    if not project:
        raise NotFoundError("项目", project_id)
    
    return {
        "experience_books": [
            {
                "id": 1,
                "title": f"项目{project_id}经验书1",
                "summary": "这是一个测试经验书",
                "created_at": "2024-01-01T00:00:00"
            }
        ]
    }

@router.get("/experience-book/{book_id}")
async def get_experience_book_detail(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取经验书详细内容"""
    
    return {
        "id": book_id,
        "title": f"经验书{book_id}",
        "content": "这是一个测试经验书的详细内容",
        "created_at": "2024-01-01T00:00:00"
    }

@router.get("/project/{project_id}/main-experience")
async def get_main_experience(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取项目主经验"""
    
    # 验证项目存在和所有权
    project = db.query(Project).filter_by(
        id=project_id, 
        owner_id=current_user.id
    ).first()
    
    if not project:
        raise NotFoundError("项目", project_id)
    
    return {
        "exists": True,
        "id": 1,
        "content": f"项目{project_id}的主经验内容测试",
        "created_at": "2024-01-01T00:00:00"
    }
