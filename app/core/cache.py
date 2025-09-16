"""
多层缓存管理器
支持本地缓存、Redis分布式缓存和缓存预热
"""

import redis
import json
import hashlib
import asyncio
import time
from functools import wraps
from typing import Any, Optional, Dict, List, Callable, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class CacheLevel(Enum):
    """缓存层级"""
    LOCAL = "local"
    REDIS = "redis"
    BOTH = "both"

@dataclass
class CacheConfig:
    """缓存配置"""
    ttl: int = 3600  # 默认1小时
    level: CacheLevel = CacheLevel.BOTH
    key_prefix: str = ""
    max_size: int = 1000  # 本地缓存最大条目数
    serialize: bool = True

class LocalCache:
    """本地LRU缓存实现"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: Dict[str, Dict] = {}
        self.access_order: List[str] = []
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self.cache:
                # 检查过期时间
                entry = self.cache[key]
                if entry['expires'] > time.time():
                    # 更新访问顺序
                    self.access_order.remove(key)
                    self.access_order.append(key)
                    return entry['value']
                else:
                    # 删除过期条目
                    del self.cache[key]
                    self.access_order.remove(key)
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        async with self._lock:
            # 如果缓存已满，删除最旧的条目
            if len(self.cache) >= self.max_size and key not in self.cache:
                oldest_key = self.access_order.pop(0)
                del self.cache[oldest_key]
            
            # 添加或更新条目
            self.cache[key] = {
                'value': value,
                'expires': time.time() + ttl,
                'created': time.time()
            }
            
            # 更新访问顺序
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
    
    async def delete(self, key: str):
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                self.access_order.remove(key)
    
    async def clear(self):
        async with self._lock:
            self.cache.clear()
            self.access_order.clear()
    
    def size(self) -> int:
        return len(self.cache)
    
    def stats(self) -> Dict:
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'keys': list(self.cache.keys())
        }

class CacheManager:
    """多层缓存管理器"""
    
    def __init__(
        self, 
        redis_url: str = "redis://redis:6379/0",
        local_cache_size: int = 1000
    ):
        # Redis客户端
        self.redis_client = redis.from_url(
            redis_url, 
            decode_responses=True,
            max_connections=50,
            retry_on_timeout=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # 本地缓存
        self.local_cache = LocalCache(local_cache_size)
        
        # 统计信息
        self.stats = {
            'hits': {'local': 0, 'redis': 0},
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
    
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict, prefix: str = "") -> str:
        """生成缓存键"""
        # 创建唯一标识符
        key_data = {
            'function': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else None
        }
        
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        
        if prefix:
            return f"{prefix}:{key_hash}"
        return key_hash
    
    async def get(self, key: str, level: CacheLevel = CacheLevel.BOTH) -> Optional[Any]:
        """获取缓存值"""
        try:
            # 先查本地缓存
            if level in [CacheLevel.LOCAL, CacheLevel.BOTH]:
                local_value = await self.local_cache.get(key)
                if local_value is not None:
                    self.stats['hits']['local'] += 1
                    return local_value
            
            # 再查Redis缓存
            if level in [CacheLevel.REDIS, CacheLevel.BOTH]:
                redis_value = self.redis_client.get(key)
                if redis_value is not None:
                    self.stats['hits']['redis'] += 1
                    try:
                        parsed_value = json.loads(redis_value)
                        # 回填本地缓存
                        if level == CacheLevel.BOTH:
                            await self.local_cache.set(key, parsed_value, ttl=300)  # 本地缓存5分钟
                        return parsed_value
                    except json.JSONDecodeError:
                        return redis_value
            
            self.stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.stats['errors'] += 1
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 3600, 
        level: CacheLevel = CacheLevel.BOTH,
        serialize: bool = True
    ):
        """设置缓存值"""
        try:
            # 序列化值
            if serialize and not isinstance(value, str):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = value
            
            # 设置本地缓存
            if level in [CacheLevel.LOCAL, CacheLevel.BOTH]:
                await self.local_cache.set(key, value, ttl)
            
            # 设置Redis缓存
            if level in [CacheLevel.REDIS, CacheLevel.BOTH]:
                self.redis_client.setex(key, ttl, serialized_value)
            
            self.stats['sets'] += 1
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self.stats['errors'] += 1
    
    async def delete(self, key: str, level: CacheLevel = CacheLevel.BOTH):
        """删除缓存值"""
        try:
            if level in [CacheLevel.LOCAL, CacheLevel.BOTH]:
                await self.local_cache.delete(key)
            
            if level in [CacheLevel.REDIS, CacheLevel.BOTH]:
                self.redis_client.delete(key)
            
            self.stats['deletes'] += 1
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            self.stats['errors'] += 1
    
    async def clear(self, level: CacheLevel = CacheLevel.BOTH):
        """清空缓存"""
        try:
            if level in [CacheLevel.LOCAL, CacheLevel.BOTH]:
                await self.local_cache.clear()
            
            if level in [CacheLevel.REDIS, CacheLevel.BOTH]:
                self.redis_client.flushdb()
                
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            self.stats['errors'] += 1
    
    async def exists(self, key: str, level: CacheLevel = CacheLevel.BOTH) -> bool:
        """检查缓存键是否存在"""
        try:
            if level in [CacheLevel.LOCAL, CacheLevel.BOTH]:
                local_value = await self.local_cache.get(key)
                if local_value is not None:
                    return True
            
            if level in [CacheLevel.REDIS, CacheLevel.BOTH]:
                return bool(self.redis_client.exists(key))
            
            return False
            
        except Exception as e:
            logger.error(f"Cache exists check error for key {key}: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        total_hits = self.stats['hits']['local'] + self.stats['hits']['redis']
        total_requests = total_hits + self.stats['misses']
        
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'total_hits': total_hits,
            'total_requests': total_requests,
            'hit_rate': round(hit_rate, 2),
            'local_cache_size': self.local_cache.size(),
            'local_cache_stats': self.local_cache.stats()
        }
    
    async def warm_up(self, warm_up_data: Dict[str, Any]):
        """缓存预热"""
        logger.info("Starting cache warm-up...")
        
        for key, data in warm_up_data.items():
            try:
                await self.set(
                    key, 
                    data.get('value'), 
                    ttl=data.get('ttl', 3600),
                    level=data.get('level', CacheLevel.BOTH)
                )
            except Exception as e:
                logger.error(f"Cache warm-up error for key {key}: {e}")
        
        logger.info(f"Cache warm-up completed. Warmed {len(warm_up_data)} keys.")

# 全局缓存管理器实例
cache_manager = CacheManager()

def cached(
    ttl: int = 3600,
    level: CacheLevel = CacheLevel.BOTH,
    key_prefix: str = "",
    serialize: bool = True,
    cache_none: bool = False
):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存生存时间（秒）
        level: 缓存层级
        key_prefix: 键前缀
        serialize: 是否序列化
        cache_none: 是否缓存None值
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = cache_manager._generate_key(
                func.__name__, args, kwargs, key_prefix
            )
            
            # 尝试从缓存获取
            cached_result = await cache_manager.get(cache_key, level)
            if cached_result is not None:
                return cached_result
            
            # 执行原函数
            result = await func(*args, **kwargs)
            
            # 缓存结果（如果不是None或允许缓存None）
            if result is not None or cache_none:
                await cache_manager.set(
                    cache_key, result, ttl, level, serialize
                )
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 对于同步函数，使用asyncio.run
            async def async_sync_wrapper():
                cache_key = cache_manager._generate_key(
                    func.__name__, args, kwargs, key_prefix
                )
                
                cached_result = await cache_manager.get(cache_key, level)
                if cached_result is not None:
                    return cached_result
                
                result = func(*args, **kwargs)
                
                if result is not None or cache_none:
                    await cache_manager.set(
                        cache_key, result, ttl, level, serialize
                    )
                
                return result
            
            return asyncio.run(async_sync_wrapper())
        
        # 判断是否为异步函数
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class CacheInvalidator:
    """缓存失效管理器"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.invalidation_patterns: Dict[str, List[str]] = {}
    
    def register_pattern(self, event: str, patterns: List[str]):
        """注册失效模式"""
        self.invalidation_patterns[event] = patterns
    
    async def invalidate_by_event(self, event: str, **context):
        """根据事件失效缓存"""
        patterns = self.invalidation_patterns.get(event, [])
        
        for pattern in patterns:
            # 支持简单的通配符匹配
            if '*' in pattern:
                await self._invalidate_by_pattern(pattern, context)
            else:
                # 直接删除特定键
                formatted_key = pattern.format(**context)
                await self.cache_manager.delete(formatted_key)
    
    async def _invalidate_by_pattern(self, pattern: str, context: Dict):
        """根据模式失效缓存"""
        try:
            # 将模式转换为Redis键模式
            redis_pattern = pattern.format(**context)
            keys = self.redis_client.keys(redis_pattern)
            
            if keys:
                for key in keys:
                    await self.cache_manager.delete(key)
                    
                logger.info(f"Invalidated {len(keys)} cache keys matching pattern: {redis_pattern}")
                
        except Exception as e:
            logger.error(f"Cache invalidation error for pattern {pattern}: {e}")

