"""
健康检查服务 - 系统状态监控和就绪性验证
"""

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Literal, Optional
from sqlalchemy import text
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from loguru import logger

from app.core.database import SessionLocal, engine
from app.core.redis import redis_manager
from app.core.elasticsearch import ElasticsearchClient
from app.celery import celery_app


@dataclass
class ComponentStatus:
    """组件状态"""
    name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class HealthSnapshot:
    """健康状态快照"""
    overall: Literal["healthy", "degraded", "unhealthy"]
    checked_at: datetime
    components: List[ComponentStatus]


class HealthCheckService:
    """健康检查服务"""

    def __init__(self):
        self.es_client = ElasticsearchClient()
        self._cache: Optional[HealthSnapshot] = None
        self._cache_expires = 0
        self._cache_ttl = 30  # 缓存30秒
        self.lightweight_mode = os.getenv("LIGHTWEIGHT_MODE", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    async def check_database(self) -> ComponentStatus:
        """检查数据库连接"""
        started = time.perf_counter()
        try:
            with SessionLocal() as session:
                result = session.execute(text("SELECT 1")).scalar()
                if result == 1:
                    status = "healthy"
                    details = {"connection": "active", "query_test": "passed"}
                else:
                    status = "unhealthy"
                    details = {"connection": "active", "query_test": "failed"}
        except Exception as exc:
            status = "unhealthy"
            details = {"error": str(exc)}

        latency = (time.perf_counter() - started) * 1000
        return ComponentStatus("database", status, latency, details)

    async def check_redis(self) -> ComponentStatus:
        """检查Redis连接"""
        started = time.perf_counter()
        if self.lightweight_mode:
            return ComponentStatus(
                name="redis",
                status="healthy",
                latency_ms=0.0,
                details={"note": "轻量模式下跳过 Redis 连接"},
            )
        try:
            client = await redis_manager.get_client()
            await client.ping()
            status = "healthy"
            details = {"connection": "active", "ping": "success"}
        except Exception as exc:
            status = "unhealthy"
            details = {"error": str(exc)}

        latency = (time.perf_counter() - started) * 1000
        return ComponentStatus("redis", status, latency, details)

    async def check_elasticsearch(self) -> ComponentStatus:
        """检查Elasticsearch连接"""
        started = time.perf_counter()
        if self.lightweight_mode:
            return ComponentStatus(
                name="elasticsearch",
                status="healthy",
                latency_ms=0.0,
                details={"note": "轻量模式下跳过 Elasticsearch 连接"},
            )
        try:
            if not self.es_client.client:
                await self.es_client.connect()

            if self.es_client.client:
                await self.es_client.client.ping()
                cluster_health = await self.es_client.client.cluster.health(
                    wait_for_status="yellow", timeout="5s"
                )
                status = "healthy" if cluster_health["status"] in ["green", "yellow"] else "degraded"
                details = {
                    "connection": "active",
                    "cluster_status": cluster_health["status"],
                    "nodes": cluster_health["number_of_nodes"]
                }
            else:
                status = "unhealthy"
                details = {"error": "client not initialized"}

        except Exception as exc:
            status = "unhealthy"
            details = {"error": str(exc)}

        latency = (time.perf_counter() - started) * 1000
        return ComponentStatus("elasticsearch", status, latency, details)

    async def check_celery(self) -> ComponentStatus:
        """检查Celery工作器"""
        started = time.perf_counter()
        if self.lightweight_mode:
            return ComponentStatus(
                name="celery",
                status="healthy",
                latency_ms=0.0,
                details={"note": "轻量模式下跳过 Celery 检查"},
            )
        try:
            # 使用asyncio.to_thread来包装同步的Celery调用
            ping_result = await asyncio.to_thread(
                celery_app.control.ping, timeout=3
            )

            worker_names: List[str] = []

            if isinstance(ping_result, list):
                for item in ping_result:
                    if isinstance(item, dict):
                        worker_names.extend(item.keys())
            elif isinstance(ping_result, dict):
                worker_names.extend(ping_result.keys())

            active_workers = len(worker_names)

            if active_workers > 0:
                status = "healthy"
                details = {
                    "active_workers": active_workers,
                    "workers": worker_names,
                }
            else:
                status = "degraded" if ping_result else "unhealthy"
                details = {
                    "active_workers": 0,
                    "workers": worker_names,
                    "error": "no workers responding" if not ping_result else "unexpected ping response format",
                }

        except Exception as exc:
            status = "unhealthy"
            details = {"error": str(exc)}

        latency = (time.perf_counter() - started) * 1000
        return ComponentStatus("celery", status, latency, details)

    async def check_migrations(self) -> ComponentStatus:
        """检查数据库迁移状态"""
        started = time.perf_counter()
        try:
            config = Config("alembic.ini")
            script = ScriptDirectory.from_config(config)

            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                db_revision = context.get_current_revision()

            head_revision = script.get_current_head()

            if db_revision == head_revision:
                status = "healthy"
                pending_migrations = []
            else:
                status = "degraded"
                pending_migrations = [
                    rev.revision for rev in
                    script.iterate_revisions(head_revision, db_revision)
                ]

            details = {
                "database_revision": db_revision,
                "head_revision": head_revision,
                "pending_migrations": pending_migrations,
                "is_up_to_date": db_revision == head_revision
            }

        except Exception as exc:
            status = "unhealthy"
            details = {"error": str(exc)}

        latency = (time.perf_counter() - started) * 1000
        return ComponentStatus("migrations", status, latency, details)

    async def composite_health(self, *, include_background: bool = False) -> HealthSnapshot:
        """综合健康检查"""
        # 检查缓存
        now = time.time()
        if self._cache and now < self._cache_expires:
            return self._cache

        try:
            # 并行执行所有检查
            checks = [
                self.check_database(),
                self.check_redis(),
                self.check_migrations(),
            ]

            if include_background:
                checks.extend([
                    self.check_elasticsearch(),
                    self.check_celery(),
                ])

            results = await asyncio.gather(*checks, return_exceptions=True)

            # 处理异常结果
            components = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    component_name = ["database", "redis", "migrations", "elasticsearch", "celery"][i]
                    components.append(ComponentStatus(
                        name=component_name,
                        status="unhealthy",
                        latency_ms=0,
                        details={"error": str(result)}
                    ))
                else:
                    components.append(result)

            # 计算整体状态
            unhealthy_count = sum(1 for c in components if c.status == "unhealthy")
            degraded_count = sum(1 for c in components if c.status == "degraded")

            if unhealthy_count > 0:
                overall = "unhealthy"
            elif degraded_count > 0:
                overall = "degraded"
            else:
                overall = "healthy"

            snapshot = HealthSnapshot(
                overall=overall,
                checked_at=datetime.utcnow(),
                components=components
            )

            # 更新缓存
            self._cache = snapshot
            self._cache_expires = now + self._cache_ttl

            return snapshot

        except Exception as exc:
            logger.error(f"健康检查失败: {exc}")
            return HealthSnapshot(
                overall="unhealthy",
                checked_at=datetime.utcnow(),
                components=[ComponentStatus(
                    name="system",
                    status="unhealthy",
                    latency_ms=0,
                    details={"error": str(exc)}
                )]
            )


# 全局实例
health_service = HealthCheckService()
