"""MCP tool interface endpoints"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.mcp_schemas import MCPInvokeRequest, MCPInvokeResponse, MCPToolListResponse
from app.services.mcp_tool_registry import mcp_tool_registry
from app.services.task_service import TaskService

router = APIRouter()


@router.get("/tools", response_model=MCPToolListResponse)
async def list_mcp_tools():
    tools = mcp_tool_registry.list_tools()
    public_tools = [
        {
            "name": meta["name"],
            "description": meta["description"],
            "input_schema": meta["input_schema"],
        }
        for meta in tools.values()
    ]
    return MCPToolListResponse(tools=public_tools)


def _dispatch_tool(tool_name: str, payload: Dict[str, Any], db: Session, user: User) -> Dict[str, Any]:
    service = TaskService(db)
    if tool_name == "collect_literature":
        project_id = payload.get("project_id")
        if not project_id:
            raise ValueError("project_id is required")
        keywords = payload.get("keywords") or []
        max_count = payload.get("max_count", 100)
        sources = payload.get("sources") or []
        search_mode = payload.get("search_mode", "standard")
        if search_mode == "ai_batch":
            query = payload.get("query")
            if not query:
                raise ValueError("query is required for ai_batch mode")
            task = service.create_ai_search_task(
                owner_id=user.id,
                project_id=project_id,
                query=query,
                max_results=max_count,
            )
        else:
            task = service.create_literature_collection_task(
                owner_id=user.id,
                project_id=project_id,
                keywords=keywords,
                max_count=max_count,
                sources=sources,
            )
        return {"task_id": task.id}
    if tool_name == "process_literature":
        project_id = payload.get("project_id")
        if not project_id:
            raise ValueError("project_id is required")
        keywords = payload.get("keywords") or []
        config = payload.get("config") or {}
        task = service.create_search_build_task(
            owner_id=user.id,
            project_id=project_id,
            keywords=keywords,
            config=config,
        )
        return {"task_id": task.id}
    if tool_name == "generate_experience":
        project_id = payload.get("project_id")
        if not project_id:
            raise ValueError("project_id is required")
        research_question = payload.get("research_question") or "通用研究问题"
        task = service.create_experience_task(
            owner_id=user.id,
            project_id=project_id,
            research_question=research_question,
            processing_method=payload.get("processing_method", "standard"),
        )
        return {"task_id": task.id}
    if tool_name == "task_statistics":
        stats = service.get_task_statistics(
            owner_id=user.id,
            project_id=payload.get("project_id"),
            limit_recent=payload.get("limit_recent", 5),
        )
        return {
            "total_tasks": stats["total_tasks"],
            "status_breakdown": stats["status_breakdown"],
            "running_task_ids": stats["running_task_ids"],
            "cost_summary": stats["cost_summary"],
            "recent_tasks": [
                {
                    "id": task.id,
                    "type": task.task_type,
                    "status": task.status,
                    "progress": task.progress_percentage,
                    "title": task.title,
                    "cost_estimate": task.cost_estimate or 0.0,
                    "token_usage": task.token_usage or 0.0,
                }
                for task in stats["recent_tasks"]
            ],
        }
    raise ValueError(f"Unknown tool: {tool_name}")


@router.post("/run", response_model=MCPInvokeResponse)
async def run_mcp_tool(
    request: MCPInvokeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.tool not in mcp_tool_registry.list_tools():
        raise HTTPException(status_code=404, detail="Tool not found")
    try:
        result = _dispatch_tool(request.tool, request.parameters or {}, db, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MCPInvokeResponse(success=True, result=result)
