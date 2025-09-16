"""
Knowledge Graph API - 知识图谱和引用网络API接口
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.knowledge_graph_service import knowledge_graph_service
from app.services.stream_progress_service import stream_progress_service


router = APIRouter()


# =============== Pydantic Models ===============

class KnowledgeGraphRequest(BaseModel):
    """知识图谱构建请求"""
    project_id: int = Field(..., description="项目ID")
    include_entities: Optional[List[str]] = Field(
        ["authors", "concepts", "methods", "materials", "institutions"],
        description="包含的实体类型"
    )
    depth_level: int = Field(2, description="图谱深度", ge=1, le=5)


class KnowledgeGraphResponse(BaseModel):
    """知识图谱响应"""
    project_id: int
    literature_count: int
    entity_types: List[str]
    entities: Dict[str, List[Dict[str, Any]]]
    relationships: List[Dict[str, Any]]
    graph_metrics: Dict[str, Any]
    visualization_data: Dict[str, Any]
    key_insights: Dict[str, Any]
    knowledge_clusters: Dict[str, Any]
    evolution_timeline: Dict[str, Any]
    timestamp: str


class CitationNetworkRequest(BaseModel):
    """引用网络分析请求"""
    project_id: int = Field(..., description="项目ID")
    analysis_depth: str = Field("comprehensive", description="分析深度")


class CitationNetworkResponse(BaseModel):
    """引用网络分析响应"""
    project_id: int
    analysis_depth: str
    literature_count: int
    citation_network: Dict[str, Any]
    citation_patterns: Dict[str, Any]
    influence_metrics: Dict[str, Any]
    key_papers_authors: Dict[str, Any]
    knowledge_flow: Dict[str, Any]
    potential_citations: Dict[str, Any]
    network_visualization: Dict[str, Any]
    temporal_analysis: Dict[str, Any]
    timestamp: str


class CollaborationAnalysisRequest(BaseModel):
    """协作关系分析请求"""
    project_id: int = Field(..., description="项目ID")
    collaboration_type: str = Field("all", description="协作类型")


class CollaborationAnalysisResponse(BaseModel):
    """协作关系分析响应"""
    project_id: int
    collaboration_type: str
    collaboration_entities: Dict[str, Any]
    network_metrics: Dict[str, Any]
    collaboration_patterns: Dict[str, Any]
    core_collaborators: Dict[str, Any]
    collaboration_opportunities: Dict[str, Any]
    interdisciplinary_analysis: Dict[str, Any]
    network_visualization: Dict[str, Any]
    temporal_evolution: Dict[str, Any]
    timestamp: str


class ConceptMapRequest(BaseModel):
    """语义概念图请求"""
    project_id: int = Field(..., description="项目ID")
    concept_granularity: str = Field("medium", description="概念粒度")


class ConceptMapResponse(BaseModel):
    """语义概念图响应"""
    project_id: int
    concept_granularity: str
    semantic_concepts: Dict[str, Any]
    concept_hierarchy: Dict[str, Any]
    concept_clusters: Dict[str, Any]
    concept_evolution: Dict[str, Any]
    emerging_concepts: List[str]
    declining_concepts: List[str]
    concept_map_visualization: Dict[str, Any]
    cross_concept_insights: Dict[str, Any]
    timestamp: str


# =============== API Endpoints ===============

@router.post("/knowledge-graph/build", response_model=KnowledgeGraphResponse)
async def build_knowledge_graph(
    request: KnowledgeGraphRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    构建项目知识图谱

    突破性功能:
    - 多层次实体关系提取
    - 语义相似度聚类
    - 动态图谱布局优化
    - 交互式可视化数据
    """
    try:
        task_id = f"knowledge_graph_{current_user.id}_{request.project_id}"

        await stream_progress_service.send_progress_update(
            task_id,
            "开始构建知识图谱",
            0,
            {"entity_types": request.include_entities}
        )

        # 执行知识图谱构建
        result = await knowledge_graph_service.build_project_knowledge_graph(
            project_id=request.project_id,
            include_entities=request.include_entities,
            depth_level=request.depth_level
        )

        await stream_progress_service.send_progress_update(
            task_id,
            "知识图谱构建完成",
            100,
            {
                "entities_count": len(result.get("entities", {})),
                "relationships_count": len(result.get("relationships", []))
            }
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return KnowledgeGraphResponse(**result)

    except Exception as e:
        await stream_progress_service.send_progress_update(
            task_id,
            f"知识图谱构建失败: {str(e)}",
            -1,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"知识图谱构建失败: {str(e)}")


@router.post("/knowledge-graph/citation-network", response_model=CitationNetworkResponse)
async def analyze_citation_network(
    request: CitationNetworkRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    分析引用网络

    突破性功能:
    - 智能引用关系发现
    - 学术影响力评估
    - 引用模式分析
    - 知识传播路径追踪
    """
    try:
        task_id = f"citation_network_{current_user.id}_{request.project_id}"

        await stream_progress_service.send_progress_update(
            task_id,
            "开始分析引用网络",
            0,
            {"analysis_depth": request.analysis_depth}
        )

        # 执行引用网络分析
        result = await knowledge_graph_service.analyze_citation_network(
            project_id=request.project_id,
            analysis_depth=request.analysis_depth
        )

        await stream_progress_service.send_progress_update(
            task_id,
            "引用网络分析完成",
            100,
            {"citation_count": result.get("citation_network", {}).get("edges", 0)}
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return CitationNetworkResponse(**result)

    except Exception as e:
        await stream_progress_service.send_progress_update(
            task_id,
            f"引用网络分析失败: {str(e)}",
            -1,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"引用网络分析失败: {str(e)}")


@router.post("/knowledge-graph/collaboration-analysis", response_model=CollaborationAnalysisResponse)
async def discover_research_collaborations(
    request: CollaborationAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    发现研究协作关系

    突破性功能:
    - 多维度协作网络分析
    - 协作强度量化
    - 潜在协作机会识别
    - 学科交叉分析
    """
    try:
        task_id = f"collaboration_analysis_{current_user.id}_{request.project_id}"

        await stream_progress_service.send_progress_update(
            task_id,
            "开始协作关系分析",
            0,
            {"collaboration_type": request.collaboration_type}
        )

        # 执行协作关系分析
        result = await knowledge_graph_service.discover_research_collaborations(
            project_id=request.project_id,
            collaboration_type=request.collaboration_type
        )

        await stream_progress_service.send_progress_update(
            task_id,
            "协作关系分析完成",
            100,
            {"collaborators_count": result.get("network_metrics", {}).get("total_collaborators", 0)}
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return CollaborationAnalysisResponse(**result)

    except Exception as e:
        await stream_progress_service.send_progress_update(
            task_id,
            f"协作关系分析失败: {str(e)}",
            -1,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"协作关系分析失败: {str(e)}")


@router.post("/knowledge-graph/concept-map", response_model=ConceptMapResponse)
async def create_semantic_concept_map(
    request: ConceptMapRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建语义概念图

    突破性功能:
    - 深度语义概念提取
    - 概念层次结构构建
    - 语义相似度聚类
    - 概念演化追踪
    """
    try:
        task_id = f"concept_map_{current_user.id}_{request.project_id}"

        await stream_progress_service.send_progress_update(
            task_id,
            "开始创建语义概念图",
            0,
            {"concept_granularity": request.concept_granularity}
        )

        # 执行语义概念图创建
        result = await knowledge_graph_service.create_semantic_concept_map(
            project_id=request.project_id,
            concept_granularity=request.concept_granularity
        )

        await stream_progress_service.send_progress_update(
            task_id,
            "语义概念图创建完成",
            100,
            {"concepts_count": len(result.get("semantic_concepts", {}).get("concepts", []))}
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return ConceptMapResponse(**result)

    except Exception as e:
        await stream_progress_service.send_progress_update(
            task_id,
            f"语义概念图创建失败: {str(e)}",
            -1,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"语义概念图创建失败: {str(e)}")


@router.get("/knowledge-graph/entity-types")
async def get_supported_entity_types():
    """获取支持的实体类型"""
    return {
        "entity_types": [
            {
                "type": "authors",
                "description": "作者和研究者",
                "extraction_methods": ["文献元数据", "AI识别"]
            },
            {
                "type": "concepts",
                "description": "研究概念和理论",
                "extraction_methods": ["关键词提取", "语义分析"]
            },
            {
                "type": "methods",
                "description": "研究方法和技术",
                "extraction_methods": ["方法学章节分析", "AI识别"]
            },
            {
                "type": "materials",
                "description": "材料和物质",
                "extraction_methods": ["化学实体识别", "材料数据库匹配"]
            },
            {
                "type": "institutions",
                "description": "研究机构和大学",
                "extraction_methods": ["作者隶属机构", "地址解析"]
            },
            {
                "type": "locations",
                "description": "地理位置",
                "extraction_methods": ["地理实体识别", "地址解析"]
            },
            {
                "type": "journals",
                "description": "期刊和出版物",
                "extraction_methods": ["文献元数据", "期刊数据库"]
            },
            {
                "type": "keywords",
                "description": "关键词和术语",
                "extraction_methods": ["关键词字段", "TF-IDF提取"]
            }
        ],
        "relationship_types": [
            "co_occurrence",
            "citation",
            "collaboration",
            "similarity",
            "temporal",
            "hierarchical"
        ],
        "visualization_formats": [
            "force_directed",
            "hierarchical",
            "circular",
            "geographic",
            "timeline"
        ]
    }


@router.get("/knowledge-graph/analysis-capabilities")
async def get_analysis_capabilities():
    """获取分析能力说明"""
    return {
        "knowledge_graph_analysis": {
            "capabilities": [
                "多类型实体提取",
                "语义关系识别",
                "图谱结构分析",
                "中心性计算",
                "社区发现",
                "路径分析"
            ],
            "metrics": [
                "节点度中心性",
                "介数中心性",
                "接近中心性",
                "聚类系数",
                "网络密度",
                "连通性"
            ]
        },
        "citation_network_analysis": {
            "capabilities": [
                "引用关系发现",
                "影响力评估",
                "知识传播追踪",
                "潜在引用预测",
                "时间演化分析"
            ],
            "algorithms": [
                "PageRank",
                "HITS算法",
                "引用链分析",
                "影响因子计算"
            ]
        },
        "collaboration_analysis": {
            "capabilities": [
                "协作网络构建",
                "协作强度量化",
                "核心协作者识别",
                "协作机会发现",
                "学科交叉分析"
            ],
            "dimensions": [
                "作者协作",
                "机构协作",
                "国家协作",
                "跨时间协作"
            ]
        },
        "concept_mapping": {
            "capabilities": [
                "概念提取",
                "语义聚类",
                "概念层次构建",
                "概念演化追踪",
                "跨概念关联"
            ],
            "techniques": [
                "NLP语义分析",
                "词向量聚类",
                "层次聚类",
                "时间序列分析"
            ]
        }
    }


@router.get("/knowledge-graph/project/{project_id}/summary")
async def get_project_graph_summary(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目图谱摘要信息"""
    try:
        # 这里可以返回已缓存的图谱摘要信息
        return {
            "project_id": project_id,
            "cached_graphs": [],
            "available_analyses": [
                "knowledge_graph",
                "citation_network",
                "collaboration_analysis",
                "concept_map"
            ],
            "last_updated": None,
            "statistics": {
                "total_entities": 0,
                "total_relationships": 0,
                "entity_types_count": 0,
                "largest_component_size": 0
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目图谱摘要失败: {str(e)}")