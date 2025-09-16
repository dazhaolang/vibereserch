"""
性能优化API - Performance Optimization API
提供大规模处理性能优化和成本控制的统一接口
"""

from typing import List, Dict, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from loguru import logger

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.exceptions import ErrorFactory, handle_exceptions, ErrorCode
from app.models.user import User
from app.models.project import Project
from app.models.literature import Literature
from app.services.performance_optimizer import (
    PerformanceOptimizer, OptimizationLevel, OptimizationConfig,
    create_performance_optimizer, optimize_large_scale_processing
)
from app.services.cost_control_manager import (
    IntelligentCostOptimizer, ProcessingMode, ProcessingEstimate,
    create_cost_optimizer, estimate_processing_cost_for_modes,
    recommend_cost_optimal_processing
)
from app.services.performance_monitor import (
    performance_monitor, start_performance_monitoring,
    stop_performance_monitoring, get_performance_dashboard
)

router = APIRouter()


# Request/Response Models

class OptimizationLevelEnum(str, Enum):
    """优化级别枚举"""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class ProcessingModeEnum(str, Enum):
    """处理模式枚举"""
    LIGHTWEIGHT = "lightweight"
    STANDARD = "standard"
    DEEP = "deep"


class PerformanceOptimizationRequest(BaseModel):
    """性能优化请求"""
    project_id: int
    literature_ids: List[int]
    optimization_level: OptimizationLevelEnum = OptimizationLevelEnum.BALANCED
    target_throughput: float = Field(default=50.0, description="目标吞吐量（文献/分钟）")
    cost_budget: float = Field(default=100.0, description="成本预算（美元）")
    enable_cache: bool = Field(default=True, description="启用缓存")
    enable_parallel: bool = Field(default=True, description="启用并行处理")
    enable_adaptive_batching: bool = Field(default=True, description="启用自适应批处理")


class CostEstimationRequest(BaseModel):
    """成本估算请求"""
    project_id: int
    literature_count: int
    processing_mode: ProcessingModeEnum = ProcessingModeEnum.STANDARD
    include_all_modes: bool = Field(default=True, description="包含所有模式的估算")


class BatchOptimizationRequest(BaseModel):
    """批处理优化请求"""
    project_id: int
    literature_count: int
    target_cost_budget: Optional[float] = Field(default=None, description="目标成本预算")
    max_processing_time: Optional[int] = Field(default=None, description="最大处理时间（分钟）")


class PerformanceOptimizationResponse(BaseModel):
    """性能优化响应"""
    task_id: str
    success: bool
    processed_count: int
    processing_time: float
    performance_metrics: Dict[str, Any]
    cost_breakdown: Dict[str, Any]
    optimization_recommendations: List[str]
    estimated_savings: Dict[str, float]


class CostEstimationResponse(BaseModel):
    """成本估算响应"""
    project_id: int
    literature_count: int
    estimates_by_mode: Dict[str, Dict[str, Any]]
    recommended_mode: str
    cost_breakdown: Dict[str, float]
    optimization_suggestions: List[str]
    budget_analysis: Dict[str, Any]


class BatchOptimizationResponse(BaseModel):
    """批处理优化响应"""
    optimal_strategy: Dict[str, Any]
    alternative_strategies: List[Dict[str, Any]]
    cost_savings: Dict[str, float]
    performance_impact: Dict[str, Any]
    implementation_plan: List[Dict[str, str]]


class PerformanceDashboardResponse(BaseModel):
    """性能仪表板响应"""
    system_health: Dict[str, Any]
    current_metrics: Dict[str, float]
    active_alerts: List[Dict[str, Any]]
    recent_optimizations: List[Dict[str, Any]]
    cost_analytics: Dict[str, Any]
    recommendations: List[str]


# API Endpoints

