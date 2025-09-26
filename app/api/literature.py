"""
文献管理API路由 - 整合v2架构改进
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
from pydantic import BaseModel
from enum import Enum
import asyncio
import tempfile
import os
import json
import time
from pathlib import Path
import hashlib
import uuid
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
from app.services.task_service import TaskService
from app.core.config import settings
from app.schemas.literature_schemas import (
    LiteratureCreateRequest, LiteratureUpdateRequest, LiteratureResponse,
    LiteratureListResponse, LiteratureSearchRequest, LiteratureSearchResponse,
    LiteratureCollectionRequest, LiteratureCollectionResponse,
    LiteratureStatisticsResponse, LiteratureStatsResponse,
    LiteratureProjectStatisticsResponse, LiteratureSegmentsResponse,
    AILiteratureSearchRequest, SearchLibraryModeRequest, AISearchModeRequest,
    LiteraturePageResponse,
)

router = APIRouter()

_SEMANTIC_PLATFORM_KEYS = {
    None,
    "",
    "researchrabbit",
    "research_rabbit",
    "ai_search",
    "semantic",
    "semantic_scholar",
    "rabbit",
}


def _normalize_source_platform(raw: Optional[str]) -> str:
    key = (raw or "").strip().lower()
    if key in _SEMANTIC_PLATFORM_KEYS:
        return "semantic_scholar"
    return key or "semantic_scholar"


def _build_literature_response(lit: Literature) -> LiteratureResponse:
    """统一构造 LiteratureResponse，避免重复代码"""
    normalized_source = _normalize_source_platform(getattr(lit, "source_platform", None))
    return LiteratureResponse(
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
        source_platform=normalized_source,
        source_url=lit.source_url,
        pdf_url=lit.pdf_url,
        pdf_path=lit.pdf_path,
        status=lit.status,
        parsing_status=lit.parsing_status if lit.parsing_status else "pending",
        parsed_content=lit.parsed_content,
        citation_count=lit.citation_count or 0,
        impact_factor=float(lit.impact_factor) if lit.impact_factor is not None else None,
        quality_score=float(lit.quality_score) if lit.quality_score is not None else None,
        is_downloaded=bool(lit.is_downloaded),
        is_parsed=bool(lit.is_parsed),
        is_starred=bool(getattr(lit, "is_starred", False)),
        file_path=lit.file_path,
        file_size=lit.file_size,
        file_hash=lit.file_hash,
        created_at=lit.created_at,
        updated_at=lit.updated_at,
        relevance_score=None,
        is_selected=False,
        tags=lit.tags,
        category=lit.category,
        segments=None,
        projects=None
    )


def _user_accessible_literature_query(
    db: Session,
    user_id: int,
    project_id: Optional[int] = None,
):
    """构建当前用户可访问的文献查询对象"""

    query = db.query(Literature)

    if hasattr(query, "outerjoin"):
        query = query.outerjoin(Project)
    elif hasattr(query, "join"):
        query = query.join(Project)

    if project_id is not None:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.owner_id == user_id)
            .first()
        )

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        query = query.filter(
            or_(
                Literature.project_id == project_id,
                Literature.projects.any(Project.id == project_id),
            )
        )
    if hasattr(query, "filter"):
        query.filter(Project.owner_id == user_id)

    query = query.filter(
        or_(
            Project.owner_id == user_id,
            Literature.projects.any(Project.owner_id == user_id),
        )
    )

    if hasattr(query, "distinct"):
        return query.distinct(Literature.id)
    return query

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
        keywords,
        request.project_id,
        current_user.id,
        {
            "max_results": max_results,
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
        estimated_duration=max_results * 8,
        config={
            "keywords": keywords,
            "max_results": max_results,
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
    
    # 检查会员限制与来源
    membership = current_user.membership
    if membership:
        if membership.membership_type.value == "free" and request.max_count > 1000:
            request.max_count = 1000
        elif membership.membership_type.value == "premium" and request.max_count > 2000:
            request.max_count = 2000

    requested_sources = request.sources or ["researchrabbit"]
    normalized_sources = {src.lower() for src in requested_sources}
    if normalized_sources - {"researchrabbit"}:
        raise HTTPException(status_code=400, detail="当前仅支持 ResearchRabbit 作为数据来源")
    sanitized_sources = ["researchrabbit"]

    # 创建任务
    task = Task(
        project_id=request.project_id,
        task_type="literature_collection",
        title=f"文献采集 - {', '.join(request.keywords)}",
        description=f"采集关键词相关文献，最大数量：{request.max_count}",
        config={
            "keywords": request.keywords,
            "max_count": request.max_count,
            "sources": sanitized_sources
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
        sanitized_sources
    )

    return LiteratureCollectionResponse(
        task_id=task.id,
        message="文献采集任务已启动",
        estimated_duration=300,
        collection_config={
            "keywords": request.keywords,
            "max_count": request.max_count,
            "sources": sanitized_sources
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

    page = max(page, 1)
    page_size = max(1, page_size)
    offset = (page - 1) * page_size

    query = _user_accessible_literature_query(db, current_user.id, project_id)
    literature_list = (
        query.order_by(
            Literature.quality_score.desc(),
            Literature.created_at.desc(),
            Literature.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return [_build_literature_response(lit) for lit in literature_list]

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
        or_(
            Literature.project_id == project_id,
            Literature.projects.any(id=project_id)
        ),
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
        or_(
            Literature.project_id == project_id,
            Literature.projects.any(id=project_id)
        )
    ).count()

    processed_literature = db.query(Literature).filter(
        or_(
            Literature.project_id == project_id,
            Literature.projects.any(id=project_id)
        ),
        Literature.is_parsed == True
    ).count()

    total_segments = db.query(LiteratureSegment).join(Literature).filter(
        or_(
            Literature.project_id == project_id,
            Literature.projects.any(id=project_id)
        )
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
        or_(
            Literature.project_id == request.project_id,
            Literature.projects.any(id=request.project_id)
        )
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
        or_(
            Literature.project_id == request.project_id,
            Literature.projects.any(id=request.project_id)
        )
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
    db: Session = Depends(get_db),
):
    """上传文献文件，支持 PDF 与 Zotero 导出"""

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    try:
        project_id_int = int(project_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="无效的项目ID")

    project = (
        db.query(Project)
        .filter(Project.id == project_id_int, Project.owner_id == current_user.id)
        .first()
    )

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权访问")

    file_extension = Path(file.filename).suffix.lower()

    async def _process_pdf_upload() -> Dict[str, Any]:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="上传文件为空")

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing_literature = (
            db.query(Literature)
            .filter(Literature.file_hash == file_hash)
            .first()
        )

        if existing_literature:
            if existing_literature not in project.literature:
                project.literature.append(existing_literature)
            if not existing_literature.project_id:
                existing_literature.project_id = project.id
            db.commit()

            return {
                "success": True,
                "message": "该PDF已存在，已复用并关联到当前项目",
                "literature_id": existing_literature.id,
                "import_type": "pdf",
                "imported_count": 0,
            }

        project_dir = Path(settings.upload_path) / f"project_{project.id}"
        project_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid.uuid4().hex}{file_extension or '.pdf'}"
        stored_path = project_dir / stored_filename
        with open(stored_path, "wb") as fp:
            fp.write(file_bytes)

        literature = Literature(
            title=file.filename or "未命名文献",
            authors=[],
            abstract=None,
            source_platform="semantic_scholar",
            source_url=None,
            file_path=str(stored_path),
            pdf_path=str(stored_path),
            file_size=len(file_bytes),
            file_hash=file_hash,
            is_downloaded=True,
            is_parsed=False,
            parsing_status="pending",
            status="pending",
            quality_score=7.5,
            raw_data={
                "import_type": "pdf_upload",
                "original_filename": file.filename,
            },
        )

        literature.project = project
        db.add(literature)
        db.flush()
        project.literature.append(literature)
        db.commit()

        task_service = TaskService(db)
        processing_task = task_service.create_literature_processing_task(
            owner_id=current_user.id,
            project_id=project.id,
            description=f"处理上传文献 {literature.title[:40]}",
        )

        return {
            "success": True,
            "message": "PDF文件上传成功，已启动后台处理任务",
            "imported_count": 1,
            "import_type": "pdf",
            "literature_id": literature.id,
            "task_id": processing_task.id,
        }

    async def _process_zotero_upload() -> Dict[str, Any]:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="上传文件为空")

        try:
            file_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            file_text = file_bytes.decode("utf-8", errors="ignore")

        integration_manager = ThirdPartyIntegrationManager()
        literature_items: List[Dict]

        if file_extension == ".ris":
            literature_items = integration_manager.import_from_file(file_text, "ris")
        elif file_extension == ".bib":
            literature_items = integration_manager.import_from_file(file_text, "bibtex")
        elif file_extension in {".json", ".csl"}:
            try:
                json_data = json.loads(file_text)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="JSON 文件格式错误")
            literature_items = _parse_csl_json(json_data)
        elif file_extension in {".xml", ".rdf"}:
            literature_items = _parse_zotero_rdf(file_text)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的Zotero文件格式: {file_extension}",
            )

        if not literature_items:
            raise HTTPException(status_code=400, detail="未从文件中解析到有效文献信息")

        def _safe_int(value: Optional[str]) -> Optional[int]:
            try:
                if value is None:
                    return None
                return int(str(value)[:4])
            except (TypeError, ValueError):
                return None

        imported_count = 0
        reused_count = 0

        for item in literature_items:
            title = item.get("title") or file.filename
            if not title:
                continue

            doi = item.get("doi") or item.get("DOI")
            existing = None
            if doi:
                existing = db.query(Literature).filter(Literature.doi == doi).first()
            if not existing:
                existing = (
                    db.query(Literature)
                    .filter(Literature.title == title)
                    .first()
                )

            if existing:
                if existing not in project.literature:
                    project.literature.append(existing)
                if not existing.project_id:
                    existing.project_id = project.id
                reused_count += 1
                continue

            authors = item.get("authors") or []
            if authors and isinstance(authors[0], dict):
                normalized_authors = []
                for author in authors:
                    name = author.get("name")
                    if not name:
                        name = f"{author.get('firstName', '')} {author.get('lastName', '')}".strip()
                    if name:
                        normalized_authors.append(name)
                authors = normalized_authors

            literature = Literature(
                title=title,
                authors=authors,
                abstract=item.get("abstract", ""),
                journal=item.get("journal") or item.get("publication") or "",
                publication_year=_safe_int(item.get("publication_year") or item.get("year")),
                doi=doi,
                source_platform=_normalize_source_platform(item.get("source_platform", "semantic_scholar")),
                source_url=item.get("source_url") or item.get("url"),
                is_downloaded=False,
                is_parsed=False,
                parsing_status="pending",
                status="pending",
                quality_score=min(float(item.get("quality_score", 6.5)), 10.0),
                raw_data=item,
            )

            literature.project = project
            db.add(literature)
            db.flush()
            project.literature.append(literature)
            imported_count += 1

        db.commit()

        task_id = None
        if imported_count > 0:
            task_service = TaskService(db)
            processing_task = task_service.create_literature_processing_task(
                owner_id=current_user.id,
                project_id=project.id,
                description="处理Zotero导入的文献",
            )
            task_id = processing_task.id

        return {
            "success": True,
            "message": f"成功导入 {imported_count} 篇文献，复用 {reused_count} 篇",
            "imported_count": imported_count,
            "reused_count": reused_count,
            "import_type": "zotero",
            "task_id": task_id,
        }

    if import_type == "zotero":
        return await _process_zotero_upload()

    if import_type == "regular" and file_extension == ".pdf":
        return await _process_pdf_upload()

    raise HTTPException(status_code=400, detail=f"不支持的导入类型或文件格式: {import_type}")


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
                    if not existing.project_id:
                        existing.project_id = project.id
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
                    source_platform="semantic_scholar",
                    source_url=paper.get("url", ""),
                    citation_count=paper.get("citations", 0),
                    quality_score=75.0,  # 默认质量评分
                    is_downloaded=False,
                    is_parsed=False,
                    parsing_status="pending"
                )

                literature.project = project
                db.add(literature)
                db.flush()  # 获取ID

                # 添加到项目
                project.literature.append(literature)
                added_count += 1

                # 如果有DOI，启动后台PDF处理任务
                if doi:
                    try:
                        task_service = TaskService(db)
                        pdf_task = task_service.create_pdf_processing_task(
                            owner_id=current_user.id,
                            project_id=project.id,
                            literature_id=literature.id,
                            literature_title=title or literature.title or f"文献 {literature.id}",
                        )
                        logger.info(
                            f"已创建PDF处理任务: literature_id={literature.id}, task_id={pdf_task.id}"
                        )
                    except Exception as task_error:
                        logger.error(f"创建PDF处理任务失败: {task_error}")
                        raise HTTPException(status_code=500, detail="创建PDF处理任务失败")

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
                source_platform=_normalize_source_platform(lit_data.get("source_platform", "semantic_scholar")),
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

@router.get("/", response_model=LiteraturePageResponse)
async def list_literature(
    page: int = 1,
    page_size: int = 20,
    size: Optional[int] = Query(None, alias="size"),
    query: Optional[str] = Query(None, alias="query"),
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取文献列表 - 基础端点"""

    try:
        requested_size = size.default if hasattr(size, "default") else size
        normalized_size: Optional[int] = None
        if requested_size is not None:
            try:
                normalized_size = int(requested_size)
            except (TypeError, ValueError):
                normalized_size = None

        actual_page_size = max(1, normalized_size) if normalized_size and normalized_size > 0 else max(1, page_size)
        page = max(page, 1)
        offset = (page - 1) * actual_page_size

        query_builder = _user_accessible_literature_query(db, current_user.id, project_id)

        required_methods = ("order_by", "count", "offset", "limit", "all")
        if not all(hasattr(query_builder, attr) for attr in required_methods):
            return []

        raw_query = query.default if hasattr(query, "default") else query
        if raw_query:
            filter_keyword = raw_query.strip()
            if filter_keyword:
                sanitized = f"%{filter_keyword}%"
                query_builder = query_builder.filter(
                    or_(
                        Literature.title.ilike(sanitized),
                        Literature.abstract.ilike(sanitized),
                    )
                )

        total = query_builder.order_by(None).count()
        literature_items = (
            query_builder
            .order_by(
                Literature.quality_score.desc(),
                Literature.created_at.desc(),
                Literature.id.desc(),
            )
            .offset(offset)
            .limit(actual_page_size)
            .all()
        )

        items = [_build_literature_response(lit) for lit in literature_items]
        has_more = (page * actual_page_size) < total

        return LiteraturePageResponse(
            items=items,
            total=total,
            page=page,
            page_size=actual_page_size,
            has_more=has_more,
        )
    except HTTPException:
        raise
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
        literature = db.query(Literature).filter(Literature.id == literature_id).first()

        if not literature:
            raise HTTPException(status_code=404, detail="文献不存在")

        project_ids = [pid for (pid,) in db.query(Project.id).filter(Project.owner_id == current_user.id).all()]

        has_access = False
        if literature.project_id and literature.project_id in project_ids:
            has_access = True
        else:
            associated_ids = {proj.id for proj in literature.projects}
            if associated_ids.intersection(project_ids):
                has_access = True

        if not has_access:
            raise HTTPException(status_code=403, detail="无权访问该文献")

        return _build_literature_response(literature)
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
        max_results = min(request.max_results or 20, 500)
        async with ResearchRabbitClient() as client:
            papers = await client.search_all_papers(request.query, max_results)

        mapped_results = []
        for paper in papers:
            authors = [author.get("name") for author in paper.get("authors", []) if author.get("name")]
            mapped_results.append(
                {
                    "id": paper.get("paperId", ""),
                    "title": paper.get("title", ""),
                    "authors": authors,
                    "abstract": paper.get("abstract", ""),
                    "year": paper.get("year"),
                    "doi": paper.get("externalIds", {}).get("DOI"),
                    "url": paper.get("url"),
                    "quality_score": EnhancedLiteratureCollector._calculate_quality_score(paper),
                    "source": "researchrabbit",
                }
            )

        return LiteratureSearchResponse(
            results=mapped_results,
            total=len(mapped_results),
            query=request.query
        )
    except Exception as e:
        logger.error(f"文献搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"文献搜索失败: {str(e)}")


# =================== Phase B 批量操作 API ===================

class BatchStarRequest(BaseModel):
    """批量收藏请求"""
    literature_ids: List[int]
    starred: bool

class BatchArchiveRequest(BaseModel):
    """批量归档请求"""
    literature_ids: List[int]
    archived: bool

class BatchTagsRequest(BaseModel):
    """批量标签请求"""
    literature_ids: List[int]
    action: str  # 'add', 'remove', 'replace'
    tags: List[str]

class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    literature_ids: List[int]

class BatchExportRequest(BaseModel):
    """批量导出请求"""
    literature_ids: List[int]
    format: str  # 'csv', 'bibtex', 'json'
    fields: List[str]
    includeAbstract: bool = False
    includeKeywords: bool = False

class BatchOperationResponse(BaseModel):
    """批量操作响应"""
    success: bool
    updated: int
    message: str = ""

class BatchExportResponse(BaseModel):
    """批量导出响应"""
    success: bool
    downloadUrl: str
    message: str = ""


@router.post("/batch/star", response_model=BatchOperationResponse)
@handle_exceptions(ErrorCode.DATABASE_ERROR)
async def batch_star_literature(
    request: BatchStarRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """批量收藏/取消收藏文献"""
    if not request.literature_ids:
        raise HTTPException(status_code=400, detail="未选择文献")

    try:
        # 验证用户对所有文献的访问权限
        user_project_ids = [p.id for p in current_user.projects]
        literature_items = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids)
        ).all()

        valid_literature = []
        for lit in literature_items:
            # 检查文献是否属于用户的项目
            has_access = False
            if lit.project_id and lit.project_id in user_project_ids:
                has_access = True
            else:
                # 检查多对多关联
                for project in lit.projects:
                    if project.id in user_project_ids:
                        has_access = True
                        break

            if has_access:
                valid_literature.append(lit)

        if not valid_literature:
            raise HTTPException(status_code=403, detail="无权访问选中的文献")

        # 更新is_starred字段
        for lit in valid_literature:
            lit.is_starred = request.starred

        db.commit()

        action = "收藏" if request.starred else "取消收藏"
        return BatchOperationResponse(
            success=True,
            updated=len(valid_literature),
            message=f"成功{action} {len(valid_literature)} 篇文献"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"批量收藏操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量收藏操作失败: {str(e)}")


