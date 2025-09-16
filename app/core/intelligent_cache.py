"""
智能多层缓存系统
提供L1(内存) + L2(Redis) + L3(文件)三层缓存架构
"""

import asyncio
import json
import time
import hashlib
import pickle
import aiofiles
import os
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from collections import OrderedDict
from loguru import logger
import threading
from dataclasses import dataclass
from enum import Enum

from app.core.database import redis_client

class CacheLevel(Enum):
    L1_MEMORY = "l1_memory"
    L2_REDIS = "l2_redis"
    L3_FILE = "l3_file"

class CacheStrategy(Enum):
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"

@dataclass
class CacheItem:
    data: Any
    created_at: float
    accessed_at: float
    access_count: int
    ttl: Optional[float] = None
    size_bytes: int = 0

@dataclass
class CacheConfig:
    max_size: int = 1000
    ttl_seconds: Optional[float] = None
    strategy: CacheStrategy = CacheStrategy.LRU
    enable_compression: bool = False
    enable_serialization: bool = True

class L1MemoryCache:
    """L1内存缓存 - 最快访问速度"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache: OrderedDict[str, CacheItem] = OrderedDict()
        self.lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_size': 0
        }
    
    def _calculate_size(self, data: Any) -> int:
        """计算数据大小（字节）"""
        try:
            if isinstance(data, (str, bytes)):
                return len(data.encode('utf-8') if isinstance(data, str) else data)
            else:
                return len(pickle.dumps(data))
        except:
            return 1024  # 默认1KB
    
    def _should_evict(self) -> bool:
        """判断是否需要淘汰数据"""
        return len(self.cache) >= self.config.max_size
    
    def _evict_item(self):
        """淘汰数据"""
        if not self.cache:
            return
        
        now = time.time()
        
        if self.config.strategy == CacheStrategy.LRU:
            # 淘汰最少使用的
            key = next(iter(self.cache))
        elif self.config.strategy == CacheStrategy.LFU:
            # 淘汰访问次数最少的
            key = min(self.cache.keys(), key=lambda k: self.cache[k].access_count)
        elif self.config.strategy == CacheStrategy.TTL:
            # 淘汰最先过期的
            expired_keys = [
                k for k, v in self.cache.items()
                if v.ttl and (now - v.created_at) > v.ttl
            ]
            if expired_keys:
                key = expired_keys[0]
            else:
                key = next(iter(self.cache))
        else:  # FIFO
            key = next(iter(self.cache))
        
        item = self.cache.pop(key)
        self.stats['evictions'] += 1
        self.stats['total_size'] -= item.size_bytes
        logger.debug(f"L1缓存淘汰: {key}")
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        with self.lock:
            if key not in self.cache:
                self.stats['misses'] += 1
                return None
            
            item = self.cache[key]
            now = time.time()
            
            # 检查TTL
            if item.ttl and (now - item.created_at) > item.ttl:
                del self.cache[key]
                self.stats['misses'] += 1
                return None
            
            # 更新访问信息
            item.accessed_at = now
            item.access_count += 1
            
            # LRU策略：移到末尾
            if self.config.strategy == CacheStrategy.LRU:
                self.cache.move_to_end(key)
            
            self.stats['hits'] += 1
            return item.data
    
    def set(self, key: str, data: Any, ttl: Optional[float] = None):
        """设置缓存数据"""
        with self.lock:
            now = time.time()
            size_bytes = self._calculate_size(data)
            
            # 检查是否需要淘汰
            while self._should_evict():
                self._evict_item()
            
            item = CacheItem(
                data=data,
                created_at=now,
                accessed_at=now,
                access_count=1,
                ttl=ttl or self.config.ttl_seconds,
                size_bytes=size_bytes
            )
            
            self.cache[key] = item
            self.stats['total_size'] += size_bytes
    
    def delete(self, key: str) -> bool:
        """删除缓存数据"""
        with self.lock:
            if key in self.cache:
                item = self.cache.pop(key)
                self.stats['total_size'] -= item.size_bytes
                return True
            return False
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.stats = {
                'hits': 0,
                'misses': 0,
                'evictions': 0,
                'total_size': 0
            }
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                **self.stats,
                'cache_size': len(self.cache),
                'hit_rate': hit_rate,
                'avg_size_bytes': self.stats['total_size'] / len(self.cache) if self.cache else 0
            }

class L2RedisCache:
    """L2 Redis缓存 - 持久化和共享"""
    
    def __init__(self, prefix: str = "cache"):
        self.prefix = prefix
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0
        }
    
    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """获取Redis缓存数据"""
        try:
            redis_key = self._make_key(key)
            data = await redis_client.get(redis_key)
            
            if data is None:
                self.stats['misses'] += 1
                return None
            
            self.stats['hits'] += 1
            return json.loads(data)
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis缓存读取错误: {e}")
            return None
    
    async def set(self, key: str, data: Any, ttl: Optional[int] = None):
        """设置Redis缓存数据"""
        try:
            redis_key = self._make_key(key)
            serialized_data = json.dumps(data, default=str)
            
            if ttl:
                await redis_client.setex(redis_key, ttl, serialized_data)
            else:
                await redis_client.set(redis_key, serialized_data)
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis缓存写入错误: {e}")
    
    async def delete(self, key: str) -> bool:
        """删除Redis缓存数据"""
        try:
            redis_key = self._make_key(key)
            result = await redis_client.delete(redis_key)
            return result > 0
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Redis缓存删除错误: {e}")
            return False
    
    async def clear_pattern(self, pattern: str):
        """按模式清除缓存"""
        try:
            redis_pattern = self._make_key(pattern)
            keys = await redis_client.keys(redis_pattern)
            if keys:
                await redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis缓存模式清除错误: {e}")
    
    def get_stats(self) -> Dict:
        """获取Redis缓存统计"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'hit_rate': hit_rate
        }

