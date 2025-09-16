"""
项目管理API路由
"""

from typing import List, Optional, Dict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json
import os
from pathlib import Path

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.models.project import Project
from app.models.task import Task, TaskProgress
from app.models.experience import ExperienceBook
from app.services.ai_service import AIService
from app.utils.file_handler import FileHandler
from loguru import logger

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    research_direction: Optional[str] = None
    keywords: List[str] = []
    research_categories: Optional[List[str]] = None  # 添加：研究类别
    max_literature_count: Optional[int] = None       # 添加：最大文献数量

class BasicProjectCreate(BaseModel):
    """简化的项目创建模型 - 用于空项目创建"""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    research_direction: Optional[str]
    keywords: List[str]
    research_categories: Optional[List[str]] = None
    status: str
    literature_sources: Optional[List[str]] = None
    max_literature_count: int
    structure_template: Optional[Dict] = None
    extraction_prompts: Optional[Dict] = None
    owner_id: int
    created_at: str
    updated_at: Optional[str] = None
    # 前端扩展字段
    literature_count: Optional[int] = 0  # 计算字段
    progress_percentage: Optional[float] = None  # 项目进度

class ResearchDirectionRequest(BaseModel):
    user_input: str
    conversation_history: List[Dict] = []

class ResearchDirectionResponse(BaseModel):
    suggested_direction: str
    keywords: List[str]
    research_categories: List[str]
    confidence: float
    follow_up_questions: List[str]

@router.post("/create-empty", response_model=ProjectResponse)
async def create_empty_project(
    project_data: BasicProjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建空项目 - 无需研究方向，支持后续添加文献"""
    
    # 检查项目名称是否重复
    existing_project = db.query(Project).filter(
        Project.name == project_data.name,
        Project.owner_id == current_user.id
    ).first()
    
    if existing_project:
        raise HTTPException(status_code=400, detail="项目名称已存在")
    
    # 创建空项目
    project = Project(
        name=project_data.name,
        description=project_data.description,
        research_direction=None,  # 空项目暂无研究方向
        keywords=[],  # 空关键词列表
        status='empty',  # 标记为空项目状态
        owner_id=current_user.id
    )
    
    # 如果提供了分类，存储为临时元数据
    if project_data.category:
        project.metadata = {"category": project_data.category}
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    logger.info(f"用户 {current_user.id} 创建空项目: {project.name}")
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        research_direction=project.research_direction,
        keywords=project.keywords or [],
        research_categories=project.research_categories,
        status=project.status,
        literature_sources=project.literature_sources,
        max_literature_count=project.max_literature_count,
        structure_template=project.structure_template,
        extraction_prompts=project.extraction_prompts,
        owner_id=project.owner_id,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
        literature_count=0,
        progress_percentage=None
    )

@router.post("/create", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """创建新项目"""
    
    # 检查项目名称是否重复
    existing_project = db.query(Project).filter(
        Project.name == project_data.name,
        Project.owner_id == current_user.id
    ).first()
    
    if existing_project:
        raise HTTPException(status_code=400, detail="项目名称已存在")
    
    # 创建项目
    project = Project(
        name=project_data.name,
        description=project_data.description,
        research_direction=project_data.research_direction,
        keywords=project_data.keywords,
        research_categories=project_data.research_categories,
        max_literature_count=project_data.max_literature_count,
        owner_id=current_user.id
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        research_direction=project.research_direction,
        keywords=project.keywords or [],
        research_categories=project.research_categories,
        status=project.status,
        literature_sources=project.literature_sources,
        max_literature_count=project.max_literature_count,
        structure_template=project.structure_template,
        extraction_prompts=project.extraction_prompts,
        owner_id=project.owner_id,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
        literature_count=0,
        progress_percentage=None
    )

@router.get("/list", response_model=List[ProjectResponse])
async def get_user_projects(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取用户项目列表"""
    
    projects = db.query(Project).filter(
        Project.owner_id == current_user.id
    ).order_by(Project.created_at.desc()).all()
    
    project_responses = []
    for project in projects:
        # 计算文献数量
        literature_count = len(project.literature)
        
        project_responses.append(ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            research_direction=project.research_direction,
            keywords=project.keywords or [],
            research_categories=project.research_categories,
            status=project.status,
            literature_sources=project.literature_sources,
            max_literature_count=project.max_literature_count,
            structure_template=project.structure_template,
            extraction_prompts=project.extraction_prompts,
            owner_id=project.owner_id,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat() if project.updated_at else None,
            literature_count=literature_count,
            progress_percentage=None
        ))
    
    return project_responses

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取项目详情"""
    
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        research_direction=project.research_direction,
        keywords=project.keywords or [],
        research_categories=project.research_categories,
        status=project.status,
        literature_sources=project.literature_sources,
        max_literature_count=project.max_literature_count,
        structure_template=project.structure_template,
        extraction_prompts=project.extraction_prompts,
        owner_id=project.owner_id,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat() if project.updated_at else None,
        literature_count=len(project.literature),
        progress_percentage=None
    )

@router.post("/determine-direction", response_model=ResearchDirectionResponse)
async def determine_research_direction(
    request: ResearchDirectionRequest,
    current_user: User = Depends(get_current_active_user)
):
    """智能确定研究方向"""
    
    ai_service = AIService()
    
    try:
        # 构建对话提示词
        conversation_context = ""
        for msg in request.conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conversation_context += f"{role}: {content}\n"
        
        prompt = f"""
