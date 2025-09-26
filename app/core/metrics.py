"""
Prometheus指标收集和导出
"""

from prometheus_client import (
    CollectorRegistry, Counter, Histogram, Gauge,
    CONTENT_TYPE_LATEST, generate_latest
)
from typing import Dict, Any
import psutil
import threading
import time


class MetricsCollector:
    """Prometheus指标收集器"""

    def __init__(self):
        # 创建独立的注册器
        self.registry = CollectorRegistry(auto_describe=False)

        # API请求指标
        self.request_count = Counter(
            "api_requests_total",
            "Total API requests",
            ["method", "path", "status"],
            registry=self.registry
        )

        self.request_latency = Histogram(
            "api_request_latency_seconds",
            "API request latency in seconds",
            ["method", "path"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry
        )

        # 系统指标
        self.system_cpu = Gauge(
            "system_cpu_percent",
            "CPU usage percent",
            registry=self.registry
        )

        self.system_memory = Gauge(
            "system_memory_percent",
            "Memory usage percent",
            registry=self.registry
        )

        self.system_disk = Gauge(
            "system_disk_percent",
            "Disk usage percent",
            registry=self.registry
        )

        # 健康检查指标
        self.health_check_status = Gauge(
            "health_check_status",
            "Health check status (1=healthy, 0.5=degraded, 0=unhealthy)",
            ["component"],
            registry=self.registry
        )

        self.health_check_latency = Gauge(
            "health_check_latency_seconds",
            "Health check latency in seconds",
            ["component"],
            registry=self.registry
        )

        # 业务指标
        self.active_users = Gauge(
            "active_users_count",
            "Number of active users",
            registry=self.registry
        )

        self.literature_count = Gauge(
            "literature_total",
            "Total literature count",
            registry=self.registry
        )

        self.tasks_pending = Gauge(
            "celery_tasks_pending",
            "Number of pending Celery tasks",
            ["queue"],
            registry=self.registry
        )

        # 启动系统指标收集
        self._start_system_metrics_collection()

    def record_request(self, method: str, path: str, status_code: int, latency_seconds: float):
        """记录API请求指标"""
        self.request_count.labels(method=method, path=path, status=str(status_code)).inc()
        self.request_latency.labels(method=method, path=path).observe(latency_seconds)

    def update_health_status(self, component: str, status: str, latency_seconds: float):
        """更新健康检查状态"""
        status_value = {
            "healthy": 1.0,
            "degraded": 0.5,
            "unhealthy": 0.0
        }.get(status, 0.0)

        self.health_check_status.labels(component=component).set(status_value)
        self.health_check_latency.labels(component=component).set(latency_seconds)

    def update_business_metrics(self, metrics_data: Dict[str, Any]):
        """更新业务指标"""
        if "active_users" in metrics_data:
            self.active_users.set(metrics_data["active_users"])

        if "literature_count" in metrics_data:
            self.literature_count.set(metrics_data["literature_count"])

        if "pending_tasks" in metrics_data:
            for queue, count in metrics_data["pending_tasks"].items():
                self.tasks_pending.labels(queue=queue).set(count)

    def _start_system_metrics_collection(self):
        """启动系统指标收集线程"""
        def collect_system_metrics():
            while True:
                try:
                    # CPU使用率
                    cpu_percent = psutil.cpu_percent(interval=1)
                    self.system_cpu.set(cpu_percent)

                    # 内存使用率
                    memory = psutil.virtual_memory()
                    self.system_memory.set(memory.percent)

                    # 磁盘使用率
                    disk = psutil.disk_usage('/')
                    self.system_disk.set(disk.percent)

                except Exception as e:
                    # 忽略系统指标收集错误
                    pass

                time.sleep(15)  # 每15秒更新一次

        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()

    def generate_metrics(self) -> bytes:
        """生成Prometheus格式的指标"""
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """获取指标内容类型"""
        return CONTENT_TYPE_LATEST


# 全局指标收集器实例
metrics_collector = MetricsCollector()


class MetricsBridge:
    """指标桥接器，提供容错的指标记录接口"""

    @staticmethod
    def record_request(method: str, path: str, status_code: int, latency_seconds: float):
        """记录API请求（容错）"""
        try:
            metrics_collector.record_request(method, path, status_code, latency_seconds)
        except Exception:
            # 静默失败，不影响主业务
            pass

    @staticmethod
    def update_health_status(component: str, status: str, latency_seconds: float):
        """更新健康状态（容错）"""
        try:
            metrics_collector.update_health_status(component, status, latency_seconds)
        except Exception:
            pass

    @staticmethod
    def update_business_metrics(metrics_data: Dict[str, Any]):
        """更新业务指标（容错）"""
        try:
            metrics_collector.update_business_metrics(metrics_data)
        except Exception:
            pass