class L3FileCache:
    """L3文件缓存 - 大容量持久化"""
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0
        }
    
    def _get_file_path(self, key: str) -> str:
        """获取缓存文件路径"""
        # 使用MD5哈希避免文件名问题
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_key}.cache")
    
    def _get_meta_path(self, key: str) -> str:
        """获取元数据文件路径"""
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_key}.meta")
    
    async def get(self, key: str) -> Optional[Any]:
        """获取文件缓存数据"""
        try:
            file_path = self._get_file_path(key)
            meta_path = self._get_meta_path(key)
            
            if not os.path.exists(file_path) or not os.path.exists(meta_path):
                self.stats['misses'] += 1
                return None
            
            # 检查元数据
            async with aiofiles.open(meta_path, 'r') as f:
                meta = json.loads(await f.read())
            
            # 检查TTL
            if meta.get('ttl'):
                if time.time() - meta['created_at'] > meta['ttl']:
                    await self._delete_files(file_path, meta_path)
                    self.stats['misses'] += 1
                    return None
            
            # 读取数据
            async with aiofiles.open(file_path, 'rb') as f:
                data = pickle.loads(await f.read())
            
            # 更新访问时间
            meta['accessed_at'] = time.time()
            meta['access_count'] = meta.get('access_count', 0) + 1
            
            async with aiofiles.open(meta_path, 'w') as f:
                await f.write(json.dumps(meta))
            
            self.stats['hits'] += 1
            return data
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"文件缓存读取错误: {e}")
            return None
    
    async def set(self, key: str, data: Any, ttl: Optional[float] = None):
        """设置文件缓存数据"""
        try:
            file_path = self._get_file_path(key)
            meta_path = self._get_meta_path(key)
            
            # 写入数据
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(pickle.dumps(data))
            
            # 写入元数据
            meta = {
                'key': key,
                'created_at': time.time(),
                'accessed_at': time.time(),
                'access_count': 1,
                'ttl': ttl,
                'size_bytes': os.path.getsize(file_path)
            }
            
            async with aiofiles.open(meta_path, 'w') as f:
                await f.write(json.dumps(meta))
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"文件缓存写入错误: {e}")
    
    async def delete(self, key: str) -> bool:
        """删除文件缓存数据"""
        try:
            file_path = self._get_file_path(key)
            meta_path = self._get_meta_path(key)
            return await self._delete_files(file_path, meta_path)
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"文件缓存删除错误: {e}")
            return False
    
    async def _delete_files(self, file_path: str, meta_path: str) -> bool:
        """删除缓存文件和元数据"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(meta_path):
                os.remove(meta_path)
            return True
        except:
            return False
    
    async def cleanup_expired(self):
        """清理过期的缓存文件"""
        try:
            now = time.time()
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.meta'):
                    meta_path = os.path.join(self.cache_dir, filename)
                    try:
                        async with aiofiles.open(meta_path, 'r') as f:
                            meta = json.loads(await f.read())
                        
                        if meta.get('ttl') and (now - meta['created_at']) > meta['ttl']:
                            file_path = meta_path.replace('.meta', '.cache')
                            await self._delete_files(file_path, meta_path)
                    except:
                        continue
        except Exception as e:
            logger.error(f"清理过期缓存失败: {e}")

class IntelligentCacheManager:
    """智能缓存管理器"""
    
    def __init__(self):
        # 配置不同层级的缓存
        self.l1_config = CacheConfig(max_size=1000, ttl_seconds=300)  # 5分钟
        self.l2_config = CacheConfig(max_size=10000, ttl_seconds=3600)  # 1小时
        self.l3_config = CacheConfig(max_size=100000, ttl_seconds=86400)  # 24小时
        
        self.l1_cache = L1MemoryCache(self.l1_config)
        self.l2_cache = L2RedisCache("intelligent_cache")
        self.l3_cache = L3FileCache("./cache/l3")
        
        # 数据分类配置
        self.data_classification = {
            'hot': {  # 热数据：用户信息、项目信息
                'levels': [CacheLevel.L1_MEMORY, CacheLevel.L2_REDIS],
                'ttl': {'l1': 300, 'l2': 1800}
            },
            'warm': {  # 温数据：文献列表、分析结果
                'levels': [CacheLevel.L2_REDIS, CacheLevel.L3_FILE],
                'ttl': {'l2': 3600, 'l3': 86400}
            },
            'cold': {  # 冷数据：大文件、历史数据
                'levels': [CacheLevel.L3_FILE],
                'ttl': {'l3': 604800}  # 7天
            }
        }
    
    def _classify_data(self, key: str, data: Any) -> str:
        """数据分类"""
        # 根据key前缀和数据特征分类
        if any(prefix in key for prefix in ['user:', 'project:', 'session:']):
            return 'hot'
        elif any(prefix in key for prefix in ['literature:', 'analysis:', 'query:']):
            return 'warm'
        else:
            return 'cold'
    
    def _calculate_cache_score(self, key: str, data: Any) -> float:
        """计算缓存价值分数"""
        score = 0.0
        
        # 数据大小因子（小数据更适合缓存）
        size_bytes = self.l1_cache._calculate_size(data)
        if size_bytes < 1024:  # < 1KB
            score += 0.3
        elif size_bytes < 10240:  # < 10KB
            score += 0.2
        elif size_bytes < 102400:  # < 100KB
            score += 0.1
        
        # 访问模式因子
        if 'user:' in key or 'session:' in key:
            score += 0.4  # 用户数据访问频繁
        elif 'literature:' in key:
            score += 0.3  # 文献数据中等频率
        
        # 计算复杂度因子
        if 'analysis:' in key or 'ai_result:' in key:
            score += 0.3  # AI结果计算成本高
        
        return min(1.0, score)
    
    async def get(self, key: str) -> Optional[Any]:
        """智能获取缓存数据"""
        # L1 -> L2 -> L3 的查找顺序
        
        # 尝试L1缓存
        data = self.l1_cache.get(key)
        if data is not None:
            logger.debug(f"L1缓存命中: {key}")
            return data
        
        # 尝试L2缓存
        data = await self.l2_cache.get(key)
        if data is not None:
            logger.debug(f"L2缓存命中: {key}")
            # 根据数据分类决定是否提升到L1
            classification = self._classify_data(key, data)
            if classification == 'hot':
                self.l1_cache.set(key, data, ttl=300)
            return data
        
        # 尝试L3缓存
        data = await self.l3_cache.get(key)
        if data is not None:
            logger.debug(f"L3缓存命中: {key}")
            # 根据分类提升到合适层级
            classification = self._classify_data(key, data)
            if classification == 'hot':
                self.l1_cache.set(key, data, ttl=300)
                await self.l2_cache.set(key, data, ttl=1800)
            elif classification == 'warm':
                await self.l2_cache.set(key, data, ttl=3600)
            return data
        
        logger.debug(f"缓存未命中: {key}")
        return None
    
    async def set(self, key: str, data: Any, ttl: Optional[int] = None):
        """智能设置缓存数据"""
        classification = self._classify_data(key, data)
        cache_score = self._calculate_cache_score(key, data)
        
        config = self.data_classification[classification]
        levels = config['levels']
        ttl_config = config['ttl']
        
        # 根据分类和分数决定缓存策略
        if CacheLevel.L1_MEMORY in levels and cache_score > 0.7:
            self.l1_cache.set(key, data, ttl=ttl or ttl_config.get('l1'))
        
        if CacheLevel.L2_REDIS in levels and cache_score > 0.5:
            await self.l2_cache.set(key, data, ttl=ttl or ttl_config.get('l2'))
        
        if CacheLevel.L3_FILE in levels:
            await self.l3_cache.set(key, data, ttl=ttl or ttl_config.get('l3'))
        
        logger.debug(f"缓存设置完成: {key} -> {classification} (score: {cache_score:.2f})")
    
    async def delete(self, key: str):
        """从所有层级删除缓存"""
        self.l1_cache.delete(key)
        await self.l2_cache.delete(key)
        await self.l3_cache.delete(key)
    
    async def invalidate_pattern(self, pattern: str):
        """按模式失效缓存"""
        # L1缓存模式匹配删除
        keys_to_delete = [k for k in self.l1_cache.cache.keys() if pattern in k]
        for key in keys_to_delete:
            self.l1_cache.delete(key)
        
        # L2缓存模式删除
        await self.l2_cache.clear_pattern(f"*{pattern}*")
        
        # L3缓存暂不支持模式删除
    
    async def get_comprehensive_stats(self) -> Dict:
        """获取综合缓存统计"""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats()
        
        return {
            'l1_memory': l1_stats,
            'l2_redis': l2_stats,
            'l3_file': {'hits': self.l3_cache.stats['hits'], 'misses': self.l3_cache.stats['misses']},
            'overall': {
                'total_hits': l1_stats['hits'] + l2_stats['hits'] + self.l3_cache.stats['hits'],
                'total_misses': l1_stats['misses'] + l2_stats['misses'] + self.l3_cache.stats['misses'],
                'memory_usage_mb': l1_stats['total_size'] / 1024 / 1024,
                'cache_efficiency': self._calculate_efficiency()
            }
        }
    
    def _calculate_efficiency(self) -> float:
        """计算缓存效率"""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats()
        
        total_hits = l1_stats['hits'] + l2_stats['hits'] + self.l3_cache.stats['hits']
        total_requests = total_hits + l1_stats['misses'] + l2_stats['misses'] + self.l3_cache.stats['misses']
        
        return (total_hits / total_requests * 100) if total_requests > 0 else 0
    
    async def start_maintenance_tasks(self):
        """启动维护任务"""
        async def maintenance_loop():
            while True:
                try:
                    # 清理过期的L3缓存
                    await self.l3_cache.cleanup_expired()
                    
                    # 记录统计信息
                    stats = await self.get_comprehensive_stats()
                    logger.info(f"缓存统计: {stats['overall']}")
                    
                    await asyncio.sleep(3600)  # 每小时执行一次
                except Exception as e:
                    logger.error(f"缓存维护任务错误: {e}")
                    await asyncio.sleep(300)  # 错误时5分钟后重试
        
        asyncio.create_task(maintenance_loop())

# 全局缓存管理器实例
cache_manager = IntelligentCacheManager()

# 缓存装饰器
def cached(
    key_template: str,
    ttl: Optional[int] = None,
    classification: str = 'warm'
):
    """缓存装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 生成缓存key
            cache_key = key_template.format(*args, **kwargs)
            
            # 尝试从缓存获取
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 执行函数并缓存结果
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator

# 使用示例
@cached("literature:project:{0}", ttl=3600)
async def get_project_literature(project_id: int):
    """获取项目文献（带缓存）"""
    # 实际的数据库查询逻辑
    pass