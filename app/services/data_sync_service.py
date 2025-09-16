"""
MySQL和Elasticsearch数据同步服务
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.elasticsearch import get_elasticsearch
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.services.ai_service import AIService
import logging

logger = logging.getLogger(__name__)

class DataSyncService:
    """MySQL和Elasticsearch数据同步服务"""

    def __init__(self):
        self.ai_service = AIService()
        self.es_client = None

    async def init_elasticsearch(self):
        """初始化Elasticsearch客户端"""
        self.es_client = await get_elasticsearch()

    async def sync_literature_to_es(self, literature_id: int, db: Session):
        """同步单个文献到Elasticsearch"""
        try:
            # 从MySQL获取文献数据
            literature = db.query(Literature).filter(Literature.id == literature_id).first()
            if not literature:
                logger.warning(f"Literature {literature_id} not found in MySQL")
                return

            # 生成嵌入向量
            title_embedding = None
            abstract_embedding = None

            if literature.title:
                title_embedding = await self.ai_service.get_embedding(literature.title)

            if literature.abstract:
                abstract_embedding = await self.ai_service.get_embedding(literature.abstract)

            # 构建ES文档
            es_doc = {
                "literature_id": literature.id,
                "title": literature.title,
                "abstract": literature.abstract or "",
                "authors": literature.authors or [],
                "keywords": literature.keywords or [],
                "journal": literature.journal,
                "publication_year": literature.publication_year,
                "doi": literature.doi,
                "category": literature.category,
                "tags": literature.tags or [],
                "quality_score": float(literature.quality_score) if literature.quality_score else 0.0,
                "reliability_score": float(literature.reliability_score) if literature.reliability_score else 0.5,
                "citation_count": literature.citation_count or 0,
                "impact_factor": float(literature.impact_factor) if literature.impact_factor else 0.0,
                "source_platform": literature.source_platform,
                "status": literature.status,
                "created_at": literature.created_at.isoformat() if literature.created_at else None,
                "updated_at": literature.updated_at.isoformat() if literature.updated_at else None
            }

            # 添加向量嵌入
            if title_embedding:
                es_doc["title_embedding"] = title_embedding

            if abstract_embedding:
                es_doc["abstract_embedding"] = abstract_embedding

            # 索引到Elasticsearch
            await self.es_client.index_document(
                index_name="literature_index",
                doc_id=str(literature_id),
                document=es_doc
            )

            logger.info(f"Successfully synced literature {literature_id} to Elasticsearch")

        except Exception as e:
            logger.error(f"Failed to sync literature {literature_id} to ES: {e}")
            raise

    async def sync_literature_segment_to_es(self, segment_id: int, db: Session):
        """同步文献段落到Elasticsearch"""
        try:
            # 从MySQL获取段落数据
            segment = db.query(LiteratureSegment).filter(LiteratureSegment.id == segment_id).first()
            if not segment:
                logger.warning(f"Literature segment {segment_id} not found in MySQL")
                return

            # 获取关联的文献信息
            literature = segment.literature

            # 生成内容嵌入
            content_embedding = None
            if segment.content:
                content_embedding = await self.ai_service.get_embedding(segment.content)

            # 获取该文献关联的项目ID列表
            project_ids = [p.id for p in literature.projects] if literature.projects else []

            # 构建ES文档
            es_doc = {
                "segment_id": segment.id,
                "literature_id": segment.literature_id,
                "project_ids": project_ids,
                "segment_type": segment.segment_type,
                "section_title": segment.section_title,
                "content": segment.content,
                "page_number": segment.page_number,
                "paragraph_index": segment.paragraph_index,
                "structured_data": segment.structured_data or {},
                "extraction_confidence": float(segment.extraction_confidence) if segment.extraction_confidence else 0.0,
                "literature_title": literature.title,
                "literature_authors": literature.authors or [],
                "publication_year": literature.publication_year,
                "created_at": segment.created_at.isoformat() if segment.created_at else None
            }

            # 添加内容嵌入
            if content_embedding:
                es_doc["content_embedding"] = content_embedding

            # 索引到Elasticsearch
            await self.es_client.index_document(
                index_name="literature_segments_index",
                doc_id=str(segment_id),
                document=es_doc
            )

            logger.info(f"Successfully synced literature segment {segment_id} to Elasticsearch")

        except Exception as e:
            logger.error(f"Failed to sync literature segment {segment_id} to ES: {e}")
            raise

    async def sync_project_literature_association(self, project_id: int, literature_id: int, db: Session):
        """同步项目文献关联到Elasticsearch（更新段落的project_ids字段）"""
        try:
            # 获取该文献的所有段落
            segments = db.query(LiteratureSegment).filter(
                LiteratureSegment.literature_id == literature_id
            ).all()

            for segment in segments:
                # 获取该文献的所有关联项目
                literature = segment.literature
                project_ids = [p.id for p in literature.projects] if literature.projects else []

                # 更新ES中的段落文档
                update_doc = {"project_ids": project_ids}

                await self.es_client.update_document(
                    index_name="literature_segments_index",
                    doc_id=str(segment.id),
                    document=update_doc
                )

            logger.info(f"Updated project associations for literature {literature_id}")

        except Exception as e:
            logger.error(f"Failed to sync project literature association: {e}")
            raise

    async def remove_literature_from_es(self, literature_id: int):
        """从Elasticsearch移除文献"""
        try:
            # 删除文献索引
            await self.es_client.delete_document(
                index_name="literature_index",
                doc_id=str(literature_id)
            )

            # 删除相关段落（需要先查询出段落ID）
            search_query = {
                "query": {"term": {"literature_id": literature_id}},
                "size": 1000,
                "_source": False
            }

            response = await self.es_client.search(
                index_name="literature_segments_index",
                query=search_query
            )

            # 删除所有段落
            for hit in response.get("hits", {}).get("hits", []):
                segment_id = hit["_id"]
                await self.es_client.delete_document(
                    index_name="literature_segments_index",
                    doc_id=segment_id
                )

            logger.info(f"Removed literature {literature_id} from Elasticsearch")

        except Exception as e:
            logger.error(f"Failed to remove literature {literature_id} from ES: {e}")
            raise

    async def remove_literature_segment_from_es(self, segment_id: int):
        """从Elasticsearch移除文献段落"""
        try:
            await self.es_client.delete_document(
                index_name="literature_segments_index",
                doc_id=str(segment_id)
            )

            logger.info(f"Removed literature segment {segment_id} from Elasticsearch")

        except Exception as e:
            logger.error(f"Failed to remove literature segment {segment_id} from ES: {e}")
            raise

    async def bulk_sync_literature_to_es(self, literature_ids: List[int], db: Session):
        """批量同步文献到Elasticsearch"""
        success_count = 0
        failed_count = 0

        for literature_id in literature_ids:
            try:
                await self.sync_literature_to_es(literature_id, db)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to sync literature {literature_id}: {e}")
                failed_count += 1

        logger.info(f"Bulk sync completed: {success_count} success, {failed_count} failed")
        return {"success": success_count, "failed": failed_count}

    async def verify_sync_status(self, literature_id: int) -> Dict[str, bool]:
        """验证文献同步状态"""
        try:
            # 检查文献是否在ES中存在
            literature_exists = False
            try:
                await self.es_client.client.get(
                    index=f"{self.es_client.index_prefix}literature_index",
                    id=str(literature_id)
                )
                literature_exists = True
            except:
                pass

            # 检查段落数量是否一致
            segments_query = {
                "query": {"term": {"literature_id": literature_id}},
                "size": 0
            }

            es_response = await self.es_client.search(
                index_name="literature_segments_index",
                query=segments_query
            )

            es_segment_count = es_response.get("hits", {}).get("total", {}).get("value", 0)

            return {
                "literature_in_es": literature_exists,
                "es_segment_count": es_segment_count
            }

        except Exception as e:
            logger.error(f"Failed to verify sync status for literature {literature_id}: {e}")
            return {"literature_in_es": False, "es_segment_count": 0}

# 全局服务实例
data_sync_service = DataSyncService()

async def get_data_sync_service():
    """获取数据同步服务实例"""
    if not data_sync_service.es_client:
        await data_sync_service.init_elasticsearch()
    return data_sync_service