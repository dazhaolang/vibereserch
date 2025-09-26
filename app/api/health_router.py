"""
健康检查和监控API端点
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError

from app.services.healthcheck import health_service
from app.core.metrics import metrics_collector, MetricsBridge
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.models.literature import Literature
from app.models.task import Task, TaskStatus


SERVICE_BOOT_TIME = datetime.utcnow()
_BOOT_MONOTONIC = time.perf_counter()
BUILD_COMMIT = os.getenv("BUILD_COMMIT", "unknown")
BUILD_TIMESTAMP = os.getenv("BUILD_TIMESTAMP")
BUILD_VERSION = os.getenv("BUILD_VERSION", settings.app_name)


router = APIRouter()

# 关键组件列表 - 这些组件不健康时返回503
CRITICAL_COMPONENTS = {"database", "redis", "migrations"}


def serialize_health_snapshot(snapshot) -> Dict[str, Any]:
    """序列化健康状态快照"""
    return {
        "status": snapshot.overall,
        "checked_at": snapshot.checked_at.isoformat(),
        "components": [
            {
                "name": component.name,
                "status": component.status,
                "latency_ms": round(component.latency_ms, 2),
                "details": component.details,
                "error": component.error
            }
            for component in snapshot.components
        ]
    }


def _uptime_seconds() -> float:
    return max(0.0, time.perf_counter() - _BOOT_MONOTONIC)


def _collect_business_metrics_sync() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "active_users": 0,
        "literature_count": 0,
        "pending_tasks": {"pending": 0, "running": 0},
    }

    try:
        with SessionLocal() as db:
            metrics["active_users"] = db.query(User).filter(User.is_active.is_(True)).count()
            metrics["literature_count"] = db.query(Literature).count()

            pending_count = db.query(Task).filter(Task.status == TaskStatus.PENDING.value).count()
            running_count = db.query(Task).filter(Task.status == TaskStatus.RUNNING.value).count()
            metrics["pending_tasks"] = {
                "pending": pending_count,
                "running": running_count,
            }
    except SQLAlchemyError as exc:
        # 保留基本结构，便于 Prometheus 指标更新
        metrics["error"] = str(exc)

    return metrics


async def _collect_business_metrics() -> Dict[str, Any]:
    """异步采集业务指标，避免阻塞事件循环"""
    return await asyncio.to_thread(_collect_business_metrics_sync)


def _build_info() -> Dict[str, Any]:
    timestamp = BUILD_TIMESTAMP or SERVICE_BOOT_TIME.isoformat()
    return {
        "version": BUILD_VERSION,
        "commit": BUILD_COMMIT,
        "timestamp": timestamp,
    }


@router.get("/healthz", include_in_schema=False)
async def healthz():
    """
    基础健康检查 - 快速探活
    用于负载均衡器的存活探测
    """
    snapshot = await health_service.composite_health(include_background=False)

    # 更新Prometheus指标
    for component in snapshot.components:
        MetricsBridge.update_health_status(
            component.name,
            component.status,
            component.latency_ms / 1000  # 转换为秒
        )

    return {
        "status": snapshot.overall,
        "checked_at": snapshot.checked_at.isoformat(),
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "uptime_seconds": round(_uptime_seconds(), 2),
    }


@router.get("/readyz", include_in_schema=False)
async def readyz():
    """
    就绪状态检查 - 完整的依赖检查
    用于容器编排的就绪探测
    """
    snapshot = await health_service.composite_health(include_background=True)

    # 更新Prometheus指标
    for component in snapshot.components:
        MetricsBridge.update_health_status(
            component.name,
            component.status,
            component.latency_ms / 1000
        )

    response_data = serialize_health_snapshot(snapshot)

    # 检查关键组件状态
    critical_unhealthy = [
        c for c in snapshot.components
        if c.name in CRITICAL_COMPONENTS and c.status == "unhealthy"
    ]

    if critical_unhealthy:
        # 关键组件不健康，返回503
        raise HTTPException(
            status_code=503,
            detail={
                **response_data,
                "critical_failures": [c.name for c in critical_unhealthy]
            }
        )

    return response_data


@router.get("/live", include_in_schema=False)
async def live():
    """
    存活探测 - 最简单的探活检查
    仅检查应用是否运行
    """
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/status", include_in_schema=False)
async def status():
    """
    系统状态概览 - 包含版本信息和系统概况
    """
    snapshot = await health_service.composite_health(include_background=True)

    return {
        "application": {
            "name": "VibResearch Platform",
            "version": _build_info()["version"],
            "status": snapshot.overall,
            "environment": settings.environment,
        },
        "health": serialize_health_snapshot(snapshot),
        "system": {
            "uptime_seconds": round(_uptime_seconds(), 2),
            "timestamp": datetime.utcnow().isoformat(),
        }
    }


@router.get("/info", include_in_schema=False)
async def info():
    """
    应用信息 - 静态版本和配置信息
    """
    return {
        "application": {
            "name": "VibResearch Platform",
            "version": _build_info()["version"],
            "description": "科研文献智能分析平台",
            "environment": settings.environment
        },
        "build": {
            "timestamp": _build_info()["timestamp"],
            "commit": _build_info()["commit"]
        },
        "features": [
            "literature_collection",
            "ai_analysis",
            "experience_generation",
            "intelligent_interaction",
            "real_time_collaboration"
        ]
    }


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """
    Prometheus指标端点
    返回Prometheus格式的系统指标
    """
    try:
        business_metrics = await _collect_business_metrics()
        MetricsBridge.update_business_metrics(business_metrics)

        # 生成Prometheus格式指标
        metrics_data = metrics_collector.generate_metrics()
        return Response(
            content=metrics_data,
            media_type=metrics_collector.get_content_type()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"指标生成失败: {str(e)}")


# 添加标签
router.tags = ["Monitoring"]
