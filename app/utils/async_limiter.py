"""
异步限流器 - 用于控制API请求频率
"""

import asyncio
import time
from typing import Optional


class AsyncLimiter:
    """异步限流器"""
    
    def __init__(self, max_calls: int, time_window: float):
        """
        初始化限流器
        
        Args:
            max_calls: 时间窗口内最大调用次数
            time_window: 时间窗口（秒）
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        async with self._lock:
            now = time.time()
            
            # 清理过期的调用记录
            self.calls = [call_time for call_time in self.calls 
                         if now - call_time < self.time_window]
            
            # 如果达到限制，等待
            if len(self.calls) >= self.max_calls:
                # 计算需要等待的时间
                oldest_call = min(self.calls)
                wait_time = self.time_window - (now - oldest_call) + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            # 记录本次调用
            self.calls.append(time.time())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        pass


class GlobalRateLimiter:
    """全局限流器管理"""
    
    def __init__(self):
        self.limiters = {}
    
    def get_limiter(self, name: str, max_calls: int, time_window: float) -> AsyncLimiter:
        """获取或创建限流器"""
        if name not in self.limiters:
            self.limiters[name] = AsyncLimiter(max_calls, time_window)
        return self.limiters[name]


# 全局限流器实例
global_rate_limiter = GlobalRateLimiter()