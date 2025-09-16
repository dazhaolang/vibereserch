"""
Elasticsearch 连接和管理
"""

from elasticsearch import AsyncElasticsearch
from typing import Optional, Dict, Any, List
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class ElasticsearchClient:
    """Elasticsearch客户端封装"""

    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
        self.index_prefix = settings.elasticsearch_index_prefix

    async def connect(self):
        """连接到Elasticsearch"""
        try:
            self.client = AsyncElasticsearch(
                hosts=[settings.elasticsearch_url],
                timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )

            # 测试连接
            await self.client.info()
            logger.info("Connected to Elasticsearch successfully")

        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            raise

    async def close(self):
        """关闭连接"""
        if self.client:
            await self.client.close()

    async def create_index(self, index_name: str, mapping: Dict[str, Any], settings_config: Optional[Dict[str, Any]] = None):
        """创建索引"""
        full_index_name = f"{self.index_prefix}{index_name}"

        try:
            index_body = {"mappings": mapping}
            if settings_config:
                index_body["settings"] = settings_config

            await self.client.indices.create(
                index=full_index_name,
                body=index_body,
                ignore=400  # 忽略索引已存在的错误
            )
            logger.info(f"Created index: {full_index_name}")

        except Exception as e:
            logger.error(f"Failed to create index {full_index_name}: {e}")
            raise

    async def index_document(self, index_name: str, doc_id: str, document: Dict[str, Any]):
        """索引文档"""
        full_index_name = f"{self.index_prefix}{index_name}"

        try:
            await self.client.index(
                index=full_index_name,
                id=doc_id,
                document=document
            )

        except Exception as e:
            logger.error(f"Failed to index document {doc_id} in {full_index_name}: {e}")
            raise

    async def bulk_index(self, index_name: str, documents: List[Dict[str, Any]]):
        """批量索引文档"""
        full_index_name = f"{self.index_prefix}{index_name}"

        try:
            body = []
            for doc in documents:
                action = {"index": {"_index": full_index_name, "_id": doc.get("id")}}
                body.extend([action, doc])

            if body:
                await self.client.bulk(body=body)
                logger.info(f"Bulk indexed {len(documents)} documents to {full_index_name}")

        except Exception as e:
            logger.error(f"Failed to bulk index documents to {full_index_name}: {e}")
            raise

    async def search(self, index_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """搜索文档"""
        full_index_name = f"{self.index_prefix}{index_name}"

        try:
            response = await self.client.search(
                index=full_index_name,
                body=query
            )
            return response

        except Exception as e:
            logger.error(f"Failed to search in {full_index_name}: {e}")
            raise

    async def delete_document(self, index_name: str, doc_id: str):
        """删除文档"""
        full_index_name = f"{self.index_prefix}{index_name}"

        try:
            await self.client.delete(
                index=full_index_name,
                id=doc_id,
                ignore=404  # 忽略文档不存在的错误
            )

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id} from {full_index_name}: {e}")
            raise

    async def update_document(self, index_name: str, doc_id: str, document: Dict[str, Any]):
        """更新文档"""
        full_index_name = f"{self.index_prefix}{index_name}"

        try:
            await self.client.update(
                index=full_index_name,
                id=doc_id,
                body={"doc": document}
            )

        except Exception as e:
            logger.error(f"Failed to update document {doc_id} in {full_index_name}: {e}")
            raise

    async def delete_index(self, index_name: str):
        """删除索引"""
        full_index_name = f"{self.index_prefix}{index_name}"

        try:
            await self.client.indices.delete(
                index=full_index_name,
                ignore=404  # 忽略索引不存在的错误
            )
            logger.info(f"Deleted index: {full_index_name}")

        except Exception as e:
            logger.error(f"Failed to delete index {full_index_name}: {e}")
            raise

# 全局ES客户端实例
es_client = ElasticsearchClient()

async def get_elasticsearch():
    """获取Elasticsearch客户端"""
    if not es_client.client:
        await es_client.connect()
    return es_client