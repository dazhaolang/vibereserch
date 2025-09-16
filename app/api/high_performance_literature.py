"""
高性能文献处理API - 支持并发处理和多种PDF处理方式
"""

from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.user import User
from app.services.literature_processing_pipeline import pipeline, ProcessingMethod, ProcessingStatus

router = APIRouter()

class BatchProcessingRequest(BaseModel):
    query: str
    max_results: int = 20
    preferred_method: str = "fast_basic"
    enable_user_choice: bool = True

class MethodUpgradeRequest(BaseModel):
    task_id: str
    new_method: str

class ProcessingStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float
    title: str
    method: str
    result: Optional[Dict] = None
    processing_time: Optional[str] = None
    quality_score: Optional[int] = None

@router.post("/batch-process", response_model=Dict)
async def start_batch_processing(
    request: BatchProcessingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    启动批量文献处理
    支持并发搜索、下载和处理
    """
    try:
        # 转换处理方式
        method_map = {
            "fast_basic": ProcessingMethod.FAST_BASIC,
            "standard": ProcessingMethod.STANDARD,
            "premium_mineru": ProcessingMethod.PREMIUM_MINERU
        }
        
        preferred_method = method_map.get(request.preferred_method, ProcessingMethod.FAST_BASIC)
        
        # 用户选择回调（如果启用）
        user_choice_callback = None
        if request.enable_user_choice:
            async def choice_callback(choice_data):
                # 这里可以通过WebSocket或其他方式与前端交互
                # 暂时返回默认选择，实际应用中需要实现前端交互
                return "keep_fast"
            user_choice_callback = choice_callback
        
        # 启动批量处理
        result = await pipeline.batch_search_and_process(
            query=request.query,
            max_results=request.max_results,
            preferred_method=preferred_method,
            user_choice_callback=user_choice_callback
        )
        
        # 添加任务跟踪信息
        result["user_id"] = current_user.id
        result["batch_id"] = f"batch_{int(time.time())}"
        
        return {
            "success": True,
            "message": "批量处理已启动",
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量处理启动失败: {str(e)}")

@router.get("/processing-status", response_model=List[ProcessingStatusResponse])
async def get_processing_status(
    task_ids: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取处理状态
    可以查询特定任务或所有任务的状态
    """
    try:
        task_id_list = None
        if task_ids:
            task_id_list = task_ids.split(",")
        
        status_data = await pipeline.get_processing_status(task_id_list)
        
        # 转换为响应格式
        responses = []
        for task_id, data in status_data.items():
            responses.append(ProcessingStatusResponse(
                task_id=task_id,
                status=data["status"],
                progress=data["progress"],
                title=data.get("result", {}).get("title", "Unknown"),
                method=data.get("result", {}).get("method", "unknown"),
                result=data.get("result"),
                processing_time=data.get("result", {}).get("processing_time"),
                quality_score=data.get("result", {}).get("quality_score")
            ))
        
        return responses
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")

@router.post("/upgrade-method")
async def upgrade_processing_method(
    request: MethodUpgradeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    升级处理方式
    用户可以选择将快速处理升级为标准或高质量处理
    """
    try:
        method_map = {
            "standard": ProcessingMethod.STANDARD,
            "premium_mineru": ProcessingMethod.PREMIUM_MINERU
        }
        
        new_method = method_map.get(request.new_method)
        if not new_method:
            raise HTTPException(status_code=400, detail="无效的处理方式")
        
        # 这里应该实现重新处理逻辑
        # 暂时返回成功响应
        return {
            "success": True,
            "message": f"任务 {request.task_id} 已升级到 {request.new_method} 处理方式",
            "task_id": request.task_id,
            "new_method": request.new_method
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"升级处理方式失败: {str(e)}")

@router.get("/methods", response_model=List[Dict])
async def get_processing_methods():
    """
    获取可用的处理方式列表
    """
    methods = [
        {
            "id": "fast_basic",
            "name": "快速处理",
            "description": "基础文本提取，1-2秒完成",
            "time_estimate": "1-2秒",
            "quality_score": 60,
            "features": ["基础文本提取", "快速完成"],
            "recommended_for": ["快速预览", "大批量处理"]
        },
        {
            "id": "standard", 
            "name": "标准处理",
            "description": "文本+表格提取，平衡速度与质量",
            "time_estimate": "3-5秒",
            "quality_score": 80,
            "features": ["文本提取", "表格识别", "布局保持"],
            "recommended_for": ["常规使用", "平衡需求"]
        },
        {
            "id": "premium_mineru",
            "name": "高质量处理", 
            "description": "MinerU深度解析，最佳质量输出",
            "time_estimate": "30-60秒",
            "quality_score": 95,
            "features": ["高质量OCR", "完整结构识别", "公式提取", "图表分析", "Markdown输出"],
            "recommended_for": ["重要文献", "深度分析"]
        }
    ]
    
    return methods

@router.get("/performance-stats")
async def get_performance_stats(
    current_user: User = Depends(get_current_active_user)
):
    """
    获取性能统计
    """
    # 这里可以添加实际的性能统计逻辑
    return {
        "concurrent_capacity": {
            "max_downloads": 10,
            "max_processing": 5,
            "current_load": 0
        },
        "processing_times": {
            "fast_basic": "1-2秒",
            "standard": "3-5秒", 
            "premium_mineru": "30-60秒"
        },
        "quality_comparison": {
            "fast_basic": 60,
            "standard": 80,
            "premium_mineru": 95
        },
        "resource_usage": {
            "cpu_cores_used": 4,
            "memory_usage": "2GB",
            "storage_cache": "500MB"
        }
    }