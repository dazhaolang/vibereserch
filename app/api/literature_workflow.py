"""
增强的用户交互工作流程API
整合AI助手、质量控制、个性化和预测分析功能
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import json
import logging
from pydantic import BaseModel

from ..services.literature_ai_assistant import (
    ai_assistant, InteractionRequest, TaskStage, UserLevel
)
from ..services.quality_control_system import quality_control_system
from ..services.personalization_engine import (
    personalization_engine, UserBehavior, UserPreference, ResearchDomain, UserExpertiseLevel
)
from ..services.predictive_analytics import predictive_analytics
from ..schemas.literature_schemas import AutoResearchModeRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Literature Workflow"])


# 辅助函数
def map_user_expertise_to_level(user_expertise: str) -> UserExpertiseLevel:
    """将用户专业水平字符串映射到UserExpertiseLevel枚举"""
    expertise_mapping = {
        "beginner": UserExpertiseLevel.UNDERGRADUATE,
        "intermediate": UserExpertiseLevel.GRADUATE,
        "advanced": UserExpertiseLevel.SENIOR_RESEARCHER,
        "expert": UserExpertiseLevel.PROFESSOR,
        "undergraduate": UserExpertiseLevel.UNDERGRADUATE,
        "graduate": UserExpertiseLevel.GRADUATE,
        "postdoc": UserExpertiseLevel.POSTDOC,
        "junior_researcher": UserExpertiseLevel.JUNIOR_RESEARCHER,
        "senior_researcher": UserExpertiseLevel.SENIOR_RESEARCHER,
        "professor": UserExpertiseLevel.PROFESSOR
    }
    
    try:
        return expertise_mapping.get(user_expertise.lower(), UserExpertiseLevel.GRADUATE)
    except (AttributeError, KeyError):
        logger.warning(f"Invalid user_expertise value: {user_expertise}, using default: GRADUATE")
        return UserExpertiseLevel.GRADUATE


def map_research_domain(research_domain: str) -> ResearchDomain:
    """将研究领域字符串映射到ResearchDomain枚举"""
    domain_mapping = {
        "materials_science": ResearchDomain.MATERIALS_SCIENCE,
        "chemistry": ResearchDomain.CHEMISTRY,
        "physics": ResearchDomain.PHYSICS,
        "engineering": ResearchDomain.ENGINEERING,
        "biology": ResearchDomain.BIOLOGY,
        "interdisciplinary": ResearchDomain.INTERDISCIPLINARY
    }
    
    try:
        return domain_mapping.get(research_domain.lower(), ResearchDomain.MATERIALS_SCIENCE)
    except (AttributeError, KeyError):
        logger.warning(f"Invalid research_domain value: {research_domain}, using default: MATERIALS_SCIENCE")
        return ResearchDomain.MATERIALS_SCIENCE


def map_user_expertise_to_user_level(user_expertise: str) -> UserLevel:
    """将用户专业水平字符串映射到UserLevel枚举"""
    user_level_mapping = {
        "beginner": UserLevel.BEGINNER,
        "intermediate": UserLevel.INTERMEDIATE,
        "advanced": UserLevel.ADVANCED,
        "expert": UserLevel.EXPERT,
        "undergraduate": UserLevel.BEGINNER,
        "graduate": UserLevel.INTERMEDIATE,
        "postdoc": UserLevel.ADVANCED,
        "junior_researcher": UserLevel.INTERMEDIATE,
        "senior_researcher": UserLevel.ADVANCED,
        "professor": UserLevel.EXPERT
    }
    
    try:
        return user_level_mapping.get(user_expertise.lower(), UserLevel.INTERMEDIATE)
    except (AttributeError, KeyError):
        logger.warning(f"Invalid user_expertise value for UserLevel: {user_expertise}, using default: INTERMEDIATE")
        return UserLevel.INTERMEDIATE


# 请求和响应模型
class StartWorkflowRequest(BaseModel):
    user_id: str
    research_topic: str
    research_domain: Optional[str] = "materials_science"
    user_expertise: Optional[str] = "intermediate"
    target_literature_count: Optional[int] = 1000
    custom_requirements: Optional[Dict[str, Any]] = {}


class WorkflowStatusResponse(BaseModel):
    session_id: str
    current_stage: str
    progress_percentage: float
    estimated_remaining_minutes: float
    quality_score: Optional[float] = None
    next_actions: List[Dict[str, Any]] = []
    ai_recommendations: List[str] = []


class InteractionResponse(BaseModel):
    response: str
    suggestions: List[str] = []
    next_actions: List[Dict[str, Any]] = []
    requires_confirmation: bool = False
    estimated_time: Optional[int] = None
    confidence_score: float = 0.0


class QualityReportResponse(BaseModel):
    overall_score: float
    quality_level: str
    stage_scores: Dict[str, float]
    issues: List[Dict[str, Any]]
    recommendations: List[str]
    improvement_suggestions: List[str]


# 工作流程状态管理
class WorkflowManager:
    def __init__(self):
        self.active_sessions = {}  # 存储活跃会话
        self.session_progress = {}  # 存储会话进度
        
    def create_session(self, user_id: str, initial_params: Dict[str, Any]) -> str:
        """创建新的工作流会话"""
        session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now(),
            "current_stage": TaskStage.RESEARCH_DIRECTION,
            "parameters": initial_params,
            "stage_history": [],
            "quality_history": [],
            "user_interactions": []
        }
        
        self.session_progress[session_id] = {
            "overall_progress": 0.0,
            "stage_progress": {
                "research_direction": 0.0,
                "literature_collection": 0.0,
                "lightweight_structuring": 0.0,
                "experience_enhancement": 0.0,
                "solution_generation": 0.0
            }
        }
        
        return session_id
    
    def update_progress(self, session_id: str, stage: str, progress: float):
        """更新会话进度"""
        if session_id in self.session_progress:
            self.session_progress[session_id]["stage_progress"][stage] = progress
            
            # 计算总体进度
            stage_weights = {
                "research_direction": 0.15,
                "literature_collection": 0.25,
                "lightweight_structuring": 0.30,
                "experience_enhancement": 0.25,
                "solution_generation": 0.05
            }
            
            overall_progress = sum(
                progress * stage_weights.get(stage_name, 0)
                for stage_name, progress in self.session_progress[session_id]["stage_progress"].items()
            )
            
            self.session_progress[session_id]["overall_progress"] = overall_progress


workflow_manager = WorkflowManager()


@router.post("/start", response_model=Dict[str, Any])
async def start_workflow(request: StartWorkflowRequest, background_tasks: BackgroundTasks):
    """启动文献轻结构化工作流程"""
    
    try:
        # 创建工作流会话
        session_id = workflow_manager.create_session(request.user_id, request.dict())
        
        # 初始化用户偏好
        # 安全转换枚举值
        expertise_level = map_user_expertise_to_level(request.user_expertise)
        primary_domain = map_research_domain(request.research_domain)
        
        user_preferences = UserPreference(
            user_id=request.user_id,
            expertise_level=expertise_level,
            primary_domain=primary_domain
        )
        
        # 初始化个性化档案
        await personalization_engine.initialize_user_profile(request.user_id, user_preferences)
        
        # 记录用户行为
        behavior = UserBehavior(
            user_id=request.user_id,
            session_id=session_id,
            action="start_workflow",
            context={
                "research_topic": request.research_topic,
                "domain": request.research_domain,
                "target_count": request.target_literature_count
            }
        )
        await personalization_engine.update_user_profile(behavior)
        
        # 生成初始预测
        task_params = {
            "literature_count": request.target_literature_count,
            "domain": request.research_domain,
            "user_experience_score": 0.5,  # 默认中等水平
            "has_custom_template": bool(request.custom_requirements),
            "data_quality_score": 0.8,  # 预估数据质量
        }
        
        prediction = await predictive_analytics.comprehensive_prediction(task_params, session_id)
        
        # 启动AI助手交互
        # 安全转换UserLevel枚举值
        user_level = map_user_expertise_to_user_level(request.user_expertise)
        
        ai_request = InteractionRequest(
            user_id=request.user_id,
            session_id=session_id,
            stage=TaskStage.RESEARCH_DIRECTION,
            message=f"我想研究{request.research_topic}",
            context={"domain": request.research_domain},
            user_level=user_level
        )
        
        ai_response = await ai_assistant.handle_interaction(ai_request)
        
        return {
            "session_id": session_id,
            "status": "started",
            "current_stage": "research_direction",
            "ai_response": {
                "message": ai_response.response,
                "suggestions": ai_response.suggestions,
                "next_actions": ai_response.next_actions,
                "estimated_time": ai_response.estimated_time
            },
            "predictions": {
                "total_estimated_hours": prediction["time_estimates"]["total_estimated_hours"],
                "predicted_quality": prediction["quality_prediction"]["predicted_score"],
                "success_probability": prediction["success_probability"],
                "risk_level": prediction["risk_assessment"]["overall_risk_level"]
            },
            "recommendations": prediction["recommendations"]
        }
        
    except Exception as e:
        logger.error(f"Error starting workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动工作流失败: {str(e)}")


@router.post("/interact/{session_id}", response_model=InteractionResponse)
async def interact_with_ai(
    session_id: str,
    message: str,
    stage: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
):
    """与AI助手交互"""
    
    try:
        if session_id not in workflow_manager.active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = workflow_manager.active_sessions[session_id]
        user_id = session["user_id"]
        
        # 确定当前阶段
        current_stage = TaskStage(stage) if stage else session["current_stage"]
        
        # 记录用户行为
        behavior = UserBehavior(
            user_id=user_id,
            session_id=session_id,
            action="ai_interaction",
            context={
                "message": message,
                "stage": current_stage.value,
                "context": context or {}
            }
        )
        await personalization_engine.update_user_profile(behavior)
        
        # AI助手处理
        ai_request = InteractionRequest(
            user_id=user_id,
            session_id=session_id,
            stage=current_stage,
            message=message,
            context=context or {}
        )
        
        ai_response = await ai_assistant.handle_interaction(ai_request)
        
        # 获取个性化推荐
        personalized_recommendations = await personalization_engine.get_personalized_recommendations(
            user_id, context or {}
        )
        
        # 更新会话信息
        session["user_interactions"].append({
            "timestamp": datetime.now(),
            "message": message,
            "response": ai_response.response,
            "stage": current_stage.value
        })
        
        return InteractionResponse(
            response=ai_response.response,
            suggestions=ai_response.suggestions + [r["label"] for r in personalized_recommendations[:2]],
            next_actions=ai_response.next_actions,
            requires_confirmation=ai_response.requires_confirmation,
            estimated_time=ai_response.estimated_time,
            confidence_score=ai_response.confidence_score
        )
        
    except Exception as e:
        logger.error(f"Error in AI interaction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI交互失败: {str(e)}")


@router.get("/status/{session_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(session_id: str):
    """获取工作流状态"""
    
    try:
        if session_id not in workflow_manager.active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = workflow_manager.active_sessions[session_id]
        progress = workflow_manager.session_progress[session_id]
        user_id = session["user_id"]
        
        # 获取质量控制实时指标
        quality_metrics = await quality_control_system.get_real_time_quality_metrics(session_id)
        
        # 获取个性化推荐
        personalized_actions = await personalization_engine.get_personalized_recommendations(user_id)
        
        # 获取预测洞察
        prediction_insights = await predictive_analytics.get_prediction_insights(session_id)
        
        # 估算剩余时间
        estimated_remaining = 0.0
        if "latest_prediction_summary" in prediction_insights:
            total_hours = prediction_insights["latest_prediction_summary"]["total_estimated_hours"]
            completed_ratio = progress["overall_progress"] / 100
            estimated_remaining = total_hours * (1 - completed_ratio) * 60  # 转换为分钟
        
        return WorkflowStatusResponse(
            session_id=session_id,
            current_stage=session["current_stage"].value,
            progress_percentage=progress["overall_progress"],
            estimated_remaining_minutes=estimated_remaining,
            quality_score=quality_metrics.get("current_quality_score"),
            next_actions=[
                {"action": action["action"], "label": action["label"]} 
                for action in personalized_actions[:3]
            ],
            ai_recommendations=prediction_insights.get("key_recommendations", [])
        )
        
    except Exception as e:
        logger.error(f"Error getting workflow status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.post("/literature/collect/{session_id}")
async def collect_literature(
    session_id: str,
    keywords: List[str],
    target_count: Optional[int] = 1000,
    quality_threshold: Optional[float] = 0.7
):
    """采集文献"""
    
    try:
        if session_id not in workflow_manager.active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = workflow_manager.active_sessions[session_id]
        user_id = session["user_id"]
        
        # 更新阶段
        session["current_stage"] = TaskStage.LITERATURE_COLLECTION
        workflow_manager.update_progress(session_id, "literature_collection", 0.1)
        
        # 记录用户行为
        behavior = UserBehavior(
            user_id=user_id,
            session_id=session_id,
            action="start_literature_collection",
            context={
                "keywords": keywords,
                "target_count": target_count,
                "quality_threshold": quality_threshold
            }
        )
        await personalization_engine.update_user_profile(behavior)
        
        # 模拟文献采集过程
        collected_literature = []
        for i in range(min(target_count, 100)):  # 模拟采集
            literature = {
                "id": f"paper_{i}",
                "title": f"Research Paper {i}",
                "authors": ["Author A", "Author B"],
                "journal": "Sample Journal",
                "year": 2023,
                "abstract": f"Abstract for paper {i}",
                "citations": i * 10,
                "doi": f"10.1000/paper{i}"
            }
            collected_literature.append(literature)
            
            # 更新进度
            if i % 10 == 0:
                progress = 0.1 + (i / target_count) * 0.8
                workflow_manager.update_progress(session_id, "literature_collection", progress)
                await asyncio.sleep(0.1)  # 模拟处理时间
        
        # 质量评估
        quality_assessment = await quality_control_system.assess_literature_quality(
            collected_literature, session_id
        )
        
        # 完成采集阶段
        workflow_manager.update_progress(session_id, "literature_collection", 1.0)
        
        return {
            "status": "completed",
            "collected_count": len(collected_literature),
            "quality_assessment": {
                "overall_score": quality_assessment.overall_score,
                "quality_level": quality_assessment.quality_level.value,
                "issues_count": len(quality_assessment.issues),
                "recommendations": quality_assessment.recommendations
            },
            "next_stage": "lightweight_structuring"
        }
        
    except Exception as e:
        logger.error(f"Error collecting literature: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文献采集失败: {str(e)}")


@router.post("/structure/process/{session_id}")
async def process_structuring(
    session_id: str,
    template_config: Optional[Dict[str, Any]] = None,
    custom_fields: Optional[List[str]] = None
):
    """处理轻结构化"""
    
    try:
        if session_id not in workflow_manager.active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = workflow_manager.active_sessions[session_id]
        user_id = session["user_id"]
        
        # 更新阶段
        session["current_stage"] = TaskStage.LIGHTWEIGHT_STRUCTURING
        workflow_manager.update_progress(session_id, "lightweight_structuring", 0.1)
        
        # 记录用户行为
        behavior = UserBehavior(
            user_id=user_id,
            session_id=session_id,
            action="start_structuring",
            context={
                "template_config": template_config,
                "custom_fields": custom_fields
            }
        )
        await personalization_engine.update_user_profile(behavior)
        
        # 模拟结构化处理
        structured_data = []
        mock_papers = [{"title": f"Paper {i}", "abstract": f"Abstract {i}"} for i in range(100)]
        
        for i, paper in enumerate(mock_papers):
            structured_entry = {
                "source_paper": paper["title"],
                "preparation": f"Preparation method for {paper['title']}",
                "characterization": f"Characterization results for {paper['title']}",
                "application": f"Application scenarios for {paper['title']}",
                "mechanism": f"Mechanism analysis for {paper['title']}"
            }
            structured_data.append(structured_entry)
            
            # 更新进度
            if i % 10 == 0:
                progress = 0.1 + (i / len(mock_papers)) * 0.8
                workflow_manager.update_progress(session_id, "lightweight_structuring", progress)
                await asyncio.sleep(0.1)
        
        # 质量监控
        quality_assessment = await quality_control_system.monitor_structuring_quality(
            structured_data, mock_papers, session_id
        )
        
        # 完成结构化阶段
        workflow_manager.update_progress(session_id, "lightweight_structuring", 1.0)
        
        return {
            "status": "completed",
            "structured_count": len(structured_data),
            "quality_assessment": {
                "overall_score": quality_assessment.overall_score,
                "quality_level": quality_assessment.quality_level.value,
                "recommendations": quality_assessment.recommendations
            },
            "next_stage": "experience_enhancement"
        }
        
    except Exception as e:
        logger.error(f"Error processing structuring: {str(e)}")
        raise HTTPException(status_code=500, detail=f"结构化处理失败: {str(e)}")


@router.post("/enhance/experience/{session_id}")
async def enhance_experience(
    session_id: str,
    target_quality: Optional[float] = 0.9,
    max_iterations: Optional[int] = 10
):
    """经验增强迭代"""
    
    try:
        if session_id not in workflow_manager.active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = workflow_manager.active_sessions[session_id]
        user_id = session["user_id"]
        
        # 更新阶段
        session["current_stage"] = TaskStage.EXPERIENCE_ENHANCEMENT
        workflow_manager.update_progress(session_id, "experience_enhancement", 0.1)
        
        # 记录用户行为
        behavior = UserBehavior(
            user_id=user_id,
            session_id=session_id,
            action="start_experience_enhancement",
            context={
                "target_quality": target_quality,
                "max_iterations": max_iterations
            }
        )
        await personalization_engine.update_user_profile(behavior)
        
        # 模拟经验增强迭代
        current_quality = 0.6
        iteration_round = 1
        experience_content = "初始经验内容..."
        
        while iteration_round <= max_iterations and current_quality < target_quality:
            # 模拟迭代处理
            await asyncio.sleep(0.5)  # 模拟处理时间
            
            # 更新经验内容
            experience_content += f"\n第{iteration_round}轮迭代增强内容..."
            current_quality += 0.05 + (0.1 / iteration_round)  # 递减改进
            
            # 质量跟踪
            mock_papers = [{"title": f"Paper {i}"} for i in range(100)]
            quality_assessment = await quality_control_system.track_experience_quality(
                iteration_round, experience_content, mock_papers, session_id
            )
            
            # 更新进度
            progress = 0.1 + (iteration_round / max_iterations) * 0.8
            workflow_manager.update_progress(session_id, "experience_enhancement", progress)
            
            # 检查停止条件
            if quality_assessment.overall_score >= target_quality:
                break
            
            # 检查改进率
            if iteration_round >= 3 and quality_assessment.overall_score - current_quality < 0.05:
                break  # 改进率过低，停止迭代
            
            iteration_round += 1
        
        # 完成经验增强阶段
        workflow_manager.update_progress(session_id, "experience_enhancement", 1.0)
        
        return {
            "status": "completed",
            "total_iterations": iteration_round - 1,
            "final_quality_score": current_quality,
            "experience_length": len(experience_content),
            "improvement_achieved": current_quality - 0.6,
            "next_stage": "solution_generation"
        }
        
    except Exception as e:
        logger.error(f"Error enhancing experience: {str(e)}")
        raise HTTPException(status_code=500, detail=f"经验增强失败: {str(e)}")


@router.post("/generate/solution/{session_id}")
async def generate_solution(
    session_id: str,
    user_question: str,
    solution_type: Optional[str] = "comprehensive"
):
    """生成解决方案"""
    
    try:
        if session_id not in workflow_manager.active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = workflow_manager.active_sessions[session_id]
        user_id = session["user_id"]
        
        # 更新阶段
        session["current_stage"] = TaskStage.SOLUTION_GENERATION
        workflow_manager.update_progress(session_id, "solution_generation", 0.5)
        
        # 记录用户行为
        behavior = UserBehavior(
            user_id=user_id,
            session_id=session_id,
            action="generate_solution",
            context={
                "question": user_question,
                "solution_type": solution_type
            }
        )
        await personalization_engine.update_user_profile(behavior)
        
        # AI助手生成解决方案
        ai_request = InteractionRequest(
            user_id=user_id,
            session_id=session_id,
            stage=TaskStage.SOLUTION_GENERATION,
            message=user_question,
            context={"solution_type": solution_type}
        )
        
        ai_response = await ai_assistant.handle_interaction(ai_request)
        
        # 获取个性化内容
        personalized_solution = await personalization_engine.get_personalized_content(
            user_id, ai_response.response
        )
        
        # 完成解决方案生成
        workflow_manager.update_progress(session_id, "solution_generation", 1.0)
        
        # 记录任务完成
        completed_task = {
            "type": "solution_generation",
            "success": True,
            "duration": 300,  # 5分钟
            "complexity": "medium",
            "question": user_question
        }
        
        learning_progress = await personalization_engine.track_task_completion(
            user_id, completed_task
        )
        
        return {
            "status": "completed",
            "solution": personalized_solution,
            "suggestions": ai_response.suggestions,
            "confidence_score": ai_response.confidence_score,
            "learning_progress": learning_progress,
            "workflow_completed": True
        }
        
    except Exception as e:
        logger.error(f"Error generating solution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"解决方案生成失败: {str(e)}")


@router.get("/quality/report/{session_id}", response_model=QualityReportResponse)
async def get_quality_report(session_id: str):
    """获取质量报告"""
    
    try:
        if session_id not in workflow_manager.active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 生成质量报告
        quality_report = await quality_control_system.generate_quality_report(session_id)
        
        if "error" in quality_report:
            raise HTTPException(status_code=404, detail=quality_report["error"])
        
        # 提取阶段质量分数
        stage_scores = {}
        for stage, summary in quality_report["stage_quality_summary"].items():
            stage_scores[stage] = summary["latest_score"]
        
        # 计算总体分数
        overall_score = sum(stage_scores.values()) / len(stage_scores) if stage_scores else 0
        
        # 确定质量等级
        if overall_score >= 90:
            quality_level = "优秀"
        elif overall_score >= 80:
            quality_level = "良好"
        elif overall_score >= 70:
            quality_level = "中等"
        else:
            quality_level = "需要改进"
        
        return QualityReportResponse(
            overall_score=overall_score,
            quality_level=quality_level,
            stage_scores=stage_scores,
            issues=[],  # 简化处理
            recommendations=quality_report["key_recommendations"],
            improvement_suggestions=[
                "建议关注质量评分较低的阶段",
                "可以考虑增加人工审核环节",
                "建议优化数据源质量"
            ]
        )
        
    except Exception as e:
        logger.error(f"Error generating quality report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成质量报告失败: {str(e)}")


@router.get("/analytics/insights/{session_id}")
async def get_analytics_insights(session_id: str):
    """获取分析洞察"""
    
    try:
        if session_id not in workflow_manager.active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session = workflow_manager.active_sessions[session_id]
        user_id = session["user_id"]
        
        # 获取预测洞察
        prediction_insights = await predictive_analytics.get_prediction_insights(session_id)
        
        # 获取用户洞察
        user_insights = await personalization_engine.get_user_insights(user_id)
        
        # 获取质量指标
        quality_metrics = await quality_control_system.get_real_time_quality_metrics(session_id)
        
        return {
            "session_analytics": {
                "session_id": session_id,
                "duration_minutes": (datetime.now() - session["created_at"]).total_seconds() / 60,
                "interactions_count": len(session["user_interactions"]),
                "current_stage": session["current_stage"].value
            },
            "prediction_insights": prediction_insights,
            "user_insights": user_insights,
            "quality_metrics": quality_metrics,
            "recommendations": [
                "建议定期检查工作流进度",
                "可以考虑调整个性化设置",
                "建议关注质量控制指标"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics insights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取分析洞察失败: {str(e)}")


@router.delete("/session/{session_id}")
async def cleanup_session(session_id: str):
    """清理会话"""
    
    try:
        if session_id in workflow_manager.active_sessions:
            session = workflow_manager.active_sessions[session_id]
            user_id = session["user_id"]
            
            # 记录会话结束行为
            behavior = UserBehavior(
                user_id=user_id,
                session_id=session_id,
                action="end_session",
                context={"duration_minutes": (datetime.now() - session["created_at"]).total_seconds() / 60}
            )
            await personalization_engine.update_user_profile(behavior)
            
            # 清理会话数据
            del workflow_manager.active_sessions[session_id]
            del workflow_manager.session_progress[session_id]
            
            return {"status": "cleaned", "message": "会话已成功清理"}
        else:
            raise HTTPException(status_code=404, detail="会话不存在")
            
    except Exception as e:
        logger.error(f"Error cleaning up session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清理会话失败: {str(e)}")


@router.get("/sessions/active")
async def get_active_sessions():
    """获取活跃会话列表"""
    
    try:
        active_sessions = []
        for session_id, session_data in workflow_manager.active_sessions.items():
            progress = workflow_manager.session_progress.get(session_id, {})
            
            active_sessions.append({
                "session_id": session_id,
                "user_id": session_data["user_id"],
                "created_at": session_data["created_at"].isoformat(),
                "current_stage": session_data["current_stage"].value,
                "overall_progress": progress.get("overall_progress", 0.0),
                "interactions_count": len(session_data["user_interactions"])
            })
        
        return {
            "active_sessions_count": len(active_sessions),
            "sessions": active_sessions
        }

    except Exception as e:
        logger.error(f"Error getting active sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取活跃会话失败: {str(e)}")


@router.post("/auto-research", response_model=Dict[str, Any])
async def auto_research(
    request: AutoResearchModeRequest,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """自动研究端点 - 支持三模式API格式"""
    try:
        # 创建启动工作流请求
        start_request = StartWorkflowRequest(
            user_id=str(request.project_id),  # 使用project_id作为user_id临时方案
            research_topic=request.query,
            research_domain="materials_science",  # 默认材料科学
            user_expertise="intermediate",       # 默认中等水平
            target_literature_count=request.max_results or 20,
            custom_requirements={
                "research_scope": request.research_scope,
                "max_iterations": request.max_iterations,
                "args": request.args,
                "kwargs": request.kwargs,
                "original_query": request.query
            }
        )

        # 调用现有的启动工作流功能
        response = await start_workflow(start_request, background_tasks)

        return {
            "success": True,
            "message": "自动研究已启动",
            "session_id": response.get("session_id"),
            "task_id": response.get("task_id"),
            "estimated_duration": response.get("estimated_duration", 300),
            "project_id": request.project_id,
            "query": request.query
        }

    except Exception as e:
        logger.error(f"自动研究启动失败: {e}")
        raise HTTPException(status_code=500, detail=f"自动研究启动失败: {str(e)}")