作为科研方向分析专家，请基于用户输入和对话历史，确定具体的研究方向。

对话历史：
{conversation_context}

用户当前输入：{request.user_input}

请分析并返回：
1. 建议的具体研究方向
2. 核心关键词列表
3. 研究分类层级
4. 确定度评估
5. 需要进一步确认的问题

请以JSON格式返回：
{{
    "suggested_direction": "具体研究方向",
    "keywords": ["关键词1", "关键词2"],
    "research_categories": ["一级分类", "二级分类", "三级分类"],
    "confidence": 置信度(0-1),
    "follow_up_questions": ["确认问题1", "确认问题2"],
    "analysis": "分析过程"
}}
"""
        
        response = await ai_service.client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        
        result = json.loads(response.choices[0].message.content)
        
        return ResearchDirectionResponse(
            suggested_direction=result.get("suggested_direction", ""),
            keywords=result.get("keywords", []),
            research_categories=result.get("research_categories", []),
            confidence=result.get("confidence", 0.5),
            follow_up_questions=result.get("follow_up_questions", [])
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"研究方向确定失败: {str(e)}")

@router.post("/{project_id}/upload-files")
async def upload_project_files(
    project_id: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """上传项目相关文件（项目书、申请书等）"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    file_handler = FileHandler()
    ai_service = AIService()
    
    uploaded_files = []
    extracted_info = {}
    
    for file in files:
        # 保存文件
        file_path = await file_handler.save_uploaded_file(file, project_id)
        
        # 提取文件内容
        if file.filename.lower().endswith('.pdf'):
            from app.services.pdf_processor import PDFProcessor
            pdf_processor = PDFProcessor()
            
            content_result = await pdf_processor.process_pdf(file_path)
            if content_result["success"]:
                file_content = content_result["content"]["text_content"]
                
                # 使用AI分析文件内容，提取研究方向
                analysis_prompt = f"""
请分析以下项目文件内容，提取关键的研究方向信息：

文件内容：
{file_content[:3000]}

请提取：
1. 具体研究方向和目标
2. 核心关键词
3. 研究方法
4. 预期成果

请以JSON格式返回：
{{
    "research_direction": "研究方向",
    "keywords": ["关键词列表"],
    "methods": ["研究方法"],
    "objectives": ["研究目标"]
}}
"""
                
                try:
                    analysis_response = await ai_service.client.chat.completions.create(
                        model=settings.openai_model,
                        messages=[{"role": "user", "content": analysis_prompt}],
                        temperature=0.2,
                        max_tokens=1000
                    )
                    
                    analysis_result = json.loads(analysis_response.choices[0].message.content)
                    extracted_info[file.filename] = analysis_result
                    
                except Exception as e:
                    logger.error(f"文件内容分析失败: {e}")
        
        uploaded_files.append({
            "filename": file.filename,
            "file_path": file_path,
            "size": file.size
        })
    
    # 如果提取到了研究方向信息，更新项目
    if extracted_info:
        all_keywords = []
        all_directions = []
        
        for file_info in extracted_info.values():
            all_keywords.extend(file_info.get("keywords", []))
            if file_info.get("research_direction"):
                all_directions.append(file_info["research_direction"])
        
        # 更新项目信息
        if all_directions:
            project.research_direction = "; ".join(all_directions)
        if all_keywords:
            existing_keywords = project.keywords or []
            project.keywords = list(set(existing_keywords + all_keywords))
        
        db.commit()
    
    return {
        "message": "文件上传成功",
        "uploaded_files": uploaded_files,
        "extracted_info": extracted_info,
        "project_updated": bool(extracted_info)
    }

