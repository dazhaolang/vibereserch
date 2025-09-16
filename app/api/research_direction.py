"""
研究方向确定API路由
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
import json

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.research_direction_service import ResearchDirectionService
from app.services.file_upload_service import FileUploadService

router = APIRouter(prefix="/research-direction", tags=["research-direction"])


@router.post("/interactive")
async def determine_research_direction_interactive(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """交互式确定研究方向"""
    try:
        service = ResearchDirectionService(db)
        
        initial_input = request_data.get("initial_input")
        conversation_history = request_data.get("conversation_history", [])
        
        result = await service.determine_research_direction_interactive(
            user=current_user,
            initial_input=initial_input,
            conversation_history=conversation_history
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file-analysis")
async def analyze_file_for_research_direction(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """基于文件分析研究方向"""
    try:
        service = ResearchDirectionService(db)
        
        # 读取文件内容
        file_content = await file.read()
        
        result = await service.determine_research_direction_from_file(
            user=current_user,
            file_content=file_content,
            filename=file.filename or "uploaded_file"
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discipline-menu")
async def get_discipline_menu_suggestions(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取学科分类菜单建议"""
    try:
        service = ResearchDirectionService(db)
        
        selected_path = request_data.get("selected_path", [])
        
        result = await service.get_discipline_menu_suggestions(
            user=current_user,
            selected_path=selected_path
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finalize-menu")
async def finalize_from_menu_selection(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """基于菜单选择最终确定"""
    try:
        service = ResearchDirectionService(db)
        
        selected_option = request_data.get("selected_option")
        
        # 构建研究数据
        research_data = {
            "research_direction": selected_option.get("name", ""),
            "keywords": selected_option.get("keywords", []),
            "research_categories": selected_option.get("path", []),
            "source": "menu_selection"
        }
        
        result = await service.finalize_research_direction(
            user=current_user,
            research_data=research_data,
            source_type="menu"
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finalize")
async def finalize_research_direction(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """最终确定研究方向"""
    try:
        service = ResearchDirectionService(db)
        
        research_data = request_data.get("research_data")
        source_type = request_data.get("source_type", "interactive")
        
        result = await service.finalize_research_direction(
            user=current_user,
            research_data=research_data,
            source_type=source_type
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions")
async def get_research_direction_suggestions(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取研究方向建议"""
    try:
        keywords = request_data.get("keywords", [])
        research_field = request_data.get("research_field")
        
        # 这里可以基于关键词和领域生成建议
        # 简化实现
        suggestions = {
            "success": True,
            "suggestions": [
                {
                    "direction": f"基于{', '.join(keywords[:2])}的研究",
                    "confidence": 0.8,
                    "keywords": keywords,
                    "description": f"针对{research_field or '相关领域'}的深入研究"
                }
            ]
        }
        
        return suggestions
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_research_direction(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """验证研究方向"""
    try:
        research_direction = request_data.get("research_direction")
        
        # 简化验证逻辑
        validation_result = {
            "success": True,
            "valid": True,
            "validation_score": 8.5,
            "suggestions": [
                "研究方向明确具体",
                "关键词选择恰当",
                "具有良好的研究价值"
            ],
            "warnings": []
        }
        
        return validation_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))