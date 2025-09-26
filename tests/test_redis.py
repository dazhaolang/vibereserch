"""
Redis缓存服务单元测试
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from app.core.redis import (
    RedisManager,
    CacheKeys,
    CacheService,
    cache_result
)


class TestRedisManager:
    """测试Redis连接管理器"""

    @pytest.mark.asyncio
    async def test_connection_success(self):
        """测试成功连接Redis"""
        manager = RedisManager()

        with patch('app.core.redis.redis.from_url') as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_from_url.return_value = mock_client

            await manager.connect()

            assert manager.is_connected
            assert manager.redis_client is not None
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """测试连接Redis失败"""
        manager = RedisManager()

        with patch('app.core.redis.redis.from_url') as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=Exception("Connection failed"))
            mock_from_url.return_value = mock_client

            await manager.connect()

            assert not manager.is_connected
            assert manager.redis_client is None

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """测试断开Redis连接"""
        manager = RedisManager()
        manager.redis_client = AsyncMock()
        manager.is_connected = True

        await manager.disconnect()

        manager.redis_client.close.assert_called_once()
        assert not manager.is_connected


class TestCacheKeys:
    """测试缓存键管理"""

    def test_key_templates(self):
        """测试缓存键模板"""
        user_id = 123
        project_id = 456

        user_session_key = CacheKeys.USER_SESSION.format(user_id=user_id)
        assert user_session_key == "vibesearch:session:123"

        project_key = CacheKeys.PROJECT_DETAIL.format(project_id=project_id)
        assert project_key == "vibesearch:project:456"

    def test_hash_generation(self):
        """测试哈希生成"""
        # 相同数据产生相同哈希
        data1 = {"key": "value", "num": 123}
        hash1 = CacheKeys.generate_hash(data1)
        hash2 = CacheKeys.generate_hash(data1)
        assert hash1 == hash2

        # 不同数据产生不同哈希
        data2 = {"key": "different", "num": 456}
        hash3 = CacheKeys.generate_hash(data2)
        assert hash1 != hash3

        # 哈希长度应该是8个字符
        assert len(hash1) == 8


class TestCacheService:
    """测试缓存服务"""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """测试设置和获取缓存"""
        service = CacheService()

        with patch('app.core.redis.redis_manager.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            # 测试设置缓存
            mock_client.setex = AsyncMock(return_value=True)
            result = await service.set("test_key", {"data": "value"}, ttl=60)
            assert result is True

            # 验证JSON序列化
            mock_client.setex.assert_called_once()
            call_args = mock_client.setex.call_args
            assert call_args[0][0] == "test_key"
            assert call_args[0][1] == 60
            assert json.loads(call_args[0][2]) == {"data": "value"}

            # 测试获取缓存
            mock_client.get = AsyncMock(return_value=json.dumps({"data": "value"}).encode())
            result = await service.get("test_key")
            assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_delete(self):
        """测试删除缓存"""
        service = CacheService()

        with patch('app.core.redis.redis_manager.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.delete = AsyncMock(return_value=2)

            result = await service.delete("key1", "key2")
            assert result == 2
            mock_client.delete.assert_called_once_with("key1", "key2")

    @pytest.mark.asyncio
    async def test_exists(self):
        """测试检查键存在"""
        service = CacheService()

        with patch('app.core.redis.redis_manager.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.exists = AsyncMock(return_value=1)

            result = await service.exists("test_key")
            assert result is True
            mock_client.exists.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_increment(self):
        """测试计数增加"""
        service = CacheService()

        with patch('app.core.redis.redis_manager.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.incrby = AsyncMock(return_value=5)

            result = await service.increment("counter_key", 2)
            assert result == 5
            mock_client.incrby.assert_called_once_with("counter_key", 2)

    @pytest.mark.asyncio
    async def test_batch_operations(self):
        """测试批量操作"""
        service = CacheService()

        with patch('app.core.redis.redis_manager.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_pipeline = AsyncMock()
            mock_client.pipeline.return_value = mock_pipeline
            mock_get_client.return_value = mock_client

            # 测试批量设置
            mapping = {
                "key1": {"value": 1},
                "key2": {"value": 2}
            }
            result = await service.set_many(mapping, ttl=60)
            assert result is True
            assert mock_pipeline.setex.call_count == 2

            # 测试批量获取
            mock_client.mget = AsyncMock(
                return_value=[
                    json.dumps({"value": 1}).encode(),
                    json.dumps({"value": 2}).encode()
                ]
            )
            result = await service.get_many(["key1", "key2"])
            assert result == {
                "key1": {"value": 1},
                "key2": {"value": 2}
            }

    @pytest.mark.asyncio
    async def test_clear_pattern(self):
        """测试清除模式匹配的键"""
        service = CacheService()

        with patch('app.core.redis.redis_manager.get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            # 模拟scan_iter返回键
            async def mock_scan_iter(match):
                for key in [b"test:1", b"test:2", b"test:3"]:
                    yield key

            mock_client.scan_iter = mock_scan_iter
            mock_client.delete = AsyncMock(return_value=3)

            result = await service.clear_pattern("test:*")
            assert result == 3


class TestCacheDecorator:
    """测试缓存装饰器"""

    @pytest.mark.asyncio
    async def test_cache_result_decorator(self):
        """测试缓存结果装饰器"""
        call_count = 0

        @cache_result(
            key_pattern="test:{user_id}:{project_id}",
            ttl=60,
            key_params=["user_id", "project_id"]
        )
        async def get_data(user_id: int, project_id: int):
            nonlocal call_count
            call_count += 1
            return {"result": f"data_{user_id}_{project_id}"}

        with patch('app.core.redis.cache_service.get') as mock_get, \
             patch('app.core.redis.cache_service.set') as mock_set:

            # 第一次调用，缓存未命中
            mock_get.return_value = None
            mock_set.return_value = True

            result1 = await get_data(1, 2)
            assert result1 == {"result": "data_1_2"}
            assert call_count == 1

            # 验证缓存键生成正确
            mock_get.assert_called_with("test:1:2")
            mock_set.assert_called_once()

            # 第二次调用，缓存命中
            mock_get.return_value = {"result": "data_1_2"}
            result2 = await get_data(1, 2)
            assert result2 == {"result": "data_1_2"}
            assert call_count == 1  # 函数不应再次执行

    @pytest.mark.asyncio
    async def test_cache_decorator_without_params(self):
        """测试不带参数的缓存装饰器"""
        call_count = 0

        @cache_result(key_pattern="", ttl=60)
        async def get_static_data():
            nonlocal call_count
            call_count += 1
            return {"static": "data"}

        with patch('app.core.redis.cache_service.get') as mock_get, \
             patch('app.core.redis.cache_service.set') as mock_set:

            mock_get.return_value = None
            mock_set.return_value = True

            result = await get_static_data()
            assert result == {"static": "data"}
            assert call_count == 1

            # 验证使用了函数名和参数哈希生成键
            assert mock_get.called
            call_args = mock_get.call_args[0][0]
            assert "get_static_data" in call_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])