"""
智能模板管理API路由
提供完全动态的模板生成、用户友好的界面管理、反馈机制
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
import json

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.project import Project
from app.models.literature import Literature
from app.models.intelligent_template import TemplateDiscovery, PromptTemplate, PromptFeedback
from app.services.intelligent_template_service import IntelligentTemplateService
from loguru import logger

router = APIRouter()

# ======================== Pydantic Models ========================

class TemplateGenerationRequest(BaseModel):
    """模板生成请求"""
    project_id: int
    force_regenerate: bool = False  # 是否强制重新生成
    max_literature_samples: int = Field(default=50, ge=5, le=200)  # 最大样本数量


class TemplateGenerationResponse(BaseModel):
    """模板生成响应"""
    success: bool
    discovery_id: Optional[int] = None
    field_name: Optional[str] = None
    research_areas: List[Dict] = []
    user_friendly_prompts: List[Dict] = []
    confidence: float = 0.0
    representative_literature_count: int = 0
    message: Optional[str] = None


class UserFriendlyPrompt(BaseModel):
    """用户友好的提示词展示"""
    section_name: str
    display_title: str
    description: str
    examples: List[str] = []
    is_configurable: bool = True
    current_status: str = "active"  # active, inactive, needs_review


class PromptUpdateRequest(BaseModel):
    """提示词更新请求"""
    prompt_template_id: int
    user_modifications: Dict
    custom_instructions: Optional[str] = None
    reason: str = "User customization"


class FeedbackSubmissionRequest(BaseModel):
    """反馈提交请求"""
    prompt_template_id: int
    feedback_type: str = Field(..., pattern="^(improvement|complaint|suggestion)$")
    rating: int = Field(..., ge=1, le=5)
    feedback_text: str
    suggested_changes: Optional[Dict] = None


# ======================== API Endpoints ========================

@router.post("/projects/{project_id}/templates/generate", response_model=TemplateGenerationResponse)
async def generate_intelligent_template(
    project_id: int,
    request: TemplateGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    为项目生成智能模板
    
    核心功能：从项目文献中完全自主发现研究重点，生成针对性的双重提示词系统
    """
    # 验证项目权限
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")
    
    # 检查是否已有模板且不强制重新生成
    existing_discovery = db.query(TemplateDiscovery).filter(
        TemplateDiscovery.project_id == project_id,
        TemplateDiscovery.status.in_(["active", "user_reviewed"])
    ).first()
    
    if existing_discovery and not request.force_regenerate:
        return TemplateGenerationResponse(
            success=True,
            discovery_id=existing_discovery.id,
            field_name=existing_discovery.field_name,
            research_areas=existing_discovery.research_discovery.get("research_areas", []),
            user_friendly_prompts=await _get_user_friendly_prompts(db, existing_discovery.id),
            confidence=existing_discovery.discovery_confidence,
            representative_literature_count=len(existing_discovery.representative_literature_ids or []),
            message="使用现有模板，如需重新生成请设置 force_regenerate=true"
        )
    
    # 获取项目文献
    literature_list = db.query(Literature).join(
        Literature.projects
    ).filter(
        Project.id == project_id
    ).limit(request.max_literature_samples).all()
    
    if len(literature_list) < 3:
        raise HTTPException(
            status_code=400, 
            detail=f"项目文献数量不足（当前{len(literature_list)}篇，需要至少3篇）"
        )
    
    # 启动后台任务生成模板
    background_tasks.add_task(
        _generate_template_background,
        db, project, literature_list, current_user.id
    )
    
    return TemplateGenerationResponse(
        success=True,
        message=f"已启动智能模板生成，分析{len(literature_list)}篇文献中..."
    )


