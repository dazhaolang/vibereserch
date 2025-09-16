"""
简化的研究发现API - 用户导向的单一接口
替代复杂的多步骤API，提供统一的研究体验
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import asyncio
from datetime import datetime
from loguru import logger

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.project import Project
from app.models.task import Task
from app.models.literature import Literature
from app.services.research_ai_service import research_ai_service
from app.services.research_rabbit_client import ResearchRabbitClient
from app.services.stream_progress_service import StreamProgressService

router = APIRouter()

class ResearchDiscoveryRequest(BaseModel):
    project_id: int
    query: str
    max_results: int = 50
    quality_filter: str = "high"  # high, medium, all
    time_range: str = "all"  # recent, all

class ResearchDiscoveryResponse(BaseModel):
    success: bool
    task_id: int
    message: str
    estimated_duration: int  # 秒

@router.post("/research-discovery", response_model=ResearchDiscoveryResponse)
async def start_research_discovery(
    request: ResearchDiscoveryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    启动智能研究发现 - 一体化流程
    自动完成: 搜索 → 筛选 → 分析 → 洞察生成
    """
    
    # 验证项目权限
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")
    
    # 创建任务记录
    task = Task(
        project_id=request.project_id,
        task_type="research_discovery",
        title=f"研究发现: {request.query}",
        description=f"智能搜索和分析相关研究",
        config={
            "query": request.query,
            "max_results": request.max_results,
            "quality_filter": request.quality_filter,
            "time_range": request.time_range,
            "workflow": "integrated"  # 标记为一体化流程
        },
        status="pending",
        estimated_duration=300  # 5分钟预估
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # 启动一体化研究发现任务
    from app.tasks.celery_tasks import research_discovery_celery
    task_result = research_discovery_celery.delay(
        task.id,
        request.query,
        request.max_results,
        request.quality_filter,
        request.time_range
    )
    
    return ResearchDiscoveryResponse(
        success=True,
        task_id=task.id,
        message=f"研究发现已启动: {request.query}",
        estimated_duration=300
    )

async def integrated_research_discovery_workflow(
    task_id: int,
    query: str,
    max_results: int,
    quality_filter: str,
    time_range: str
) -> Dict:
    """
    集成的研究发现工作流 - 简化用户体验
    """
    db = SessionLocal()
    progress_service = StreamProgressService()
    
    try:
        # 获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError("任务不存在")
        
        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            raise ValueError("项目不存在")
        
        # 阶段1: 搜索阶段 (0-40%)
        task.status = "running"
        task.started_at = datetime.utcnow()
        task.current_step = "🔍 正在搜索相关研究..."
        task.progress_percentage = 5
        db.commit()
        
        await progress_service.broadcast_task_update(task_id, {
            "type": "progress_event",
            "stage": "searching",
            "progress": 5,
            "message": "正在搜索相关研究...",
            "discoveries": []
        })
        
        # 使用Research Rabbit搜索文献
        papers_found = []
        async with ResearchRabbitClient() as client:
            papers = await client.search_all_papers(query, max_results)
            
            # 进度更新: 搜索完成
            await progress_service.broadcast_task_update(task_id, {
                "type": "progress_event",
                "stage": "searching", 
                "progress": 25,
                "message": f"发现 {len(papers)} 篇相关论文",
                "discoveries": [{
                    "type": "paper",
                    "title": "文献搜索",
                    "description": f"从学术数据库中找到 {len(papers)} 篇相关研究论文",
                    "confidence": 0.9,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            })
            
            # 阶段2: 智能筛选和质量评估 (25-60%)
            task.current_step = "🧠 正在分析论文质量..."
            task.progress_percentage = 30
            db.commit()
            
            high_quality_papers = []
            quality_discoveries = []
            
            for i, paper in enumerate(papers):
                try:
                    # 使用统一AI服务评估质量
                    quality_result = await research_ai_service.evaluate_literature_quality(
                        title=paper.get("title", ""),
                        abstract=paper.get("abstract", ""),
                        authors=paper.get("authors", []),
                        journal=paper.get("journal", {}).get("name", ""),
                        year=paper.get("year")
                    )
                    
                    if quality_result.get("success") and quality_result.get("overall_score", 0) > 0.6:
                        high_quality_papers.append({
                            **paper,
                            "ai_quality_score": quality_result.get("overall_score"),
                            "relevance_score": quality_result.get("relevance_score"),
                            "key_contributions": quality_result.get("key_contributions", [])
                        })
                        
                        # 记录高质量发现
                        if quality_result.get("overall_score", 0) > 0.8:
                            quality_discoveries.append({
                                "type": "insight",
                                "title": f"高质量研究发现",
                                "description": f"发现高影响力论文: {paper.get('title', '')[:100]}",
                                "confidence": quality_result.get("overall_score"),
                                "timestamp": datetime.utcnow().isoformat()
                            })
                    
                    # 更新进度
                    if (i + 1) % 5 == 0:
                        progress = 30 + int((i + 1) / len(papers) * 30)
                        await progress_service.broadcast_task_update(task_id, {
                            "type": "progress_event",
                            "stage": "analyzing",
                            "progress": progress,
                            "message": f"已分析 {i + 1}/{len(papers)} 篇论文",
                            "discoveries": quality_discoveries[-3:] if quality_discoveries else []
                        })
                        
                except Exception as e:
                    logger.warning(f"质量评估失败 {i}: {e}")
                    continue
            
            # 阶段3: 生成研究洞察 (60-90%)
            task.current_step = "✨ 正在生成研究洞察..."
            task.progress_percentage = 65
            db.commit()
            
            # 准备文献内容用于洞察生成
            literature_contents = []
            for paper in high_quality_papers[:10]:  # 选择前10篇高质量论文
                literature_contents.append({
                    "title": paper.get("title", ""),
                    "content": paper.get("abstract", ""),
                    "quality_score": paper.get("ai_quality_score", 0),
                    "contributions": paper.get("key_contributions", [])
                })
            
            # 生成研究洞察
            insights_result = await research_ai_service.generate_research_insights(
                query=query,
                literature_contents=literature_contents,
                focus_areas=None
            )
            
            insights_discoveries = []
            if insights_result.get("success"):
                # 转换洞察为发现格式
                for finding in insights_result.get("key_findings", [])[:3]:
                    insights_discoveries.append({
                        "type": "insight",
                        "title": finding.get("finding", "研究发现"),
                        "description": finding.get("evidence", "")[:200],
                        "confidence": finding.get("confidence", 0.8),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                for gap in insights_result.get("research_gaps", [])[:2]:
                    insights_discoveries.append({
                        "type": "opportunity", 
                        "title": "研究机会",
                        "description": gap.get("gap", "") + " - " + gap.get("opportunity", ""),
                        "confidence": gap.get("feasibility", 0.7),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            await progress_service.broadcast_task_update(task_id, {
                "type": "progress_event",
                "stage": "insights",
                "progress": 85,
                "message": f"生成了 {len(insights_discoveries)} 个研究洞察",
                "discoveries": insights_discoveries
            })
            
            # 阶段4: 完成 (90-100%)
            task.status = "completed"
            task.current_step = "研究发现完成"
            task.progress_percentage = 100
            task.completed_at = datetime.utcnow()
            task.actual_duration = int((task.completed_at - task.started_at).total_seconds())
            task.result = {
                "success": True,
                "total_papers_found": len(papers),
                "high_quality_papers": len(high_quality_papers),
                "insights_generated": len(insights_result.get("key_findings", [])),
                "research_gaps": len(insights_result.get("research_gaps", [])),
                "recommendations": insights_result.get("recommendations", []),
                "query": query
            }
            db.commit()
            
            # 发送完成消息
            all_discoveries = quality_discoveries + insights_discoveries
            await progress_service.broadcast_task_update(task_id, {
                "type": "progress_event", 
                "stage": "complete",
                "progress": 100,
                "message": f"研究发现完成！找到 {len(high_quality_papers)} 篇高质量论文，生成 {len(all_discoveries)} 个研究发现",
                "discoveries": all_discoveries,
                "final_results": task.result
            })
            
            return {"success": True, "discoveries": all_discoveries}
            
    except Exception as e:
        logger.error(f"研究发现工作流失败: {e}")
        
        # 更新任务状态为失败
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = datetime.utcnow()
        db.commit()
        
        await progress_service.broadcast_task_update(task_id, {
            "type": "progress_event",
            "stage": "failed",
            "progress": 0,
            "message": f"研究发现失败: {str(e)}",
            "error": str(e)
        })
        
        return {"success": False, "error": str(e)}
    
    finally:
        db.close()

# 简化的文献处理状态API
@router.get("/research-discovery/{task_id}/status")
async def get_research_discovery_status(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取研究发现任务状态"""
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.task_type == "research_discovery"
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 验证项目权限
    project = db.query(Project).filter(
        Project.id == task.project_id,
        Project.owner_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=403, detail="无权限访问此任务")
    
    return {
        "task_id": task_id,
        "status": task.status,
        "progress": task.progress_percentage,
        "current_step": task.current_step,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "result": task.result,
        "error": task.error_message
    }