@router.post("/batch/archive", response_model=BatchOperationResponse)
@handle_exceptions(ErrorCode.DATABASE_ERROR)
async def batch_archive_literature(
    request: BatchArchiveRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """批量归档文献"""
    if not request.literature_ids:
        raise HTTPException(status_code=400, detail="未选择文献")

    try:
        # 验证用户对所有文献的访问权限
        user_project_ids = [p.id for p in current_user.projects]
        literature_items = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids)
        ).all()

        valid_literature = []
        for lit in literature_items:
            # 检查文献是否属于用户的项目
            has_access = False
            if lit.project_id and lit.project_id in user_project_ids:
                has_access = True
            else:
                # 检查多对多关联
                for project in lit.projects:
                    if project.id in user_project_ids:
                        has_access = True
                        break

            if has_access:
                valid_literature.append(lit)

        if not valid_literature:
            raise HTTPException(status_code=403, detail="无权访问选中的文献")

        # 更新status字段为archived
        for lit in valid_literature:
            if request.archived:
                lit.status = "archived"
            else:
                lit.status = "active"  # 取消归档

        db.commit()

        action = "归档" if request.archived else "取消归档"
        return BatchOperationResponse(
            success=True,
            updated=len(valid_literature),
            message=f"成功{action} {len(valid_literature)} 篇文献"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"批量归档操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量归档操作失败: {str(e)}")


