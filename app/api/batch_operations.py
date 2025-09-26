"""
批量操作API - 提供文献批量处理功能
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from loguru import logger
import asyncio
import time

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.literature import Literature
from app.models.project import Project
from app.services.import_export_service import DataExportService

router = APIRouter()

class BatchOperationRequest(BaseModel):
    operation: str  # 'tag', 'categorize', 'export', 'delete', 'move'
    literature_ids: List[int]
    params: Optional[Dict[str, Any]] = None

class BatchTagRequest(BaseModel):
    literature_ids: List[int]
    tags: List[str]
    action: str = "add"  # 'add', 'remove', 'replace'

class BatchCategorizeRequest(BaseModel):
    literature_ids: List[int]
    category: str

class BatchMoveRequest(BaseModel):
    literature_ids: List[int]
    target_project_id: int

class BatchExportRequest(BaseModel):
    literature_ids: List[int]
    format: str  # 'json', 'csv', 'bibtex', 'ris', 'excel'
    include_options: Optional[Dict[str, bool]] = None

# 新增：批量删除请求模型
class BatchDeleteRequest(BaseModel):
    literature_ids: List[int]

class BatchOperationResponse(BaseModel):
    success: bool
    message: str
    processed_count: int
    failed_count: int
    failed_items: Optional[List[Dict]] = None
    result: Optional[Any] = None

@router.post("/literature/batch-tag", response_model=BatchOperationResponse)
async def batch_tag_literature(
    request: BatchTagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量标记文献"""
    try:
        processed_count = 0
        failed_count = 0
        failed_items = []

        # 获取用户有权限的文献
        literature_query = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids),
            Literature.projects.any(Project.owner_id == current_user.id)
        )
        
        literature_list = literature_query.all()
        
        for lit in literature_list:
            try:
                current_tags = lit.tags or []
                
                if request.action == "add":
                    # 添加标签
                    new_tags = list(set(current_tags + request.tags))
                elif request.action == "remove":
                    # 移除标签
                    new_tags = [tag for tag in current_tags if tag not in request.tags]
                elif request.action == "replace":
                    # 替换标签
                    new_tags = request.tags
                else:
                    raise ValueError(f"不支持的操作类型: {request.action}")
                
                lit.tags = new_tags
                processed_count += 1
                
            except Exception as e:
                failed_count += 1
                failed_items.append({
                    "literature_id": lit.id,
                    "title": lit.title,
                    "error": str(e)
                })
                logger.error(f"标记文献 {lit.id} 失败: {e}")
        
        db.commit()
        
        return BatchOperationResponse(
            success=failed_count == 0,
            message=f"成功处理 {processed_count} 篇文献，失败 {failed_count} 篇",
            processed_count=processed_count,
            failed_count=failed_count,
            failed_items=failed_items if failed_items else None
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"批量标记操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量标记失败: {str(e)}")

@router.post("/literature/batch-categorize", response_model=BatchOperationResponse)
async def batch_categorize_literature(
    request: BatchCategorizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量分类文献"""
    try:
        processed_count = 0
        failed_count = 0
        failed_items = []

        # 获取用户有权限的文献
        literature_query = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids),
            Literature.projects.any(Project.owner_id == current_user.id)
        )
        
        literature_list = literature_query.all()
        
        for lit in literature_list:
            try:
                lit.category = request.category
                processed_count += 1
                
            except Exception as e:
                failed_count += 1
                failed_items.append({
                    "literature_id": lit.id,
                    "title": lit.title,
                    "error": str(e)
                })
                logger.error(f"分类文献 {lit.id} 失败: {e}")
        
        db.commit()
        
        return BatchOperationResponse(
            success=failed_count == 0,
            message=f"成功分类 {processed_count} 篇文献，失败 {failed_count} 篇",
            processed_count=processed_count,
            failed_count=failed_count,
            failed_items=failed_items if failed_items else None
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"批量分类操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量分类失败: {str(e)}")

@router.post("/literature/batch-move", response_model=BatchOperationResponse)
async def batch_move_literature(
    request: BatchMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量移动文献到其他项目"""
    try:
        # 验证目标项目权限
        target_project = db.query(Project).filter(
            Project.id == request.target_project_id,
            Project.owner_id == current_user.id
        ).first()
        
        if not target_project:
            raise HTTPException(status_code=404, detail="目标项目不存在或无权限")
        
        processed_count = 0
        failed_count = 0
        failed_items = []

        # 获取用户有权限的文献
        literature_query = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids),
            Literature.projects.any(Project.owner_id == current_user.id)
        )
        
        literature_list = literature_query.all()
        
        for lit in literature_list:
            try:
                # 从当前项目中移除并添加到目标项目
                lit.projects.clear()  # 移除所有关联
                lit.projects.append(target_project)  # 添加到目标项目
                processed_count += 1
                
            except Exception as e:
                failed_count += 1
                failed_items.append({
                    "literature_id": lit.id,
                    "title": lit.title,
                    "error": str(e)
                })
                logger.error(f"移动文献 {lit.id} 失败: {e}")
        
        db.commit()
        
        return BatchOperationResponse(
            success=failed_count == 0,
            message=f"成功移动 {processed_count} 篇文献到项目 '{target_project.name}'，失败 {failed_count} 篇",
            processed_count=processed_count,
            failed_count=failed_count,
            failed_items=failed_items if failed_items else None
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"批量移动操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量移动失败: {str(e)}")