# 缓存失效管理器实例
cache_invalidator = CacheInvalidator(cache_manager)

# 注册常见的失效模式
cache_invalidator.register_pattern('user_updated', [
    'user:{user_id}:*',
    'user_list:*'
])

cache_invalidator.register_pattern('literature_updated', [
    'literature:{literature_id}:*',
    'literature_list:*',
    'user:{user_id}:literature:*'
])

cache_invalidator.register_pattern('project_updated', [
    'project:{project_id}:*',
    'project_list:*',
    'user:{user_id}:project:*'
])

# 缓存预热数据配置
CACHE_WARMUP_CONFIG = {
    'popular_literature': {
        'value': None,  # 将在运行时填充
        'ttl': 7200,    # 2小时
        'level': CacheLevel.BOTH
    },
    'system_config': {
        'value': None,
        'ttl': 86400,   # 24小时
        'level': CacheLevel.BOTH
    }
}

async def initialize_cache():
    """初始化缓存系统"""
    logger.info("Initializing cache system...")
    
    try:
        # 测试Redis连接
        cache_manager.redis_client.ping()
        logger.info("Redis connection established")
        
        # 缓存预热（如果需要）
        # await cache_manager.warm_up(CACHE_WARMUP_CONFIG)
        
        logger.info("Cache system initialized successfully")
        
    except Exception as e:
        logger.error(f"Cache initialization failed: {e}")
        raise e

# 使用示例装饰器
@cached(ttl=1800, key_prefix="literature")
async def get_literature_by_id(literature_id: int):
    """获取文献详情（带缓存）"""
    # 实际的数据库查询逻辑
    pass

@cached(ttl=3600, key_prefix="user", level=CacheLevel.REDIS)
async def get_user_profile(user_id: int):
    """获取用户资料（仅Redis缓存）"""
    # 实际的数据库查询逻辑
    pass