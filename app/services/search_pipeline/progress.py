"""Helpers for reporting search-build pipeline progress."""

from typing import Dict, Optional, Callable, Awaitable

from .models import ProcessingStage

_STEP_STAGE_MAP = {
    "初始化": ProcessingStage.INITIALIZATION,
    "搜索": ProcessingStage.SEARCH,
    "筛选": ProcessingStage.AI_FILTERING,
    "去重": ProcessingStage.AI_FILTERING,
    "下载PDF": ProcessingStage.PDF_DOWNLOAD,
    "提取文献内容": ProcessingStage.CONTENT_EXTRACTION,
    "结构化": ProcessingStage.STRUCTURE_PROCESSING,
    "入库": ProcessingStage.DATABASE_INGESTION,
    "清理": ProcessingStage.CLEANUP,
    "完成": ProcessingStage.COMPLETED,
}


def infer_stage(step_name: str) -> ProcessingStage:
    """Infer pipeline stage from human-readable step name."""
    for key, stage in _STEP_STAGE_MAP.items():
        if key in step_name:
            return stage
    return ProcessingStage.INITIALIZATION


async def emit_progress(
    callback: Optional[Callable[[str, int, Dict], Awaitable[None]]],
    step_name: str,
    progress: int,
    details: Optional[Dict] = None,
) -> None:
    """Emit progress update with inferred stage metadata."""
    if not callback:
        return

    payload = details.copy() if details else {}
    payload.setdefault("stage", infer_stage(step_name).value)

    await callback(step_name, progress, payload)