@router.post("/batch/tags", response_model=BatchOperationResponse)
@handle_exceptions(ErrorCode.DATABASE_ERROR)
async def batch_set_tags(
    request: BatchTagsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """批量设置标签"""
    if not request.literature_ids:
        raise HTTPException(status_code=400, detail="未选择文献")

    if request.action not in ['add', 'remove', 'replace']:
        raise HTTPException(status_code=400, detail="无效的操作类型")

    try:
        # 验证用户对所有文献的访问权限
        user_project_ids = [p.id for p in current_user.projects]
        literature_items = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids)
        ).all()

        valid_literature = []
        for lit in literature_items:
            # 检查文献是否属于用户的项目
            has_access = False
            if lit.project_id and lit.project_id in user_project_ids:
                has_access = True
            else:
                # 检查多对多关联
                for project in lit.projects:
                    if project.id in user_project_ids:
                        has_access = True
                        break

            if has_access:
                valid_literature.append(lit)

        if not valid_literature:
            raise HTTPException(status_code=403, detail="无权访问选中的文献")

        # 处理标签操作
        for lit in valid_literature:
            current_tags = set(lit.tags or [])
            new_tags = set(request.tags)

            if request.action == 'add':
                # 添加标签
                updated_tags = current_tags.union(new_tags)
            elif request.action == 'remove':
                # 移除标签
                updated_tags = current_tags.difference(new_tags)
            else:  # replace
                # 替换标签
                updated_tags = new_tags

            lit.tags = list(updated_tags)

        db.commit()

        action_map = {'add': '添加', 'remove': '移除', 'replace': '替换'}
        action_name = action_map[request.action]

        return BatchOperationResponse(
            success=True,
            updated=len(valid_literature),
            message=f"成功{action_name}标签，共处理 {len(valid_literature)} 篇文献"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"批量标签操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量标签操作失败: {str(e)}")


