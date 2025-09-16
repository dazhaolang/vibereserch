"""
文献管理API路由 - 整合v2架构改进
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text, and_
from pydantic import BaseModel
from enum import Enum
import asyncio
import tempfile
import os
import json
import time
from pathlib import Path
from loguru import logger

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.exceptions import ErrorFactory, handle_exceptions, ErrorCode
from app.models.user import User
from app.models.project import Project
from app.models.literature import Literature, LiteratureSegment
from app.models.task import Task, TaskType
from app.services.literature_collector import EnhancedLiteratureCollector
from app.services.pdf_processor import PDFProcessor
from app.services.research_ai_service import research_ai_service
from app.services.literature_reliability_service import LiteratureReliabilityService
from app.services.zotero_service import ThirdPartyIntegrationManager
from app.services.research_rabbit_client import ResearchRabbitClient
from app.services.shared_literature_service import SharedLiteratureService
from app.schemas.literature_schemas import (
    LiteratureCreateRequest, LiteratureUpdateRequest, LiteratureResponse,
    LiteratureListResponse, LiteratureSearchRequest, LiteratureSearchResponse,
    LiteratureCollectionRequest, LiteratureCollectionResponse,
    LiteratureStatisticsResponse, LiteratureStatsResponse,
    LiteratureProjectStatisticsResponse, LiteratureSegmentsResponse,
    AILiteratureSearchRequest, SearchLibraryModeRequest, AISearchModeRequest
)

router = APIRouter()

# 处理方式枚举和请求模型

class ProcessingMethodEnum(str, Enum):
    """PDF处理方式枚举"""
    FAST_BASIC = "fast_basic"       # 快速基础解析 (PyPDF2) - 1-2秒
    STANDARD = "standard"           # 标准解析 (pdfplumber) - 3-5秒  
    PREMIUM_MINERU = "premium_mineru"  # 高质量解析 (MinerU) - 30-60秒

class BatchProcessingRequest(BaseModel):
    """批量处理请求"""
    project_id: int
    query: str
    max_results: int = 20
    preferred_method: ProcessingMethodEnum = ProcessingMethodEnum.FAST_BASIC
    enable_user_choice: bool = True

class LiteratureAddRequest(BaseModel):
    project_id: int
    paper_ids: List[str]

class MethodUpgradeRequest(BaseModel):
    """方法升级请求"""
    task_id: str
    new_method: ProcessingMethodEnum

# 全局处理管道实例（延迟初始化）
_processing_pipeline = None

def get_processing_pipeline():
    """获取处理管道实例"""
    global _processing_pipeline
    if _processing_pipeline is None:
        from app.services.literature_processing_pipeline import pipeline
        _processing_pipeline = pipeline
    return _processing_pipeline

# API请求模型 - 向后兼容保留的响应模型
class SearchAndBuildLibraryResponse(BaseModel):
    """搜索建库响应"""
    task_id: int
    message: str
    estimated_duration: int
    config: Dict

# 使用统一的Schema定义，删除重复定义

@router.post("/search-and-build-library", response_model=SearchAndBuildLibraryResponse)
@handle_exceptions(ErrorCode.EXTERNAL_API_ERROR)
async def start_search_and_build_library(
    request: SearchLibraryModeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    启动搜索建库原子化任务 - 完整的搜索→筛选→下载PDF→转Markdown→结构化→入库流水线
    支持200-500篇文献的大规模批量处理
    """

    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 检查会员限制
    membership = current_user.membership
    max_results = request.max_results or 200
    if membership:
        if membership.membership_type.value == "free" and max_results > 100:
            max_results = 100
        elif membership.membership_type.value == "premium" and max_results > 500:
            max_results = 500
    else:
        max_results = min(max_results, 50)  # 未付费用户限制50篇

    # 处理关键词：从query和keywords字段提取
    keywords = request.keywords or []
    if request.query and request.query not in keywords:
        keywords.insert(0, request.query)

    # 如果没有关键词，使用query作为关键词
    if not keywords:
        keywords = [request.query]

    # 创建任务
    task = Task(
        project_id=request.project_id,
        task_type="search_and_build_library",
        title=f"搜索建库 - {', '.join(keywords)}",
        description=f"搜索→筛选→PDF处理→结构化→入库完整流水线，最大数量：{max_results}",
        config={
            "keywords": keywords,
            "max_results": max_results,
            "enable_ai_filtering": request.enable_ai_filtering,
            "enable_pdf_processing": request.enable_pdf_processing,
            "enable_structured_extraction": request.enable_structured_extraction,
            "quality_threshold": request.quality_threshold,
            "batch_size": request.batch_size,
            "max_concurrent_downloads": request.max_concurrent_downloads,
            "processing_method": request.processing_method,
            # 记录原始请求参数供调试使用
            "original_query": request.query,
            "args": request.args,
            "kwargs": request.kwargs
        },
        status="pending",
        estimated_duration=max_results * 8  # 预估每篇文献8秒处理时间
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    # 启动Celery任务
    from app.tasks.celery_tasks import search_and_build_library_celery
    task_result = search_and_build_library_celery.delay(
        task.id,
        request.keywords,
        request.project_id,
        current_user.id,
        {
            "max_results": request.max_results,
            "enable_ai_filtering": request.enable_ai_filtering,
            "enable_pdf_processing": request.enable_pdf_processing,
            "enable_structured_extraction": request.enable_structured_extraction,
            "quality_threshold": request.quality_threshold,
            "batch_size": request.batch_size,
            "max_concurrent_downloads": request.max_concurrent_downloads
        }
    )

    return SearchAndBuildLibraryResponse(
        task_id=task.id,
        message="搜索建库任务已启动，正在执行完整的文献处理流水线",
        estimated_duration=request.max_results * 8,
        config={
            "keywords": request.keywords,
            "max_results": request.max_results,
            "processing_stages": [
                "搜索文献", "AI智能筛选", "PDF下载",
                "内容提取", "结构化处理", "数据库入库"
            ]
        }
    )

@router.post("/collect", response_model=LiteratureCollectionResponse)
@handle_exceptions(ErrorCode.EXTERNAL_API_ERROR)
async def start_literature_collection(
    request: LiteratureCollectionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """启动文献采集任务"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查会员限制
    membership = current_user.membership
    if membership:
        if membership.membership_type.value == "free" and request.max_count > 1000:
            request.max_count = 1000
        elif membership.membership_type.value == "premium" and request.max_count > 2000:
            request.max_count = 2000
    
    # 创建任务
    task = Task(
        project_id=request.project_id,
        task_type="literature_collection",
        title=f"文献采集 - {', '.join(request.keywords)}",
        description=f"采集关键词相关文献，最大数量：{request.max_count}",
        config={
            "keywords": request.keywords,
            "max_count": request.max_count,
            "sources": request.sources
        },
        status="pending",
        estimated_duration=300  # 预估5分钟
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 启动Celery任务
    from app.tasks.celery_tasks import literature_collection_celery
    task_result = literature_collection_celery.delay(
        task.id,
        request.keywords,
        request.max_count,
        request.sources
    )
    
    return LiteratureCollectionResponse(
        task_id=task.id,
        message="文献采集任务已启动",
        estimated_duration=300,
        collection_config={
            "keywords": request.keywords,
            "max_count": request.max_count,
            "sources": request.sources
        }
    )

@router.get("/project/{project_id}", response_model=List[LiteratureResponse])
async def get_project_literature(
    project_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取项目文献列表"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 分页查询文献 - 优化查询性能
    offset = (page - 1) * page_size
    # 使用子查询避免复杂的JOIN操作
    literature_list = db.query(Literature).filter(
        Literature.projects.any(id=project_id)
    ).order_by(
        Literature.quality_score.desc().nullslast(),
        Literature.created_at.desc()
    ).offset(offset).limit(page_size).all()
    
    # 批量构建响应，避免N+1查询问题
    literature_responses = []
    for lit in literature_list:
        literature_responses.append(LiteratureResponse(
            id=lit.id,
            title=lit.title,
            authors=lit.authors or [],
            abstract=lit.abstract,
            keywords=lit.keywords,
            journal=lit.journal,
            publication_year=lit.publication_year,
            volume=lit.volume,
            issue=lit.issue,
            pages=lit.pages,
            doi=lit.doi,
            source_platform=lit.source_platform,
            source_url=lit.source_url,
            pdf_url=lit.pdf_url,
            pdf_path=lit.pdf_path,
            status=lit.status,
            parsing_status=lit.parsing_status,
            parsed_content=lit.parsed_content,
            citation_count=lit.citation_count or 0,
            impact_factor=lit.impact_factor,
            quality_score=lit.quality_score,
            is_downloaded=lit.is_downloaded,
            is_parsed=lit.is_parsed,
            file_path=lit.file_path,
            file_size=lit.file_size,
            file_hash=lit.file_hash,
            created_at=lit.created_at,
            updated_at=lit.updated_at,
            relevance_score=None,  # TODO: 从项目关联表获取相关性评分
            is_selected=False,  # 默认不选中
            tags=None,  # TODO: 从文献标签获取
            projects=None  # TODO: 从项目关联获取
        ))
    
    return literature_responses

@router.post("/project/{project_id}/start-processing")
async def start_literature_processing(
    project_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """启动文献处理任务"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查是否有文献需要处理
    unprocessed_literature = db.query(Literature).filter(
        Literature.projects.any(id=project_id),
        Literature.is_parsed == False
    ).count()
    
    if unprocessed_literature == 0:
        raise HTTPException(status_code=400, detail="没有需要处理的文献")
    
    # 创建处理任务
    task = Task(
        project_id=project_id,
        task_type="structure_extraction",
        title="文献轻结构化处理",
        description=f"处理 {unprocessed_literature} 篇文献",
        config={"literature_count": unprocessed_literature},
        status="pending",
        estimated_duration=unprocessed_literature * 30  # 每篇文献预估30秒
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 启动后台任务
    from app.tasks.literature_tasks import start_literature_processing_task
    background_tasks.add_task(start_literature_processing_task, task.id)
    
    return {
        "task_id": task.id,
        "message": "文献处理任务已启动",
        "literature_count": unprocessed_literature
    }

@router.get("/{literature_id}/segments", response_model=LiteratureSegmentsResponse)
async def get_literature_segments(
    literature_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取文献的结构化段落"""
    
    # 验证文献访问权限（通过项目所有权）
    literature = db.query(Literature).filter(Literature.id == literature_id).first()
    if not literature:
        raise HTTPException(status_code=404, detail="文献不存在")
    
    # 检查用户是否有权限访问此文献
    user_projects = [p.id for p in current_user.projects]
    literature_projects = [p.id for p in literature.projects]
    
    if not any(pid in user_projects for pid in literature_projects):
        raise HTTPException(status_code=403, detail="无权限访问此文献")
    
    # 获取文献段落
    segments = db.query(LiteratureSegment).filter(
        LiteratureSegment.literature_id == literature_id
    ).order_by(LiteratureSegment.segment_type, LiteratureSegment.paragraph_index).all()
    
    segment_list = []
    for segment in segments:
        segment_list.append({
            "id": segment.id,
            "segment_type": segment.segment_type,
            "content": segment.content,
            "order_index": segment.page_number or 0,
            "embedding_status": "processed" if segment.structured_data else "pending",
            "created_at": segment.created_at.isoformat() if segment.created_at else ""
        })
    
    return {"segments": segment_list}

@router.get("/project/{project_id}/statistics", response_model=LiteratureProjectStatisticsResponse)
async def get_project_literature_statistics(
    project_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取项目文献统计信息"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 统计文献信息
    total_literature = db.query(Literature).filter(
        Literature.projects.any(id=project_id)
    ).count()
    
    processed_literature = db.query(Literature).filter(
        Literature.projects.any(id=project_id),
        Literature.is_parsed == True
    ).count()
    
    total_segments = db.query(LiteratureSegment).join(Literature).filter(
        Literature.projects.any(id=project_id)
    ).count()
    
    # 按年份统计
    year_stats = db.execute(text("""
        SELECT publication_year, COUNT(*) as count
        FROM literature l
        JOIN project_literature_associations pla ON l.id = pla.literature_id
        WHERE pla.project_id = :project_id AND l.publication_year IS NOT NULL
        GROUP BY publication_year
        ORDER BY publication_year DESC
    """), {"project_id": project_id}).fetchall()
    
    # 按期刊统计
    journal_stats = db.execute(text("""
        SELECT journal, COUNT(*) as count
        FROM literature l
        JOIN project_literature_associations pla ON l.id = pla.literature_id
        WHERE pla.project_id = :project_id AND l.journal IS NOT NULL
        GROUP BY journal
        ORDER BY count DESC
        LIMIT 10
    """), {"project_id": project_id}).fetchall()
    
    return {
        "total_literature": total_literature,
        "processed_literature": processed_literature,
        "processing_rate": (processed_literature / total_literature * 100) if total_literature > 0 else 0,
        "total_segments": total_segments,
        "unprocessed_literature": total_literature - processed_literature,
        "storage_saved": {
            "year_distribution": [{"year": row[0], "count": row[1]} for row in year_stats],
            "top_journals": [{"journal": row[0], "count": row[1]} for row in journal_stats]
        }
    }


# 新增的可靠性相关Schema
class LiteratureReliabilityRequest(BaseModel):
    project_id: int

class LiteratureReliabilityResponse(BaseModel):
    success: bool
    total_processed: int
    reliability_distribution: Dict[str, int]
    avg_reliability_score: float
    top_reliable_literature: List[Dict]

class LiteratureReliabilitySortRequest(BaseModel):
    project_id: int
    prioritize_high_reliability: bool = True
    limit: Optional[int] = 50

class LiteratureReliabilitySortResponse(BaseModel):
    success: bool
    sorted_literature: List[Dict]
    reliability_stats: Dict


@router.post("/evaluate-reliability", response_model=LiteratureReliabilityResponse)
@handle_exceptions(ErrorCode.AI_PROCESSING_FAILED)
async def evaluate_literature_reliability(
    request: LiteratureReliabilityRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """评估项目文献的可靠性"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 获取项目文献
    literature_list = db.query(Literature).filter(
        Literature.projects.any(id=request.project_id)
    ).all()
    
    if not literature_list:
        raise HTTPException(status_code=404, detail="项目中没有文献")
    
    # 初始化可靠性服务
    reliability_service = LiteratureReliabilityService(db)
    
    # 批量评估可靠性
    result = await reliability_service.batch_evaluate_literature_reliability(literature_list)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"可靠性评估失败: {result.get('error')}")
    
    # 统计可靠性分布
    reliability_distribution = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    total_reliability = 0
    
    for lit in literature_list:
        reliability_level = lit.source_reliability or "unknown"
        reliability_distribution[reliability_level] += 1
        total_reliability += lit.reliability_score or 0.5
    
    avg_reliability = total_reliability / len(literature_list)
    
    # 获取可靠性最高的文献
    top_reliable = sorted(
        literature_list, 
        key=lambda x: x.reliability_score or 0.0, 
        reverse=True
    )[:10]
    
    top_reliable_literature = []
    for lit in top_reliable:
        top_reliable_literature.append({
            "id": lit.id,
            "title": lit.title[:100],
            "journal": lit.journal,
            "impact_factor": lit.impact_factor,
            "reliability_score": lit.reliability_score,
            "source_reliability": lit.source_reliability,
            "citation_count": lit.citation_count
        })
    
    return {
        "success": True,
        "total_processed": result["total_processed"],
        "reliability_distribution": reliability_distribution,
        "avg_reliability_score": avg_reliability,
        "top_reliable_literature": top_reliable_literature
    }


@router.post("/sort-by-reliability", response_model=LiteratureReliabilitySortResponse)
@handle_exceptions(ErrorCode.AI_PROCESSING_FAILED)
async def sort_literature_by_reliability(
    request: LiteratureReliabilitySortRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """按可靠性排序文献"""
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 获取项目文献
    literature_list = db.query(Literature).filter(
        Literature.projects.any(id=request.project_id)
    ).all()
    
    if not literature_list:
        raise HTTPException(status_code=404, detail="项目中没有文献")
    
    # 初始化可靠性服务
    reliability_service = LiteratureReliabilityService(db)
    
    # 排序文献
    sorted_literature = reliability_service.sort_literature_by_reliability(
        literature_list, 
        prioritize_high_reliability=request.prioritize_high_reliability
    )
    
    # 限制返回数量
    if request.limit:
        sorted_literature = sorted_literature[:request.limit]
    
    # 构建返回数据
    sorted_literature_data = []
    for lit in sorted_literature:
        sorted_literature_data.append({
            "id": lit.id,
            "title": lit.title,
            "authors": lit.authors,
            "journal": lit.journal,
            "publication_year": lit.publication_year,
            "impact_factor": lit.impact_factor,
            "citation_count": lit.citation_count,
            "reliability_score": lit.reliability_score,
            "source_reliability": lit.source_reliability,
            "doi": lit.doi
        })
    
    # 计算可靠性统计
    reliability_scores = [lit.reliability_score or 0.5 for lit in sorted_literature]
    reliability_stats = {
        "avg_reliability": sum(reliability_scores) / len(reliability_scores),
        "max_reliability": max(reliability_scores),
        "min_reliability": min(reliability_scores),
        "high_reliability_count": len([s for s in reliability_scores if s >= 0.8]),
        "medium_reliability_count": len([s for s in reliability_scores if 0.5 <= s < 0.8]),
        "low_reliability_count": len([s for s in reliability_scores if s < 0.5])
    }
    
    return {
        "success": True,
        "sorted_literature": sorted_literature_data,
        "reliability_stats": reliability_stats
    }


# 新增的API端点

@router.post("/upload")
@handle_exceptions(ErrorCode.FILE_PROCESSING_FAILED)
async def upload_literature_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    import_type: str = Form(default="regular"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    上传文献文件 - 支持PDF、Zotero导出文件等
    """
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == int(project_id),
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 检查文件类型
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    file_extension = Path(file.filename).suffix.lower()
    
    try:
        # 读取文件内容
        file_content = await file.read()
        
        imported_count = 0
        
        if import_type == "zotero":
            # 处理Zotero导出文件
            integration_manager = ThirdPartyIntegrationManager()
            
            # 根据文件扩展名选择解析方法
            if file_extension == ".ris":
                literature_data = integration_manager.import_from_file(
                    file_content.decode('utf-8'), 'ris'
                )
            elif file_extension == ".bib":
                literature_data = integration_manager.import_from_file(
                    file_content.decode('utf-8'), 'bibtex'
                )
            elif file_extension in [".json", ".csl"]:
                import json
                # 处理CSL JSON格式
                json_data = json.loads(file_content.decode('utf-8'))
                literature_data = _parse_csl_json(json_data)
            elif file_extension in [".xml", ".rdf"]:
                # 处理Zotero RDF格式
                literature_data = _parse_zotero_rdf(file_content.decode('utf-8'))
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"不支持的Zotero文件格式: {file_extension}"
                )
            
            # 将解析的文献数据保存到数据库
            for lit_data in literature_data:
                literature = Literature(
                    title=lit_data.get('title', ''),
                    authors=lit_data.get('authors', []),
                    abstract=lit_data.get('abstract', ''),
                    keywords=lit_data.get('keywords', []),
                    journal=lit_data.get('journal', ''),
                    publication_year=lit_data.get('publication_year'),
                    doi=lit_data.get('doi'),
                    source_platform=lit_data.get('source_platform', 'zotero'),
                    source_url=lit_data.get('source_url'),
                    quality_score=lit_data.get('quality_score', 75.0),
                    project_id=int(project_id),
                    user_id=current_user.id
                )
                db.add(literature)
                imported_count += 1
            
            db.commit()
            
            return {
                "success": True,
                "message": f"成功导入 {imported_count} 篇文献",
                "imported_count": imported_count,
                "import_type": "zotero"
            }
        
        elif import_type == "regular" and file_extension == ".pdf":
            # 处理PDF文件
            pdf_processor = PDFProcessor()
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # 处理PDF
                result = await pdf_processor.process_pdf(temp_file_path)
                
                if result["success"]:
                    content_data = result["content"]
                    
                    # 创建文献记录
                    literature = Literature(
                        title=content_data.get("title") or file.filename,
                        abstract=content_data.get("abstract", ""),
                        text_content=content_data.get("text_content", ""),
                        source_platform="upload",
                        quality_score=75.0,
                        project_id=int(project_id),
                        user_id=current_user.id
                    )
                    
                    db.add(literature)
                    db.commit()
                    
                    imported_count = 1
                    
                    return {
                        "success": True,
                        "message": "PDF文件上传成功",
                        "imported_count": imported_count,
                        "import_type": "pdf"
                    }
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"PDF处理失败: {result.get('error')}"
                    )
            
            finally:
                # 清理临时文件
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件类型: {file_extension}"
            )
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="文件格式错误，无法解析JSON")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请使用UTF-8编码")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@router.post("/ai-search")
@handle_exceptions(ErrorCode.EXTERNAL_API_ERROR)
async def ai_search_literature(
    request: AISearchModeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    AI智能文献搜索 - 使用Research Rabbit API
    """
    # 验证项目所有权（如果提供了project_id）
    project = None
    if request.project_id:
        project = db.query(Project).filter(
            Project.id == request.project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

    try:
        # 使用Research Rabbit API搜索
        async with ResearchRabbitClient() as client:
            papers = await client.search_all_papers(request.query, request.max_results or 20)

            # 转换为前端需要的格式
            search_results = []
            for paper in papers:
                authors_str = ", ".join([
                    author.get("name", "")
                    for author in paper.get("authors", [])
                ])

                search_results.append({
                    "id": paper.get("paperId", ""),
                    "title": paper.get("title", ""),
                    "authors": authors_str,
                    "abstract": paper.get("abstract", ""),
                    "journal": paper.get("venue", {}).get("name", "") if isinstance(paper.get("venue"), dict) else str(paper.get("venue", "")),
                    "year": paper.get("year"),
                    "citations": paper.get("citationCount", 0),
                    "doi": paper.get("externalIds", {}).get("DOI", ""),
                    "url": paper.get("url", ""),
                    "is_open_access": paper.get("isOpenAccess", False)
                })

            return {
                "success": True,
                "papers": search_results,
                "total_count": len(search_results),
                "query": request.query
            }

    except Exception as e:
        logger.error(f"文献搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.post("/add-from-search")
@handle_exceptions(ErrorCode.DATABASE_ERROR)
async def add_literature_from_search(
    request: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    从搜索结果添加文献到项目
    """
    project_id = request.get("projectId") or request.get("project_id")
    paper_ids = request.get("paperIds", [])
    papers_data = request.get("papers", [])

    if not paper_ids and not papers_data:
        raise HTTPException(status_code=400, detail="未选择要添加的文献")

    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == int(project_id),
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        added_count = 0

        # 优先处理papers数据（更完整的数据格式）
        if papers_data:
            for paper in papers_data:
                # 检查是否已存在 - 使用DOI或title检查
                doi = paper.get("doi", "")
                title = paper.get("title", "")

                existing = None
                if doi:
                    existing = db.query(Literature).filter(Literature.doi == doi).first()
                elif title:
                    existing = db.query(Literature).filter(Literature.title == title).first()

                if existing:
                    # 检查是否已经在项目中
                    if existing not in project.literature:
                        project.literature.append(existing)
                        added_count += 1
                    continue

                # 创建文献记录
                authors_list = []
                if isinstance(paper.get("authors"), str):
                    # 如果authors是字符串，按逗号分割
                    authors_list = [author.strip() for author in paper.get("authors", "").split(",")]
                elif isinstance(paper.get("authors"), list):
                    # 如果authors是列表，直接使用
                    authors_list = paper.get("authors", [])

                literature = Literature(
                    title=title,
                    authors=authors_list,
                    abstract=paper.get("abstract", ""),
                    journal=paper.get("journal", ""),
                    publication_year=paper.get("year"),
                    doi=doi,
                    source_platform="researchrabbit",
                    source_url=paper.get("url", ""),
                    citation_count=paper.get("citations", 0),
                    quality_score=75.0,  # 默认质量评分
                    is_downloaded=False,
                    is_parsed=False,
                    parsing_status="pending"
                )

                db.add(literature)
                db.flush()  # 获取ID

                # 添加到项目
                project.literature.append(literature)
                added_count += 1

                # 如果有DOI，启动后台PDF下载任务
                if doi:
                    try:
                        from app.tasks.celery_tasks import download_pdf_celery
                        # 启动后台PDF下载和处理任务
                        task = download_pdf_celery.delay(literature.id, current_user.id)
                        logger.info(f"启动PDF下载任务: literature_id={literature.id}, task_id={task.id}")
                    except Exception as e:
                        logger.warning(f"启动PDF下载任务失败: {e}")
                        # 不影响文献添加的主流程

        # 处理paper_ids（旧格式，需要重新搜索）
        elif paper_ids:
            # 这里可以根据需要实现从paper_ids获取详细信息的逻辑
            # 暂时返回错误，建议使用papers格式
            raise HTTPException(status_code=400, detail="请使用papers格式提供完整的文献数据")

        db.commit()

        return {
            "success": True,
            "message": f"成功添加 {added_count} 篇文献",
            "added_count": added_count
        }

    except Exception as e:
        db.rollback()
        logger.error(f"添加文献失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"添加文献失败: {str(e)}")


# 辅助函数

def _parse_csl_json(json_data) -> List[Dict]:
    """解析CSL JSON格式的Zotero导出"""
    literature_list = []
    
    # CSL JSON可能是单个对象或数组
    items = json_data if isinstance(json_data, list) else [json_data]
    
    for item in items:
        # 提取作者信息
        authors = []
        if "author" in item:
            for author in item["author"]:
                if "given" in author and "family" in author:
                    authors.append(f"{author['given']} {author['family']}")
                elif "literal" in author:
                    authors.append(author["literal"])
        
        literature_data = {
            "title": item.get("title", ""),
            "authors": authors,
            "abstract": item.get("abstract", ""),
            "journal": item.get("container-title", ""),
            "publication_year": item.get("issued", {}).get("date-parts", [[None]])[0][0],
            "doi": item.get("DOI", ""),
            "source_url": item.get("URL", ""),
            "source_platform": "zotero_csl",
            "quality_score": 75.0
        }
        
        literature_list.append(literature_data)
    
    return literature_list


def _parse_zotero_rdf(rdf_content: str) -> List[Dict]:
    """解析Zotero RDF格式的导出"""
    # 简化的RDF解析 - 实际项目中应使用专业的RDF解析库
    literature_list = []
    
    try:
        import re
        
        # 简单的正则表达式匹配（生产环境应使用RDF解析库）
        title_pattern = r'<dc:title>(.*?)</dc:title>'
        creator_pattern = r'<dc:creator>(.*?)</dc:creator>'
        date_pattern = r'<dc:date>(.*?)</dc:date>'
        
        titles = re.findall(title_pattern, rdf_content, re.DOTALL)
        creators = re.findall(creator_pattern, rdf_content, re.DOTALL)
        dates = re.findall(date_pattern, rdf_content, re.DOTALL)
        
        # 假设每个文献的元素是按顺序出现的
        for i in range(len(titles)):
            year = None
            if i < len(dates):
                date_match = re.search(r'\b(19|20)\d{2}\b', dates[i])
                if date_match:
                    year = int(date_match.group())
            
            literature_data = {
                "title": titles[i].strip(),
                "authors": [creators[i].strip()] if i < len(creators) else [],
                "publication_year": year,
                "source_platform": "zotero_rdf",
                "quality_score": 75.0
            }
            
            literature_list.append(literature_data)
    
    except Exception as e:
        from loguru import logger
        logger.error(f"解析Zotero RDF失败: {e}")
    
    return literature_list


@router.post("/project/{project_id}/batch-add")
@handle_exceptions(ErrorCode.DATABASE_ERROR)
async def batch_add_literature(
    project_id: int,
    request: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    批量添加文献到项目
    """
    literature_list = request.get("literature", [])
    
    if not literature_list:
        raise HTTPException(status_code=400, detail="未提供要添加的文献")
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    try:
        added_count = 0
        skipped_count = 0
        
        for lit_data in literature_list:
            # 检查是否已存在（通过DOI或标题）
            existing_query = db.query(Literature).filter(
                Literature.project_id == project_id
            )
            
            if lit_data.get("doi"):
                existing = existing_query.filter(Literature.doi == lit_data["doi"]).first()
            else:
                existing = existing_query.filter(Literature.title == lit_data.get("title", "")).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # 创建新的文献记录
            literature = Literature(
                project_id=project_id,
                title=lit_data.get("title", ""),
                authors=lit_data.get("authors", []),
                abstract=lit_data.get("abstract", ""),
                keywords=lit_data.get("keywords", []),
                journal=lit_data.get("journal", ""),
                publication_year=lit_data.get("publication_year") or lit_data.get("year"),
                doi=lit_data.get("doi"),
                source_platform=lit_data.get("source_platform", "ai_search"),
                source_url=lit_data.get("source_url", ""),
                citation_count=lit_data.get("citation_count"),
                quality_score=lit_data.get("quality_score", 0.0),
                reliability_score=lit_data.get("reliability_score", 0.0),
                status="pending"
            )
            
            db.add(literature)
            added_count += 1
        
        db.commit()
        
        return {
            "success": True,
            "message": f"成功添加 {added_count} 篇文献，跳过 {skipped_count} 篇重复文献",
            "added_count": added_count,
            "skipped_count": skipped_count
        }
    
    except Exception as e:
        logger.error(f"批量添加文献失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量添加文献失败: {str(e)}")

# =================== V2架构整合：AI批量搜索和共享文献功能 ===================

@router.post("/ai-search-batch")
async def ai_search_literature_batch(
    request: LiteratureSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    AI智能文献批量搜索 - 异步后台任务模式（从v2整合）
    """
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 创建后台任务
    task = Task(
        project_id=request.project_id,
        task_type=TaskType.LITERATURE_COLLECTION.value,
        title=f"AI智能文献搜索 - {request.query}",
        description=f"正在搜索相关文献，目标数量: {request.max_results}篇",
        config={
            "query": request.query,
            "max_results": request.max_results,
            "search_mode": "ai_batch"
        },
        status="pending",
        estimated_duration=120  # 2分钟预估
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 启动Celery任务
    from app.tasks.celery_tasks import ai_search_batch_celery
    task_result = ai_search_batch_celery.delay(
        task.id,
        request.query,
        request.max_results
    )
    
    return {
        "success": True,
        "task_id": task.id,
        "message": "AI搜索任务已启动，请通过WebSocket监听进度更新",
        "estimated_duration": task.estimated_duration
    }

@router.post("/add-from-search-v2")
async def add_literature_from_search_v2(
    request: LiteratureAddRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    从搜索结果添加文献到项目 - 使用共享文献架构（从v2整合）
    """
    
    if not request.paper_ids:
        raise HTTPException(status_code=400, detail="未选择要添加的文献")
    
    # 验证项目所有权
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    try:
        literature_service = SharedLiteratureService(db)
        added_count = 0
        reused_count = 0
        
        # 使用Research Rabbit获取详细信息
        async with ResearchRabbitClient() as client:
            for paper_id in request.paper_ids:
                # 通过搜索获取文献详情
                search_result = await client.search_papers(f"paperId:{paper_id}", limit=1)
                
                if search_result.get("data"):
                    paper = search_result["data"][0]
                    
                    # 使用共享文献服务添加
                    user_ref, is_new = await literature_service.add_literature_from_search(
                        user_id=current_user.id,
                        project_id=request.project_id,
                        paper_data=paper
                    )
                    
                    if is_new:
                        added_count += 1
                    else:
                        reused_count += 1
        
        # 启动后台处理任务
        background_tasks.add_task(literature_service.process_literature_queue)
        
        return {
            "success": True,
            "message": f"成功添加 {added_count} 篇新文献，复用 {reused_count} 篇已有文献",
            "added_count": added_count,
            "reused_count": reused_count,
            "total_count": added_count + reused_count
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加文献失败: {str(e)}")

@router.post("/batch-process")
async def start_batch_processing(
    request: BatchProcessingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    启动批量文献处理 - 支持并发搜索、下载和处理（从v2整合）
    
    特性:
    - 并发搜索: Research Rabbit API并发调用
    - 并发下载: 最多10个PDF同时下载
    - 并发处理: 最多5个PDF同时处理
    - 多种处理方式: 快速(1-2s)、标准(3-5s)、高质量(30-60s)
    - 用户选择: 快速处理完成后可选择升级
    """
    try:
        # 验证项目所有权
        project = db.query(Project).filter(
            Project.id == request.project_id,
            Project.owner_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 获取处理管道
        pipeline = get_processing_pipeline()
        
        # 转换处理方式
        method_map = {
            ProcessingMethodEnum.FAST_BASIC: pipeline.ProcessingMethod.FAST_BASIC,
            ProcessingMethodEnum.STANDARD: pipeline.ProcessingMethod.STANDARD,
            ProcessingMethodEnum.PREMIUM_MINERU: pipeline.ProcessingMethod.PREMIUM_MINERU
        }
        
        preferred_method = method_map.get(request.preferred_method, pipeline.ProcessingMethod.FAST_BASIC)
        
        # 启动批量处理
        result = await pipeline.batch_search_and_process(
            query=request.query,
            max_results=request.max_results,
            preferred_method=preferred_method,
            user_choice_callback=None
        )
        
        # 保存到共享文献库
        if result.get("success") and result.get("results"):
            literature_service = SharedLiteratureService(db)
            
            for paper_result in result["results"]:
                if paper_result.get("success"):
                    # 保存处理结果到项目
                    pass
        
        # 添加用户和批次信息
        result["user_id"] = current_user.id
        result["batch_id"] = f"batch_{int(time.time())}"
        
        return {
            "success": True,
            "message": "批量处理已启动",
            "data": result,
            "performance": {
                "concurrent_downloads": 10,
                "concurrent_processing": 5,
                "method_used": request.preferred_method.value
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量处理启动失败: {str(e)}")

@router.get("/user-library")
async def get_user_literature_library(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取用户的文献库 - 基于共享文献架构（从v2整合）
    """
    
    literature_service = SharedLiteratureService(db)
    
    # 获取用户的文献引用
    references = literature_service.get_user_literature_references(
        user_id=current_user.id,
        project_id=project_id,
        status=status,
        limit=limit,
        offset=offset
    )
    
    # 转换为API响应格式
    literature_list = []
    for ref in references:
        shared_lit = ref.shared_literature
        
        literature_list.append({
            "reference_id": ref.id,
            "literature_id": shared_lit.id,
            "title": shared_lit.title,
            "authors": shared_lit.authors,
            "abstract": shared_lit.abstract,
            "journal": shared_lit.journal,
            "publication_year": shared_lit.publication_year,
            "doi": shared_lit.doi,
            "quality_score": shared_lit.quality_score,
            "processing_status": shared_lit.processing_status,
            "is_processed": shared_lit.is_processed,
            "user_status": ref.reading_status,
            "user_rating": ref.user_rating,
            "importance_score": ref.importance_score,
            "added_at": ref.added_at,
            "last_accessed": ref.last_accessed,
            "user_notes": ref.user_notes,
            "user_tags": ref.user_tags,
            # 显示共享信息
            "reference_count": shared_lit.reference_count,
            "is_shared": shared_lit.reference_count > 1
        })
    
    return {
        "success": True,
        "literature": literature_list,
        "total_count": len(literature_list),
        "has_more": len(literature_list) == limit
    }


# Frontend compatibility route - supports project_id as path parameter
@router.get("/user-library/{project_id}")
async def get_user_literature_library_by_project(
    project_id: int,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取用户的文献库 - 支持项目ID作为路径参数（前端兼容性）
    """
    # 直接调用现有的函数，传递 project_id
    return await get_user_literature_library(
        project_id=project_id,
        status=status, 
        limit=limit,
        offset=offset,
        current_user=current_user,
        db=db
    )
@router.get("/processing-methods")
async def get_processing_methods():
    """
    获取可用的处理方式列表（从v2整合）
    """
    methods = [
        {
            "id": "fast_basic",
            "name": "快速处理",
            "description": "基础文本提取，1-2秒完成",
            "time_estimate": "1-2秒",
            "quality_score": 60,
            "features": ["基础文本提取", "快速完成"],
            "recommended_for": ["快速预览", "大批量处理"],
            "icon": "zap",
            "color": "yellow"
        },
        {
            "id": "standard", 
            "name": "标准处理",
            "description": "文本+表格提取，平衡速度与质量",
            "time_estimate": "3-5秒",
            "quality_score": 80,
            "features": ["文本提取", "表格识别", "布局保持"],
            "recommended_for": ["常规使用", "平衡需求"],
            "icon": "settings",
            "color": "blue",
            "recommended": True
        },
        {
            "id": "premium_mineru",
            "name": "高质量处理", 
            "description": "MinerU深度解析，最佳质量输出",
            "time_estimate": "30-60秒",
            "quality_score": 95,
            "features": ["高质量OCR", "完整结构识别", "公式提取", "图表分析", "Markdown输出"],
            "recommended_for": ["重要文献", "深度分析"],
            "icon": "crown",
            "color": "purple"
        }
    ]
    
    return {
        "success": True,
        "methods": methods,
        "default_method": "fast_basic"
    }

@router.get("/statistics-v2")
async def get_literature_statistics_v2(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> LiteratureStatsResponse:
    """
    获取文献处理统计信息 V2（从v2整合）
    """
    
    literature_service = SharedLiteratureService(db)
    stats = literature_service.get_processing_statistics()
    
    return LiteratureStatsResponse(**stats)


# ============================================
# 基础 REST API 端点 - 为前端兼容性添加
# ============================================

@router.get("/", response_model=List[LiteratureResponse])
async def list_literature(
    page: int = 1,
    page_size: int = 20,
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取文献列表 - 基础端点"""
    try:
        if project_id:
            # 如果指定了项目ID，返回项目文献
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.user_id == current_user.id
            ).first()

            if not project:
                raise HTTPException(status_code=404, detail="项目不存在")

            literature_query = db.query(Literature).filter(
                Literature.project_id == project_id
            )
        else:
            # 否则返回用户的所有文献
            literature_query = db.query(Literature).join(Project).filter(
                Project.user_id == current_user.id
            )

        # 分页
        offset = (page - 1) * page_size
        literature_items = literature_query.offset(offset).limit(page_size).all()

        return [
            LiteratureResponse(
                id=lit.id,
                title=lit.title,
                authors=lit.authors,
                abstract=lit.abstract,
                year=lit.year,
                doi=lit.doi,
                project_id=lit.project_id,
                created_at=lit.created_at,
                updated_at=lit.updated_at,
                status=lit.status or "pending",
                url=lit.url,
                quality_score=lit.quality_score
            )
            for lit in literature_items
        ]
    except Exception as e:
        logger.error(f"获取文献列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文献列表失败: {str(e)}")


@router.get("/{literature_id}", response_model=LiteratureResponse)
async def get_literature(
    literature_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取单个文献详情"""
    try:
        literature = db.query(Literature).join(Project).filter(
            Literature.id == literature_id,
            Project.user_id == current_user.id
        ).first()

        if not literature:
            raise HTTPException(status_code=404, detail="文献不存在")

        return LiteratureResponse(
            id=literature.id,
            title=literature.title,
            authors=literature.authors,
            abstract=literature.abstract,
            year=literature.year,
            doi=literature.doi,
            project_id=literature.project_id,
            created_at=literature.created_at,
            updated_at=literature.updated_at,
            status=literature.status or "pending",
            url=literature.url,
            quality_score=literature.quality_score
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文献详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文献详情失败: {str(e)}")


@router.post("/search", response_model=LiteratureSearchResponse)
async def search_literature(
    request: LiteratureSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """基础文献搜索端点"""
    try:
        # 使用现有的AI搜索功能，但简化响应
        collector = EnhancedLiteratureCollector()
        search_result = await collector.search_academic_literature(
            query=request.query,
            max_results=request.max_results or 20,
            sources=request.sources or ["semantic_scholar", "google_scholar"]
        )

        return LiteratureSearchResponse(
            results=[
                {
                    "id": paper.get("id", ""),
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors", []),
                    "abstract": paper.get("abstract", ""),
                    "year": paper.get("year"),
                    "doi": paper.get("doi"),
                    "url": paper.get("url"),
                    "quality_score": paper.get("quality_score", 0.0),
                    "source": paper.get("source", "unknown")
                }
                for paper in search_result.get("results", [])
            ],
            total=search_result.get("total", 0),
            query=request.query
        )
    except Exception as e:
        logger.error(f"文献搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"文献搜索失败: {str(e)}")