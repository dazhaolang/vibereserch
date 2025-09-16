"""
RAG检索增强生成服务
"""

from typing import List, Dict, Optional, Tuple
import asyncio
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
import openai
from openai import AsyncOpenAI
from loguru import logger

from app.core.config import settings
from app.models.literature import LiteratureSegment, Literature
from app.models.experience import MainExperience

class RAGService:
    """RAG检索服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        
    async def search_relevant_segments(
        self,
        query: str,
        project_id: int,
        top_k: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict]:
        """
        搜索相关文献段落
        
        Args:
            query: 查询文本
            project_id: 项目ID
            top_k: 返回数量
            similarity_threshold: 相似度阈值
            
        Returns:
            相关段落列表
        """
        try:
            # 生成查询向量
            query_embedding = await self._get_text_embedding(query)
            
            if not query_embedding:
                return []
            
            # 向量相似度搜索
            vector_results = await self._vector_similarity_search(
                query_embedding, project_id, top_k * 2
            )
            
            # 关键词匹配搜索
            keyword_results = await self._keyword_search(query, project_id, top_k)
            
            # 合并和重排序结果
            combined_results = self._combine_and_rerank_results(
                vector_results, keyword_results, query, top_k
            )
            
            # 过滤低相似度结果
            filtered_results = [
                result for result in combined_results 
                if result.get("similarity_score", 0) >= similarity_threshold
            ]
            
            return filtered_results[:top_k]
            
        except Exception as e:
            logger.error(f"RAG搜索失败: {e}")
            return []
    
    async def _get_text_embedding(self, text: str) -> Optional[List[float]]:
        """获取文本向量嵌入"""
        try:
            response = await self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"获取文本嵌入失败: {e}")
            return None
    
    async def _vector_similarity_search(
        self,
        query_embedding: List[float],
        project_id: int,
        limit: int
    ) -> List[Dict]:
        """向量相似度搜索"""
        try:
            # 构建向量搜索SQL
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            sql = text("""
                SELECT 
                    ls.id,
                    ls.content,
                    ls.segment_type,
                    ls.section_title,
                    ls.structured_data,
                    ls.extraction_confidence,
                    l.title as literature_title,
                    l.authors,
                    l.publication_year,
                    (ls.content_embedding <=> :query_embedding::vector) as similarity_score
                FROM literature_segments ls
                JOIN literature l ON ls.literature_id = l.id
                JOIN project_literature_associations pla ON l.id = pla.literature_id
                WHERE pla.project_id = :project_id 
                    AND ls.content_embedding IS NOT NULL
                ORDER BY ls.content_embedding <=> :query_embedding::vector
                LIMIT :limit
            """)
            
            result = self.db.execute(sql, {
                "query_embedding": embedding_str,
                "project_id": project_id,
                "limit": limit
            })
            
            segments = []
            for row in result:
                segments.append({
                    "id": row.id,
                    "content": row.content,
                    "segment_type": row.segment_type,
                    "section_title": row.section_title,
                    "structured_data": row.structured_data,
                    "extraction_confidence": row.extraction_confidence,
                    "literature_title": row.literature_title,
                    "authors": row.authors,
                    "publication_year": row.publication_year,
                    "similarity_score": 1 - row.similarity_score,  # 转换为相似度
                    "search_type": "vector"
                })
            
            return segments
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    async def _keyword_search(
        self,
        query: str,
        project_id: int,
        limit: int
    ) -> List[Dict]:
        """关键词搜索"""
        try:
            # 提取查询关键词
            query_lower = query.lower()
            keywords = query_lower.split()
            
            # 构建关键词搜索SQL
            sql = text("""
                SELECT 
                    ls.id,
                    ls.content,
                    ls.segment_type,
                    ls.section_title,
                    ls.structured_data,
                    ls.extraction_confidence,
                    l.title as literature_title,
                    l.authors,
                    l.publication_year,
                    ts_rank(to_tsvector('english', ls.content), plainto_tsquery('english', :query)) as rank_score
                FROM literature_segments ls
                JOIN literature l ON ls.literature_id = l.id
                JOIN project_literature_associations pla ON l.id = pla.literature_id
                WHERE pla.project_id = :project_id
                    AND (
                        to_tsvector('english', ls.content) @@ plainto_tsquery('english', :query)
                        OR LOWER(ls.content) LIKE :query_pattern
                    )
                ORDER BY rank_score DESC
                LIMIT :limit
            """)
            
            query_pattern = f"%{query_lower}%"
            
            result = self.db.execute(sql, {
                "query": query,
                "query_pattern": query_pattern,
                "project_id": project_id,
                "limit": limit
            })
            
            segments = []
            for row in result:
                # 计算关键词匹配度
                content_lower = row.content.lower()
                keyword_matches = sum(1 for kw in keywords if kw in content_lower)
                keyword_score = keyword_matches / len(keywords) if keywords else 0
                
                segments.append({
                    "id": row.id,
                    "content": row.content,
                    "segment_type": row.segment_type,
                    "section_title": row.section_title,
                    "structured_data": row.structured_data,
                    "extraction_confidence": row.extraction_confidence,
                    "literature_title": row.literature_title,
                    "authors": row.authors,
                    "publication_year": row.publication_year,
                    "similarity_score": keyword_score,
                    "rank_score": float(row.rank_score) if row.rank_score else 0.0,
                    "search_type": "keyword"
                })
            
            return segments
            
        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
            return []
    
    def _combine_and_rerank_results(
        self,
        vector_results: List[Dict],
        keyword_results: List[Dict],
        query: str,
        top_k: int
    ) -> List[Dict]:
        """合并和重排序搜索结果"""
        try:
            # 合并结果，去重
            all_results = {}
            
            # 添加向量搜索结果
            for result in vector_results:
                segment_id = result["id"]
                result["vector_score"] = result["similarity_score"]
                result["keyword_score"] = 0.0
                all_results[segment_id] = result
            
            # 合并关键词搜索结果
            for result in keyword_results:
                segment_id = result["id"]
                if segment_id in all_results:
                    # 更新关键词评分
                    all_results[segment_id]["keyword_score"] = result["similarity_score"]
                    all_results[segment_id]["rank_score"] = result.get("rank_score", 0.0)
                else:
                    # 新结果
                    result["vector_score"] = 0.0
                    result["keyword_score"] = result["similarity_score"]
                    all_results[segment_id] = result
            
            # 计算综合评分并排序
            for result in all_results.values():
                # 综合评分：向量相似度(60%) + 关键词匹配(30%) + 提取置信度(10%)
                vector_score = result.get("vector_score", 0.0)
                keyword_score = result.get("keyword_score", 0.0)
                confidence = result.get("extraction_confidence", 0.5)
                
                result["final_score"] = (
                    vector_score * 0.6 + 
                    keyword_score * 0.3 + 
                    confidence * 0.1
                )
                
                # 更新最终相似度分数
                result["similarity_score"] = result["final_score"]
            
            # 按综合评分排序
            sorted_results = sorted(
                all_results.values(),
                key=lambda x: x["final_score"],
                reverse=True
            )
            
            return sorted_results[:top_k]
            
        except Exception as e:
            logger.error(f"结果合并重排序失败: {e}")
            return vector_results[:top_k]
    
    async def build_embeddings_for_project(self, project_id: int):
        """为项目构建向量嵌入"""
        try:
            logger.info(f"开始为项目 {project_id} 构建向量嵌入")
            
            # 获取项目所有文献段落
            segments = self.db.query(LiteratureSegment).join(Literature).filter(
                Literature.projects.any(id=project_id),
                LiteratureSegment.content_embedding.is_(None)
            ).all()
            
            if not segments:
                logger.info("所有段落已有向量嵌入")
                return
            
            # 批量生成嵌入
            batch_size = 50
            for i in range(0, len(segments), batch_size):
                batch = segments[i:i + batch_size]
                
                # 准备文本列表
                texts = [segment.content for segment in batch]
                
                # 批量获取嵌入
                embeddings = await self._get_batch_embeddings(texts)
                
                if embeddings:
                    # 更新数据库
                    for j, segment in enumerate(batch):
                        if j < len(embeddings):
                            segment.content_embedding = embeddings[j]
                    
                    self.db.commit()
                    logger.info(f"已处理 {i + len(batch)}/{len(segments)} 个段落")
                
                # 避免API限制
                await asyncio.sleep(1)
            
            logger.info(f"项目 {project_id} 向量嵌入构建完成")
            
        except Exception as e:
            logger.error(f"构建向量嵌入失败: {e}")
    
    async def _get_batch_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """批量获取文本嵌入"""
        try:
            # 清理和截断文本
            cleaned_texts = []
            for text in texts:
                cleaned_text = text.strip()[:8000]  # 限制长度
                if cleaned_text:
                    cleaned_texts.append(cleaned_text)
            
            if not cleaned_texts:
                return None
            
            response = await self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=cleaned_texts
            )
            
            return [data.embedding for data in response.data]
            
        except Exception as e:
            logger.error(f"批量获取嵌入失败: {e}")
            return None