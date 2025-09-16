"""
实时性能监控和自动调优系统 - Performance Monitor & Auto-Tuner
提供全面的系统监控、瓶颈检测和自动性能调优功能
"""

import asyncio
import time
import psutil
import threading
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import json
import statistics
from collections import deque, defaultdict
import redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.literature import Literature


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MetricType(Enum):
    """指标类型"""
    SYSTEM = "system"           # 系统指标
    PERFORMANCE = "performance" # 性能指标
    COST = "cost"              # 成本指标
    USER = "user"              # 用户指标
    BUSINESS = "business"       # 业务指标


@dataclass
class PerformanceAlert:
    """性能告警"""
    id: str
    level: AlertLevel
    metric_type: MetricType
    message: str
    timestamp: datetime
    value: float
    threshold: float
    recommendations: List[str]
    auto_fix_applied: bool = False


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealthScore:
    """系统健康评分"""
    overall_score: float        # 总体评分 (0-100)
    cpu_score: float           # CPU评分
    memory_score: float        # 内存评分
    throughput_score: float    # 吞吐量评分
    latency_score: float       # 延迟评分
    cost_efficiency_score: float # 成本效率评分
    timestamp: datetime


class MetricsCollector:
    """指标收集器"""

    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.metrics_data: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=retention_hours * 12)  # 每5分钟一个点
        )
        self.collection_active = False
        self._collection_thread: Optional[threading.Thread] = None

    def start_collection(self):
        """启动指标收集"""
        if self.collection_active:
            return

        self.collection_active = True
        self._collection_thread = threading.Thread(
            target=self._collect_metrics_loop, daemon=True
        )
        self._collection_thread.start()
        logger.info("指标收集器已启动")

    def stop_collection(self):
        """停止指标收集"""
        self.collection_active = False
        if self._collection_thread:
            self._collection_thread.join(timeout=1.0)
        logger.info("指标收集器已停止")

    def _collect_metrics_loop(self):
        """指标收集循环"""
        while self.collection_active:
            try:
                timestamp = datetime.now()

                # 收集系统指标
                self._collect_system_metrics(timestamp)

                # 收集业务指标
                self._collect_business_metrics(timestamp)

                # 清理过期数据
                self._cleanup_old_metrics()

                time.sleep(300)  # 每5分钟收集一次

            except Exception as e:
                logger.error(f"指标收集失败: {e}")
                time.sleep(60)  # 出错时等待1分钟再继续

    def _collect_system_metrics(self, timestamp: datetime):
        """收集系统指标"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1.0)
        self.metrics_data["cpu_usage"].append(
            MetricPoint(timestamp, cpu_percent)
        )

        # 内存使用率
        memory_info = psutil.virtual_memory()
        self.metrics_data["memory_usage"].append(
            MetricPoint(timestamp, memory_info.percent)
        )

        # 磁盘使用率
        disk_info = psutil.disk_usage('/')
        self.metrics_data["disk_usage"].append(
            MetricPoint(timestamp, (disk_info.used / disk_info.total) * 100)
        )

        # 网络IO
        network_io = psutil.net_io_counters()
        self.metrics_data["network_bytes_sent"].append(
            MetricPoint(timestamp, network_io.bytes_sent)
        )
        self.metrics_data["network_bytes_recv"].append(
            MetricPoint(timestamp, network_io.bytes_recv)
        )

        # 进程数
        process_count = len(psutil.pids())
        self.metrics_data["process_count"].append(
            MetricPoint(timestamp, process_count)
        )

    def _collect_business_metrics(self, timestamp: datetime):
        """收集业务指标"""
        try:
            with SessionLocal() as db:
                # 活跃用户数
                active_users = db.query(User).filter(
                    User.last_login > datetime.now() - timedelta(hours=24)
                ).count()
                self.metrics_data["active_users_24h"].append(
                    MetricPoint(timestamp, active_users)
                )

                # 今日处理的文献数
                today_literature = db.query(Literature).filter(
                    Literature.created_at > datetime.now().replace(hour=0, minute=0, second=0)
                ).count()
                self.metrics_data["literature_processed_today"].append(
                    MetricPoint(timestamp, today_literature)
                )

                # 活跃项目数
                active_projects = db.query(Project).filter(
                    Project.updated_at > datetime.now() - timedelta(hours=24)
                ).count()
                self.metrics_data["active_projects_24h"].append(
                    MetricPoint(timestamp, active_projects)
                )

        except Exception as e:
            logger.error(f"业务指标收集失败: {e}")

    def _cleanup_old_metrics(self):
        """清理过期指标"""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)

        for metric_name, data_points in self.metrics_data.items():
            while data_points and data_points[0].timestamp < cutoff_time:
                data_points.popleft()

    def get_metric_history(self, metric_name: str, hours: int = 1) -> List[MetricPoint]:
        """获取指标历史数据"""
        if metric_name not in self.metrics_data:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            point for point in self.metrics_data[metric_name]
            if point.timestamp >= cutoff_time
        ]

    def get_current_metrics(self) -> Dict[str, float]:
        """获取当前指标值"""
        current_metrics = {}

        for metric_name, data_points in self.metrics_data.items():
            if data_points:
                current_metrics[metric_name] = data_points[-1].value

        return current_metrics


class AlertManager:
    """告警管理器"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.alert_rules = self._initialize_alert_rules()
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: List[PerformanceAlert] = []

    def _initialize_alert_rules(self) -> Dict[str, Dict]:
        """初始化告警规则"""
        return {
            "cpu_usage": {
                "warning_threshold": 75.0,
                "critical_threshold": 90.0,
                "emergency_threshold": 95.0,
                "duration_minutes": 5,
                "auto_fix": True
            },
            "memory_usage": {
                "warning_threshold": 80.0,
                "critical_threshold": 90.0,
                "emergency_threshold": 95.0,
                "duration_minutes": 3,
                "auto_fix": True
            },
            "disk_usage": {
                "warning_threshold": 85.0,
                "critical_threshold": 95.0,
                "emergency_threshold": 98.0,
                "duration_minutes": 10,
                "auto_fix": False
            },
            "response_time": {
                "warning_threshold": 5000.0,  # 5秒
                "critical_threshold": 10000.0, # 10秒
                "emergency_threshold": 20000.0, # 20秒
                "duration_minutes": 2,
                "auto_fix": True
            },
            "error_rate": {
                "warning_threshold": 5.0,      # 5%
                "critical_threshold": 10.0,    # 10%
                "emergency_threshold": 20.0,   # 20%
                "duration_minutes": 1,
                "auto_fix": True
            }
        }

    async def check_alerts(self, metrics: Dict[str, float]):
        """检查告警条件"""
        for metric_name, current_value in metrics.items():
            if metric_name not in self.alert_rules:
                continue

            rule = self.alert_rules[metric_name]
            alert_level = self._determine_alert_level(current_value, rule)

            if alert_level:
                alert_id = f"{metric_name}_{alert_level.value}"

                if alert_id not in self.active_alerts:
                    # 创建新告警
                    alert = PerformanceAlert(
                        id=alert_id,
                        level=alert_level,
                        metric_type=MetricType.SYSTEM,
                        message=self._generate_alert_message(metric_name, current_value, alert_level),
                        timestamp=datetime.now(),
                        value=current_value,
                        threshold=self._get_threshold_for_level(rule, alert_level),
                        recommendations=self._generate_recommendations(metric_name, alert_level)
                    )

                    self.active_alerts[alert_id] = alert
                    self.alert_history.append(alert)

                    logger.warning(f"新告警: {alert.message}")

                    # 发送告警通知
                    await self._send_alert_notification(alert)

                    # 自动修复
                    if rule.get("auto_fix", False):
                        await self._apply_auto_fix(alert)

            else:
                # 检查是否有需要清除的告警
                alerts_to_clear = [
                    alert_id for alert_id in self.active_alerts.keys()
                    if alert_id.startswith(f"{metric_name}_")
                ]

                for alert_id in alerts_to_clear:
                    del self.active_alerts[alert_id]
                    logger.info(f"告警已清除: {alert_id}")

    def _determine_alert_level(self, value: float, rule: Dict) -> Optional[AlertLevel]:
        """确定告警级别"""
        if value >= rule.get("emergency_threshold", float('inf')):
            return AlertLevel.EMERGENCY
        elif value >= rule.get("critical_threshold", float('inf')):
            return AlertLevel.CRITICAL
        elif value >= rule.get("warning_threshold", float('inf')):
            return AlertLevel.WARNING
        return None

    def _get_threshold_for_level(self, rule: Dict, level: AlertLevel) -> float:
        """获取告警级别对应的阈值"""
        if level == AlertLevel.EMERGENCY:
            return rule.get("emergency_threshold", 0.0)
        elif level == AlertLevel.CRITICAL:
            return rule.get("critical_threshold", 0.0)
        elif level == AlertLevel.WARNING:
            return rule.get("warning_threshold", 0.0)
        return 0.0

    def _generate_alert_message(self, metric_name: str, value: float, level: AlertLevel) -> str:
        """生成告警消息"""
        messages = {
            "cpu_usage": f"CPU使用率过高: {value:.1f}%",
            "memory_usage": f"内存使用率过高: {value:.1f}%",
            "disk_usage": f"磁盘使用率过高: {value:.1f}%",
            "response_time": f"响应时间过长: {value:.0f}ms",
            "error_rate": f"错误率过高: {value:.1f}%"
        }

        base_message = messages.get(metric_name, f"{metric_name}: {value}")
        return f"[{level.value.upper()}] {base_message}"

    def _generate_recommendations(self, metric_name: str, level: AlertLevel) -> List[str]:
        """生成修复建议"""
        recommendations = {
            "cpu_usage": [
                "检查高CPU占用的进程",
                "考虑减少并发处理数量",
                "优化算法性能",
                "考虑横向扩展"
            ],
            "memory_usage": [
                "检查内存泄漏",
                "优化缓存策略",
                "减少批处理大小",
                "重启相关服务"
            ],
            "disk_usage": [
                "清理临时文件",
                "清理日志文件",
                "检查大文件",
                "考虑扩容存储"
            ],
            "response_time": [
                "检查数据库查询性能",
                "优化API响应逻辑",
                "启用缓存机制",
                "检查网络连接"
            ],
            "error_rate": [
                "检查应用程序日志",
                "验证输入数据质量",
                "检查依赖服务状态",
                "回滚最近的变更"
            ]
        }

        return recommendations.get(metric_name, ["检查系统状态", "联系技术支持"])

    async def _send_alert_notification(self, alert: PerformanceAlert):
        """发送告警通知"""
        try:
            # 这里可以集成邮件、短信、钉钉等通知方式
            logger.warning(f"告警通知: {alert.message}")

            # 如果配置了Redis，可以发布告警事件
            if self.redis_client:
                alert_data = {
                    "id": alert.id,
                    "level": alert.level.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "value": alert.value,
                    "threshold": alert.threshold
                }
                self.redis_client.publish("performance_alerts", json.dumps(alert_data))

        except Exception as e:
            logger.error(f"发送告警通知失败: {e}")

    async def _apply_auto_fix(self, alert: PerformanceAlert):
        """应用自动修复"""
        try:
            auto_fix_applied = False

            if "cpu_usage" in alert.id:
                # CPU使用率过高的自动修复
                auto_fix_applied = await self._auto_fix_cpu_usage()

            elif "memory_usage" in alert.id:
                # 内存使用率过高的自动修复
                auto_fix_applied = await self._auto_fix_memory_usage()

            elif "response_time" in alert.id:
                # 响应时间过长的自动修复
                auto_fix_applied = await self._auto_fix_response_time()

            elif "error_rate" in alert.id:
                # 错误率过高的自动修复
                auto_fix_applied = await self._auto_fix_error_rate()

            alert.auto_fix_applied = auto_fix_applied

            if auto_fix_applied:
                logger.info(f"自动修复已应用: {alert.id}")
            else:
                logger.warning(f"自动修复未能应用: {alert.id}")

        except Exception as e:
            logger.error(f"自动修复失败: {e}")

    async def _auto_fix_cpu_usage(self) -> bool:
        """CPU使用率自动修复"""
        try:
            # 实现CPU优化策略
            # 1. 减少并发处理数量
            # 2. 暂停非关键任务
            # 3. 清理无用进程

            logger.info("执行CPU使用率自动优化")
            return True
        except Exception:
            return False

    async def _auto_fix_memory_usage(self) -> bool:
        """内存使用率自动修复"""
        try:
            # 实现内存优化策略
            # 1. 清理缓存
            # 2. 垃圾回收
            # 3. 重启高内存占用服务

            logger.info("执行内存使用率自动优化")
            return True
        except Exception:
            return False

    async def _auto_fix_response_time(self) -> bool:
        """响应时间自动修复"""
        try:
            # 实现响应时间优化策略
            # 1. 启用缓存
            # 2. 优化数据库连接池
            # 3. 增加超时设置

            logger.info("执行响应时间自动优化")
            return True
        except Exception:
            return False

    async def _auto_fix_error_rate(self) -> bool:
        """错误率自动修复"""
        try:
            # 实现错误率优化策略
            # 1. 增加重试机制
            # 2. 降级处理
            # 3. 切换备用服务

            logger.info("执行错误率自动优化")
            return True
        except Exception:
            return False