@router.post("/{project_id}/start-indexing")
async def start_literature_indexing(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """手动触发文献库索引构建"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查是否有文献数据
    literature_count = len(project.literature)
    if literature_count == 0:
        raise HTTPException(status_code=400, detail="项目中没有文献，请先添加文献")
    
    # 检查项目状态
    if project.status == 'indexing':
        raise HTTPException(status_code=400, detail="项目正在索引中，请勿重复操作")
    
    try:
        # 更新项目状态为索引中
        project.status = 'indexing'
        project.updated_at = datetime.utcnow()
        db.commit()
        
        # 创建索引构建任务
        from app.tasks.literature_tasks import build_literature_index
        import uuid
        import asyncio
        
        task_id = f"indexing_{project_id}_{uuid.uuid4().hex[:8]}"
        
        # 启动后台任务
        asyncio.create_task(build_literature_index(project_id, task_id, current_user.id))
        
        estimated_time = f"{literature_count * 2}-{literature_count * 5} 秒"
        
        logger.info(f"开始为项目 {project_id} 构建文献索引，任务ID: {task_id}")
        
        return {
            "message": "索引构建已启动",
            "task_id": task_id,
            "estimated_time": estimated_time,
            "literature_count": literature_count
        }
        
    except Exception as e:
        # 如果启动失败，恢复项目状态
        project.status = 'literature_added'
        db.commit()
        
        logger.error(f"启动索引构建失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动索引构建失败: {str(e)}")

@router.get("/{project_id}/indexing-status/{task_id}")
async def get_indexing_status(
    project_id: int,
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取索引构建状态"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 这里应该从任务系统查询状态
    # 暂时返回模拟状态
    from app.services.task_service import TaskService
    task_service = TaskService()
    
    try:
        status = await task_service.get_task_status(task_id)
        return {
            "task_id": task_id,
            "status": status.get("status", "pending"),
            "progress": status.get("progress", 0),
            "message": status.get("message", "处理中..."),
            "result": status.get("result") if status.get("status") == "completed" else None,
            "error": status.get("error") if status.get("status") == "failed" else None
        }
    except Exception as e:
        logger.error(f"查询任务状态失败: {e}")
        return {
            "task_id": task_id,
            "status": "unknown",
            "progress": 0,
            "message": "无法查询任务状态",
            "error": str(e)
        }

@router.get("/{project_id}/tasks")
async def get_project_tasks(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取项目任务列表"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 获取任务列表
    tasks = db.query(Task).filter(Task.project_id == project_id).order_by(Task.created_at.desc()).all()
    
    task_list = []
    for task in tasks:
        # 获取最新进度
        latest_progress = db.query(TaskProgress).filter(
            TaskProgress.task_id == task.id
        ).order_by(TaskProgress.started_at.desc()).first()
        
        task_list.append({
            "id": task.id,
            "title": task.title,
            "task_type": task.task_type,
            "status": task.status,
            "progress_percentage": task.progress_percentage,
            "current_step": task.current_step,
            "created_at": task.created_at.isoformat(),
            "latest_progress": {
                "step_name": latest_progress.step_name if latest_progress else "",
                "started_at": latest_progress.started_at.isoformat() if latest_progress else ""
            }
        })
    
    return {"tasks": task_list}

class ProjectStatistics(BaseModel):
    """项目统计数据响应模型"""
    literature_count: int
    experience_books_count: int
    analysis_count: int
    progress_percentage: float
    task_count: int
    active_tasks: int

@router.get("/{project_id}/statistics", response_model=ProjectStatistics)
async def get_project_statistics(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取项目统计数据"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 统计文献数量
    literature_count = len(project.literature) if project.literature else 0
    
    # 统计经验书数量
    experience_books_count = db.query(ExperienceBook).filter(
        ExperienceBook.project_id == project_id
    ).count()
    
    # 统计分析数量（这里可以根据实际情况调整，暂时使用任务数量）
    analysis_count = db.query(Task).filter(
        Task.project_id == project_id,
        Task.task_type.in_(['analysis', 'experience_generation'])
    ).count()
    
    # 统计任务数量
    total_tasks = db.query(Task).filter(Task.project_id == project_id).count()
    active_tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status.in_(['pending', 'running', 'processing'])
    ).count()
    
    # 计算项目进度（基于多个因素）
    progress_percentage = 0.0
    if project.status == 'empty':
        progress_percentage = 5.0
    elif project.status == 'literature_added' and literature_count > 0:
        progress_percentage = 25.0 + min(literature_count * 5, 40)  # 25% + 最多40%
    elif project.status == 'indexing':
        progress_percentage = 70.0
    elif project.status == 'completed':
        progress_percentage = 100.0
    else:
        # 基于文献数量和分析数量计算进度
        base_progress = min(literature_count * 3, 30)  # 文献贡献最多30%
        analysis_progress = min(analysis_count * 15, 50)  # 分析贡献最多50%
        experience_progress = min(experience_books_count * 10, 20)  # 经验书贡献最多20%
        progress_percentage = base_progress + analysis_progress + experience_progress
    
    # 确保进度在0-100之间
    progress_percentage = max(0.0, min(100.0, progress_percentage))
    
    logger.info(f"项目 {project_id} 统计: 文献{literature_count}, 经验书{experience_books_count}, 分析{analysis_count}, 进度{progress_percentage}%")
    
    return ProjectStatistics(
        literature_count=literature_count,
        experience_books_count=experience_books_count,
        analysis_count=analysis_count,
        progress_percentage=progress_percentage,
        task_count=total_tasks,
        active_tasks=active_tasks
    )