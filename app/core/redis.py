"""
Redis缓存配置和管理
"""

import os
from typing import Optional, Any, Union
import json
import pickle
from datetime import timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError
from loguru import logger
from functools import wraps
import hashlib

from app.core.config import settings

# Redis配置
REDIS_URL = settings.redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_POOL_SIZE = int(os.getenv("REDIS_POOL_SIZE", "20"))
REDIS_DECODE_RESPONSES = False  # 支持二进制数据

class RedisManager:
    """Redis连接管理器"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.is_connected = False

    async def connect(self):
        """建立Redis连接"""
        try:
            self.redis_client = redis.from_url(
                REDIS_URL,
                max_connections=REDIS_POOL_SIZE,
                decode_responses=REDIS_DECODE_RESPONSES
            )
            # 测试连接
            await self.redis_client.ping()
            self.is_connected = True
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.is_connected = False
            self.redis_client = None

    async def disconnect(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.is_connected = False
            logger.info("Redis connection closed")

    async def get_client(self) -> Optional[redis.Redis]:
        """获取Redis客户端"""
        if not self.is_connected:
            await self.connect()
        return self.redis_client

# 全局Redis管理器实例
redis_manager = RedisManager()

class CacheKeys:
    """缓存键管理"""

    # 键前缀
    PREFIX = "vibesearch:"

    # 缓存键模板
    USER_SESSION = PREFIX + "session:{user_id}"
    USER_PROFILE = PREFIX + "user:{user_id}"
    PROJECT_DETAIL = PREFIX + "project:{project_id}"
    PROJECT_LIST = PREFIX + "projects:user:{user_id}:page:{page}"
    LITERATURE_DETAIL = PREFIX + "literature:{literature_id}"
    LITERATURE_SEARCH = PREFIX + "literature:search:{hash}"
    TASK_STATUS = PREFIX + "task:{task_id}"
    TASK_RESULT = PREFIX + "task:result:{task_id}"
    RESEARCH_EXPERIENCE = PREFIX + "experience:{project_id}:{hash}"
    SYSTEM_STATUS = PREFIX + "system:status"
    API_RATE_LIMIT = PREFIX + "rate:{user_id}:{endpoint}"

    @staticmethod
    def generate_hash(data: Any) -> str:
        """生成数据的哈希值作为缓存键的一部分"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()[:8]

class CacheService:
    """缓存服务"""

    def __init__(self):
        self.default_ttl = 300  # 默认5分钟过期

    async def get(
        self,
        key: str,
        deserialize: bool = True
    ) -> Optional[Any]:
        """获取缓存"""
        client = await redis_manager.get_client()
        if not client:
            return None

        try:
            value = await client.get(key)
            if value is None:
                return None

            if deserialize:
                # 尝试JSON反序列化
                try:
                    return json.loads(value)
                except:
                    # 失败则尝试pickle反序列化
                    try:
                        return pickle.loads(value)
                    except:
                        return value.decode() if isinstance(value, bytes) else value
            return value
        except RedisError as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """设置缓存"""
        client = await redis_manager.get_client()
        if not client:
            return False

        try:
            if serialize:
                # 尝试JSON序列化
                try:
                    value = json.dumps(value)
                except:
                    # 失败则使用pickle序列化
                    value = pickle.dumps(value)

            if ttl is None:
                ttl = self.default_ttl

            await client.setex(key, ttl, value)
            return True
        except RedisError as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    async def delete(self, *keys: str) -> int:
        """删除缓存"""
        client = await redis_manager.get_client()
        if not client:
            return 0

        try:
            return await client.delete(*keys)
        except RedisError as e:
            logger.error(f"Redis delete error for keys {keys}: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        client = await redis_manager.get_client()
        if not client:
            return False

        try:
            return await client.exists(key) > 0
        except RedisError as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        client = await redis_manager.get_client()
        if not client:
            return False

        try:
            return await client.expire(key, ttl)
        except RedisError as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """增加计数"""
        client = await redis_manager.get_client()
        if not client:
            return None

        try:
            return await client.incrby(key, amount)
        except RedisError as e:
            logger.error(f"Redis increment error for key {key}: {e}")
            return None

    async def get_many(self, keys: list) -> dict:
        """批量获取缓存"""
        client = await redis_manager.get_client()
        if not client:
            return {}

        try:
            values = await client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except:
                        result[key] = value
            return result
        except RedisError as e:
            logger.error(f"Redis mget error for keys {keys}: {e}")
            return {}

    async def set_many(self, mapping: dict, ttl: Optional[int] = None) -> bool:
        """批量设置缓存"""
        client = await redis_manager.get_client()
        if not client:
            return False

        try:
            # 序列化所有值
            serialized = {}
            for key, value in mapping.items():
                try:
                    serialized[key] = json.dumps(value)
                except:
                    serialized[key] = pickle.dumps(value)

            # 批量设置
            pipeline = await client.pipeline()
            for key, value in serialized.items():
                if ttl:
                    await pipeline.setex(key, ttl, value)
                else:
                    await pipeline.set(key, value)
            await pipeline.execute()
            return True
        except RedisError as e:
            logger.error(f"Redis mset error: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """清除符合模式的所有键"""
        client = await redis_manager.get_client()
        if not client:
            return 0

        try:
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await client.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Redis clear pattern error for {pattern}: {e}")
            return 0

# 全局缓存服务实例
cache_service = CacheService()

# 缓存装饰器
def cache_result(
    key_pattern: str,
    ttl: int = 300,
    key_params: list = None
):
    """
    缓存函数结果的装饰器

    Args:
        key_pattern: 缓存键模板，可包含占位符
        ttl: 过期时间（秒）
        key_params: 用于生成键的参数名列表
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_params:
                key_values = {}
                # 获取函数参数
                import inspect
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                for param in key_params:
                    if param in bound_args.arguments:
                        key_values[param] = bound_args.arguments[param]

                cache_key = key_pattern.format(**key_values)
            else:
                # 使用函数名和参数哈希生成键
                params_hash = CacheKeys.generate_hash({
                    "args": args,
                    "kwargs": kwargs
                })
                cache_key = f"{CacheKeys.PREFIX}{func.__name__}:{params_hash}"

            # 尝试获取缓存
            cached = await cache_service.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached

            # 执行函数
            result = await func(*args, **kwargs)

            # 保存到缓存
            await cache_service.set(cache_key, result, ttl)
            logger.debug(f"Cache set for key: {cache_key}")

            return result
        return wrapper
    return decorator

# 使用示例
"""
@cache_result(
    key_pattern=CacheKeys.PROJECT_DETAIL,
    ttl=600,
    key_params=['project_id']
)
async def get_project_detail(project_id: int):
    # 获取项目详情的业务逻辑
    pass
"""