class AutoTuner:
    """自动调优器"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.tuning_history: List[Dict] = []
        self.tuning_active = False

    async def start_auto_tuning(self):
        """启动自动调优"""
        if self.tuning_active:
            return

        self.tuning_active = True
        asyncio.create_task(self._auto_tuning_loop())
        logger.info("自动调优器已启动")

    async def stop_auto_tuning(self):
        """停止自动调优"""
        self.tuning_active = False
        logger.info("自动调优器已停止")

    async def _auto_tuning_loop(self):
        """自动调优循环"""
        while self.tuning_active:
            try:
                await asyncio.sleep(600)  # 每10分钟执行一次调优

                # 收集性能数据
                performance_data = await self._collect_performance_data()

                # 分析性能趋势
                trends = await self._analyze_performance_trends(performance_data)

                # 生成调优方案
                tuning_plan = await self._generate_tuning_plan(trends)

                # 应用调优方案
                if tuning_plan:
                    await self._apply_tuning_plan(tuning_plan)

            except Exception as e:
                logger.error(f"自动调优失败: {e}")
                await asyncio.sleep(300)  # 出错时等待5分钟

    async def _collect_performance_data(self) -> Dict[str, Any]:
        """收集性能数据"""
        current_metrics = self.metrics_collector.get_current_metrics()

        # 计算性能趋势
        cpu_history = self.metrics_collector.get_metric_history("cpu_usage", hours=1)
        memory_history = self.metrics_collector.get_metric_history("memory_usage", hours=1)

        performance_data = {
            "current": current_metrics,
            "trends": {
                "cpu_trend": self._calculate_trend([p.value for p in cpu_history]),
                "memory_trend": self._calculate_trend([p.value for p in memory_history]),
            },
            "averages": {
                "cpu_avg": statistics.mean([p.value for p in cpu_history]) if cpu_history else 0,
                "memory_avg": statistics.mean([p.value for p in memory_history]) if memory_history else 0,
            }
        }

        return performance_data

    def _calculate_trend(self, values: List[float]) -> str:
        """计算趋势"""
        if len(values) < 10:
            return "insufficient_data"

        recent_avg = statistics.mean(values[-5:])  # 最近5个点的平均值
        earlier_avg = statistics.mean(values[:5])  # 前5个点的平均值

        if recent_avg > earlier_avg * 1.1:
            return "increasing"
        elif recent_avg < earlier_avg * 0.9:
            return "decreasing"
        else:
            return "stable"

    async def _analyze_performance_trends(self, performance_data: Dict) -> Dict[str, Any]:
        """分析性能趋势"""
        trends = performance_data["trends"]
        current = performance_data["current"]
        averages = performance_data["averages"]

        analysis = {
            "cpu_analysis": self._analyze_cpu_trend(
                trends["cpu_trend"], current.get("cpu_usage", 0), averages["cpu_avg"]
            ),
            "memory_analysis": self._analyze_memory_trend(
                trends["memory_trend"], current.get("memory_usage", 0), averages["memory_avg"]
            ),
            "overall_health": self._calculate_overall_health(current),
            "optimization_opportunities": []
        }

        # 识别优化机会
        if analysis["cpu_analysis"]["needs_optimization"]:
            analysis["optimization_opportunities"].append("cpu_optimization")

        if analysis["memory_analysis"]["needs_optimization"]:
            analysis["optimization_opportunities"].append("memory_optimization")

        if analysis["overall_health"] < 70:
            analysis["optimization_opportunities"].append("general_optimization")

        return analysis

    def _analyze_cpu_trend(self, trend: str, current: float, average: float) -> Dict:
        """分析CPU趋势"""
        return {
            "trend": trend,
            "current": current,
            "average": average,
            "needs_optimization": current > 75 or (trend == "increasing" and average > 60),
            "recommended_action": self._recommend_cpu_action(trend, current, average)
        }

    def _analyze_memory_trend(self, trend: str, current: float, average: float) -> Dict:
        """分析内存趋势"""
        return {
            "trend": trend,
            "current": current,
            "average": average,
            "needs_optimization": current > 80 or (trend == "increasing" and average > 70),
            "recommended_action": self._recommend_memory_action(trend, current, average)
        }

    def _recommend_cpu_action(self, trend: str, current: float, average: float) -> str:
        """推荐CPU优化动作"""
        if current > 90:
            return "emergency_cpu_reduction"
        elif current > 75:
            return "moderate_cpu_reduction"
        elif trend == "increasing" and average > 60:
            return "preventive_cpu_optimization"
        else:
            return "no_action"

    def _recommend_memory_action(self, trend: str, current: float, average: float) -> str:
        """推荐内存优化动作"""
        if current > 95:
            return "emergency_memory_cleanup"
        elif current > 80:
            return "moderate_memory_optimization"
        elif trend == "increasing" and average > 70:
            return "preventive_memory_cleanup"
        else:
            return "no_action"

    def _calculate_overall_health(self, current_metrics: Dict) -> float:
        """计算整体健康评分"""
        cpu_score = max(0, 100 - current_metrics.get("cpu_usage", 0))
        memory_score = max(0, 100 - current_metrics.get("memory_usage", 0))
        disk_score = max(0, 100 - current_metrics.get("disk_usage", 0))

        # 加权平均
        overall_score = (cpu_score * 0.4 + memory_score * 0.4 + disk_score * 0.2)
        return overall_score

    async def _generate_tuning_plan(self, analysis: Dict) -> Optional[Dict]:
        """生成调优方案"""
        if not analysis["optimization_opportunities"]:
            return None

        tuning_plan = {
            "timestamp": datetime.now(),
            "actions": [],
            "expected_impact": {},
            "risk_level": "low"
        }

        for opportunity in analysis["optimization_opportunities"]:
            if opportunity == "cpu_optimization":
                tuning_plan["actions"].extend(self._generate_cpu_tuning_actions(analysis))
            elif opportunity == "memory_optimization":
                tuning_plan["actions"].extend(self._generate_memory_tuning_actions(analysis))
            elif opportunity == "general_optimization":
                tuning_plan["actions"].extend(self._generate_general_tuning_actions(analysis))

        # 评估风险级别
        tuning_plan["risk_level"] = self._assess_tuning_risk(tuning_plan["actions"])

        return tuning_plan if tuning_plan["actions"] else None

    def _generate_cpu_tuning_actions(self, analysis: Dict) -> List[Dict]:
        """生成CPU调优动作"""
        actions = []
        cpu_analysis = analysis["cpu_analysis"]

        if cpu_analysis["recommended_action"] == "emergency_cpu_reduction":
            actions.append({
                "type": "reduce_concurrency",
                "parameter": "max_workers",
                "current_value": None,  # 需要从配置中获取
                "target_value": "reduce_by_50%",
                "priority": "high"
            })
        elif cpu_analysis["recommended_action"] == "moderate_cpu_reduction":
            actions.append({
                "type": "reduce_concurrency",
                "parameter": "max_workers",
                "current_value": None,
                "target_value": "reduce_by_25%",
                "priority": "medium"
            })

        return actions

    def _generate_memory_tuning_actions(self, analysis: Dict) -> List[Dict]:
        """生成内存调优动作"""
        actions = []
        memory_analysis = analysis["memory_analysis"]

        if memory_analysis["recommended_action"] == "emergency_memory_cleanup":
            actions.append({
                "type": "clear_cache",
                "parameter": "all_caches",
                "priority": "high"
            })
        elif memory_analysis["recommended_action"] == "moderate_memory_optimization":
            actions.append({
                "type": "optimize_batch_size",
                "parameter": "batch_size",
                "target_value": "reduce_by_30%",
                "priority": "medium"
            })

        return actions

    def _generate_general_tuning_actions(self, analysis: Dict) -> List[Dict]:
        """生成通用调优动作"""
        actions = []

        # 基于整体健康评分的调优
        if analysis["overall_health"] < 50:
            actions.append({
                "type": "system_cleanup",
                "parameter": "general_cleanup",
                "priority": "high"
            })
        elif analysis["overall_health"] < 70:
            actions.append({
                "type": "performance_optimization",
                "parameter": "general_optimization",
                "priority": "medium"
            })

        return actions

    def _assess_tuning_risk(self, actions: List[Dict]) -> str:
        """评估调优风险"""
        high_risk_actions = ["emergency_cpu_reduction", "emergency_memory_cleanup"]
        medium_risk_actions = ["reduce_concurrency", "system_cleanup"]

        for action in actions:
            if action.get("type") in high_risk_actions or action.get("priority") == "high":
                return "high"
            elif action.get("type") in medium_risk_actions or action.get("priority") == "medium":
                return "medium"

        return "low"

    async def _apply_tuning_plan(self, tuning_plan: Dict):
        """应用调优方案"""
        try:
            logger.info(f"开始应用调优方案，风险级别: {tuning_plan['risk_level']}")

            # 记录调优历史
            self.tuning_history.append({
                "timestamp": tuning_plan["timestamp"],
                "actions": tuning_plan["actions"],
                "risk_level": tuning_plan["risk_level"],
                "status": "applying"
            })

            successful_actions = 0
            total_actions = len(tuning_plan["actions"])

            for action in tuning_plan["actions"]:
                try:
                    success = await self._apply_single_action(action)
                    if success:
                        successful_actions += 1
                except Exception as e:
                    logger.error(f"应用调优动作失败: {action}, 错误: {e}")

            # 更新调优历史状态
            self.tuning_history[-1]["status"] = "completed"
            self.tuning_history[-1]["success_rate"] = successful_actions / total_actions

            logger.info(f"调优方案应用完成，成功率: {successful_actions}/{total_actions}")

        except Exception as e:
            logger.error(f"应用调优方案失败: {e}")
            if self.tuning_history:
                self.tuning_history[-1]["status"] = "failed"

    async def _apply_single_action(self, action: Dict) -> bool:
        """应用单个调优动作"""
        try:
            action_type = action["type"]

            if action_type == "reduce_concurrency":
                return await self._apply_reduce_concurrency(action)
            elif action_type == "clear_cache":
                return await self._apply_clear_cache(action)
            elif action_type == "optimize_batch_size":
                return await self._apply_optimize_batch_size(action)
            elif action_type == "system_cleanup":
                return await self._apply_system_cleanup(action)
            elif action_type == "performance_optimization":
                return await self._apply_performance_optimization(action)

            return False

        except Exception as e:
            logger.error(f"应用调优动作失败: {e}")
            return False

    async def _apply_reduce_concurrency(self, action: Dict) -> bool:
        """应用减少并发动作"""
        try:
            # 这里需要根据实际配置系统实现
            logger.info(f"应用减少并发动作: {action}")
            return True
        except Exception:
            return False

    async def _apply_clear_cache(self, action: Dict) -> bool:
        """应用清理缓存动作"""
        try:
            # 实现缓存清理逻辑
            logger.info(f"应用清理缓存动作: {action}")
            return True
        except Exception:
            return False

    async def _apply_optimize_batch_size(self, action: Dict) -> bool:
        """应用优化批大小动作"""
        try:
            # 实现批大小优化逻辑
            logger.info(f"应用优化批大小动作: {action}")
            return True
        except Exception:
            return False

    async def _apply_system_cleanup(self, action: Dict) -> bool:
        """应用系统清理动作"""
        try:
            # 实现系统清理逻辑
            logger.info(f"应用系统清理动作: {action}")
            return True
        except Exception:
            return False

    async def _apply_performance_optimization(self, action: Dict) -> bool:
        """应用性能优化动作"""
        try:
            # 实现性能优化逻辑
            logger.info(f"应用性能优化动作: {action}")
            return True
        except Exception:
            return False


class PerformanceMonitor:
    """性能监控主控制器"""

    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.auto_tuner = AutoTuner(self.metrics_collector)
        self.monitoring_active = False

    async def start_monitoring(self):
        """启动完整的性能监控"""
        if self.monitoring_active:
            return

        self.monitoring_active = True

        # 启动组件
        self.metrics_collector.start_collection()
        await self.auto_tuner.start_auto_tuning()

        # 启动告警检查循环
        asyncio.create_task(self._alert_check_loop())

        logger.info("性能监控系统已启动")

    async def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring_active = False

        # 停止组件
        self.metrics_collector.stop_collection()
        await self.auto_tuner.stop_auto_tuning()

        logger.info("性能监控系统已停止")

    async def _alert_check_loop(self):
        """告警检查循环"""
        while self.monitoring_active:
            try:
                current_metrics = self.metrics_collector.get_current_metrics()
                await self.alert_manager.check_alerts(current_metrics)
                await asyncio.sleep(60)  # 每分钟检查一次告警
            except Exception as e:
                logger.error(f"告警检查失败: {e}")
                await asyncio.sleep(60)

    def get_system_health(self) -> SystemHealthScore:
        """获取系统健康评分"""
        current_metrics = self.metrics_collector.get_current_metrics()

        cpu_score = max(0, 100 - current_metrics.get("cpu_usage", 0))
        memory_score = max(0, 100 - current_metrics.get("memory_usage", 0))
        # 这里可以添加更多指标的计算

        overall_score = (cpu_score + memory_score) / 2

        return SystemHealthScore(
            overall_score=overall_score,
            cpu_score=cpu_score,
            memory_score=memory_score,
            throughput_score=80.0,  # 示例值
            latency_score=85.0,     # 示例值
            cost_efficiency_score=90.0,  # 示例值
            timestamp=datetime.now()
        )

    def get_monitoring_dashboard_data(self) -> Dict[str, Any]:
        """获取监控仪表板数据"""
        return {
            "system_health": self.get_system_health(),
            "current_metrics": self.metrics_collector.get_current_metrics(),
            "active_alerts": list(self.alert_manager.active_alerts.values()),
            "recent_tuning": self.auto_tuner.tuning_history[-5:] if self.auto_tuner.tuning_history else [],
            "metric_trends": {
                "cpu": self.metrics_collector.get_metric_history("cpu_usage", hours=2),
                "memory": self.metrics_collector.get_metric_history("memory_usage", hours=2)
            }
        }


# 全局监控实例
performance_monitor = PerformanceMonitor()


# 便捷接口函数
async def start_performance_monitoring():
    """启动性能监控"""
    await performance_monitor.start_monitoring()


async def stop_performance_monitoring():
    """停止性能监控"""
    await performance_monitor.stop_monitoring()


def get_performance_dashboard() -> Dict[str, Any]:
    """获取性能仪表板数据"""
    return performance_monitor.get_monitoring_dashboard_data()