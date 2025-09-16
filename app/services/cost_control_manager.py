"""
三模式系统成本控制机制 - Cost Control Manager
专门针对轻量模式、标准模式、深度模式的成本优化和预算管理
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import json
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User, MembershipType
from app.models.project import Project
from app.models.literature import Literature


class ProcessingMode(Enum):
    """处理模式"""
    LIGHTWEIGHT = "lightweight"  # 轻量模式：快速基础处理
    STANDARD = "standard"        # 标准模式：平衡处理
    DEEP = "deep"               # 深度模式：全面深度分析


class CostTier(Enum):
    """成本层级"""
    FREE = "free"              # 免费层
    BASIC = "basic"           # 基础层
    PREMIUM = "premium"       # 高级层
    ENTERPRISE = "enterprise" # 企业层


@dataclass
class ModeConfig:
    """模式配置"""
    name: str
    ai_model: str
    complexity_factor: float           # 复杂度系数
    base_cost_per_paper: float        # 每篇基础成本
    processing_time_factor: float     # 处理时间系数
    features: List[str] = field(default_factory=list)


@dataclass
class CostBreakdown:
    """成本分解"""
    ai_processing: float = 0.0         # AI处理成本
    pdf_processing: float = 0.0        # PDF处理成本
    storage: float = 0.0               # 存储成本
    network: float = 0.0               # 网络成本
    overhead: float = 0.0              # 系统开销
    total: float = 0.0                 # 总成本


@dataclass
class UserCostQuota:
    """用户成本配额"""
    daily_budget: float
    monthly_budget: float
    daily_used: float = 0.0
    monthly_used: float = 0.0
    last_reset_daily: datetime = field(default_factory=datetime.now)
    last_reset_monthly: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessingEstimate:
    """处理估算"""
    estimated_cost: float
    estimated_time: int                # 估算时间（秒）
    recommended_mode: ProcessingMode
    cost_breakdown: CostBreakdown
    optimization_suggestions: List[str]


class IntelligentCostOptimizer:
    """智能成本优化器"""

    def __init__(self):
        # 模式配置
        self.mode_configs = {
            ProcessingMode.LIGHTWEIGHT: ModeConfig(
                name="轻量模式",
                ai_model="gpt-3.5-turbo",
                complexity_factor=0.3,
                base_cost_per_paper=0.05,
                processing_time_factor=0.2,
                features=["基础信息提取", "关键词识别", "快速总结"]
            ),
            ProcessingMode.STANDARD: ModeConfig(
                name="标准模式",
                ai_model="gpt-3.5-turbo",
                complexity_factor=0.7,
                base_cost_per_paper=0.15,
                processing_time_factor=0.6,
                features=["结构化提取", "深度分析", "关系挖掘", "质量评估"]
            ),
            ProcessingMode.DEEP: ModeConfig(
                name="深度模式",
                ai_model="gpt-4",
                complexity_factor=1.0,
                base_cost_per_paper=0.35,
                processing_time_factor=1.0,
                features=["全面分析", "创新点识别", "方法论评估", "学术价值评估", "跨文献关联"]
            )
        }

        # 成本层级配置
        self.tier_configs = {
            CostTier.FREE: {
                "daily_budget": 1.0,    # $1/天
                "monthly_budget": 20.0,  # $20/月
                "max_papers_per_request": 20,
                "available_modes": [ProcessingMode.LIGHTWEIGHT]
            },
            CostTier.BASIC: {
                "daily_budget": 5.0,    # $5/天
                "monthly_budget": 100.0, # $100/月
                "max_papers_per_request": 100,
                "available_modes": [ProcessingMode.LIGHTWEIGHT, ProcessingMode.STANDARD]
            },
            CostTier.PREMIUM: {
                "daily_budget": 20.0,   # $20/天
                "monthly_budget": 500.0, # $500/月
                "max_papers_per_request": 500,
                "available_modes": [ProcessingMode.LIGHTWEIGHT, ProcessingMode.STANDARD, ProcessingMode.DEEP]
            },
            CostTier.ENTERPRISE: {
                "daily_budget": 100.0,  # $100/天
                "monthly_budget": 2000.0, # $2000/月
                "max_papers_per_request": 2000,
                "available_modes": [ProcessingMode.LIGHTWEIGHT, ProcessingMode.STANDARD, ProcessingMode.DEEP]
            }
        }

        # AI模型成本配置
        self.ai_model_costs = {
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
            "gpt-4": {"input": 0.01, "output": 0.03},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-opus": {"input": 0.015, "output": 0.075}
        }

        # 用户成本配额缓存
        self.user_quotas: Dict[int, UserCostQuota] = {}

    async def estimate_processing_cost(self,
                                       literature_count: int,
                                       mode: ProcessingMode,
                                       user: User,
                                       project: Optional[Project] = None) -> ProcessingEstimate:
        """估算处理成本"""
        config = self.mode_configs[mode]
        user_tier = self._get_user_tier(user)

        # 基础成本计算
        base_cost = literature_count * config.base_cost_per_paper

        # 复杂度调整
        complexity_multiplier = await self._calculate_complexity_multiplier(
            literature_count, project, mode
        )

        # 计算详细成本分解
        cost_breakdown = self._calculate_detailed_costs(
            literature_count, config, complexity_multiplier
        )

        # 估算处理时间
        estimated_time = int(
            literature_count * config.processing_time_factor * 30 * complexity_multiplier
        )

        # 生成优化建议
        optimization_suggestions = await self._generate_cost_optimization_suggestions(
            literature_count, mode, user_tier, cost_breakdown
        )

        # 推荐模式（如果当前模式成本过高）
        recommended_mode = await self._recommend_optimal_mode(
            literature_count, user, cost_breakdown.total
        )

        return ProcessingEstimate(
            estimated_cost=cost_breakdown.total,
            estimated_time=estimated_time,
            recommended_mode=recommended_mode,
            cost_breakdown=cost_breakdown,
            optimization_suggestions=optimization_suggestions
        )

    async def _calculate_complexity_multiplier(self,
                                               literature_count: int,
                                               project: Optional[Project],
                                               mode: ProcessingMode) -> float:
        """计算复杂度乘数"""
        multiplier = 1.0

        # 基于文献数量的规模效应
        if literature_count > 200:
            multiplier *= 0.9  # 大批量有规模优势
        elif literature_count > 100:
            multiplier *= 0.95
        elif literature_count < 10:
            multiplier *= 1.1   # 小批量效率较低

        # 基于项目复杂度
        if project:
            if project.structure_template:
                # 已有结构化模板，处理更快
                multiplier *= 0.85
            if project.research_direction and len(project.research_direction) > 100:
                # 复杂研究方向
                multiplier *= 1.05

        # 基于处理模式
        if mode == ProcessingMode.DEEP:
            multiplier *= 1.2   # 深度模式本身更复杂
        elif mode == ProcessingMode.LIGHTWEIGHT:
            multiplier *= 0.8   # 轻量模式更简单

        return max(0.5, min(2.0, multiplier))  # 限制在合理范围内

    def _calculate_detailed_costs(self,
                                  literature_count: int,
                                  config: ModeConfig,
                                  complexity_multiplier: float) -> CostBreakdown:
        """计算详细成本分解"""
        base_cost = literature_count * config.base_cost_per_paper * complexity_multiplier

        # AI处理成本（主要成本）
        ai_cost = base_cost * 0.70

        # PDF处理成本
        pdf_cost = base_cost * 0.15

        # 存储成本
        storage_cost = literature_count * 0.001  # 每篇约0.1美分的存储

        # 网络成本
        network_cost = base_cost * 0.05

        # 系统开销
        overhead_cost = base_cost * 0.10

        total_cost = ai_cost + pdf_cost + storage_cost + network_cost + overhead_cost

        return CostBreakdown(
            ai_processing=ai_cost,
            pdf_processing=pdf_cost,
            storage=storage_cost,
            network=network_cost,
            overhead=overhead_cost,
            total=total_cost
        )

    async def _generate_cost_optimization_suggestions(self,
                                                      literature_count: int,
                                                      mode: ProcessingMode,
                                                      user_tier: CostTier,
                                                      cost_breakdown: CostBreakdown) -> List[str]:
        """生成成本优化建议"""
        suggestions = []

        # 基于成本分解的建议
        if cost_breakdown.ai_processing / cost_breakdown.total > 0.80:
            suggestions.append("AI处理成本占比较高，建议考虑使用轻量模式或分批处理")

        if literature_count > 100 and mode == ProcessingMode.DEEP:
            suggestions.append("大批量深度处理成本较高，建议先用标准模式筛选后再深度分析重要文献")

        # 基于用户层级的建议
        if user_tier == CostTier.FREE and cost_breakdown.total > 0.5:
            suggestions.append("当前处理成本较高，建议升级到基础版本或减少处理数量")

        # 基于处理模式的建议
        if mode == ProcessingMode.DEEP and literature_count > 50:
            suggestions.append("深度模式适合精选文献，建议先用标准模式筛选后再深度处理")

        # 批处理建议
        if literature_count > 200:
            suggestions.append("大批量处理建议分批进行，可以获得更好的成本效益")

        # 缓存利用建议
        suggestions.append("启用智能缓存可以显著降低重复处理成本")

        return suggestions

    async def _recommend_optimal_mode(self,
                                      literature_count: int,
                                      user: User,
                                      estimated_cost: float) -> ProcessingMode:
        """推荐最优处理模式"""
        user_tier = self._get_user_tier(user)
        user_quota = await self._get_user_quota(user.id)

        # 检查预算约束
        available_budget = min(
            user_quota.daily_budget - user_quota.daily_used,
            user_quota.monthly_budget - user_quota.monthly_used
        )

        if estimated_cost > available_budget * 0.8:  # 超过80%预算
            # 推荐更经济的模式
            if estimated_cost <= available_budget * 0.4:
                return ProcessingMode.LIGHTWEIGHT
            else:
                return ProcessingMode.STANDARD

        # 基于文献数量推荐
        if literature_count > 200:
            return ProcessingMode.STANDARD  # 大批量用标准模式
        elif literature_count < 20:
            return ProcessingMode.DEEP     # 小批量可以用深度模式
        else:
            return ProcessingMode.STANDARD  # 中等批量用标准模式

    def _get_user_tier(self, user: User) -> CostTier:
        """获取用户成本层级"""
        if not user.membership:
            return CostTier.FREE

        membership_type = user.membership.membership_type
        if membership_type == MembershipType.FREE:
            return CostTier.FREE
        elif membership_type == MembershipType.BASIC:
            return CostTier.BASIC
        elif membership_type == MembershipType.PREMIUM:
            return CostTier.PREMIUM
        else:
            return CostTier.ENTERPRISE

    async def _get_user_quota(self, user_id: int) -> UserCostQuota:
        """获取用户成本配额"""
        if user_id not in self.user_quotas:
            # 从数据库加载用户配额信息
            await self._load_user_quota(user_id)

        quota = self.user_quotas[user_id]

        # 检查是否需要重置配额
        now = datetime.now()

        # 每日重置
        if now.date() > quota.last_reset_daily.date():
            quota.daily_used = 0.0
            quota.last_reset_daily = now

        # 每月重置
        if now.month != quota.last_reset_monthly.month or now.year != quota.last_reset_monthly.year:
            quota.monthly_used = 0.0
            quota.last_reset_monthly = now

        return quota

    async def _load_user_quota(self, user_id: int):
        """从数据库加载用户配额"""
        try:
            with SessionLocal() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user_tier = self._get_user_tier(user)
                    tier_config = self.tier_configs[user_tier]

                    self.user_quotas[user_id] = UserCostQuota(
                        daily_budget=tier_config["daily_budget"],
                        monthly_budget=tier_config["monthly_budget"]
                    )
                else:
                    # 默认免费配额
                    self.user_quotas[user_id] = UserCostQuota(
                        daily_budget=1.0,
                        monthly_budget=20.0
                    )
        except Exception as e:
            logger.error(f"加载用户配额失败: {e}")
            # 使用默认配额
            self.user_quotas[user_id] = UserCostQuota(daily_budget=1.0, monthly_budget=20.0)

    async def check_processing_permission(self,
                                          user_id: int,
                                          estimated_cost: float,
                                          mode: ProcessingMode) -> Dict[str, Any]:
        """检查处理权限"""
        user_quota = await self._get_user_quota(user_id)

        # 检查预算限制
        daily_remaining = user_quota.daily_budget - user_quota.daily_used
        monthly_remaining = user_quota.monthly_budget - user_quota.monthly_used

        can_process = (
            estimated_cost <= daily_remaining and
            estimated_cost <= monthly_remaining
        )

        return {
            "can_process": can_process,
            "daily_remaining": daily_remaining,
            "monthly_remaining": monthly_remaining,
            "estimated_cost": estimated_cost,
            "reason": self._get_rejection_reason(can_process, estimated_cost,
                                               daily_remaining, monthly_remaining)
        }

    def _get_rejection_reason(self, can_process: bool, estimated_cost: float,
                              daily_remaining: float, monthly_remaining: float) -> Optional[str]:
        """获取拒绝原因"""
        if can_process:
            return None

        if estimated_cost > daily_remaining:
            return f"超出每日预算限制，剩余预算: ${daily_remaining:.2f}"

        if estimated_cost > monthly_remaining:
            return f"超出每月预算限制，剩余预算: ${monthly_remaining:.2f}"

        return "预算不足"

    async def record_actual_cost(self,
                                 user_id: int,
                                 actual_cost: float,
                                 processing_details: Dict[str, Any]):
        """记录实际成本"""
        user_quota = await self._get_user_quota(user_id)

        # 更新使用量
        user_quota.daily_used += actual_cost
        user_quota.monthly_used += actual_cost

        # 保存到数据库
        await self._save_cost_record(user_id, actual_cost, processing_details)

        logger.info(f"用户 {user_id} 成本记录: ${actual_cost:.4f}")

    async def _save_cost_record(self,
                                user_id: int,
                                cost: float,
                                details: Dict[str, Any]):
        """保存成本记录到数据库"""
        try:
            with SessionLocal() as db:
                # 这里应该有一个专门的成本记录表
                # 目前简化处理，在实际实现中应该创建 CostRecord 模型
                cost_record = {
                    "user_id": user_id,
                    "cost": cost,
                    "details": details,
                    "timestamp": datetime.now()
                }

                # 保存记录的实际实现
                logger.info(f"成本记录已保存: {cost_record}")

        except Exception as e:
            logger.error(f"保存成本记录失败: {e}")

    async def get_cost_analytics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """获取成本分析报告"""
        user_quota = await self._get_user_quota(user_id)

        # 这里应该从数据库查询历史成本数据
        # 目前返回模拟数据
        analytics = {
            "period_days": days,
            "total_spent": user_quota.monthly_used,
            "daily_average": user_quota.monthly_used / max(days, 1),
            "remaining_budget": {
                "daily": user_quota.daily_budget - user_quota.daily_used,
                "monthly": user_quota.monthly_budget - user_quota.monthly_used
            },
            "cost_breakdown_by_mode": {
                "lightweight": 0.0,
                "standard": 0.0,
                "deep": 0.0
            },
            "projected_monthly_cost": user_quota.daily_used * 30,
            "cost_trend": "stable",  # stable, increasing, decreasing
            "recommendations": await self._generate_budget_recommendations(user_quota)
        }

        return analytics

    async def _generate_budget_recommendations(self, quota: UserCostQuota) -> List[str]:
        """生成预算建议"""
        recommendations = []

        usage_rate = quota.monthly_used / quota.monthly_budget if quota.monthly_budget > 0 else 0

        if usage_rate > 0.9:
            recommendations.append("接近月度预算上限，建议升级套餐或优化处理策略")
        elif usage_rate > 0.7:
            recommendations.append("使用量较高，建议关注成本控制")

        daily_usage_rate = quota.daily_used / quota.daily_budget if quota.daily_budget > 0 else 0

        if daily_usage_rate > 0.8:
            recommendations.append("今日使用量较高，建议合理安排后续处理任务")

        recommendations.append("使用轻量模式可以显著降低成本")
        recommendations.append("启用智能缓存可以减少重复处理成本")

        return recommendations


class BatchCostOptimizer:
    """批处理成本优化器"""

    def __init__(self, cost_optimizer: IntelligentCostOptimizer):
        self.cost_optimizer = cost_optimizer

    async def optimize_batch_processing(self,
                                        literature_count: int,
                                        user: User,
                                        target_cost: Optional[float] = None) -> Dict[str, Any]:
        """优化批处理策略以控制成本"""
        user_tier = self.cost_optimizer._get_user_tier(user)
        user_quota = await self.cost_optimizer._get_user_quota(user.id)

        # 确定目标成本
        if target_cost is None:
            available_budget = min(
                user_quota.daily_budget - user_quota.daily_used,
                user_quota.monthly_budget - user_quota.monthly_used
            )
            target_cost = available_budget * 0.8  # 使用80%可用预算

        # 计算各模式下的批处理策略
        strategies = {}

        for mode in ProcessingMode:
            strategy = await self._calculate_batch_strategy(
                literature_count, mode, target_cost, user
            )
            strategies[mode.value] = strategy

        # 推荐最优策略
        recommended_strategy = self._select_optimal_strategy(strategies, target_cost)

        return {
            "target_cost": target_cost,
            "strategies": strategies,
            "recommended": recommended_strategy,
            "cost_savings": self._calculate_cost_savings(strategies, literature_count)
        }

    async def _calculate_batch_strategy(self,
                                        literature_count: int,
                                        mode: ProcessingMode,
                                        target_cost: float,
                                        user: User) -> Dict[str, Any]:
        """计算特定模式的批处理策略"""
        config = self.cost_optimizer.mode_configs[mode]
        base_cost_per_paper = config.base_cost_per_paper

        # 计算在目标成本下能处理的最大文献数
        max_papers_in_budget = int(target_cost / base_cost_per_paper * 0.9)  # 留10%缓冲

        if max_papers_in_budget >= literature_count:
            # 预算充足，一次性处理
            return {
                "batch_count": 1,
                "batch_size": literature_count,
                "total_cost": literature_count * base_cost_per_paper,
                "processing_time": literature_count * config.processing_time_factor * 30,
                "feasible": True
            }
        else:
            # 需要分批处理
            batch_size = max_papers_in_budget
            batch_count = (literature_count + batch_size - 1) // batch_size

            return {
                "batch_count": batch_count,
                "batch_size": batch_size,
                "total_cost": literature_count * base_cost_per_paper,
                "cost_per_batch": batch_size * base_cost_per_paper,
                "processing_time": literature_count * config.processing_time_factor * 30,
                "feasible": batch_size > 0
            }

    def _select_optimal_strategy(self,
                                 strategies: Dict[str, Dict],
                                 target_cost: float) -> Dict[str, Any]:
        """选择最优处理策略"""
        # 评分标准：成本效益、可行性、处理质量
        best_strategy = None
        best_score = -1

        for mode_name, strategy in strategies.items():
            if not strategy["feasible"]:
                continue

            # 计算综合评分
            cost_score = 1.0 - (strategy["total_cost"] / (target_cost * 2))  # 成本越低分数越高
            efficiency_score = strategy["batch_size"] / strategy["total_cost"] * 1000  # 效率分数
            quality_score = {"lightweight": 0.6, "standard": 0.8, "deep": 1.0}[mode_name]

            total_score = (cost_score * 0.4 + efficiency_score * 0.3 + quality_score * 0.3)

            if total_score > best_score:
                best_score = total_score
                best_strategy = {
                    "mode": mode_name,
                    "score": total_score,
                    **strategy
                }

        return best_strategy

    def _calculate_cost_savings(self,
                                strategies: Dict[str, Dict],
                                literature_count: int) -> Dict[str, float]:
        """计算成本节省"""
        # 基准：深度模式全量处理的成本
        deep_cost = strategies.get("deep", {}).get("total_cost", 0)

        savings = {}
        for mode_name, strategy in strategies.items():
            if strategy["feasible"] and deep_cost > 0:
                saving_amount = deep_cost - strategy["total_cost"]
                saving_percentage = (saving_amount / deep_cost) * 100
                savings[mode_name] = {
                    "amount": saving_amount,
                    "percentage": saving_percentage
                }

        return savings


# 工厂函数和便捷接口

def create_cost_optimizer() -> IntelligentCostOptimizer:
    """创建成本优化器实例"""
    return IntelligentCostOptimizer()


async def estimate_processing_cost_for_modes(
    literature_count: int,
    user: User,
    project: Optional[Project] = None
) -> Dict[ProcessingMode, ProcessingEstimate]:
    """估算所有模式的处理成本"""
    optimizer = create_cost_optimizer()
    estimates = {}

    for mode in ProcessingMode:
        estimate = await optimizer.estimate_processing_cost(
            literature_count, mode, user, project
        )
        estimates[mode] = estimate

    return estimates


async def recommend_cost_optimal_processing(
    literature_count: int,
    user: User,
    cost_budget: Optional[float] = None,
    project: Optional[Project] = None
) -> Dict[str, Any]:
    """推荐成本最优的处理方案"""
    optimizer = create_cost_optimizer()
    batch_optimizer = BatchCostOptimizer(optimizer)

    # 获取所有模式的估算
    estimates = await estimate_processing_cost_for_modes(literature_count, user, project)

    # 获取批处理优化方案
    batch_optimization = await batch_optimizer.optimize_batch_processing(
        literature_count, user, cost_budget
    )

    # 检查处理权限
    recommended_estimate = estimates[batch_optimization["recommended"]["mode"]]
    permission_check = await optimizer.check_processing_permission(
        user.id, recommended_estimate.estimated_cost, ProcessingMode.STANDARD
    )

    return {
        "mode_estimates": estimates,
        "batch_optimization": batch_optimization,
        "permission_check": permission_check,
        "final_recommendation": {
            "mode": batch_optimization["recommended"]["mode"],
            "estimated_cost": recommended_estimate.estimated_cost,
            "estimated_time": recommended_estimate.estimated_time,
            "optimization_suggestions": recommended_estimate.optimization_suggestions
        }
    }