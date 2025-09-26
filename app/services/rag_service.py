"""
RAG检索增强生成服务 - 使用Elasticsearch进行语义/关键词混合检索
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from loguru import logger

from app.core.config import settings
from app.models.literature import LiteratureSegment, Literature
from app.models.experience import MainExperience
from app.services.enhanced_search_service import get_enhanced_search_service
from app.services.data_sync_service import DataSyncService
from openai import AsyncOpenAI


class RAGService:
    """基于Elasticsearch的RAG检索服务"""

    def __init__(self, db: Session):
        self.db = db
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._search_service = None

    async def search_relevant_segments(
        self,
        query: str,
        project_id: int,
        top_k: int = 10,
        similarity_threshold: float = 0.25
    ) -> List[Dict]:
        """从Elasticsearch中检索相关文献段落"""
        try:
            search_service = await self._get_search_service()

            search_response = await search_service.hybrid_search(
                query=query,
                project_id=project_id,
                top_k=top_k * 2  # 额外检索用于后续筛选
            )

            segments = self._format_es_results(search_response)

            # 如果结果为空，尝试同步项目段落到Elasticsearch后重试一次
            if not segments:
                await self._sync_project_segments(project_id)
                search_response = await search_service.hybrid_search(
                    query=query,
                    project_id=project_id,
                    top_k=top_k * 2
                )
                segments = self._format_es_results(search_response)

            # 过滤低分结果并限制返回数量
            filtered_segments = [
                segment for segment in segments
                if segment.get("similarity_score", 0) >= similarity_threshold
            ]

            return filtered_segments[:top_k]

        except Exception as e:
            logger.error(f"RAG搜索失败: {e}")
            return []

    async def _get_search_service(self):
        if self._search_service is None:
            self._search_service = await get_enhanced_search_service()
        return self._search_service

    async def _sync_project_segments(self, project_id: int, limit: int = 200):
        """将项目相关的文献段落同步到Elasticsearch"""
        try:
            data_sync = DataSyncService()
            await data_sync.init_elasticsearch()

            segments = (
                self.db.query(LiteratureSegment)
                .join(Literature)
                .filter(Literature.projects.any(id=project_id))
                .limit(limit)
                .all()
            )

            for segment in segments:
                await data_sync.sync_literature_segment_to_es(segment.id, self.db)

        except Exception as e:
            logger.error(f"同步项目段落到Elasticsearch失败: {e}")

    def _format_es_results(self, search_response: Dict[str, any]) -> List[Dict]:
        """将Elasticsearch返回结果转换为RAG所需格式"""
        results = []
        for item in search_response.get("results", []):
            results.append({
                "id": item.get("segment_id"),
                "content": item.get("content"),
                "segment_type": item.get("section_title"),
                "section_title": item.get("section_title"),
                "structured_data": item.get("structured_data", {}),
                "extraction_confidence": item.get("extraction_confidence", 0.0),
                "literature_title": item.get("literature_title"),
                "authors": item.get("literature_authors", []),
                "publication_year": item.get("publication_year"),
                "similarity_score": item.get("score", 0.0),
                "search_type": search_response.get("search_type", "hybrid")
            })
        return results

    async def _get_text_embedding(self, text: str) -> Optional[List[float]]:
        """保持与现有接口兼容的嵌入生成方法"""
        try:
            response = await self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"获取文本嵌入失败: {e}")
            return None

    async def build_embeddings_for_project(self, project_id: int):
        """同步项目文献和段落到Elasticsearch，确保有可检索的向量"""
        try:
            data_sync = DataSyncService()
            await data_sync.init_elasticsearch()

            # 同步项目下的文献
            literature_items = (
                self.db.query(Literature)
                .filter(Literature.projects.any(id=project_id))
                .all()
            )

            for literature in literature_items:
                await data_sync.sync_literature_to_es(literature.id, self.db)

            # 同步项目段落
            segment_items = (
                self.db.query(LiteratureSegment)
                .join(Literature)
                .filter(Literature.projects.any(id=project_id))
                .all()
            )

            for segment in segment_items:
                await data_sync.sync_literature_segment_to_es(segment.id, self.db)

            logger.info(f"项目 {project_id} 的文献和段落已同步到Elasticsearch")

        except Exception as e:
            logger.error(f"构建项目 {project_id} 向量索引失败: {e}")

    async def search_main_experiences(
        self,
        project_id: int,
        research_domain: str,
        top_k: int = 3
    ) -> List[MainExperience]:
        """获取项目主经验信息"""
        try:
            return (
                self.db.query(MainExperience)
                .filter(
                    MainExperience.project_id == project_id,
                    MainExperience.research_domain == research_domain
                )
                .order_by(MainExperience.completeness_score.desc())
                .limit(top_k)
                .all()
            )
        except Exception as e:
            logger.error(f"查询主经验失败: {e}")
            return []
