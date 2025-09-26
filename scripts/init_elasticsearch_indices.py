"""Initialise Elasticsearch indices used by the platform.

The previous codebase attempted to import this module during startup but the file
was missing, causing FastAPI to fail before serving any traffic.  This module
provides a minimal yet safe implementation that can be extended later when
additional mappings are required.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict

from loguru import logger

_SKIP_VALUES = {"0", "false", "no", "off", ""}


def _should_skip_bootstrap() -> bool:
    """Return True when index bootstrap should be skipped."""

    flag = os.getenv("SKIP_ELASTICSEARCH_BOOTSTRAP", "false").lower()
    if flag not in _SKIP_VALUES:
        return True

    # 当未配置 Elasticsearch URL 或运行在轻量模式时，也直接跳过
    from app.core.config import settings  # noqa: WPS433 (runtime import)

    lightweight = os.getenv("LIGHTWEIGHT_MODE", "false").lower() not in _SKIP_VALUES
    if lightweight:
        logger.info("LIGHTWEIGHT_MODE enabled → skip Elasticsearch bootstrap")
        return True

    if not settings.elasticsearch_url:
        logger.warning("ELASTICSEARCH_URL 未配置，跳过索引初始化")
        return True

    return False


def _literature_index_mapping() -> Dict[str, Any]:
    return {
        "dynamic": True,
        "properties": {
            "literature_id": {"type": "keyword"},
            "title": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "abstract": {"type": "text"},
            "authors": {"type": "keyword"},
            "keywords": {"type": "keyword"},
            "journal": {"type": "keyword"},
            "publication_year": {"type": "integer"},
            "doi": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "quality_score": {"type": "float"},
            "reliability_score": {"type": "float"},
            "citation_count": {"type": "integer"},
            "impact_factor": {"type": "float"},
            "source_platform": {"type": "keyword"},
            "status": {"type": "keyword"},
            "created_at": {"type": "date", "format": "date_optional_time"},
            "updated_at": {"type": "date", "format": "date_optional_time"},
        },
    }


def _literature_segments_mapping() -> Dict[str, Any]:
    return {
        "dynamic": True,
        "properties": {
            "segment_id": {"type": "keyword"},
            "literature_id": {"type": "keyword"},
            "project_ids": {"type": "keyword"},
            "segment_type": {"type": "keyword"},
            "section_title": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "content": {"type": "text"},
            "page_number": {"type": "integer"},
            "paragraph_index": {"type": "integer"},
            "created_at": {"type": "date", "format": "date_optional_time"},
        },
    }


async def create_indices() -> None:
    """Create core Elasticsearch indices if they don't exist."""

    if _should_skip_bootstrap():
        return

    try:
        from app.core.elasticsearch import get_elasticsearch  # noqa: WPS433
    except Exception as exc:  # pragma: no cover
        logger.warning("无法导入 Elasticsearch 客户端，跳过索引初始化: %s", exc)
        return

    try:
        es_client = await get_elasticsearch()
    except Exception as exc:  # pragma: no cover
        logger.warning("连接 Elasticsearch 失败，跳过索引初始化: %s", exc)
        return

    tasks = [
        es_client.create_index(
            index_name="literature_index",
            mapping=_literature_index_mapping(),
            settings_config={"number_of_shards": 1, "number_of_replicas": 0},
        ),
        es_client.create_index(
            index_name="literature_segments_index",
            mapping=_literature_segments_mapping(),
            settings_config={"number_of_shards": 1, "number_of_replicas": 0},
        ),
    ]

    try:
        await asyncio.gather(*tasks)
    except Exception as exc:  # pragma: no cover
        logger.warning("创建 Elasticsearch 索引时出现错误: %s", exc)


__all__ = ["create_indices"]
