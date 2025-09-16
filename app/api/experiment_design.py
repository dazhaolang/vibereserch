"""
实验设计API路由
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.project import Project
from app.services.experiment_design_service import ExperimentDesignService

router = APIRouter(prefix="/experiment-design", tags=["experiment-design"])


@router.post("/projects/{project_id}/design")
async def design_experiment_scheme(
    project_id: int,
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """设计实验方案"""
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或无权访问")
        
        service = ExperimentDesignService(db)
        
        research_question = request_data.get("research_question")
        experiment_type = request_data.get("experiment_type", "材料制备")
        use_main_experience = request_data.get("use_main_experience", True)
        
        result = await service.design_experiment_scheme(
            project=project,
            research_question=research_question,
            experiment_type=experiment_type,
            use_main_experience=use_main_experience
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/parameter-optimization")
async def optimize_experiment_parameters(
    project_id: int,
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """优化实验参数"""
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或无权访问")
        
        service = ExperimentDesignService(db)
        
        base_scheme = request_data.get("base_scheme")
        optimization_objectives = request_data.get("optimization_objectives", [])
        constraints = request_data.get("constraints", {})
        
        result = await service.optimize_experiment_parameters(
            project=project,
            base_scheme=base_scheme,
            optimization_objectives=optimization_objectives,
            constraints=constraints
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/protocol")
async def generate_experimental_protocol(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """生成实验操作规程"""
    try:
        service = ExperimentDesignService(db)
        
        experiment_scheme = request_data.get("experiment_scheme")
        detail_level = request_data.get("detail_level", "detailed")
        
        result = await service.generate_experimental_protocol(
            experiment_scheme=experiment_scheme,
            detail_level=detail_level
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def get_experiment_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取实验模板"""
    try:
        # 返回实验模板配置
        templates = {
            "材料制备": {
                "name": "材料制备实验模板",
                "description": "用于材料合成和制备的实验模板",
                "sections": ["实验目标", "原料与设备", "实验步骤", "工艺参数", "表征方法", "风险控制"]
            },
            "性能测试": {
                "name": "性能测试实验模板",
                "description": "用于材料性能评估的实验模板",
                "sections": ["测试目标", "样品准备", "测试方法", "数据分析"]
            },
            "机理研究": {
                "name": "机理研究实验模板",
                "description": "用于机理验证和理论研究的实验模板",
                "sections": ["研究目标", "实验设计", "检测手段", "理论分析"]
            }
        }
        
        return {
            "success": True,
            "templates": templates
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_experiment_scheme(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出实验方案"""
    try:
        scheme = request_data.get("scheme")
        format_type = request_data.get("format", "pdf")
        
        # 这里应该实现实际的导出逻辑
        # 目前返回模拟结果
        return {
            "success": True,
            "export_url": f"/downloads/experiment_scheme_{current_user.id}.{format_type}",
            "format": format_type,
            "generated_at": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/share")
async def share_experiment_scheme(
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分享实验方案"""
    try:
        scheme = request_data.get("scheme")
        share_options = request_data.get("share_options", {})
        
        # 这里应该实现实际的分享逻辑
        # 目前返回模拟结果
        return {
            "success": True,
            "share_id": f"share_{current_user.id}_{int(datetime.now().timestamp())}",
            "share_url": "https://platform.example.com/shared/experiment_scheme",
            "expires_at": "2024-02-01T00:00:00Z"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/schemes")
async def save_experiment_scheme(
    project_id: int,
    request_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """保存实验方案"""
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或无权访问")
        
        scheme = request_data.get("scheme")
        scheme_name = request_data.get("scheme_name")
        
        # 这里应该实现实际的保存逻辑
        # 目前返回模拟结果
        return {
            "success": True,
            "scheme_id": f"scheme_{project_id}_{current_user.id}",
            "scheme_name": scheme_name,
            "saved_at": "2024-01-01T00:00:00Z"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/schemes")
async def get_project_experiment_schemes(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目的实验方案列表"""
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或无权访问")
        
        # 这里应该实现实际的查询逻辑
        # 目前返回模拟结果
        return {
            "success": True,
            "schemes": [
                {
                    "id": f"scheme_{project_id}_1",
                    "name": "默认实验方案",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z"
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))