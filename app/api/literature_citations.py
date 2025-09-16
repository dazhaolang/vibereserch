"""
文献引用查询API - 支持懒加载和实时查询
"""

from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.literature import Literature
from app.services.research_rabbit_client import ResearchRabbitClient
from app.services.stream_progress_service import stream_progress_service
from loguru import logger

router = APIRouter()

class CitationRequest(BaseModel):
    literature_id: int
    include_references: bool = True
    include_citations: bool = True
    max_citations: int = 50

class CitationResponse(BaseModel):
    literature_id: int
    title: str
    citations: List[Dict]
    references: List[Dict] 
    citation_count: int
    reference_count: int
    citation_graph: Dict
    last_updated: str

@router.get("/literature/{literature_id}/citations", response_model=CitationResponse)
async def get_literature_citations(
    literature_id: int,
    task_id: Optional[str] = Query(None, description="关联的任务ID"),
    include_references: bool = Query(True, description="包含参考文献"),
    include_citations: bool = Query(True, description="包含被引文献"),
    max_citations: int = Query(50, description="最大引用数量"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    懒加载获取文献的引用和被引信息
    点击时才从ResearchRabbit查询，节省算力
    """
    
    # 查找文献
    literature = db.query(Literature).filter(Literature.id == literature_id).first()
    if not literature:
        raise HTTPException(status_code=404, detail="文献不存在")
    
    try:
        # 如果有task_id，更新进度
        if task_id:
            await stream_progress_service.update_stage_progress(
                task_id, "interaction", 25, 
                f"正在查询文献引用: {literature.title[:50]}...",
                sub_progress={"action": "fetching_citations", "literature_id": literature_id}
            )
        
        # 使用ResearchRabbit客户端查询引用
        rabbit_client = ResearchRabbitClient()
        
        citations = []
        references = []
        citation_graph = {}
        
        # 查询被引文献
        if include_citations:
            if task_id:
                await stream_progress_service.update_stage_progress(
                    task_id, "interaction", 50,
                    "查询被引文献中...",
                    sub_progress={"action": "fetching_citations", "type": "citations"}
                )
            
            citations_result = await rabbit_client.get_citations(
                literature.doi or literature.title,
                limit=max_citations
            )
            citations = citations_result.get("citations", [])
        
        # 查询参考文献  
        if include_references:
            if task_id:
                await stream_progress_service.update_stage_progress(
                    task_id, "interaction", 75,
                    "查询参考文献中...",
                    sub_progress={"action": "fetching_references", "type": "references"}
                )
            
            references_result = await rabbit_client.get_references(
                literature.doi or literature.title,
                limit=max_citations
            )
            references = references_result.get("references", [])
        
        # 构建引用图谱
        citation_graph = {
            "nodes": [
                {
                    "id": literature_id,
                    "title": literature.title,
                    "type": "main",
                    "citation_count": len(citations),
                    "reference_count": len(references)
                }
            ] + [
                {
                    "id": f"cite_{i}",
                    "title": cite.get("title", ""),
                    "type": "citation",
                    "year": cite.get("year")
                } for i, cite in enumerate(citations[:10])
            ] + [
                {
                    "id": f"ref_{i}", 
                    "title": ref.get("title", ""),
                    "type": "reference",
                    "year": ref.get("year")
                } for i, ref in enumerate(references[:10])
            ],
            "links": [
                {"source": f"cite_{i}", "target": literature_id, "type": "cites"}
                for i in range(min(len(citations), 10))
            ] + [
                {"source": literature_id, "target": f"ref_{i}", "type": "references"}
                for i in range(min(len(references), 10))
            ]
        }
        
        # 更新任务中的文献引用信息
        if task_id:
            await stream_progress_service.update_literature_citations(
                task_id, literature_id, {
                    "citations": citations,
                    "references": references, 
                    "citation_graph": citation_graph
                }
            )
            
            await stream_progress_service.update_stage_progress(
                task_id, "interaction", 100,
                f"引用查询完成 - 找到 {len(citations)} 个被引, {len(references)} 个参考",
                results_data={
                    "literature_id": literature_id,
                    "citation_count": len(citations),
                    "reference_count": len(references)
                }
            )
        
        return CitationResponse(
            literature_id=literature_id,
            title=literature.title,
            citations=citations,
            references=references,
            citation_count=len(citations),
            reference_count=len(references),
            citation_graph=citation_graph,
            last_updated=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"查询文献引用失败: {e}")
        if task_id:
            await stream_progress_service.update_stage_progress(
                task_id, "interaction", -1,
                f"引用查询失败: {str(e)}",
                status="failed"
            )
        raise HTTPException(status_code=500, detail=f"查询引用失败: {str(e)}")

@router.get("/literature/{literature_id}/quick-stats")
async def get_literature_quick_stats(
    literature_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取文献的快速统计信息（不查询外部API）"""
    
    literature = db.query(Literature).filter(Literature.id == literature_id).first()
    if not literature:
        raise HTTPException(status_code=404, detail="文献不存在")
    
    return {
        "id": literature.id,
        "title": literature.title,
        "authors": literature.authors,
        "journal": literature.journal,
        "year": literature.publication_date.year if literature.publication_date else None,
        "doi": literature.doi,
        "abstract": literature.abstract[:500] + "..." if len(literature.abstract or "") > 500 else literature.abstract,
        "keywords": literature.keywords,
        "quality_score": literature.quality_score,
        "pdf_available": bool(literature.pdf_path),
        "citation_count": literature.citation_count,  # 来自数据库的缓存值
        "has_detailed_citations": False,  # 表示需要懒加载
        "segments_count": len(literature.segments) if literature.segments else 0
    }

@router.post("/task/{task_id}/literature-batch-stats")
async def get_literature_batch_stats(
    task_id: str,
    literature_ids: List[int],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """批量获取文献统计信息"""
    
    literature_list = db.query(Literature).filter(
        Literature.id.in_(literature_ids)
    ).all()
    
    results = []
    for lit in literature_list:
        results.append({
            "id": lit.id,
            "title": lit.title,
            "authors": lit.authors[:3] if lit.authors else [],  # 只显示前3个作者
            "journal": lit.journal,
            "year": lit.publication_date.year if lit.publication_date else None,
            "quality_score": lit.quality_score,
            "citation_count": lit.citation_count,
            "has_pdf": bool(lit.pdf_path),
            "segments_count": len(lit.segments) if lit.segments else 0,
            "structured": any(seg.structured_data for seg in lit.segments) if lit.segments else False
        })
    
    # 更新任务进度
    await stream_progress_service.update_stage_progress(
        task_id, "collection", 100,
        f"文献元数据加载完成 - {len(results)} 篇文献",
        results_data={"literature_list": results},
        status="stage_completed"
    )
    
    return {
        "task_id": task_id,
        "literature_count": len(results),
        "literature_list": results,
        "next_stage": "structuring"
    }