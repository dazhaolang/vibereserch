"""
限流器工具
提供基于令牌桶算法的限流功能
"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
from loguru import logger

@dataclass
class RateLimitConfig:
    requests_per_minute: int
    burst_size: Optional[int] = None
    
    def __post_init__(self):
        if self.burst_size is None:
            self.burst_size = max(1, self.requests_per_minute // 10)

class RateLimiter:
    """基于令牌桶算法的限流器"""
    
    def __init__(self, requests_per_minute: int, burst_size: Optional[int] = None):
        self.config = RateLimitConfig(requests_per_minute, burst_size)
        self.tokens = float(self.config.burst_size)
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self, tokens_needed: int = 1) -> bool:
        """获取令牌"""
        async with self.lock:
            now = time.time()
            
            # 计算应该添加的令牌数
            time_passed = now - self.last_update
            tokens_to_add = time_passed * (self.config.requests_per_minute / 60.0)
            
            # 更新令牌桶
            self.tokens = min(
                self.config.burst_size, 
                self.tokens + tokens_to_add
            )
            self.last_update = now
            
            # 检查是否有足够的令牌
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True
            else:
                return False
    
    async def wait_for_token(self, tokens_needed: int = 1, timeout: float = 60.0) -> bool:
        """等待令牌可用"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await self.acquire(tokens_needed):
                return True
            
            # 计算等待时间
            wait_time = min(1.0, 60.0 / self.config.requests_per_minute)
            await asyncio.sleep(wait_time)
        
        return False
    
    def get_status(self) -> Dict[str, float]:
        """获取限流器状态"""
        return {
            'available_tokens': self.tokens,
            'max_tokens': self.config.burst_size,
            'refill_rate': self.config.requests_per_minute / 60.0,
            'last_update': self.last_update
        }

class MultiServiceRateLimiter:
    """多服务限流管理器"""
    
    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {}
        self.default_configs = {
            'openai': RateLimitConfig(60, 10),
            'semantic_scholar': RateLimitConfig(100, 20),
            'google_scholar': RateLimitConfig(60, 10),
            'pubmed': RateLimitConfig(120, 20),
            'arxiv': RateLimitConfig(180, 30),
            'crossref': RateLimitConfig(50, 10)
        }
    
    def get_limiter(self, service_name: str) -> RateLimiter:
        """获取或创建服务限流器"""
        if service_name not in self.limiters:
            config = self.default_configs.get(service_name, RateLimitConfig(60, 10))
            self.limiters[service_name] = RateLimiter(
                config.requests_per_minute, 
                config.burst_size
            )
        
        return self.limiters[service_name]
    
    async def acquire_for_service(self, service_name: str, tokens_needed: int = 1) -> bool:
        """为特定服务获取令牌"""
        limiter = self.get_limiter(service_name)
        return await limiter.acquire(tokens_needed)
    
    async def wait_for_service(self, service_name: str, tokens_needed: int = 1, timeout: float = 60.0) -> bool:
        """等待特定服务的令牌"""
        limiter = self.get_limiter(service_name)
        return await limiter.wait_for_token(tokens_needed, timeout)
    
    def get_all_status(self) -> Dict[str, Dict[str, float]]:
        """获取所有限流器状态"""
        return {
            service_name: limiter.get_status()
            for service_name, limiter in self.limiters.items()
        }

# 全局多服务限流器
global_rate_limiter = MultiServiceRateLimiter()