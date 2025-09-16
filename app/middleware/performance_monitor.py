"""
性能监控中间件
提供API响应时间、错误率、业务指标监控
"""

import time
import asyncio
from typing import Dict, Optional, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import psutil
import threading

from app.core.database import redis_client

class PerformanceMetrics:
    """性能指标收集器"""
    
    def __init__(self):
        # 内存中的指标缓存（最近1小时）
        self.response_times = defaultdict(lambda: deque(maxlen=1000))
        self.error_counts = defaultdict(int)
        self.request_counts = defaultdict(int)
        self.status_codes = defaultdict(lambda: defaultdict(int))
        
        # 业务指标
        self.business_metrics = {
            'literature_processed': 0,
            'ai_requests': 0,
            'user_sessions': 0,
            'projects_created': 0,
            'exports_completed': 0
        }
        
        # 系统资源指标
        self.system_metrics = {}
        
        # 启动系统监控线程
        self._start_system_monitor()
    
    def _start_system_monitor(self):
        """启动系统资源监控线程"""
        def monitor_system():
            while True:
                try:
                    self.system_metrics = {
                        'cpu_percent': psutil.cpu_percent(interval=1),
                        'memory_percent': psutil.virtual_memory().percent,
                        'disk_usage': psutil.disk_usage('/').percent,
                        'network_io': dict(psutil.net_io_counters()._asdict()),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    
                    # 存储到Redis（保留24小时）
                    redis_key = f"system_metrics:{int(time.time())}"
                    redis_client.setex(
                        redis_key, 
                        86400,  # 24小时
                        json.dumps(self.system_metrics)
                    )
                    
                except Exception as e:
                    logger.error(f"系统监控错误: {e}")
                
                time.sleep(30)  # 每30秒收集一次
        
        thread = threading.Thread(target=monitor_system, daemon=True)
        thread.start()
    
    def record_request(self, method: str, path: str, status_code: int, response_time: float):
        """记录请求指标"""
        endpoint = f"{method} {path}"
        
        # 记录响应时间
        self.response_times[endpoint].append(response_time)
        
        # 记录请求数
        self.request_counts[endpoint] += 1
        
        # 记录状态码
        self.status_codes[endpoint][status_code] += 1
        
        # 记录错误
        if status_code >= 400:
            self.error_counts[endpoint] += 1
        
        # 存储到Redis
        self._store_to_redis(endpoint, status_code, response_time)
    
    def _store_to_redis(self, endpoint: str, status_code: int, response_time: float):
        """存储指标到Redis"""
        try:
            timestamp = int(time.time())
            metrics_data = {
                'endpoint': endpoint,
                'status_code': status_code,
                'response_time': response_time,
                'timestamp': timestamp
            }
            
            # 使用时间序列存储
            redis_key = f"api_metrics:{timestamp}"
            redis_client.setex(redis_key, 3600, json.dumps(metrics_data))  # 1小时过期
            
            # 更新汇总统计
            daily_key = f"daily_stats:{datetime.now().strftime('%Y-%m-%d')}"
            redis_client.hincrby(daily_key, 'total_requests', 1)
            if status_code >= 400:
                redis_client.hincrby(daily_key, 'error_requests', 1)
            redis_client.expire(daily_key, 86400 * 7)  # 保留7天
            
        except Exception as e:
            logger.error(f"存储指标到Redis失败: {e}")
    
    def record_business_metric(self, metric_name: str, value: int = 1):
        """记录业务指标"""
        if metric_name in self.business_metrics:
            self.business_metrics[metric_name] += value
            
            # 存储到Redis
            try:
                daily_key = f"business_metrics:{datetime.now().strftime('%Y-%m-%d')}"
                redis_client.hincrby(daily_key, metric_name, value)
                redis_client.expire(daily_key, 86400 * 30)  # 保留30天
            except Exception as e:
                logger.error(f"存储业务指标失败: {e}")
    
    def get_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """获取端点统计信息"""
        response_times = list(self.response_times[endpoint])
        
        if not response_times:
            return {
                'request_count': 0,
                'error_count': 0,
                'error_rate': 0,
                'avg_response_time': 0,
                'p95_response_time': 0,
                'p99_response_time': 0
            }
        
        response_times.sort()
        total_requests = self.request_counts[endpoint]
        error_count = self.error_counts[endpoint]
        
        return {
            'request_count': total_requests,
            'error_count': error_count,
            'error_rate': (error_count / total_requests * 100) if total_requests > 0 else 0,
            'avg_response_time': sum(response_times) / len(response_times),
            'p95_response_time': response_times[int(len(response_times) * 0.95)] if response_times else 0,
            'p99_response_time': response_times[int(len(response_times) * 0.99)] if response_times else 0,
            'status_codes': dict(self.status_codes[endpoint])
        }
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """获取整体统计信息"""
        all_endpoints = set(self.request_counts.keys())
        total_requests = sum(self.request_counts.values())
        total_errors = sum(self.error_counts.values())
        
        all_response_times = []
        for times in self.response_times.values():
            all_response_times.extend(times)
        
        if all_response_times:
            all_response_times.sort()
            avg_response_time = sum(all_response_times) / len(all_response_times)
            p95_response_time = all_response_times[int(len(all_response_times) * 0.95)]
            p99_response_time = all_response_times[int(len(all_response_times) * 0.99)]
        else:
            avg_response_time = p95_response_time = p99_response_time = 0
        
        return {
            'total_endpoints': len(all_endpoints),
            'total_requests': total_requests,
            'total_errors': total_errors,
            'error_rate': (total_errors / total_requests * 100) if total_requests > 0 else 0,
            'avg_response_time': avg_response_time,
            'p95_response_time': p95_response_time,
            'p99_response_time': p99_response_time,
            'business_metrics': self.business_metrics.copy(),
            'system_metrics': self.system_metrics.copy()
        }

# 全局指标收集器
metrics_collector = PerformanceMetrics()

class PerformanceMonitorMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ['/health', '/metrics', '/docs', '/openapi.json']
    
    async def dispatch(self, request: Request, call_next):
        # 跳过监控的路径
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        start_time = time.time()
        
        # 记录请求开始
        request_id = id(request)
        logger.debug(f"请求开始: {request.method} {request.url.path} [{request_id}]")
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算响应时间
            response_time = (time.time() - start_time) * 1000  # 毫秒
            
            # 记录指标
            metrics_collector.record_request(
                request.method,
                request.url.path,
                response.status_code,
                response_time
            )
            
            # 添加性能头部
            response.headers["X-Response-Time"] = f"{response_time:.2f}ms"
            response.headers["X-Request-ID"] = str(request_id)
            
            # 记录请求完成
            logger.debug(f"请求完成: {request.method} {request.url.path} [{request_id}] - {response.status_code} ({response_time:.2f}ms)")
            
            return response
            
        except Exception as e:
            # 记录异常
            response_time = (time.time() - start_time) * 1000
            metrics_collector.record_request(
                request.method,
                request.url.path,
                500,
                response_time
            )
            
            logger.error(f"请求异常: {request.method} {request.url.path} [{request_id}] - {str(e)}")
            raise

class PerformanceAnalyzer:
    """性能分析器"""
    
    @staticmethod
    async def get_slow_endpoints(threshold_ms: float = 1000, limit: int = 10) -> list:
        """获取慢端点列表"""
        slow_endpoints = []
        
        for endpoint in metrics_collector.request_counts.keys():
            stats = metrics_collector.get_endpoint_stats(endpoint)
            if stats['avg_response_time'] > threshold_ms:
                slow_endpoints.append({
                    'endpoint': endpoint,
                    'avg_response_time': stats['avg_response_time'],
                    'request_count': stats['request_count'],
                    'error_rate': stats['error_rate']
                })
        
        # 按平均响应时间排序
        slow_endpoints.sort(key=lambda x: x['avg_response_time'], reverse=True)
        return slow_endpoints[:limit]
    
    @staticmethod
    async def get_error_endpoints(min_error_rate: float = 5.0, limit: int = 10) -> list:
        """获取高错误率端点列表"""
        error_endpoints = []
        
        for endpoint in metrics_collector.request_counts.keys():
            stats = metrics_collector.get_endpoint_stats(endpoint)
            if stats['error_rate'] > min_error_rate and stats['request_count'] >= 10:
                error_endpoints.append({
                    'endpoint': endpoint,
                    'error_rate': stats['error_rate'],
                    'error_count': stats['error_count'],
                    'request_count': stats['request_count']
                })
        
        # 按错误率排序
        error_endpoints.sort(key=lambda x: x['error_rate'], reverse=True)
        return error_endpoints[:limit]
    
    @staticmethod
    async def get_performance_report() -> Dict[str, Any]:
        """获取性能报告"""
        overall_stats = metrics_collector.get_overall_stats()
        slow_endpoints = await PerformanceAnalyzer.get_slow_endpoints()
        error_endpoints = await PerformanceAnalyzer.get_error_endpoints()
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_stats': overall_stats,
            'slow_endpoints': slow_endpoints,
            'error_endpoints': error_endpoints,
            'recommendations': PerformanceAnalyzer._generate_recommendations(
                overall_stats, slow_endpoints, error_endpoints
            )
        }
    
    @staticmethod
    def _generate_recommendations(overall_stats: dict, slow_endpoints: list, error_endpoints: list) -> list:
        """生成性能优化建议"""
        recommendations = []
        
        # 整体性能建议
        if overall_stats['avg_response_time'] > 1000:
            recommendations.append({
                'type': 'performance',
                'priority': 'high',
                'message': f"整体平均响应时间过高 ({overall_stats['avg_response_time']:.2f}ms)，建议优化数据库查询和API调用"
            })
        
        if overall_stats['error_rate'] > 5:
            recommendations.append({
                'type': 'reliability',
                'priority': 'high',
                'message': f"整体错误率过高 ({overall_stats['error_rate']:.2f}%)，需要排查错误原因"
            })
        
        # 系统资源建议
        system_metrics = overall_stats.get('system_metrics', {})
        if system_metrics.get('cpu_percent', 0) > 80:
            recommendations.append({
                'type': 'resource',
                'priority': 'medium',
                'message': f"CPU使用率过高 ({system_metrics['cpu_percent']:.1f}%)，建议优化计算密集型操作"
            })
        
        if system_metrics.get('memory_percent', 0) > 80:
            recommendations.append({
                'type': 'resource',
                'priority': 'medium',
                'message': f"内存使用率过高 ({system_metrics['memory_percent']:.1f}%)，建议优化内存使用"
            })
        
        # 慢端点建议
        for endpoint in slow_endpoints[:3]:
            recommendations.append({
                'type': 'optimization',
                'priority': 'medium',
                'message': f"端点 {endpoint['endpoint']} 响应时间过慢 ({endpoint['avg_response_time']:.2f}ms)"
            })
        
        # 错误端点建议
        for endpoint in error_endpoints[:3]:
            recommendations.append({
                'type': 'bug_fix',
                'priority': 'high',
                'message': f"端点 {endpoint['endpoint']} 错误率过高 ({endpoint['error_rate']:.2f}%)"
            })
        
        return recommendations

# 性能分析器实例
performance_analyzer = PerformanceAnalyzer()