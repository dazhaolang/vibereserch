"""
高性能中间件模块
包含限流、熔断、监控等中间件实现
"""

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.base import BaseHTTPMiddleware
import time
import asyncio
import json
import hashlib
from collections import defaultdict, deque
from typing import Dict, Optional, Callable
import redis
from prometheus_client import Counter, Histogram, Gauge
import logging

# 配置日志
logger = logging.getLogger(__name__)

# Prometheus 指标
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Number of active connections')
RATE_LIMIT_EXCEEDED = Counter('rate_limit_exceeded_total', 'Rate limit exceeded count', ['endpoint'])

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件
    支持基于IP和用户的限流
    """
    
    def __init__(
        self, 
        app: FastAPI, 
        calls: int = 1000, 
        period: int = 60,
        redis_url: str = "redis://redis:6379/3"
    ):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # 不同端点的限流配置
        self.endpoint_limits = {
            "/api/upload": {"calls": 10, "period": 60},
            "/api/analysis": {"calls": 50, "period": 60},
            "/api/search": {"calls": 200, "period": 60},
        }
    
    async def dispatch(self, request: Request, call_next):
        # 获取客户端标识
        client_id = self._get_client_id(request)
        endpoint = request.url.path
        
        # 获取该端点的限流配置
        limit_config = self.endpoint_limits.get(endpoint, {
            "calls": self.calls, 
            "period": self.period
        })
        
        # 检查限流
        if not await self._check_rate_limit(client_id, endpoint, limit_config):
            RATE_LIMIT_EXCEEDED.labels(endpoint=endpoint).inc()
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": limit_config["calls"],
                    "period": limit_config["period"],
                    "retry_after": limit_config["period"]
                }
            )
        
        response = await call_next(request)
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """获取客户端唯一标识"""
        # 优先使用用户ID（如果已认证）
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # 否则使用IP地址
        client_ip = request.headers.get("X-Forwarded-For", request.client.host)
        return f"ip:{client_ip}"
    
    async def _check_rate_limit(self, client_id: str, endpoint: str, config: dict) -> bool:
        """检查是否超出限流"""
        key = f"rate_limit:{client_id}:{endpoint}"
        
        try:
            # 使用 Redis 的 INCR 和 EXPIRE 实现滑动窗口
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, config["period"])
            results = pipe.execute()
            
            current_calls = results[0]
            return current_calls <= config["calls"]
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # 如果 Redis 不可用，允许请求通过
            return True

class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    熔断器中间件
    防止级联故障
    """
    
    def __init__(
        self, 
        app: FastAPI, 
        failure_threshold: int = 10, 
        timeout: int = 60,
        success_threshold: int = 3
    ):
        super().__init__(app)
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        
        # 每个端点的熔断状态
        self.circuit_states: Dict[str, dict] = defaultdict(lambda: {
            "state": "CLOSED",  # CLOSED, OPEN, HALF_OPEN
            "failure_count": 0,
            "success_count": 0,
            "last_failure_time": 0,
            "next_attempt": 0
        })
    
    async def dispatch(self, request: Request, call_next):
        endpoint = request.url.path
        circuit = self.circuit_states[endpoint]
        current_time = time.time()
        
        # 检查熔断状态
        if circuit["state"] == "OPEN":
            if current_time < circuit["next_attempt"]:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Service temporarily unavailable (Circuit Open)",
                        "retry_after": int(circuit["next_attempt"] - current_time)
                    }
                )
            else:
                circuit["state"] = "HALF_OPEN"
                circuit["success_count"] = 0
        
        try:
            # 记录请求开始时间
            start_time = time.time()
            response = await call_next(request)
            duration = time.time() - start_time
            
            # 检查响应是否成功
            is_success = response.status_code < 500 and duration < 30  # 30秒超时
            
            if is_success:
                await self._record_success(endpoint, circuit)
            else:
                await self._record_failure(endpoint, circuit, current_time)
            
            return response
            
        except Exception as e:
            await self._record_failure(endpoint, circuit, current_time)
            raise e
    
    async def _record_success(self, endpoint: str, circuit: dict):
        """记录成功请求"""
        if circuit["state"] == "HALF_OPEN":
            circuit["success_count"] += 1
            if circuit["success_count"] >= self.success_threshold:
                circuit["state"] = "CLOSED"
                circuit["failure_count"] = 0
        elif circuit["state"] == "CLOSED":
            circuit["failure_count"] = max(0, circuit["failure_count"] - 1)
    
    async def _record_failure(self, endpoint: str, circuit: dict, current_time: float):
        """记录失败请求"""
        circuit["failure_count"] += 1
        circuit["last_failure_time"] = current_time
        
        if circuit["failure_count"] >= self.failure_threshold:
            circuit["state"] = "OPEN"
            circuit["next_attempt"] = current_time + self.timeout

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    性能监控中间件
    收集请求指标和性能数据
    """
    
    def __init__(self, app: FastAPI):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # 增加活跃连接数
        ACTIVE_CONNECTIONS.inc()
        
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            
            # 记录成功请求
            REQUEST_COUNT.labels(
                method=method, 
                endpoint=path, 
                status=status_code
            ).inc()
            
            return response
            
        except Exception as e:
            # 记录异常请求
            REQUEST_COUNT.labels(
                method=method, 
                endpoint=path, 
                status="500"
            ).inc()
            raise e
            
        finally:
            # 记录请求时长
            duration = time.time() - start_time
            REQUEST_DURATION.observe(duration)
            
            # 减少活跃连接数
            ACTIVE_CONNECTIONS.dec()
            
            # 记录慢查询
            if duration > 1.0:  # 超过1秒的请求
                logger.warning(
                    f"Slow request: {method} {path} took {duration:.2f}s",
                    extra={
                        "method": method,
                        "path": path,
                        "duration": duration,
                        "type": "slow_request"
                    }
                )

class CacheMiddleware(BaseHTTPMiddleware):
    """
    HTTP 缓存中间件
    为GET请求提供缓存支持
    """
    
    def __init__(
        self, 
        app: FastAPI, 
        redis_url: str = "redis://redis:6379/4",
        default_ttl: int = 300
    ):
        super().__init__(app)
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = default_ttl
        
        # 可缓存的端点配置
        self.cacheable_endpoints = {
            "/api/literature": 600,    # 10分钟
            "/api/projects": 300,      # 5分钟
            "/api/analysis": 1800,     # 30分钟
        }
    
    async def dispatch(self, request: Request, call_next):
        # 只缓存 GET 请求
        if request.method != "GET":
            return await call_next(request)
        
        path = request.url.path
        
        # 检查是否为可缓存端点
        if not any(path.startswith(endpoint) for endpoint in self.cacheable_endpoints):
            return await call_next(request)
        
        # 生成缓存键
        cache_key = self._generate_cache_key(request)
        
        # 尝试从缓存获取
        try:
            cached_response = self.redis_client.get(cache_key)
            if cached_response:
                data = json.loads(cached_response)
                return Response(
                    content=data["content"],
                    status_code=data["status_code"],
                    headers=data["headers"],
                    media_type=data["media_type"]
                )
        except Exception as e:
            logger.error(f"Cache read error: {e}")
        
        # 执行请求
        response = await call_next(request)
        
        # 缓存响应（仅缓存成功响应）
        if response.status_code == 200:
            await self._cache_response(cache_key, response, path)
        
        return response
    
    def _generate_cache_key(self, request: Request) -> str:
        """生成缓存键"""
        # 包含路径、查询参数和用户ID（如果有）
        path = request.url.path
        query_params = str(request.query_params)
        user_id = getattr(request.state, 'user_id', 'anonymous')
        
        key_data = f"{path}:{query_params}:{user_id}"
        return f"http_cache:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    async def _cache_response(self, cache_key: str, response: Response, path: str):
        """缓存响应"""
        try:
            # 读取响应内容
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # 获取TTL
            ttl = self.default_ttl
            for endpoint, endpoint_ttl in self.cacheable_endpoints.items():
                if path.startswith(endpoint):
                    ttl = endpoint_ttl
                    break
            
            # 构造缓存数据
            cache_data = {
                "content": body.decode('utf-8'),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type
            }
            
            # 存储到Redis
            self.redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(cache_data)
            )
            
            # 重新创建响应体迭代器
            response.body_iterator = self._create_body_iterator(body)
            
        except Exception as e:
            logger.error(f"Cache write error: {e}")
    
    def _create_body_iterator(self, body: bytes):
        """创建响应体迭代器"""
        async def generate():
            yield body
        return generate()

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件
    记录详细的请求和响应信息
    """
    
    def __init__(self, app: FastAPI, log_body: bool = False):
        super().__init__(app)
        self.log_body = log_body
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 记录请求信息
        request_info = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "client": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": start_time
        }
        
        # 缓存请求体以避免消耗流
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                # 检查是否已经缓存了请求体
                if not hasattr(request.state, "cached_body"):
                    body = await request.body()
                    request.state.cached_body = body
                    
                    # 重写 body() 方法以返回缓存的内容
                    original_body = request.body
                    async def cached_body():
                        return request.state.cached_body
                    request.body = cached_body
                
                if request.state.cached_body:
                    request_info["body_size"] = len(request.state.cached_body)
            except Exception:
                pass
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # 记录响应信息
            response_info = {
                **request_info,
                "status_code": response.status_code,
                "duration": duration,
                "response_headers": dict(response.headers)
            }
            
            # 根据状态码选择日志级别
            if response.status_code >= 500:
                logger.error("Server error", extra=response_info)
            elif response.status_code >= 400:
                logger.warning("Client error", extra=response_info)
            else:
                logger.info("Request completed", extra=response_info)
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            error_info = {
                **request_info,
                "error": str(e),
                "duration": duration,
                "exception_type": type(e).__name__
            }
            
            logger.error("Request failed", extra=error_info)
            raise e

def setup_middleware(app: FastAPI, config: dict = None):
    """
    设置所有中间件
    """
    if config is None:
        config = {}
    
    # 请求日志中间件（最外层）
    app.add_middleware(
        RequestLoggingMiddleware,
        log_body=config.get("log_request_body", False)
    )
    
    # 性能监控中间件
    app.add_middleware(PerformanceMonitoringMiddleware)
    
    # 缓存中间件
    if config.get("enable_cache", True):
        app.add_middleware(
            CacheMiddleware,
            redis_url=config.get("cache_redis_url", "redis://redis:6379/4"),
            default_ttl=config.get("cache_default_ttl", 300)
        )
    
    # 熔断器中间件
    if config.get("enable_circuit_breaker", True):
        app.add_middleware(
            CircuitBreakerMiddleware,
            failure_threshold=config.get("circuit_failure_threshold", 10),
            timeout=config.get("circuit_timeout", 60)
        )
    
    # 限流中间件（最内层，最先执行）
    if config.get("enable_rate_limit", True):
        app.add_middleware(
            RateLimitMiddleware,
            calls=config.get("rate_limit_calls", 1000),
            period=config.get("rate_limit_period", 60),
            redis_url=config.get("rate_limit_redis_url", "redis://redis:6379/3")
        )