"""
Smart Research Assistant API - 智能科研助手API接口
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.smart_research_assistant import smart_research_assistant
from app.services.stream_progress_service import stream_progress_service


router = APIRouter()


# =============== Pydantic Models ===============

class ResearchQuestionRequest(BaseModel):
    """研究问题请求"""
    question: str = Field(..., description="研究问题")
    project_id: int = Field(..., description="项目ID")
    context_literature_ids: Optional[List[int]] = Field(None, description="指定文献ID列表")
    max_literature_count: int = Field(10, description="最大文献数量")


class ResearchQuestionResponse(BaseModel):
    """研究问题回答"""
    question: str
    answer: str
    detailed_analysis: str
    key_findings: List[str]
    confidence: float
    sources: List[Dict[str, Any]]
    research_gaps: List[str]
    next_questions: List[str]
    methodology_suggestions: List[str]
    timestamp: str
    literature_count: int


class HypothesisGenerationRequest(BaseModel):
    """假设生成请求"""
    project_id: int = Field(..., description="项目ID")
    research_domain: str = Field(..., description="研究领域")
    literature_scope: str = Field("all", description="文献范围: all, recent, high_impact")


class HypothesisGenerationResponse(BaseModel):
    """假设生成回应"""
    research_domain: str
    literature_summary: Dict[str, Any]
    identified_gaps: List[str]
    generated_hypotheses: List[Dict[str, Any]]
    experimental_designs: List[str]
    innovation_opportunities: List[str]
    collaboration_suggestions: List[str]
    timestamp: str


class LiteratureSummaryRequest(BaseModel):
    """文献综述请求"""
    project_id: int = Field(..., description="项目ID")
    summary_type: str = Field("comprehensive", description="综述类型")
    grouping_method: str = Field("thematic", description="分组方法")


class LiteratureSummaryResponse(BaseModel):
    """文献综述响应"""
    summary_type: str
    grouping_method: str
    literature_count: int
    thematic_clusters: Dict[str, Any]
    methodology_evolution: Dict[str, Any]
    key_findings: Dict[str, Any]
    citation_analysis: Dict[str, Any]
    structured_summary: Dict[str, Any]
    research_timeline: Dict[str, Any]
    collaboration_network: Dict[str, Any]
    timestamp: str


class TrendAnalysisRequest(BaseModel):
    """趋势分析请求"""
    project_id: int = Field(..., description="项目ID")
    time_window: str = Field("5_years", description="时间窗口")
    trend_aspects: List[str] = Field(["keywords", "methods", "collaborations", "citations"], description="趋势方面")


class TrendAnalysisResponse(BaseModel):
    """趋势分析响应"""
    time_window: str
    literature_count: int
    trend_analysis: Dict[str, Any]
    emerging_topics: List[str]
    declining_topics: List[str]
    future_predictions: Dict[str, Any]
    innovation_opportunities: List[str]
    timestamp: str


# =============== API Endpoints ===============

@router.post("/smart-assistant/ask", response_model=ResearchQuestionResponse)
async def ask_research_question(
    request: ResearchQuestionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    智能问答 - 回答复杂的研究问题

    功能特点:
    - 基于多篇文献的深度分析
    - 语义相似度智能文献选择
    - 结构化分层答案生成
    - 引用溯源和可信度评估
    """
    try:
        # 启动进度跟踪
        task_id = f"research_question_{current_user.id}_{request.project_id}"

        # 发送开始事件
        await stream_progress_service.send_progress_update(
            task_id,
            "开始分析研究问题",
            0,
            {"question": request.question}
        )

        # 执行智能问答
        result = await smart_research_assistant.answer_complex_research_question(
            question=request.question,
            project_id=request.project_id,
            user_id=current_user.id,
            context_literature_ids=request.context_literature_ids,
            max_literature_count=request.max_literature_count
        )

        # 发送完成事件
        await stream_progress_service.send_progress_update(
            task_id,
            "研究问题分析完成",
            100,
            {"result_summary": result.get("answer", "")[:200]}
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return ResearchQuestionResponse(**result)

    except Exception as e:
        # 发送错误事件
        await stream_progress_service.send_progress_update(
            task_id,
            f"分析失败: {str(e)}",
            -1,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"问答服务出错: {str(e)}")


@router.post("/smart-assistant/generate-hypotheses", response_model=HypothesisGenerationResponse)
async def generate_research_hypotheses(
    request: HypothesisGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    自动生成研究假设

    功能特点:
    - 基于文献空白的自动假设生成
    - 跨学科知识整合
    - 创新性评估和可行性分析
    - 实验设计建议
    """
    try:
        # 启动进度跟踪
        task_id = f"hypothesis_generation_{current_user.id}_{request.project_id}"

        await stream_progress_service.send_progress_update(
            task_id,
            "开始生成研究假设",
            0,
            {"research_domain": request.research_domain}
        )

        # 执行假设生成
        result = await smart_research_assistant.generate_research_hypotheses(
            project_id=request.project_id,
            research_domain=request.research_domain,
            literature_scope=request.literature_scope
        )

        await stream_progress_service.send_progress_update(
            task_id,
            "研究假设生成完成",
            100,
            {"hypotheses_count": len(result.get("generated_hypotheses", []))}
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return HypothesisGenerationResponse(**result)

    except Exception as e:
        await stream_progress_service.send_progress_update(
            task_id,
            f"假设生成失败: {str(e)}",
            -1,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"假设生成服务出错: {str(e)}")


@router.post("/smart-assistant/create-summary", response_model=LiteratureSummaryResponse)
async def create_intelligent_literature_summary(
    request: LiteratureSummaryRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建智能文献综述

    功能特点:
    - 自动主题聚类和组织
    - 多维度分析(方法、发现、趋势)
    - 智能引用网络分析
    - 自动生成综述结构
    """
    try:
        task_id = f"literature_summary_{current_user.id}_{request.project_id}"

        await stream_progress_service.send_progress_update(
            task_id,
            "开始创建文献综述",
            0,
            {"summary_type": request.summary_type}
        )

        # 执行综述创建
        result = await smart_research_assistant.create_intelligent_literature_summary(
            project_id=request.project_id,
            summary_type=request.summary_type,
            grouping_method=request.grouping_method
        )

        await stream_progress_service.send_progress_update(
            task_id,
            "文献综述创建完成",
            100,
            {"literature_count": result.get("literature_count", 0)}
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return LiteratureSummaryResponse(**result)

    except Exception as e:
        await stream_progress_service.send_progress_update(
            task_id,
            f"综述创建失败: {str(e)}",
            -1,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"综述创建服务出错: {str(e)}")


@router.post("/smart-assistant/analyze-trends", response_model=TrendAnalysisResponse)
async def analyze_research_trends(
    request: TrendAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    分析研究趋势

    功能特点:
    - 多维度趋势分析
    - 新兴技术识别
    - 研究热点预测
    - 协作网络演化
    """
    try:
        task_id = f"trend_analysis_{current_user.id}_{request.project_id}"

        await stream_progress_service.send_progress_update(
            task_id,
            "开始趋势分析",
            0,
            {"time_window": request.time_window}
        )

        # 执行趋势分析
        result = await smart_research_assistant.analyze_research_trends(
            project_id=request.project_id,
            time_window=request.time_window,
            trend_aspects=request.trend_aspects
        )

        await stream_progress_service.send_progress_update(
            task_id,
            "趋势分析完成",
            100,
            {"trends_count": len(result.get("trend_analysis", {}))}
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return TrendAnalysisResponse(**result)

    except Exception as e:
        await stream_progress_service.send_progress_update(
            task_id,
            f"趋势分析失败: {str(e)}",
            -1,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"趋势分析服务出错: {str(e)}")


@router.get("/smart-assistant/conversation-history/{project_id}")
async def get_conversation_history(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取对话历史"""
    try:
        conversation_key = f"user_{current_user.id}_project_{project_id}"
        history = smart_research_assistant.conversation_memory.get(conversation_key, [])

        return {
            "project_id": project_id,
            "conversation_count": len(history),
            "conversations": history[-20:]  # 返回最近20条
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话历史失败: {str(e)}")


@router.get("/smart-assistant/capabilities")
async def get_assistant_capabilities():
    """获取助手能力说明"""
    return {
        "capabilities": [
            {
                "name": "智能问答",
                "description": "基于多篇文献回答复杂研究问题",
                "features": [
                    "语义相似度文献选择",
                    "跨文献证据整合",
                    "置信度评估",
                    "研究建议生成"
                ]
            },
            {
                "name": "假设生成",
                "description": "自动识别研究空白并生成创新假设",
                "features": [
                    "文献空白识别",
                    "创新性评估",
                    "可行性分析",
                    "实验设计建议"
                ]
            },
            {
                "name": "文献综述",
                "description": "自动创建结构化文献综述",
                "features": [
                    "主题聚类",
                    "方法学演进分析",
                    "引用网络分析",
                    "协作模式识别"
                ]
            },
            {
                "name": "趋势分析",
                "description": "多维度研究趋势分析和预测",
                "features": [
                    "关键词趋势",
                    "方法趋势",
                    "协作趋势",
                    "未来预测"
                ]
            }
        ],
        "supported_formats": [
            "PDF文献解析",
            "结构化数据提取",
            "向量语义搜索",
            "实时进度跟踪"
        ],
        "ai_models": [
            "OpenAI GPT-3.5/4",
            "本地分类模型",
            "本地摘要模型",
            "向量嵌入模型"
        ]
    }