@router.post("/batch/delete", response_model=BatchOperationResponse)
@handle_exceptions(ErrorCode.DATABASE_ERROR)
async def batch_delete_literature(
    request: BatchDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """批量删除文献"""
    if not request.literature_ids:
        raise HTTPException(status_code=400, detail="未选择文献")

    try:
        # 验证用户对所有文献的访问权限
        user_project_ids = [p.id for p in current_user.projects]
        literature_items = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids)
        ).all()

        valid_literature = []
        for lit in literature_items:
            # 检查文献是否属于用户的项目
            has_access = False
            if lit.project_id and lit.project_id in user_project_ids:
                has_access = True
            else:
                # 检查多对多关联
                for project in lit.projects:
                    if project.id in user_project_ids:
                        has_access = True
                        break

            if has_access:
                valid_literature.append(lit)

        if not valid_literature:
            raise HTTPException(status_code=403, detail="无权访问选中的文献")

        # 删除文献记录
        deleted_count = 0
        for lit in valid_literature:
            # 清理文件（如果存在）
            if lit.file_path and os.path.exists(lit.file_path):
                try:
                    os.remove(lit.file_path)
                except OSError:
                    logger.warning(f"删除文件失败: {lit.file_path}")

            if lit.pdf_path and os.path.exists(lit.pdf_path):
                try:
                    os.remove(lit.pdf_path)
                except OSError:
                    logger.warning(f"删除PDF文件失败: {lit.pdf_path}")

            # 删除数据库记录
            db.delete(lit)
            deleted_count += 1

        db.commit()

        return BatchOperationResponse(
            success=True,
            updated=deleted_count,
            message=f"成功删除 {deleted_count} 篇文献"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"批量删除操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量删除操作失败: {str(e)}")


