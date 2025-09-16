"""
基于Elasticsearch的增强搜索服务
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from app.core.elasticsearch import get_elasticsearch
from app.services.ai_service import AIService
import logging

logger = logging.getLogger(__name__)

class EnhancedSearchService:
    """基于Elasticsearch的增强搜索服务"""

    def __init__(self):
        self.ai_service = AIService()
        self.es_client = None

    async def init_elasticsearch(self):
        """初始化Elasticsearch客户端"""
        self.es_client = await get_elasticsearch()

    async def hybrid_search(
        self,
        query: str,
        project_id: Optional[int] = None,
        search_type: str = "hybrid",  # hybrid, semantic, keyword
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        混合搜索：语义搜索 + 关键词搜索

        Args:
            query: 搜索查询
            project_id: 项目ID，用于过滤结果
            search_type: 搜索类型 (hybrid, semantic, keyword)
            top_k: 返回结果数量
            filters: 额外过滤条件

        Returns:
            搜索结果字典
        """
        try:
            if search_type == "semantic":
                return await self.semantic_search(query, project_id, top_k, filters)
            elif search_type == "keyword":
                return await self.keyword_search(query, project_id, top_k, filters)
            else:
                # 混合搜索
                semantic_results = await self.semantic_search(query, project_id, top_k * 2, filters)
                keyword_results = await self.keyword_search(query, project_id, top_k * 2, filters)
                return self.merge_and_rerank(semantic_results, keyword_results, top_k)

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise

    async def semantic_search(
        self,
        query: str,
        project_id: Optional[int] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """语义向量搜索"""
        try:
            # 生成查询向量
            query_embedding = await self.ai_service.get_embedding(query)

            # 构建过滤条件
            filter_conditions = []
            if project_id:
                filter_conditions.append({"term": {"project_ids": project_id}})

            if filters:
                if filters.get("publication_year_range"):
                    year_range = filters["publication_year_range"]
                    filter_conditions.append({
                        "range": {
                            "publication_year": {
                                "gte": year_range.get("start"),
                                "lte": year_range.get("end")
                            }
                        }
                    })

                if filters.get("categories"):
                    filter_conditions.append({
                        "terms": {"category": filters["categories"]}
                    })

                if filters.get("keywords"):
                    filter_conditions.append({
                        "terms": {"keywords": filters["keywords"]}
                    })

            # 构建语义搜索查询
            search_body = {
                "size": top_k,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": filter_conditions
                            }
                        } if filter_conditions else {"match_all": {}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'content_embedding') + 1.0",
                            "params": {"query_vector": query_embedding}
                        }
                    }
                },
                "_source": [
                    "segment_id", "literature_id", "content", "section_title",
                    "literature_title", "literature_authors", "publication_year",
                    "structured_data", "extraction_confidence"
                ]
            }

            response = await self.es_client.search(
                index_name="literature_segments_index",
                query=search_body
            )

            return self._format_search_results(response, "semantic")

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise

    async def keyword_search(
        self,
        query: str,
        project_id: Optional[int] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """关键词搜索"""
        try:
            # 构建过滤条件
            filter_conditions = []
            if project_id:
                filter_conditions.append({"term": {"project_ids": project_id}})

            if filters:
                if filters.get("publication_year_range"):
                    year_range = filters["publication_year_range"]
                    filter_conditions.append({
                        "range": {
                            "publication_year": {
                                "gte": year_range.get("start"),
                                "lte": year_range.get("end")
                            }
                        }
                    })

                if filters.get("categories"):
                    filter_conditions.append({
                        "terms": {"category": filters["categories"]}
                    })

            # 构建关键词搜索查询
            search_body = {
                "size": top_k,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": [
                                        "content^2",  # 内容权重更高
                                        "section_title^1.5",
                                        "literature_title",
                                        "content.chinese^1.5"  # 中文分析器
                                    ],
                                    "type": "best_fields",
                                    "fuzziness": "AUTO"
                                }
                            }
                        ],
                        "filter": filter_conditions
                    }
                },
                "highlight": {
                    "fields": {
                        "content": {
                            "fragment_size": 200,
                            "number_of_fragments": 3,
                            "pre_tags": ["<mark>"],
                            "post_tags": ["</mark>"]
                        },
                        "section_title": {
                            "fragment_size": 100,
                            "number_of_fragments": 1
                        }
                    }
                },
                "_source": [
                    "segment_id", "literature_id", "content", "section_title",
                    "literature_title", "literature_authors", "publication_year",
                    "structured_data", "extraction_confidence"
                ]
            }

            response = await self.es_client.search(
                index_name="literature_segments_index",
                query=search_body
            )

            return self._format_search_results(response, "keyword")

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            raise

    async def literature_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20
    ) -> Dict[str, Any]:
        """文献级别搜索"""
        try:
            # 生成查询向量（如果需要语义搜索）
            query_embedding = await self.ai_service.get_embedding(query)

            # 构建过滤条件
            filter_conditions = []
            if filters:
                if filters.get("publication_year_range"):
                    year_range = filters["publication_year_range"]
                    filter_conditions.append({
                        "range": {
                            "publication_year": {
                                "gte": year_range.get("start"),
                                "lte": year_range.get("end")
                            }
                        }
                    })

                if filters.get("categories"):
                    filter_conditions.append({
                        "terms": {"category": filters["categories"]}
                    })

                if filters.get("min_quality_score"):
                    filter_conditions.append({
                        "range": {"quality_score": {"gte": filters["min_quality_score"]}}
                    })

            # 混合查询：语义搜索 + 关键词搜索
            search_body = {
                "size": top_k,
                "query": {
                    "bool": {
                        "should": [
                            # 语义搜索
                            {
                                "script_score": {
                                    "query": {"match_all": {}},
                                    "script": {
                                        "source": "cosineSimilarity(params.query_vector, 'title_embedding') + 1.0",
                                        "params": {"query_vector": query_embedding}
                                    }
                                }
                            },
                            # 关键词搜索
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^3", "abstract^2", "keywords^1.5"],
                                    "type": "best_fields",
                                    "boost": 2.0
                                }
                            }
                        ],
                        "filter": filter_conditions,
                        "minimum_should_match": 1
                    }
                },
                "highlight": {
                    "fields": {
                        "title": {"number_of_fragments": 1},
                        "abstract": {"fragment_size": 200, "number_of_fragments": 2}
                    }
                },
                "_source": [
                    "literature_id", "title", "abstract", "authors", "journal",
                    "publication_year", "doi", "keywords", "quality_score",
                    "citation_count", "category"
                ]
            }

            response = await self.es_client.search(
                index_name="literature_index",
                query=search_body
            )

            return self._format_literature_results(response)

        except Exception as e:
            logger.error(f"Literature search failed: {e}")
            raise

    def merge_and_rerank(
        self,
        semantic_results: Dict[str, Any],
        keyword_results: Dict[str, Any],
        top_k: int
    ) -> Dict[str, Any]:
        """合并和重新排序搜索结果"""
        try:
            # 提取结果
            semantic_hits = semantic_results.get("results", [])
            keyword_hits = keyword_results.get("results", [])

            # 创建结果字典
            merged_results = {}

            # 添加语义搜索结果
            for hit in semantic_hits:
                segment_id = hit["segment_id"]
                hit["semantic_score"] = hit["score"]
                hit["keyword_score"] = 0.0
                merged_results[segment_id] = hit

            # 添加关键词搜索结果
            for hit in keyword_hits:
                segment_id = hit["segment_id"]
                if segment_id in merged_results:
                    # 已存在，添加关键词分数
                    merged_results[segment_id]["keyword_score"] = hit["score"]
                    merged_results[segment_id]["highlights"] = hit.get("highlights", {})
                else:
                    # 新结果
                    hit["semantic_score"] = 0.0
                    hit["keyword_score"] = hit["score"]
                    merged_results[segment_id] = hit

            # 计算混合分数并排序
            for result in merged_results.values():
                # 混合分数：语义搜索权重0.6，关键词搜索权重0.4
                result["hybrid_score"] = (
                    result["semantic_score"] * 0.6 + result["keyword_score"] * 0.4
                )

            # 按混合分数排序并返回前top_k个结果
            sorted_results = sorted(
                merged_results.values(),
                key=lambda x: x["hybrid_score"],
                reverse=True
            )[:top_k]

            return {
                "total": len(sorted_results),
                "results": sorted_results,
                "search_type": "hybrid",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to merge and rerank results: {e}")
            raise

    def _format_search_results(self, es_response: Dict[str, Any], search_type: str) -> Dict[str, Any]:
        """格式化搜索结果"""
        hits = es_response.get("hits", {})
        total = hits.get("total", {}).get("value", 0)

        results = []
        for hit in hits.get("hits", []):
            source = hit["_source"]
            result = {
                "segment_id": source.get("segment_id"),
                "literature_id": source.get("literature_id"),
                "content": source.get("content"),
                "section_title": source.get("section_title"),
                "literature_title": source.get("literature_title"),
                "literature_authors": source.get("literature_authors", []),
                "publication_year": source.get("publication_year"),
                "structured_data": source.get("structured_data", {}),
                "extraction_confidence": source.get("extraction_confidence", 0.0),
                "score": hit["_score"],
                "highlights": hit.get("highlight", {})
            }
            results.append(result)

        return {
            "total": total,
            "results": results,
            "search_type": search_type,
            "timestamp": datetime.now().isoformat()
        }

    def _format_literature_results(self, es_response: Dict[str, Any]) -> Dict[str, Any]:
        """格式化文献搜索结果"""
        hits = es_response.get("hits", {})
        total = hits.get("total", {}).get("value", 0)

        results = []
        for hit in hits.get("hits", []):
            source = hit["_source"]
            result = {
                "literature_id": source.get("literature_id"),
                "title": source.get("title"),
                "abstract": source.get("abstract"),
                "authors": source.get("authors", []),
                "journal": source.get("journal"),
                "publication_year": source.get("publication_year"),
                "doi": source.get("doi"),
                "keywords": source.get("keywords", []),
                "quality_score": source.get("quality_score", 0.0),
                "citation_count": source.get("citation_count", 0),
                "category": source.get("category"),
                "score": hit["_score"],
                "highlights": hit.get("highlight", {})
            }
            results.append(result)

        return {
            "total": total,
            "results": results,
            "search_type": "literature",
            "timestamp": datetime.now().isoformat()
        }

# 全局搜索服务实例
enhanced_search_service = EnhancedSearchService()

async def get_enhanced_search_service():
    """获取增强搜索服务实例"""
    if not enhanced_search_service.es_client:
        await enhanced_search_service.init_elasticsearch()
    return enhanced_search_service