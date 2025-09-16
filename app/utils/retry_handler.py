"""
API重试机制和熔断器实现
提供可靠的外部API调用能力
"""

import asyncio
import time
from typing import Any, Callable, Optional, Dict, List
from functools import wraps
from loguru import logger
import aiohttp
from enum import Enum


class RetryStrategy(Enum):
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


class CircuitBreakerState(Enum):
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态


class RetryConfig:
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions: tuple = (aiohttp.ClientError, asyncio.TimeoutError),
        retryable_status_codes: List[int] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.strategy = strategy
        self.retryable_exceptions = retryable_exceptions
        self.retryable_status_codes = retryable_status_codes or [429, 500, 502, 503, 504]


class CircuitBreakerConfig:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: tuple = (Exception,)
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception


class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0
    
    def can_execute(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker moved to HALF_OPEN state")
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        return False
    
    def record_success(self):
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:  # 连续3次成功后关闭熔断器
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker moved to CLOSED state")
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker moved back to OPEN state")
        elif (self.state == CircuitBreakerState.CLOSED and 
              self.failure_count >= self.config.failure_threshold):
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")


class RetryHandler:
    """重试处理器"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        if service_name not in self.circuit_breakers:
            config = CircuitBreakerConfig()
            self.circuit_breakers[service_name] = CircuitBreaker(config)
        return self.circuit_breakers[service_name]
    
    def calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """计算重试延迟时间"""
        if config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (2 ** (attempt - 1))
        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * attempt
        else:  # FIXED_DELAY
            delay = config.base_delay
        
        return min(delay, config.max_delay)
    
    def should_retry(self, exception: Exception, response_status: Optional[int], config: RetryConfig) -> bool:
        """判断是否应该重试"""
        # 检查异常类型
        if isinstance(exception, config.retryable_exceptions):
            return True
        
        # 检查HTTP状态码
        if response_status and response_status in config.retryable_status_codes:
            return True
        
        return False
    
    async def execute_with_retry(
        self,
        func: Callable,
        service_name: str,
        config: RetryConfig,
        *args,
        **kwargs
    ) -> Any:
        """执行带重试的函数调用"""
        circuit_breaker = self.get_circuit_breaker(service_name)
        
        if not circuit_breaker.can_execute():
            raise Exception(f"Circuit breaker is OPEN for service: {service_name}")
        
        last_exception = None
        response_status = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                logger.debug(f"Attempt {attempt}/{config.max_attempts} for {service_name}")
                result = await func(*args, **kwargs)
                circuit_breaker.record_success()
                return result
                
            except Exception as e:
                last_exception = e
                
                # 提取HTTP状态码（如果有）
                if hasattr(e, 'response') and hasattr(e.response, 'status'):
                    response_status = e.response.status
                
                # 判断是否应该重试
                if attempt < config.max_attempts and self.should_retry(e, response_status, config):
                    delay = self.calculate_delay(attempt, config)
                    logger.warning(f"Attempt {attempt} failed for {service_name}: {str(e)}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    # 不重试或达到最大重试次数
                    circuit_breaker.record_failure()
                    logger.error(f"All retry attempts failed for {service_name}: {str(e)}")
                    raise e
        
        # 这里不应该到达，但为了安全起见
        circuit_breaker.record_failure()
        raise last_exception


# 全局重试处理器实例
retry_handler = RetryHandler()


def with_retry(
    service_name: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
):
    """重试装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                strategy=strategy
            )
            return await retry_handler.execute_with_retry(
                func, service_name, config, *args, **kwargs
            )
        return wrapper
    return decorator


class APIClient:
    """增强的API客户端，包含重试和熔断机制"""
    
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @with_retry("api_client", max_attempts=3, base_delay=1.0)
    async def get(self, endpoint: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        """GET请求"""
        url = f"{self.base_url}{endpoint}"
        async with self.session.get(url, params=params, headers=headers) as response:
            if response.status >= 400:
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"HTTP {response.status}"
                )
            return await response.json()
    
    @with_retry("api_client", max_attempts=3, base_delay=1.0)
    async def post(self, endpoint: str, data: Optional[Dict] = None, json: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        """POST请求"""
        url = f"{self.base_url}{endpoint}"
        async with self.session.post(url, data=data, json=json, headers=headers) as response:
            if response.status >= 400:
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"HTTP {response.status}"
                )
            return await response.json()


# 使用示例
async def example_usage():
    """使用示例"""
    
    # 使用装饰器
    @with_retry("openai_api", max_attempts=5, base_delay=2.0)
    async def call_openai_api(prompt: str):
        # 模拟API调用
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}]},
                headers={"Authorization": "Bearer YOUR_API_KEY"}
            ) as response:
                return await response.json()
    
    # 使用API客户端
    async with APIClient("https://api.semanticscholar.org") as client:
        result = await client.get("/graph/v1/paper/search", params={"query": "machine learning"})
        return result


if __name__ == "__main__":
    # 测试代码
    asyncio.run(example_usage())