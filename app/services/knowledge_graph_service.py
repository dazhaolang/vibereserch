"""
Knowledge Graph and Citation Network Service
知识图谱和引用网络服务 - 创新性文献关系可视化
"""

import asyncio
import json
import networkx as nx
from typing import List, Dict, Optional, Any, Tuple, Set
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
import numpy as np
from collections import defaultdict, Counter
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

from app.core.database import get_db
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.services.multi_model_ai_service import MultiModelAIService
from app.core.config import settings


class KnowledgeGraphService:
    """
    知识图谱和引用网络服务

    突破性功能:
    1. 动态知识图谱构建 - 基于文献内容的实体关系图
    2. 智能引用网络分析 - 发现隐藏的学术关系
    3. 作者协作网络映射 - 识别关键研究者和团队
    4. 研究主题演化图谱 - 跟踪知识发展轨迹
    5. 跨学科知识连接 - 发现学科间的知识桥梁
    """

    def __init__(self):
        self.ai_service = MultiModelAIService()
        self.knowledge_graphs = {}  # 缓存已构建的图谱
        self.entity_cache = {}  # 实体提取缓存

    async def build_project_knowledge_graph(
        self,
        project_id: int,
        include_entities: List[str] = None,  # ['authors', 'concepts', 'methods', 'materials']
        depth_level: int = 2  # 图谱深度
    ) -> Dict[str, Any]:
        """
        构建项目知识图谱

        突破性功能:
        - 多层次实体关系提取
        - 语义相似度聚类
        - 动态图谱布局优化
        - 交互式可视化数据
        """
        try:
            if include_entities is None:
                include_entities = ['authors', 'concepts', 'methods', 'materials', 'institutions']

            db = next(get_db())

            # 1. 获取项目文献
            literature_list = db.query(Literature).filter(
                Literature.projects.any(id=project_id)
            ).all()

            if not literature_list:
                return {"error": "项目中没有文献数据"}

            # 2. 提取多类型实体
            entities = await self._extract_multi_type_entities(literature_list, include_entities)

            # 3. 构建实体关系网络
            relationships = await self._build_entity_relationships(entities, literature_list)

            # 4. 创建NetworkX图对象
            graph = await self._create_networkx_graph(entities, relationships)

            # 5. 计算图谱指标
            graph_metrics = await self._calculate_graph_metrics(graph)

            # 6. 生成可视化数据
            visualization_data = await self._generate_visualization_data(
                graph, entities, relationships, depth_level
            )

            # 7. 识别关键节点和路径
            key_insights = await self._identify_key_insights(graph, entities, literature_list)

            return {
                "project_id": project_id,
                "literature_count": len(literature_list),
                "entity_types": include_entities,
                "entities": entities,
                "relationships": relationships,
                "graph_metrics": graph_metrics,
                "visualization_data": visualization_data,
                "key_insights": key_insights,
                "knowledge_clusters": await self._identify_knowledge_clusters(graph, entities),
                "evolution_timeline": await self._create_knowledge_evolution_timeline(literature_list, entities),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"构建知识图谱时出错: {e}")
            return {"error": str(e)}

    async def analyze_citation_network(
        self,
        project_id: int,
        analysis_depth: str = "comprehensive"  # basic, standard, comprehensive
    ) -> Dict[str, Any]:
        """
        分析引用网络

        突破性功能:
        - 智能引用关系发现
        - 学术影响力评估
        - 引用模式分析
        - 知识传播路径追踪
        """
        try:
            db = next(get_db())

            # 1. 获取项目文献及其引用信息
            literature_list = db.query(Literature).filter(
                Literature.projects.any(id=project_id)
            ).all()

            # 2. 构建引用网络图
            citation_graph = await self._build_citation_network_graph(literature_list)

            # 3. 分析引用模式
            citation_patterns = await self._analyze_citation_patterns(citation_graph, literature_list)

            # 4. 计算影响力指标
            influence_metrics = await self._calculate_influence_metrics(citation_graph, literature_list)

            # 5. 识别关键论文和作者
            key_papers_authors = await self._identify_key_papers_and_authors(
                citation_graph, literature_list, influence_metrics
            )

            # 6. 分析知识传播路径
            knowledge_flow = await self._analyze_knowledge_flow_paths(citation_graph, literature_list)

            # 7. 预测潜在引用关系
            potential_citations = await self._predict_potential_citations(literature_list)

            return {
                "project_id": project_id,
                "analysis_depth": analysis_depth,
                "literature_count": len(literature_list),
                "citation_network": {
                    "nodes": citation_graph.number_of_nodes(),
                    "edges": citation_graph.number_of_edges(),
                    "density": nx.density(citation_graph),
                    "components": nx.number_connected_components(citation_graph.to_undirected())
                },
                "citation_patterns": citation_patterns,
                "influence_metrics": influence_metrics,
                "key_papers_authors": key_papers_authors,
                "knowledge_flow": knowledge_flow,
                "potential_citations": potential_citations,
                "network_visualization": await self._generate_citation_network_visualization(citation_graph),
                "temporal_analysis": await self._analyze_temporal_citation_patterns(literature_list),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"分析引用网络时出错: {e}")
            return {"error": str(e)}

    async def discover_research_collaborations(
        self,
        project_id: int,
        collaboration_type: str = "all"  # authors, institutions, countries, all
    ) -> Dict[str, Any]:
        """
        发现研究协作关系

        突破性功能:
        - 多维度协作网络分析
        - 协作强度量化
        - 潜在协作机会识别
        - 学科交叉分析
        """
        try:
            db = next(get_db())

            literature_list = db.query(Literature).filter(
                Literature.projects.any(id=project_id)
            ).all()

            # 1. 提取协作实体
            collaboration_entities = await self._extract_collaboration_entities(
                literature_list, collaboration_type
            )

            # 2. 构建协作网络
            collaboration_network = await self._build_collaboration_network(
                collaboration_entities, literature_list
            )

            # 3. 分析协作模式
            collaboration_patterns = await self._analyze_collaboration_patterns(
                collaboration_network, literature_list
            )

            # 4. 识别核心协作者
            core_collaborators = await self._identify_core_collaborators(
                collaboration_network, collaboration_entities
            )

            # 5. 发现潜在协作机会
            collaboration_opportunities = await self._discover_collaboration_opportunities(
                collaboration_network, literature_list
            )

            # 6. 分析学科交叉
            interdisciplinary_analysis = await self._analyze_interdisciplinary_connections(
                collaboration_network, literature_list
            )

            return {
                "project_id": project_id,
                "collaboration_type": collaboration_type,
                "collaboration_entities": collaboration_entities,
                "network_metrics": {
                    "total_collaborators": len(collaboration_entities),
                    "collaboration_pairs": collaboration_network.number_of_edges(),
                    "network_density": nx.density(collaboration_network),
                    "clustering_coefficient": nx.average_clustering(collaboration_network)
                },
                "collaboration_patterns": collaboration_patterns,
                "core_collaborators": core_collaborators,
                "collaboration_opportunities": collaboration_opportunities,
                "interdisciplinary_analysis": interdisciplinary_analysis,
                "network_visualization": await self._generate_collaboration_visualization(collaboration_network),
                "temporal_evolution": await self._analyze_collaboration_evolution(literature_list),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"发现研究协作关系时出错: {e}")
            return {"error": str(e)}

    async def create_semantic_concept_map(
        self,
        project_id: int,
        concept_granularity: str = "medium"  # fine, medium, coarse
    ) -> Dict[str, Any]:
        """
        创建语义概念图

        突破性功能:
        - 深度语义概念提取
        - 概念层次结构构建
        - 语义相似度聚类
        - 概念演化追踪
        """
        try:
            db = next(get_db())

            literature_list = db.query(Literature).filter(
                Literature.projects.any(id=project_id)
            ).all()

            # 1. 提取语义概念
            semantic_concepts = await self._extract_semantic_concepts(
                literature_list, concept_granularity
            )

            # 2. 构建概念层次结构
            concept_hierarchy = await self._build_concept_hierarchy(semantic_concepts)

            # 3. 计算概念相似度矩阵
            similarity_matrix = await self._compute_concept_similarity_matrix(semantic_concepts)

            # 4. 聚类相关概念
            concept_clusters = await self._cluster_related_concepts(
                semantic_concepts, similarity_matrix
            )

            # 5. 追踪概念演化
            concept_evolution = await self._track_concept_evolution(
                semantic_concepts, literature_list
            )

            # 6. 识别新兴和衰落概念
            emerging_declining = await self._identify_emerging_declining_concepts(
                semantic_concepts, literature_list
            )

            return {
                "project_id": project_id,
                "concept_granularity": concept_granularity,
                "semantic_concepts": semantic_concepts,
                "concept_hierarchy": concept_hierarchy,
                "concept_clusters": concept_clusters,
                "concept_evolution": concept_evolution,
                "emerging_concepts": emerging_declining["emerging"],
                "declining_concepts": emerging_declining["declining"],
                "concept_map_visualization": await self._generate_concept_map_visualization(
                    semantic_concepts, concept_clusters, concept_hierarchy
                ),
                "cross_concept_insights": await self._analyze_cross_concept_insights(
                    semantic_concepts, literature_list
                ),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"创建语义概念图时出错: {e}")
            return {"error": str(e)}

    # =============== 私有辅助方法 ===============

    async def _extract_multi_type_entities(
        self,
        literature_list: List[Literature],
        entity_types: List[str]
    ) -> Dict[str, List[Dict]]:
        """提取多类型实体"""
        entities = {entity_type: [] for entity_type in entity_types}

        for literature in literature_list:
            try:
                # 构建实体提取提示
                extraction_prompt = f"""
                从以下文献中提取指定类型的实体:

                标题: {literature.title}
                摘要: {literature.abstract}
                作者: {literature.authors}

                请提取以下类型的实体:
                {', '.join(entity_types)}

                对于每种类型，提取具体的实体名称，并评估其在文献中的重要性(0-1)。

                返回JSON格式：
                {{
                    "authors": [{{ "name": "作者名", "importance": 0.9 }}],
                    "concepts": [{{ "name": "概念名", "importance": 0.8 }}],
                    "methods": [{{ "name": "方法名", "importance": 0.7 }}],
                    ...
                }}
                """

                response = await self.ai_service.chat_completion(
                    [{"role": "user", "content": extraction_prompt}],
                    temperature=0.2
                )

                if response and response.get("choices"):
                    content = response["choices"][0]["message"]["content"]
                    try:
                        extracted_entities = json.loads(content)

                        for entity_type in entity_types:
                            if entity_type in extracted_entities:
                                for entity in extracted_entities[entity_type]:
                                    entity["literature_id"] = literature.id
                                    entity["literature_title"] = literature.title
                                    entities[entity_type].append(entity)

                    except json.JSONDecodeError:
                        logger.warning(f"无法解析文献{literature.id}的实体提取结果")

            except Exception as e:
                logger.error(f"从文献{literature.id}提取实体时出错: {e}")
                continue

        return entities

    async def _build_entity_relationships(
        self,
        entities: Dict[str, List[Dict]],
        literature_list: List[Literature]
    ) -> List[Dict]:
        """构建实体关系"""
        relationships = []

        # 1. 基于共现的关系
        for lit in literature_list:
            lit_entities = []
            for entity_type, entity_list in entities.items():
                lit_entities.extend([
                    (entity["name"], entity_type)
                    for entity in entity_list
                    if entity["literature_id"] == lit.id
                ])

            # 为同一文献中的实体建立关系
            for i, (entity1, type1) in enumerate(lit_entities):
                for entity2, type2 in lit_entities[i+1:]:
                    relationships.append({
                        "source": entity1,
                        "target": entity2,
                        "source_type": type1,
                        "target_type": type2,
                        "relationship_type": "co_occurrence",
                        "strength": 1.0,
                        "literature_id": lit.id
                    })

        # 2. 基于语义相似度的关系
        # 这里可以添加更复杂的语义相似度计算

        return relationships

    async def _create_networkx_graph(
        self,
        entities: Dict[str, List[Dict]],
        relationships: List[Dict]
    ) -> nx.Graph:
        """创建NetworkX图对象"""
        G = nx.Graph()

        # 添加节点
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                G.add_node(
                    entity["name"],
                    type=entity_type,
                    importance=entity["importance"],
                    literature_id=entity["literature_id"]
                )

        # 添加边
        for rel in relationships:
            G.add_edge(
                rel["source"],
                rel["target"],
                relationship_type=rel["relationship_type"],
                strength=rel["strength"],
                literature_id=rel["literature_id"]
            )

        return G

    async def _calculate_graph_metrics(self, graph: nx.Graph) -> Dict[str, Any]:
        """计算图谱指标"""
        return {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "density": nx.density(graph),
            "average_clustering": nx.average_clustering(graph),
            "connected_components": nx.number_connected_components(graph),
            "diameter": nx.diameter(graph) if nx.is_connected(graph) else "N/A",
            "average_path_length": nx.average_shortest_path_length(graph) if nx.is_connected(graph) else "N/A"
        }

    async def _generate_visualization_data(
        self,
        graph: nx.Graph,
        entities: Dict[str, List[Dict]],
        relationships: List[Dict],
        depth_level: int
    ) -> Dict[str, Any]:
        """生成可视化数据"""
        # 使用spring layout计算节点位置
        pos = nx.spring_layout(graph, k=1, iterations=50)

        nodes = []
        for node, data in graph.nodes(data=True):
            nodes.append({
                "id": node,
                "type": data.get("type", "unknown"),
                "importance": data.get("importance", 0.5),
                "x": pos[node][0],
                "y": pos[node][1],
                "size": data.get("importance", 0.5) * 20 + 10
            })

        edges = []
        for source, target, data in graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "strength": data.get("strength", 1.0),
                "type": data.get("relationship_type", "unknown")
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "layout": "force-directed",
            "depth_level": depth_level
        }

    async def _identify_key_insights(
        self,
        graph: nx.Graph,
        entities: Dict[str, List[Dict]],
        literature_list: List[Literature]
    ) -> Dict[str, Any]:
        """识别关键洞察"""
        # 计算中心性指标
        betweenness = nx.betweenness_centrality(graph)
        closeness = nx.closeness_centrality(graph)
        degree = nx.degree_centrality(graph)

        # 找出最重要的节点
        key_nodes = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "most_central_entities": [{"entity": node, "centrality": score} for node, score in key_nodes],
            "key_bridges": await self._find_bridge_entities(graph),
            "isolated_entities": list(nx.isolates(graph)),
            "largest_component_size": len(max(nx.connected_components(graph), key=len)) if graph.nodes() else 0
        }

    # =============== 占位符方法 ===============
    # 这些方法的具体实现将在后续完善

    async def _identify_knowledge_clusters(self, graph, entities):
        """识别知识集群"""
        return {"clusters": []}

    async def _create_knowledge_evolution_timeline(self, literature_list, entities):
        """创建知识演化时间线"""
        return {"timeline": []}

    async def _build_citation_network_graph(self, literature_list):
        """构建引用网络图"""
        return nx.DiGraph()

    async def _analyze_citation_patterns(self, citation_graph, literature_list):
        """分析引用模式"""
        return {"patterns": []}

    async def _calculate_influence_metrics(self, citation_graph, literature_list):
        """计算影响力指标"""
        return {"metrics": {}}

    async def _identify_key_papers_and_authors(self, citation_graph, literature_list, influence_metrics):
        """识别关键论文和作者"""
        return {"key_papers": [], "key_authors": []}

    async def _analyze_knowledge_flow_paths(self, citation_graph, literature_list):
        """分析知识流动路径"""
        return {"flow_paths": []}

    async def _predict_potential_citations(self, literature_list):
        """预测潜在引用关系"""
        return {"potential_citations": []}

    async def _generate_citation_network_visualization(self, citation_graph):
        """生成引用网络可视化"""
        return {"visualization": {}}

    async def _analyze_temporal_citation_patterns(self, literature_list):
        """分析时间引用模式"""
        return {"temporal_patterns": []}

    async def _extract_collaboration_entities(self, literature_list, collaboration_type):
        """提取协作实体"""
        return {"entities": []}

    async def _build_collaboration_network(self, collaboration_entities, literature_list):
        """构建协作网络"""
        return nx.Graph()

    async def _analyze_collaboration_patterns(self, collaboration_network, literature_list):
        """分析协作模式"""
        return {"patterns": []}

    async def _identify_core_collaborators(self, collaboration_network, collaboration_entities):
        """识别核心协作者"""
        return {"core_collaborators": []}

    async def _discover_collaboration_opportunities(self, collaboration_network, literature_list):
        """发现协作机会"""
        return {"opportunities": []}

    async def _analyze_interdisciplinary_connections(self, collaboration_network, literature_list):
        """分析学科交叉"""
        return {"interdisciplinary": []}

    async def _generate_collaboration_visualization(self, collaboration_network):
        """生成协作可视化"""
        return {"visualization": {}}

    async def _analyze_collaboration_evolution(self, literature_list):
        """分析协作演化"""
        return {"evolution": []}

    async def _extract_semantic_concepts(self, literature_list, concept_granularity):
        """提取语义概念"""
        return {"concepts": []}

    async def _build_concept_hierarchy(self, semantic_concepts):
        """构建概念层次结构"""
        return {"hierarchy": {}}

    async def _compute_concept_similarity_matrix(self, semantic_concepts):
        """计算概念相似度矩阵"""
        return np.array([])

    async def _cluster_related_concepts(self, semantic_concepts, similarity_matrix):
        """聚类相关概念"""
        return {"clusters": []}

    async def _track_concept_evolution(self, semantic_concepts, literature_list):
        """追踪概念演化"""
        return {"evolution": []}

    async def _identify_emerging_declining_concepts(self, semantic_concepts, literature_list):
        """识别新兴和衰落概念"""
        return {"emerging": [], "declining": []}

    async def _generate_concept_map_visualization(self, semantic_concepts, concept_clusters, concept_hierarchy):
        """生成概念图可视化"""
        return {"visualization": {}}

    async def _analyze_cross_concept_insights(self, semantic_concepts, literature_list):
        """分析跨概念洞察"""
        return {"insights": []}

    async def _find_bridge_entities(self, graph):
        """找出桥接实体"""
        bridges = list(nx.bridges(graph))
        return [{"bridge": bridge} for bridge in bridges[:10]]


# 创建全局实例
knowledge_graph_service = KnowledgeGraphService()