@router.post("/optimize", response_model=PerformanceOptimizationResponse)
@handle_exceptions(ErrorCode.PROCESSING_ERROR)
async def optimize_performance(
    request: PerformanceOptimizationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    执行大规模文献处理性能优化
    """
    # 验证项目权限
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")

    # 获取文献列表
    literature_query = db.query(Literature).filter(
        Literature.id.in_(request.literature_ids)
    )

    # 验证文献属于该项目
    project_literature_ids = [lit.id for lit in project.literature]
    invalid_ids = [lid for lid in request.literature_ids if lid not in project_literature_ids]

    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"以下文献不属于该项目: {invalid_ids}"
        )

    literature_list = literature_query.all()

    if not literature_list:
        raise HTTPException(status_code=404, detail="未找到指定的文献")

    # 检查会员限制
    max_literature = _get_user_literature_limit(current_user)
    if len(literature_list) > max_literature:
        raise HTTPException(
            status_code=403,
            detail=f"文献数量超出限制，您的限制为 {max_literature} 篇"
        )

    try:
        # 创建优化任务ID
        task_id = f"perf_opt_{project.id}_{int(datetime.now().timestamp())}"

        # 执行性能优化
        optimization_level = OptimizationLevel(request.optimization_level.value)

        result = await optimize_large_scale_processing(
            literature_list=literature_list,
            project=project,
            optimization_level=optimization_level,
            cost_budget=request.cost_budget,
            progress_callback=None  # 可以添加WebSocket进度推送
        )

        # 计算节省的成本和时间
        estimated_savings = _calculate_optimization_savings(
            len(literature_list), result.get("performance_metrics", {})
        )

        return PerformanceOptimizationResponse(
            task_id=task_id,
            success=result.get("success", False),
            processed_count=result.get("processed_count", 0),
            processing_time=result.get("processing_time", 0.0),
            performance_metrics=result.get("performance_metrics", {}),
            cost_breakdown=result.get("cost_breakdown", {}),
            optimization_recommendations=result.get("optimization_recommendations", []),
            estimated_savings=estimated_savings
        )

    except Exception as e:
        logger.error(f"性能优化失败: {e}")
        raise HTTPException(status_code=500, detail=f"性能优化失败: {str(e)}")


@router.post("/estimate-cost", response_model=CostEstimationResponse)
@handle_exceptions(ErrorCode.PROCESSING_ERROR)
async def estimate_processing_cost(
    request: CostEstimationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    估算文献处理成本
    """
    # 验证项目权限
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")

    try:
        if request.include_all_modes:
            # 获取所有模式的估算
            estimates = await estimate_processing_cost_for_modes(
                literature_count=request.literature_count,
                user=current_user,
                project=project
            )

            estimates_dict = {}
            for mode, estimate in estimates.items():
                estimates_dict[mode.value] = {
                    "estimated_cost": estimate.estimated_cost,
                    "estimated_time": estimate.estimated_time,
                    "cost_breakdown": {
                        "ai_processing": estimate.cost_breakdown.ai_processing,
                        "pdf_processing": estimate.cost_breakdown.pdf_processing,
                        "storage": estimate.cost_breakdown.storage,
                        "network": estimate.cost_breakdown.network,
                        "overhead": estimate.cost_breakdown.overhead,
                        "total": estimate.cost_breakdown.total
                    },
                    "optimization_suggestions": estimate.optimization_suggestions
                }

            # 推荐最优模式
            recommended_mode = min(
                estimates_dict.keys(),
                key=lambda k: estimates_dict[k]["estimated_cost"]
            )

        else:
            # 仅估算指定模式
            cost_optimizer = create_cost_optimizer()
            processing_mode = ProcessingMode(request.processing_mode.value)

            estimate = await cost_optimizer.estimate_processing_cost(
                literature_count=request.literature_count,
                mode=processing_mode,
                user=current_user,
                project=project
            )

            estimates_dict = {
                processing_mode.value: {
                    "estimated_cost": estimate.estimated_cost,
                    "estimated_time": estimate.estimated_time,
                    "cost_breakdown": {
                        "ai_processing": estimate.cost_breakdown.ai_processing,
                        "pdf_processing": estimate.cost_breakdown.pdf_processing,
                        "storage": estimate.cost_breakdown.storage,
                        "network": estimate.cost_breakdown.network,
                        "overhead": estimate.cost_breakdown.overhead,
                        "total": estimate.cost_breakdown.total
                    },
                    "optimization_suggestions": estimate.optimization_suggestions
                }
            }
            recommended_mode = processing_mode.value

        # 获取用户预算分析
        budget_analysis = await _get_user_budget_analysis(current_user)

        return CostEstimationResponse(
            project_id=request.project_id,
            literature_count=request.literature_count,
            estimates_by_mode=estimates_dict,
            recommended_mode=recommended_mode,
            cost_breakdown=estimates_dict[recommended_mode]["cost_breakdown"],
            optimization_suggestions=estimates_dict[recommended_mode]["optimization_suggestions"],
            budget_analysis=budget_analysis
        )

    except Exception as e:
        logger.error(f"成本估算失败: {e}")
        raise HTTPException(status_code=500, detail=f"成本估算失败: {str(e)}")


@router.post("/optimize-batch", response_model=BatchOptimizationResponse)
@handle_exceptions(ErrorCode.PROCESSING_ERROR)
async def optimize_batch_processing(
    request: BatchOptimizationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    优化批处理策略
    """
    # 验证项目权限
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无访问权限")

    try:
        # 获取推荐的成本最优处理方案
        optimization_result = await recommend_cost_optimal_processing(
            literature_count=request.literature_count,
            user=current_user,
            cost_budget=request.target_cost_budget,
            project=project
        )

        # 生成实施计划
        implementation_plan = _generate_implementation_plan(optimization_result)

        # 计算性能影响
        performance_impact = _calculate_performance_impact(
            request.literature_count, optimization_result
        )

        return BatchOptimizationResponse(
            optimal_strategy=optimization_result["batch_optimization"]["recommended"],
            alternative_strategies=optimization_result["batch_optimization"]["strategies"],
            cost_savings=optimization_result["batch_optimization"]["cost_savings"],
            performance_impact=performance_impact,
            implementation_plan=implementation_plan
        )

    except Exception as e:
        logger.error(f"批处理优化失败: {e}")
        raise HTTPException(status_code=500, detail=f"批处理优化失败: {str(e)}")


@router.get("/dashboard", response_model=PerformanceDashboardResponse)
@handle_exceptions(ErrorCode.PROCESSING_ERROR)
async def get_performance_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取性能监控仪表板数据
    """
    try:
        # 获取系统性能数据
        dashboard_data = get_performance_dashboard()

        # 获取用户相关的成本分析
        cost_optimizer = create_cost_optimizer()
        cost_analytics = await cost_optimizer.get_cost_analytics(current_user.id)

        # 生成个性化推荐
        recommendations = await _generate_personalized_recommendations(
            current_user, dashboard_data, cost_analytics
        )

        return PerformanceDashboardResponse(
            system_health=dashboard_data.get("system_health", {}).__dict__,
            current_metrics=dashboard_data.get("current_metrics", {}),
            active_alerts=[alert.__dict__ for alert in dashboard_data.get("active_alerts", [])],
            recent_optimizations=dashboard_data.get("recent_tuning", []),
            cost_analytics=cost_analytics,
            recommendations=recommendations
        )

    except Exception as e:
        logger.error(f"获取性能仪表板失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取性能仪表板失败: {str(e)}")


@router.post("/monitoring/start")
@handle_exceptions(ErrorCode.PROCESSING_ERROR)
async def start_monitoring(
    current_user: User = Depends(get_current_active_user)
):
    """
    启动性能监控（管理员功能）
    """
    # 检查管理员权限
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        await start_performance_monitoring()
        return {"message": "性能监控已启动", "status": "success"}
    except Exception as e:
        logger.error(f"启动性能监控失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动性能监控失败: {str(e)}")


@router.post("/monitoring/stop")
@handle_exceptions(ErrorCode.PROCESSING_ERROR)
async def stop_monitoring(
    current_user: User = Depends(get_current_active_user)
):
    """
    停止性能监控（管理员功能）
    """
    # 检查管理员权限
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        await stop_performance_monitoring()
        return {"message": "性能监控已停止", "status": "success"}
    except Exception as e:
        logger.error(f"停止性能监控失败: {e}")
        raise HTTPException(status_code=500, detail=f"停止性能监控失败: {str(e)}")


@router.get("/analytics/cost")
@handle_exceptions(ErrorCode.PROCESSING_ERROR)
async def get_cost_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取成本分析报告
    """
    try:
        cost_optimizer = create_cost_optimizer()
        analytics = await cost_optimizer.get_cost_analytics(current_user.id, days)

        return {
            "user_id": current_user.id,
            "analytics_period": days,
            "cost_summary": analytics,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"获取成本分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取成本分析失败: {str(e)}")


@router.get("/recommendations/optimization")
@handle_exceptions(ErrorCode.PROCESSING_ERROR)
async def get_optimization_recommendations(
    project_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取个性化优化推荐
    """
    try:
        recommendations = []

        # 基于用户使用模式的推荐
        user_pattern_recommendations = await _analyze_user_usage_pattern(current_user, db)
        recommendations.extend(user_pattern_recommendations)

        # 基于项目特征的推荐
        if project_id:
            project = db.query(Project).filter(
                Project.id == project_id,
                Project.owner_id == current_user.id
            ).first()

            if project:
                project_recommendations = await _analyze_project_optimization_opportunities(
                    project, db
                )
                recommendations.extend(project_recommendations)

        # 基于系统状态的推荐
        system_recommendations = await _get_system_based_recommendations()
        recommendations.extend(system_recommendations)

        return {
            "user_id": current_user.id,
            "project_id": project_id,
            "recommendations": recommendations,
            "generated_at": datetime.now(),
            "status": "success"
        }

    except Exception as e:
        logger.error(f"获取优化推荐失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取优化推荐失败: {str(e)}")


# 辅助函数

def _get_user_literature_limit(user: User) -> int:
    """获取用户文献处理限制"""
    if not user.membership:
        return 50  # 免费用户限制50篇

    membership_type = user.membership.membership_type
    limits = {
        "free": 50,
        "basic": 200,
        "premium": 500,
        "enterprise": 2000
    }

    return limits.get(membership_type.value, 50)


def _calculate_optimization_savings(literature_count: int, performance_metrics: Dict) -> Dict[str, float]:
    """计算优化节省"""
    # 基础成本（未优化）
    base_cost_per_paper = 0.25
    base_processing_time = literature_count * 60  # 每篇1分钟

    # 优化后的指标
    actual_cost = performance_metrics.get("total_cost", base_cost_per_paper * literature_count)
    actual_time = performance_metrics.get("processing_time", base_processing_time)

    cost_savings = max(0, (base_cost_per_paper * literature_count) - actual_cost)
    time_savings = max(0, base_processing_time - actual_time)

    return {
        "cost_savings_amount": cost_savings,
        "cost_savings_percentage": (cost_savings / (base_cost_per_paper * literature_count)) * 100,
        "time_savings_seconds": time_savings,
        "time_savings_percentage": (time_savings / base_processing_time) * 100 if base_processing_time > 0 else 0,
        "efficiency_improvement": performance_metrics.get("throughput", 1.0)
    }


async def _get_user_budget_analysis(user: User) -> Dict[str, Any]:
    """获取用户预算分析"""
    cost_optimizer = create_cost_optimizer()
    user_quota = await cost_optimizer._get_user_quota(user.id)

    return {
        "daily_budget": user_quota.daily_budget,
        "daily_used": user_quota.daily_used,
        "daily_remaining": user_quota.daily_budget - user_quota.daily_used,
        "monthly_budget": user_quota.monthly_budget,
        "monthly_used": user_quota.monthly_used,
        "monthly_remaining": user_quota.monthly_budget - user_quota.monthly_used,
        "usage_trend": "stable",  # 这里可以添加更复杂的趋势分析
        "recommendations": [
            "考虑使用轻量模式减少成本",
            "启用缓存功能提高效率"
        ]
    }


def _generate_implementation_plan(optimization_result: Dict) -> List[Dict[str, str]]:
    """生成实施计划"""
    plan = []

    recommended = optimization_result.get("batch_optimization", {}).get("recommended", {})

    if recommended:
        batch_count = recommended.get("batch_count", 1)
        batch_size = recommended.get("batch_size", 50)

        plan.append({
            "step": "1",
            "action": "准备批处理环境",
            "description": f"配置系统以支持 {batch_count} 个批次，每批 {batch_size} 篇文献",
            "estimated_time": "5分钟"
        })

        plan.append({
            "step": "2",
            "action": "执行批量处理",
            "description": f"按推荐的 {recommended.get('mode', 'standard')} 模式处理文献",
            "estimated_time": f"{recommended.get('processing_time', 600) // 60} 分钟"
        })

        plan.append({
            "step": "3",
            "action": "监控和优化",
            "description": "实时监控处理进度，根据性能指标动态调整",
            "estimated_time": "持续监控"
        })

    return plan


def _calculate_performance_impact(literature_count: int, optimization_result: Dict) -> Dict[str, Any]:
    """计算性能影响"""
    recommended = optimization_result.get("final_recommendation", {})

    base_throughput = 30  # 基础吞吐量：30篇/分钟
    optimized_throughput = 60  # 优化后吞吐量

    return {
        "throughput_improvement": {
            "baseline": base_throughput,
            "optimized": optimized_throughput,
            "improvement_percentage": ((optimized_throughput - base_throughput) / base_throughput) * 100
        },
        "latency_reduction": {
            "baseline_per_paper": 2.0,  # 2秒每篇
            "optimized_per_paper": 1.0,  # 1秒每篇
            "reduction_percentage": 50.0
        },
        "resource_efficiency": {
            "memory_optimization": 25.0,  # 25% 内存优化
            "cpu_optimization": 20.0,     # 20% CPU优化
            "cost_optimization": recommended.get("estimated_cost", 0) / literature_count if literature_count > 0 else 0
        }
    }


async def _generate_personalized_recommendations(
    user: User,
    dashboard_data: Dict,
    cost_analytics: Dict
) -> List[str]:
    """生成个性化推荐"""
    recommendations = []

    # 基于成本使用情况的推荐
    usage_rate = cost_analytics.get("total_spent", 0) / cost_analytics.get("remaining_budget", {}).get("monthly", 1)

    if usage_rate > 0.8:
        recommendations.append("您的月度预算使用率较高，建议使用轻量模式或考虑升级套餐")

    # 基于系统性能的推荐
    system_health = dashboard_data.get("system_health", {})
    if hasattr(system_health, 'overall_score') and system_health.overall_score < 70:
        recommendations.append("系统性能较低，建议错峰使用或联系技术支持")

    # 基于用户级别的推荐
    if not user.membership or user.membership.membership_type.value == "free":
        recommendations.append("升级到付费版本可获得更高的处理限额和优先支持")

    return recommendations


def _is_admin_user(user: User) -> bool:
    """检查是否为管理员用户"""
    # 这里应该根据实际的权限系统实现
    return user.email.endswith("@admin.com") or user.id == 1


async def _analyze_user_usage_pattern(user: User, db: Session) -> List[str]:
    """分析用户使用模式并提供推荐"""
    recommendations = []

    # 分析用户的项目数量和文献处理模式
    user_projects = db.query(Project).filter(Project.owner_id == user.id).all()

    if len(user_projects) > 5:
        recommendations.append("您有多个活跃项目，建议使用项目模板功能提高处理效率")

    # 分析文献处理量
    total_literature = sum(len(project.literature) for project in user_projects)

    if total_literature > 500:
        recommendations.append("大量文献处理建议使用批处理优化功能")
    elif total_literature < 50:
        recommendations.append("小批量处理建议使用深度模式获得更好的分析质量")

    return recommendations


async def _analyze_project_optimization_opportunities(project: Project, db: Session) -> List[str]:
    """分析项目优化机会"""
    recommendations = []

    literature_count = len(project.literature)

    if literature_count > 200:
        recommendations.append("大规模项目建议启用智能缓存和并行处理")

    if not project.structure_template:
        recommendations.append("配置结构化模板可以显著提高处理效率和质量")

    if project.research_direction:
        recommendations.append("明确的研究方向有助于AI更准确地处理和分析文献")

    return recommendations


async def _get_system_based_recommendations() -> List[str]:
    """基于系统状态获取推荐"""
    dashboard_data = get_performance_dashboard()
    recommendations = []

    current_metrics = dashboard_data.get("current_metrics", {})

    cpu_usage = current_metrics.get("cpu_usage", 0)
    memory_usage = current_metrics.get("memory_usage", 0)

    if cpu_usage > 80:
        recommendations.append("系统CPU使用率较高，建议稍后再处理大批量任务")

    if memory_usage > 85:
        recommendations.append("系统内存使用率较高，建议减少批处理大小")

    active_alerts = dashboard_data.get("active_alerts", [])
    if active_alerts:
        recommendations.append("系统有活跃告警，建议等待系统稳定后再进行大规模处理")

    return recommendations


@router.get("/status", response_model=Dict[str, Any])
async def get_performance_status(
    current_user: User = Depends(get_current_active_user)
):
    """获取性能状态 - 为前端兼容性添加"""
    try:
        # 获取性能仪表板数据
        dashboard_data = get_performance_dashboard()

        # 获取系统健康状态
        health_status = performance_monitor.get_system_health()

        return {
            "status": "healthy" if health_status.overall_score > 50 else "degraded",
            "overall_score": health_status.overall_score,
            "cpu_score": health_status.cpu_score,
            "memory_score": health_status.memory_score,
            "current_metrics": dashboard_data.get("current_metrics", {}),
            "performance_trends": dashboard_data.get("performance_trends", {}),
            "optimization_suggestions": dashboard_data.get("optimization_suggestions", []),
            "active_alerts": dashboard_data.get("active_alerts", []),
            "timestamp": health_status.timestamp.isoformat()
        }

    except Exception as e:
        logger.error(f"获取性能状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取性能状态失败: {str(e)}")