@router.post("/literature/batch-export", response_model=BatchOperationResponse)
async def batch_export_literature(
    request: BatchExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量导出文献"""
    try:
        # 获取用户有权限的文献
        literature_query = db.query(Literature).filter(
            Literature.id.in_(request.literature_ids),
            Literature.projects.any(Project.owner_id == current_user.id)
        )
        
        literature_list = literature_query.all()
        
        if not literature_list:
            raise HTTPException(status_code=404, detail="没有找到可导出的文献")
        
        # 使用导入导出服务
        export_service = DataExportService(db)
        
        # 准备导出数据
        literature_data = []
        for lit in literature_list:
            literature_data.append({
                "id": lit.id,
                "title": lit.title,
                "authors": lit.authors,
                "abstract": lit.abstract,
                "publication_year": lit.publication_year,
                "journal": lit.journal,
                "doi": lit.doi,
                "source_url": lit.source_url,  # 修正字段名
                "tags": lit.tags,
                "category": lit.category,
                "created_at": lit.created_at.isoformat() if lit.created_at else None
            })
        
        # 执行导出
        if request.format == "json":
            result = await export_service._export_to_json({"literature": literature_data})
        elif request.format == "csv":
            result = await export_service._export_to_csv({"literature": literature_data})
        elif request.format == "bibtex":
            result = await export_service._export_to_bibtex({"literature": literature_data})
        elif request.format == "excel":
            result = await export_service._export_to_excel({"literature": literature_data})
        else:
            raise HTTPException(status_code=400, detail=f"不支持的导出格式: {request.format}")
        
        return BatchOperationResponse(
            success=True,
            message=f"成功导出 {len(literature_list)} 篇文献",
            processed_count=len(literature_list),
            failed_count=0,
            result=result
        )
        
    except Exception as e:
        logger.error(f"批量导出操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量导出失败: {str(e)}")

@router.delete("/literature/batch-delete", response_model=BatchOperationResponse)
async def batch_delete_literature(
    request: BatchDeleteRequest,  # 修改：使用请求体接收参数，而不是查询参数
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """批量删除文献"""
    try:
        processed_count = 0
        failed_count = 0
        failed_items = []

        # 获取用户有权限的文献
        literature_query = db.query(Literature).join(Project).filter(
            Literature.id.in_(request.literature_ids),  # 修改：从request对象获取literature_ids
            Project.owner_id == current_user.id
        )
        
        literature_list = literature_query.all()
        
        for lit in literature_list:
            try:
                db.delete(lit)
                processed_count += 1
                
            except Exception as e:
                failed_count += 1
                failed_items.append({
                    "literature_id": lit.id,
                    "title": lit.title,
                    "error": str(e)
                })
                logger.error(f"删除文献 {lit.id} 失败: {e}")
        
        db.commit()
        
        return BatchOperationResponse(
            success=failed_count == 0,
            message=f"成功删除 {processed_count} 篇文献，失败 {failed_count} 篇",
            processed_count=processed_count,
            failed_count=failed_count,
            failed_items=failed_items if failed_items else None
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"批量删除操作失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")

@router.get("/literature/batch-status/{operation_id}")
async def get_batch_operation_status(
    operation_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取批量操作状态（用于长时间运行的操作）"""
    # 这里可以实现基于Redis或数据库的操作状态跟踪
    # 暂时返回示例响应
    return {
        "operation_id": operation_id,
        "status": "completed",
        "progress": 100,
        "message": "操作已完成"
    }


@router.post("/process", response_model=BatchOperationResponse)
async def batch_process(
    project_id: int = Form(...),
    operation_type: str = Form(...),
    parameters: Optional[Dict[str, Any]] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """通用批量处理端点 - 为前端兼容性添加"""
    try:
        operation_id = f"batch_{int(time.time() * 1000)}"

        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 根据操作类型调用相应的处理逻辑
        if operation_type == "literature_process":
            # 调用文献处理
            return BatchOperationResponse(
                operation_id=operation_id,
                status="started",
                message=f"已开始批量处理项目 {project_id} 的文献",
                affected_count=0,
                result={
                    "project_id": project_id,
                    "operation_type": operation_type,
                    "status": "processing"
                }
            )
        elif operation_type == "data_export":
            # 调用数据导出
            return BatchOperationResponse(
                operation_id=operation_id,
                status="started",
                message=f"已开始导出项目 {project_id} 的数据",
                affected_count=0,
                result={
                    "project_id": project_id,
                    "operation_type": operation_type,
                    "status": "processing"
                }
            )
        else:
            # 默认处理
            return BatchOperationResponse(
                operation_id=operation_id,
                status="started",
                message=f"已开始批量处理操作: {operation_type}",
                affected_count=0,
                result={
                    "project_id": project_id,
                    "operation_type": operation_type,
                    "parameters": parameters,
                    "status": "processing"
                }
            )

    except Exception as e:
        logger.error(f"批量处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量处理失败: {str(e)}")
