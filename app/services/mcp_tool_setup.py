"""Register MCP tools with the global registry."""

from typing import Any, Dict

from loguru import logger

from app.core.database import SessionLocal
from app.services.mcp_tool_registry import mcp_tool_registry
from app.services.task_orchestrator import TaskOrchestrator
from app.services.task_service import TaskService


def _require_field(payload: Dict[str, Any], key: str) -> Any:
    if key not in payload or payload[key] is None:
        raise ValueError(f"缺少必要参数: {key}")
    return payload[key]


def _task_to_payload(task) -> Dict[str, Any]:
    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "title": task.title,
        "status": task.status,
        "project_id": task.project_id,
        "progress": task.progress_percentage,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def _with_session(handler):
    def wrapper(payload: Dict[str, Any]) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            return handler(db, payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("MCP工具执行失败: %s", handler.__name__)
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    return wrapper


@_with_session
def _handle_collect_literature(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = int(_require_field(payload, "project_id"))
    owner_id = int(_require_field(payload, "user_id"))

    keywords = payload.get("keywords") or []
    max_count = int(payload.get("max_count") or 50)
    sources = payload.get("sources") or []
    search_mode = (payload.get("search_mode") or "standard").lower()
    query = payload.get("query")
    extra_config: Dict[str, Any] = payload.get("config") or {}

    task_service = TaskService(db)

    if search_mode == "ai_batch":
        if not query:
            raise ValueError("AI批量搜索需要提供 query 参数")
        task = task_service.create_ai_search_task(
            owner_id=owner_id,
            project_id=project_id,
            query=query,
            max_results=max_count,
        )
    else:
        if query and query not in keywords:
            keywords = [query, *keywords]
        task = task_service.create_literature_collection_task(
            owner_id=owner_id,
            project_id=project_id,
            keywords=keywords,
            max_count=max_count,
            sources=sources,
            extra_config=extra_config,
        )

    logger.info("MCP collect_literature -> task %s", task.id)
    return {"success": True, "task": _task_to_payload(task)}


@_with_session
def _handle_process_literature(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = int(_require_field(payload, "project_id"))
    owner_id = int(_require_field(payload, "user_id"))

    keywords = payload.get("keywords") or []
    config: Dict[str, Any] = payload.get("config") or {}

    orchestrator = TaskOrchestrator(db)
    task = orchestrator.trigger_search_pipeline(
        owner_id=owner_id,
        project_id=project_id,
        keywords=keywords,
        config=config,
    )

    logger.info("MCP process_literature -> task %s", task.id)
    return {"success": True, "task": _task_to_payload(task)}


@_with_session
def _handle_generate_experience(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    project_id = int(_require_field(payload, "project_id"))
    owner_id = int(_require_field(payload, "user_id"))
    research_question = payload.get("research_question") or "自动生成的研究问题"
    processing_method = payload.get("processing_method") or "standard"

    orchestrator = TaskOrchestrator(db)
    task = orchestrator.trigger_experience_task(
        owner_id=owner_id,
        project_id=project_id,
        research_question=research_question,
        processing_method=processing_method,
    )

    logger.info("MCP generate_experience -> task %s", task.id)
    return {
        "success": True,
        "task": _task_to_payload(task),
        "research_question": research_question,
        "processing_method": processing_method,
    }


@_with_session
def _handle_task_statistics(db, payload: Dict[str, Any]) -> Dict[str, Any]:
    owner_id = int(_require_field(payload, "user_id"))
    project_id = payload.get("project_id")
    limit_recent = int(payload.get("limit_recent") or 5)

    service = TaskService(db)
    stats = service.get_task_statistics(
        owner_id=owner_id,
        project_id=int(project_id) if project_id is not None else None,
        limit_recent=limit_recent,
    )

    return {"success": True, "statistics": stats}


def setup_mcp_tools() -> None:
    if mcp_tool_registry.list_tools():
        return

    mcp_tool_registry.register_tool(
        name="collect_literature",
        description="采集科研文献，可选择普通或AI批量搜索模式",
        handler=_handle_collect_literature,
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "user_id": {"type": "integer"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "max_count": {"type": "integer", "default": 100},
                "sources": {"type": "array", "items": {"type": "string"}},
                "search_mode": {"type": "string", "enum": ["standard", "ai_batch"]},
                "query": {"type": "string"},
                "config": {"type": "object"},
            },
            "required": ["project_id", "user_id"],
        },
    )

    mcp_tool_registry.register_tool(
        name="process_literature",
        description="执行搜索建库流水线（搜索→PDF→结构化→入库）",
        handler=_handle_process_literature,
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "user_id": {"type": "integer"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "config": {"type": "object"},
            },
            "required": ["project_id", "user_id"],
        },
    )

    mcp_tool_registry.register_tool(
        name="generate_experience",
        description="基于结构化文献生成研究经验书",
        handler=_handle_generate_experience,
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "user_id": {"type": "integer"},
                "research_question": {"type": "string"},
                "processing_method": {"type": "string", "enum": ["standard", "deep"]},
            },
            "required": ["project_id", "user_id"],
        },
    )

    mcp_tool_registry.register_tool(
        name="task_statistics",
        description="查询任务执行统计（总数、状态、成本等）",
        handler=_handle_task_statistics,
        input_schema={
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "user_id": {"type": "integer"},
                "limit_recent": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 5,
                },
            },
            "required": ["user_id"],
        },
    )