async def _generate_template_background(
    db: Session, 
    project: Project, 
    literature_list: List[Literature],
    user_id: int
):
    """后台任务：生成智能模板"""
    try:
        template_service = IntelligentTemplateService(db)
        
        # 定义进度回调
        async def progress_callback(message: str, progress: float, details: Dict):
            logger.info(f"项目 {project.id} 模板生成进度: {progress:.1f}% - {message}")
            # 这里可以通过WebSocket发送进度给前端
        
        # 生成智能模板
        result = await template_service.discover_research_patterns_from_literature(
            project, literature_list, progress_callback
        )
        
        if result["success"]:
            # 保存发现结果
            discovery = TemplateDiscovery(
                project_id=project.id,
                field_name=result["research_discovery"].get("field_name", "未知领域"),
                research_discovery=result["research_discovery"],
                extraction_strategy=result["extraction_strategy"],
                representative_literature_ids=result["representative_literature"],
                total_literature_analyzed=len(literature_list),
                discovery_confidence=result["metadata"]["discovery_confidence"],
                status="generated"
            )
            
            db.add(discovery)
            db.commit()
            db.refresh(discovery)
            
            # 保存双重提示词系统
            await _save_dual_prompt_system(
                db, discovery.id, project.id, result["dual_prompt_system"]
            )
            
            logger.info(f"项目 {project.id} 智能模板生成完成")
            
        else:
            logger.error(f"项目 {project.id} 模板生成失败: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"后台模板生成任务失败: {e}")


async def _save_dual_prompt_system(
    db: Session, 
    discovery_id: int, 
    project_id: int, 
    dual_prompt_system: Dict
):
    """保存双重提示词系统"""
    user_prompts = dual_prompt_system.get("user_friendly_prompts", [])
    technical_prompts = dual_prompt_system.get("technical_prompts", [])
    prompt_mapping = dual_prompt_system.get("prompt_mapping", {})
    
    for i, user_prompt in enumerate(user_prompts):
        # 找到对应的技术提示词
        tech_prompt = None
        for tech in technical_prompts:
            if tech["section_name"] == user_prompt["section_name"]:
                tech_prompt = tech
                break
        
        if tech_prompt:
            prompt_template = PromptTemplate(
                discovery_id=discovery_id,
                project_id=project_id,
                section_name=user_prompt["section_name"],
                display_order=i,
                display_title=user_prompt.get("display_title", user_prompt["section_name"]),
                user_description=user_prompt.get("description", ""),
                user_examples=user_prompt.get("examples", []),
                is_user_configurable=user_prompt.get("user_configurable", True),
                system_prompt=tech_prompt.get("system_prompt", ""),
                extraction_rules=tech_prompt.get("extraction_rules", []),
                output_format=tech_prompt.get("output_format", ""),
                fallback_instructions=tech_prompt.get("fallback_instructions", "")
            )
            
            db.add(prompt_template)
    
    db.commit()


@router.get("/projects/{project_id}/templates", response_model=List[UserFriendlyPrompt])
async def get_project_templates(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取项目的用户友好模板列表"""
    # 验证权限
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")
    
    # 获取活跃的模板发现
    discovery = db.query(TemplateDiscovery).filter(
        TemplateDiscovery.project_id == project_id,
        TemplateDiscovery.status.in_(["active", "user_reviewed", "generated"])
    ).first()
    
    if not discovery:
        return []
    
    # 获取提示词模板
    prompt_templates = db.query(PromptTemplate).filter(
        PromptTemplate.discovery_id == discovery.id,
        PromptTemplate.is_active == True
    ).order_by(PromptTemplate.display_order).all()
    
    return [
        UserFriendlyPrompt(
            section_name=pt.section_name,
            display_title=pt.display_title or pt.section_name,
            description=pt.user_description or "暂无描述",
            examples=pt.user_examples or [],
            is_configurable=pt.is_user_configurable,
            current_status="active" if pt.is_active else "inactive"
        )
        for pt in prompt_templates
    ]


async def _get_user_friendly_prompts(db: Session, discovery_id: int) -> List[Dict]:
    """获取用户友好的提示词列表"""
    prompt_templates = db.query(PromptTemplate).filter(
        PromptTemplate.discovery_id == discovery_id,
        PromptTemplate.is_active == True
    ).order_by(PromptTemplate.display_order).all()
    
    return [
        {
            "section_name": pt.section_name,
            "display_title": pt.display_title,
            "description": pt.user_description,
            "examples": pt.user_examples,
            "is_configurable": pt.is_user_configurable
        }
        for pt in prompt_templates
    ]


@router.put("/templates/{template_id}")
async def update_prompt_template(
    template_id: int,
    request: PromptUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """用户更新提示词模板"""
    # 获取模板
    template = db.query(PromptTemplate).filter(
        PromptTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 验证权限
    project = db.query(Project).filter(
        Project.id == template.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=403, detail="无权限修改此模板")
    
    # 记录用户修改
    template.user_modifications = request.user_modifications
    template.custom_instructions = request.custom_instructions
    template.updated_at = datetime.utcnow()
    
    # 增加版本号
    current_version = float(template.version)
    template.version = f"{current_version + 0.1:.1f}"
    
    db.commit()
    
    return {"success": True, "message": "模板更新成功", "new_version": template.version}


@router.post("/templates/{template_id}/feedback")
async def submit_template_feedback(
    template_id: int,
    request: FeedbackSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """提交对模板的反馈"""
    # 验证模板存在
    template = db.query(PromptTemplate).filter(
        PromptTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 创建反馈记录
    feedback = PromptFeedback(
        prompt_template_id=template_id,
        user_id=current_user.id,
        feedback_type=request.feedback_type,
        rating=request.rating,
        feedback_text=request.feedback_text,
        suggested_changes=request.suggested_changes,
        status="pending"
    )
    
    db.add(feedback)
    db.commit()
    
    return {"success": True, "message": "反馈提交成功，我们会尽快处理"}


@router.get("/projects/{project_id}/templates/discovery")
async def get_template_discovery(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取项目的模板发现详情"""
    # 验证权限
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")
    
    # 获取最新的模板发现
    discovery = db.query(TemplateDiscovery).filter(
        TemplateDiscovery.project_id == project_id
    ).order_by(TemplateDiscovery.created_at.desc()).first()
    
    if not discovery:
        return {"success": False, "message": "尚未生成智能模板"}
    
    return {
        "success": True,
        "discovery": {
            "id": discovery.id,
            "field_name": discovery.field_name,
            "research_discovery": discovery.research_discovery,
            "confidence": discovery.discovery_confidence,
            "status": discovery.status,
            "representative_literature_count": len(discovery.representative_literature_ids or []),
            "total_literature_analyzed": discovery.total_literature_analyzed,
            "created_at": discovery.created_at.isoformat(),
            "updated_at": discovery.updated_at.isoformat() if discovery.updated_at else None
        }
    }


class TemplateActivationRequest(BaseModel):
    """模板激活请求"""
    user_validation_score: float = Field(..., ge=0.0, le=10.0)


@router.post("/projects/{project_id}/templates/{discovery_id}/activate")
async def activate_template_discovery(
    project_id: int,
    discovery_id: int,
    request: TemplateActivationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """用户验证并激活模板发现"""
    # 验证权限
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")
    
    # 获取发现记录
    discovery = db.query(TemplateDiscovery).filter(
        TemplateDiscovery.id == discovery_id,
        TemplateDiscovery.project_id == project_id
    ).first()
    
    if not discovery:
        raise HTTPException(status_code=404, detail="模板发现不存在")
    
    # 更新状态
    discovery.status = "active"
    discovery.user_validation_score = request.user_validation_score
    discovery.updated_at = datetime.utcnow()
    
    # 将原来的项目模板设置为新的智能模板
    project.structure_template = discovery.research_discovery
    project.extraction_prompts = {}  # 将在实际使用时动态生成
    
    db.commit()
    
    return {"success": True, "message": "智能模板已激活并应用到项目"}


@router.get("/templates/stats")
async def get_template_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取模板使用统计（管理员功能）"""
    # 这里可以添加管理员权限检查
    
    total_discoveries = db.query(TemplateDiscovery).count()
    active_templates = db.query(TemplateDiscovery).filter(
        TemplateDiscovery.status == "active"
    ).count()
    
    avg_confidence = db.query(func.avg(TemplateDiscovery.discovery_confidence)).scalar() or 0.0
    
    recent_feedbacks = db.query(PromptFeedback).filter(
        PromptFeedback.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    return {
        "total_discoveries": total_discoveries,
        "active_templates": active_templates,
        "average_confidence": round(avg_confidence, 2),
        "recent_feedbacks": recent_feedbacks,
        "success_rate": round((active_templates / max(total_discoveries, 1)) * 100, 2)
    }