@router.post("/batch/export", response_model=BatchExportResponse)
@handle_exceptions(ErrorCode.DATABASE_ERROR)
async def batch_export_literature(
    request: BatchExportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """批量导出文献"""
    if not request.literature_ids:
        raise HTTPException(status_code=400, detail="未选择文献")

    if request.format not in ['csv', 'bibtex', 'json']:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    try:
        # 验证用户对所有文献的访问权限
        user_project_ids = [p.id for p in current_user.projects]
        literature_items = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids)
        ).all()

        valid_literature = []
        for lit in literature_items:
            # 检查文献是否属于用户的项目
            has_access = False
            if lit.project_id and lit.project_id in user_project_ids:
                has_access = True
            else:
                # 检查多对多关联
                for project in lit.projects:
                    if project.id in user_project_ids:
                        has_access = True
                        break

            if has_access:
                valid_literature.append(lit)

        if not valid_literature:
            raise HTTPException(status_code=403, detail="无权访问选中的文献")

        # 生成导出内容
        export_content = ""
        timestamp = int(time.time())
        filename = f"literature_export_{timestamp}.{request.format}"

        if request.format == 'csv':
            export_content = _generate_csv_export(valid_literature, request)
        elif request.format == 'bibtex':
            export_content = _generate_bibtex_export(valid_literature, request)
        elif request.format == 'json':
            export_content = _generate_json_export(valid_literature, request)

        # 保存到临时目录
        export_dir = Path(settings.upload_path) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        export_path = export_dir / filename
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write(export_content)

        # 生成下载URL
        download_url = f"/api/literature/download/{filename}"

        return BatchExportResponse(
            success=True,
            downloadUrl=download_url,
            message=f"成功导出 {len(valid_literature)} 篇文献"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量导出操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量导出操作失败: {str(e)}")


def _generate_csv_export(literature_items: List[Literature], request: BatchExportRequest) -> str:
    """生成CSV格式导出"""
    import csv
    import io

    output = io.StringIO()

    # 基础字段映射
    field_mapping = {
        'title': '标题',
        'authors': '作者',
        'journal': '期刊',
        'year': '年份',
        'doi': 'DOI',
        'citation_count': '引用次数',
        'quality_score': '质量评分',
        'tags': '标签'
    }

    # 构建CSV头部
    headers = []
    for field in request.fields:
        if field in field_mapping:
            headers.append(field_mapping[field])

    if request.includeAbstract:
        headers.append('摘要')
    if request.includeKeywords:
        headers.append('关键词')

    writer = csv.writer(output)
    writer.writerow(headers)

    # 写入数据行
    for lit in literature_items:
        row = []
        for field in request.fields:
            if field == 'title':
                row.append(lit.title or '')
            elif field == 'authors':
                row.append(', '.join(lit.authors or []))
            elif field == 'journal':
                row.append(lit.journal or '')
            elif field == 'year':
                row.append(lit.publication_year or '')
            elif field == 'doi':
                row.append(lit.doi or '')
            elif field == 'citation_count':
                row.append(lit.citation_count or 0)
            elif field == 'quality_score':
                row.append(lit.quality_score or 0)
            elif field == 'tags':
                row.append(', '.join(lit.tags or []))

        if request.includeAbstract:
            row.append(lit.abstract or '')
        if request.includeKeywords:
            row.append(', '.join(lit.keywords or []))

        writer.writerow(row)

    return output.getvalue()


def _generate_bibtex_export(literature_items: List[Literature], request: BatchExportRequest) -> str:
    """生成BibTeX格式导出"""
    entries = []

    for i, lit in enumerate(literature_items, 1):
        # 生成BibTeX条目ID
        entry_id = f"lit{i}"
        if lit.authors:
            first_author = lit.authors[0].split()[-1] if lit.authors[0] else "unknown"
            year = lit.publication_year or "unknown"
            entry_id = f"{first_author}{year}"

        # 构建BibTeX条目
        entry_type = "article"  # 默认为期刊文章

        bibtex_entry = f"@{entry_type}{{{entry_id},\n"

        if lit.title:
            bibtex_entry += f"  title={{{lit.title}}},\n"
        if lit.authors:
            authors = " and ".join(lit.authors)
            bibtex_entry += f"  author={{{authors}}},\n"
        if lit.journal:
            bibtex_entry += f"  journal={{{lit.journal}}},\n"
        if lit.publication_year:
            bibtex_entry += f"  year={{{lit.publication_year}}},\n"
        if lit.doi:
            bibtex_entry += f"  doi={{{lit.doi}}},\n"
        if request.includeAbstract and lit.abstract:
            bibtex_entry += f"  abstract={{{lit.abstract}}},\n"
        if request.includeKeywords and lit.keywords:
            keywords = ", ".join(lit.keywords)
            bibtex_entry += f"  keywords={{{keywords}}},\n"

        # 移除最后的逗号
        bibtex_entry = bibtex_entry.rstrip(',\n') + '\n'
        bibtex_entry += "}\n\n"

        entries.append(bibtex_entry)

    return "".join(entries)


def _generate_json_export(literature_items: List[Literature], request: BatchExportRequest) -> str:
    """生成JSON格式导出"""
    import json

    export_data = []

    for lit in literature_items:
        item = {}

        for field in request.fields:
            if field == 'title':
                item['title'] = lit.title
            elif field == 'authors':
                item['authors'] = lit.authors
            elif field == 'journal':
                item['journal'] = lit.journal
            elif field == 'year':
                item['publication_year'] = lit.publication_year
            elif field == 'doi':
                item['doi'] = lit.doi
            elif field == 'citation_count':
                item['citation_count'] = lit.citation_count
            elif field == 'quality_score':
                item['quality_score'] = lit.quality_score
            elif field == 'tags':
                item['tags'] = lit.tags

        if request.includeAbstract:
            item['abstract'] = lit.abstract
        if request.includeKeywords:
            item['keywords'] = lit.keywords

        export_data.append(item)

    return json.dumps(export_data, ensure_ascii=False, indent=2)


@router.get("/download/{filename}")
async def download_export_file(filename: str):
    """下载导出文件"""
    export_dir = Path(settings.upload_path) / "exports"
    file_path = export_dir / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="导出文件不存在")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )


# =================== Phase B: 引用关系 API ===================

@router.get("/{literature_id}/citations")
@handle_exceptions(ErrorCode.EXTERNAL_API_ERROR)
async def get_literature_citations(
    literature_id: int,
    include_references: bool = True,
    include_citations: bool = True,
    max_citations: int = 25,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取文献的引用关系数据"""

    # 验证文献访问权限
    literature = db.query(Literature).filter(Literature.id == literature_id).first()
    if not literature:
        raise HTTPException(status_code=404, detail="文献不存在")

    # 检查用户是否有权限访问此文献
    user_projects = [p.id for p in current_user.projects]
    literature_projects = [p.id for p in literature.projects] if literature.projects else []

    has_access = False
    if literature.project_id and literature.project_id in user_projects:
        has_access = True
    elif any(pid in user_projects for pid in literature_projects):
        has_access = True

    if not has_access:
        raise HTTPException(status_code=403, detail="无权限访问此文献")

    # 返回模拟的引用关系数据
    mock_citations = _get_mock_citation_data(literature_id, literature.title, max_citations)

    return mock_citations


def _get_mock_citation_data(literature_id: int, title: str, max_citations: int = 25) -> dict:
    """生成模拟的引用关系数据"""
    import random
    from datetime import datetime, timedelta

    # 生成模拟的引用文献
    citations = []
    for i in range(min(max_citations, random.randint(5, 15))):
        citations.append({
            "title": f"引用文献 {i+1}: 基于{title}的进一步研究",
            "authors": [f"作者{random.randint(1, 3)}", f"作者{random.randint(4, 6)}"],
            "year": random.randint(2020, 2024),
            "venue": random.choice(["Nature", "Science", "IEEE Transactions", "ACM Computing Surveys"]),
            "doi": f"10.1000/citation{i+1}",
            "url": f"https://example.com/citation/{i+1}",
            "citationCount": random.randint(0, 100),
            "abstract": f"这是引用文献{i+1}的摘要内容，基于原文献的理论基础进行了扩展研究。"
        })

    # 生成模拟的参考文献
    references = []
    for i in range(random.randint(8, 20)):
        references.append({
            "title": f"参考文献 {i+1}: 相关领域的基础研究",
            "authors": [f"专家{random.randint(1, 4)}", f"专家{random.randint(5, 8)}"],
            "year": random.randint(2015, 2022),
            "venue": random.choice(["Journal of AI", "ICML", "NeurIPS", "AAAI"]),
            "doi": f"10.1000/reference{i+1}",
            "url": f"https://example.com/reference/{i+1}",
            "citationCount": random.randint(10, 500),
            "abstract": f"这是参考文献{i+1}的摘要内容，为当前研究提供了理论基础。"
        })

    return {
        "literature_id": literature_id,
        "title": title,
        "citations": citations,
        "references": references,
        "citation_count": len(citations),
        "reference_count": len(references),
        "citation_graph": {
            "nodes": [
                {"id": f"center-{literature_id}", "name": title, "type": "center"},
                *[{"id": f"citation-{i}", "name": citation["title"], "type": "citation"} for i, citation in enumerate(citations)],
                *[{"id": f"reference-{i}", "name": ref["title"], "type": "reference"} for i, ref in enumerate(references)]
            ],
            "links": [
                *[{"source": f"citation-{i}", "target": f"center-{literature_id}", "type": "citation"} for i in range(len(citations))],
                *[{"source": f"center-{literature_id}", "target": f"reference-{i}", "type": "reference"} for i in range(len(references))]
            ]
        },
        "last_updated": datetime.now().isoformat()
    }
