"""
预测性分析系统
提供时间预估、质量预判、风险预警和资源需求预测
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import json
import numpy as np
from pydantic import BaseModel
from enum import Enum
import logging
from dataclasses import dataclass
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


class PredictionType(Enum):
    """预测类型枚举"""
    TIME_ESTIMATION = "time_estimation"
    QUALITY_PREDICTION = "quality_prediction"
    RESOURCE_DEMAND = "resource_demand"
    RISK_ASSESSMENT = "risk_assessment"
    SUCCESS_PROBABILITY = "success_probability"


class RiskLevel(Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TimeEstimation:
    """时间估算结果"""
    estimated_minutes: float
    confidence_interval: Tuple[float, float]  # (min, max)
    confidence_score: float
    factors_considered: List[str]
    breakdown: Dict[str, float] = None


@dataclass
class QualityPrediction:
    """质量预测结果"""
    predicted_score: float
    quality_level: str
    confidence: float
    key_factors: List[Dict[str, Any]]
    improvement_potential: float


@dataclass
class RiskAssessment:
    """风险评估结果"""
    overall_risk_level: RiskLevel
    risk_factors: List[Dict[str, Any]]
    mitigation_strategies: List[str]
    probability_of_issues: float


class TaskComplexityAnalyzer:
    """任务复杂度分析器"""
    
    def __init__(self):
        self.complexity_weights = {
            "literature_count": 0.3,
            "domain_complexity": 0.2,
            "user_experience": 0.2,
            "custom_requirements": 0.15,
            "data_quality": 0.15
        }
        
        self.domain_complexity_scores = {
            "materials_science": 0.8,
            "chemistry": 0.7,
            "physics": 0.9,
            "biology": 0.6,
            "engineering": 0.7,
            "interdisciplinary": 1.0
        }
    
    async def analyze_task_complexity(self, task_params: Dict[str, Any]) -> float:
        """分析任务复杂度 (0-1)"""
        
        complexity_score = 0.0
        
        # 文献数量复杂度
        literature_count = task_params.get("literature_count", 100)
        lit_complexity = min(literature_count / 5000, 1.0)  # 5000篇为满分
        complexity_score += lit_complexity * self.complexity_weights["literature_count"]
        
        # 领域复杂度
        domain = task_params.get("domain", "materials_science")
        domain_complexity = self.domain_complexity_scores.get(domain, 0.7)
        complexity_score += domain_complexity * self.complexity_weights["domain_complexity"]
        
        # 用户经验复杂度（经验越少，任务越复杂）
        user_experience = task_params.get("user_experience_score", 0.5)
        exp_complexity = 1.0 - user_experience
        complexity_score += exp_complexity * self.complexity_weights["user_experience"]
        
        # 自定义需求复杂度
        custom_template = task_params.get("has_custom_template", False)
        custom_workflow = task_params.get("has_custom_workflow", False)
        custom_complexity = 0.3 * custom_template + 0.7 * custom_workflow
        complexity_score += custom_complexity * self.complexity_weights["custom_requirements"]
        
        # 数据质量复杂度（质量越低，处理越复杂）
        data_quality = task_params.get("data_quality_score", 0.8)
        quality_complexity = 1.0 - data_quality
        complexity_score += quality_complexity * self.complexity_weights["data_quality"]
        
        return min(complexity_score, 1.0)


class TimePredictor:
    """时间预测器"""
    
    def __init__(self):
        self.base_times = {
            "literature_collection": 0.5,  # 每100篇文献的基础时间（分钟）
            "quality_assessment": 0.1,     # 每篇文献的评估时间
            "structuring": 2.0,            # 每篇文献的结构化时间
            "experience_enhancement": 15.0, # 每轮迭代时间
            "solution_generation": 5.0      # 方案生成基础时间
        }
        
        self.complexity_multipliers = {
            "low": 0.8,
            "medium": 1.0,
            "high": 1.5,
            "very_high": 2.0
        }
    
    async def predict_literature_collection_time(self, task_params: Dict[str, Any]) -> TimeEstimation:
        """预测文献采集时间"""
        
        literature_count = task_params.get("target_literature_count", 1000)
        data_sources = task_params.get("data_sources", ["google_scholar"])
        user_experience = task_params.get("user_experience_score", 0.5)
        
        # 基础时间计算
        base_time = (literature_count / 100) * self.base_times["literature_collection"]
        
        # 数据源复杂度调整
        source_multiplier = 1.0 + 0.2 * (len(data_sources) - 1)
        
        # 用户经验调整
        experience_multiplier = 1.5 - user_experience * 0.5
        
        # 网络和API限制因素
        api_delay_factor = 1.2  # API调用延迟
        
        estimated_time = base_time * source_multiplier * experience_multiplier * api_delay_factor
        
        # 置信区间
        confidence_interval = (
            estimated_time * 0.7,  # 最乐观情况
            estimated_time * 1.5   # 最悲观情况
        )
        
        factors = [
            f"目标文献数量: {literature_count}",
            f"数据源数量: {len(data_sources)}",
            f"用户经验影响: {experience_multiplier:.1f}x",
            "API调用延迟因素"
        ]
        
        return TimeEstimation(
            estimated_minutes=estimated_time,
            confidence_interval=confidence_interval,
            confidence_score=0.8,
            factors_considered=factors
        )
    
    async def predict_structuring_time(self, task_params: Dict[str, Any]) -> TimeEstimation:
        """预测结构化处理时间"""
        
        literature_count = task_params.get("literature_count", 1000)
        complexity = await self._get_complexity_level(task_params)
        has_custom_template = task_params.get("has_custom_template", False)
        
        # 基础时间
        base_time = literature_count * self.base_times["structuring"]
        
        # 复杂度调整
        complexity_multiplier = self.complexity_multipliers.get(complexity, 1.0)
        
        # 自定义模板调整
        template_multiplier = 1.3 if has_custom_template else 1.0
        
        # 并行处理优化
        parallel_factor = 0.6  # 并行处理可减少40%时间
        
        estimated_time = base_time * complexity_multiplier * template_multiplier * parallel_factor
        
        # 置信区间
        confidence_interval = (
            estimated_time * 0.8,
            estimated_time * 1.3
        )
        
        breakdown = {
            "基础处理时间": base_time,
            "复杂度调整": base_time * (complexity_multiplier - 1),
            "模板定制": base_time * (template_multiplier - 1),
            "并行优化节省": base_time * (1 - parallel_factor)
        }
        
        factors = [
            f"文献数量: {literature_count}",
            f"复杂度等级: {complexity}",
            f"自定义模板: {'是' if has_custom_template else '否'}",
            "并行处理优化"
        ]
        
        return TimeEstimation(
            estimated_minutes=estimated_time,
            confidence_interval=confidence_interval,
            confidence_score=0.85,
            factors_considered=factors,
            breakdown=breakdown
        )
    
    async def predict_experience_enhancement_time(self, task_params: Dict[str, Any]) -> TimeEstimation:
        """预测经验增强时间"""
        
        literature_count = task_params.get("literature_count", 1000)
        target_quality = task_params.get("target_quality_score", 0.9)
        current_quality = task_params.get("current_quality_score", 0.6)
        
        # 估算需要的迭代轮次
        quality_gap = target_quality - current_quality
        estimated_rounds = max(math.ceil(quality_gap / 0.1), 3)  # 每轮提升约10%
        
        # 每轮时间随文献数量和复杂度调整
        per_round_time = self.base_times["experience_enhancement"]
        if literature_count > 2000:
            per_round_time *= 1.5
        elif literature_count > 5000:
            per_round_time *= 2.0
        
        estimated_time = estimated_rounds * per_round_time
        
        # 考虑动态停止机制
        early_stop_probability = 0.3  # 30%概率提前停止
        adjusted_time = estimated_time * (1 - early_stop_probability * 0.3)
        
        confidence_interval = (
            adjusted_time * 0.6,  # 提前收敛
            estimated_time * 1.2  # 需要额外轮次
        )
        
        factors = [
            f"预估迭代轮次: {estimated_rounds}",
            f"质量提升目标: {quality_gap:.1f}",
            f"文献规模影响: {literature_count}篇",
            "动态停止机制"
        ]
        
        breakdown = {
            "迭代轮次": estimated_rounds,
            "每轮平均时间": per_round_time,
            "规模调整": per_round_time * (1.5 if literature_count > 2000 else 1.0) - per_round_time,
            "提前停止节省": estimated_time * early_stop_probability * 0.3
        }
        
        return TimeEstimation(
            estimated_minutes=adjusted_time,
            confidence_interval=confidence_interval,
            confidence_score=0.75,
            factors_considered=factors,
            breakdown=breakdown
        )
    
    async def _get_complexity_level(self, task_params: Dict[str, Any]) -> str:
        """获取任务复杂度等级"""
        complexity_analyzer = TaskComplexityAnalyzer()
        complexity_score = await complexity_analyzer.analyze_task_complexity(task_params)
        
        if complexity_score < 0.3:
            return "low"
        elif complexity_score < 0.6:
            return "medium"
        elif complexity_score < 0.8:
            return "high"
        else:
            return "very_high"


class QualityPredictor:
    """质量预测器"""
    
    def __init__(self):
        self.quality_factors = {
            "literature_quality": 0.3,
            "template_fitness": 0.25,
            "user_expertise": 0.2,
            "domain_complexity": 0.15,
            "iteration_potential": 0.1
        }
    
    async def predict_final_quality(self, task_params: Dict[str, Any]) -> QualityPrediction:
        """预测最终质量"""
        
        # 分析各个质量因子
        literature_quality = task_params.get("literature_quality_score", 0.8)
        template_fitness = await self._assess_template_fitness(task_params)
        user_expertise = task_params.get("user_experience_score", 0.5)
        domain_complexity = await self._assess_domain_complexity(task_params)
        iteration_potential = await self._assess_iteration_potential(task_params)
        
        # 计算加权质量分数
        predicted_score = (
            literature_quality * self.quality_factors["literature_quality"] +
            template_fitness * self.quality_factors["template_fitness"] +
            user_expertise * self.quality_factors["user_expertise"] +
            (1 - domain_complexity) * self.quality_factors["domain_complexity"] +  # 复杂度越低，质量越高
            iteration_potential * self.quality_factors["iteration_potential"]
        )
        
        # 确定质量等级
        if predicted_score >= 0.9:
            quality_level = "优秀"
        elif predicted_score >= 0.8:
            quality_level = "良好"
        elif predicted_score >= 0.7:
            quality_level = "中等"
        elif predicted_score >= 0.6:
            quality_level = "一般"
        else:
            quality_level = "需要改进"
        
        # 关键影响因子
        key_factors = [
            {"factor": "文献质量", "impact": literature_quality, "weight": self.quality_factors["literature_quality"]},
            {"factor": "模板适配性", "impact": template_fitness, "weight": self.quality_factors["template_fitness"]},
            {"factor": "用户专业度", "impact": user_expertise, "weight": self.quality_factors["user_expertise"]},
            {"factor": "领域复杂度", "impact": 1 - domain_complexity, "weight": self.quality_factors["domain_complexity"]},
            {"factor": "迭代潜力", "impact": iteration_potential, "weight": self.quality_factors["iteration_potential"]}
        ]
        
        # 排序关键因子
        key_factors.sort(key=lambda x: x["impact"] * x["weight"], reverse=True)
        
        # 改进潜力
        improvement_potential = min((1.0 - predicted_score) * iteration_potential * 2, 0.3)
        
        return QualityPrediction(
            predicted_score=predicted_score,
            quality_level=quality_level,
            confidence=0.8,
            key_factors=key_factors[:3],
            improvement_potential=improvement_potential
        )
    
    async def _assess_template_fitness(self, task_params: Dict[str, Any]) -> float:
        """评估模板适配性"""
        
        domain = task_params.get("domain", "materials_science")
        has_custom_template = task_params.get("has_custom_template", False)
        literature_diversity = task_params.get("literature_diversity_score", 0.7)
        
        base_fitness = 0.8  # 标准模板基础适配性
        
        if has_custom_template:
            base_fitness = 0.95  # 自定义模板适配性更高
        
        # 文献多样性影响适配性
        diversity_impact = literature_diversity * 0.2
        
        return min(base_fitness + diversity_impact, 1.0)
    
    async def _assess_domain_complexity(self, task_params: Dict[str, Any]) -> float:
        """评估领域复杂度"""
        
        complexity_analyzer = TaskComplexityAnalyzer()
        return await complexity_analyzer.analyze_task_complexity(task_params)
    
    async def _assess_iteration_potential(self, task_params: Dict[str, Any]) -> float:
        """评估迭代改进潜力"""
        
        literature_count = task_params.get("literature_count", 1000)
        initial_quality = task_params.get("current_quality_score", 0.6)
        
        # 文献数量越多，迭代潜力越大
        count_factor = min(literature_count / 2000, 1.0)
        
        # 初始质量越低，改进空间越大
        quality_factor = 1.0 - initial_quality
        
        return (count_factor + quality_factor) / 2


class RiskAssessor:
    """风险评估器"""
    
    def __init__(self):
        self.risk_categories = {
            "data_quality": "数据质量风险",
            "technical": "技术风险",
            "time": "时间风险",
            "resource": "资源风险",
            "user_experience": "用户体验风险"
        }
    
    async def assess_project_risks(self, task_params: Dict[str, Any]) -> RiskAssessment:
        """评估项目风险"""
        
        risk_factors = []
        overall_risk_score = 0.0
        
        # 数据质量风险
        data_quality_risk = await self._assess_data_quality_risk(task_params)
        risk_factors.append(data_quality_risk)
        overall_risk_score += data_quality_risk["score"] * 0.3
        
        # 技术风险
        technical_risk = await self._assess_technical_risk(task_params)
        risk_factors.append(technical_risk)
        overall_risk_score += technical_risk["score"] * 0.25
        
        # 时间风险
        time_risk = await self._assess_time_risk(task_params)
        risk_factors.append(time_risk)
        overall_risk_score += time_risk["score"] * 0.2
        
        # 资源风险
        resource_risk = await self._assess_resource_risk(task_params)
        risk_factors.append(resource_risk)
        overall_risk_score += resource_risk["score"] * 0.15
        
        # 用户体验风险
        ux_risk = await self._assess_user_experience_risk(task_params)
        risk_factors.append(ux_risk)
        overall_risk_score += ux_risk["score"] * 0.1
        
        # 确定总体风险等级
        if overall_risk_score < 0.3:
            overall_risk_level = RiskLevel.LOW
        elif overall_risk_score < 0.6:
            overall_risk_level = RiskLevel.MEDIUM
        elif overall_risk_score < 0.8:
            overall_risk_level = RiskLevel.HIGH
        else:
            overall_risk_level = RiskLevel.CRITICAL
        
        # 生成缓解策略
        mitigation_strategies = self._generate_mitigation_strategies(risk_factors)
        
        return RiskAssessment(
            overall_risk_level=overall_risk_level,
            risk_factors=risk_factors,
            mitigation_strategies=mitigation_strategies,
            probability_of_issues=overall_risk_score
        )
    
    async def _assess_data_quality_risk(self, task_params: Dict[str, Any]) -> Dict[str, Any]:
        """评估数据质量风险"""
        
        data_quality = task_params.get("data_quality_score", 0.8)
        literature_count = task_params.get("literature_count", 1000)
        data_sources = task_params.get("data_sources", ["google_scholar"])
        
        risk_score = 0.0
        
        # 数据质量分数风险
        if data_quality < 0.6:
            risk_score += 0.5
        elif data_quality < 0.8:
            risk_score += 0.3
        
        # 数据量风险
        if literature_count < 100:
            risk_score += 0.3
        elif literature_count > 10000:
            risk_score += 0.2
        
        # 数据源多样性风险
        if len(data_sources) == 1:
            risk_score += 0.2
        
        return {
            "category": "data_quality",
            "name": "数据质量风险",
            "score": min(risk_score, 1.0),
            "description": f"数据质量分数: {data_quality}, 文献数量: {literature_count}",
            "impact": "可能影响最终结果的准确性和可靠性"
        }
    
    async def _assess_technical_risk(self, task_params: Dict[str, Any]) -> Dict[str, Any]:
        """评估技术风险"""
        
        has_custom_template = task_params.get("has_custom_template", False)
        domain_complexity = task_params.get("domain_complexity", 0.5)
        api_dependencies = task_params.get("api_dependencies", 2)
        
        risk_score = 0.0
        
        # 自定义模板风险
        if has_custom_template:
            risk_score += 0.3
        
        # 领域复杂度风险
        risk_score += domain_complexity * 0.4
        
        # API依赖风险
        if api_dependencies > 3:
            risk_score += 0.3
        
        return {
            "category": "technical",
            "name": "技术实现风险",
            "score": min(risk_score, 1.0),
            "description": f"自定义需求: {'有' if has_custom_template else '无'}, API依赖: {api_dependencies}个",
            "impact": "可能导致系统故障或性能问题"
        }
    
    async def _assess_time_risk(self, task_params: Dict[str, Any]) -> Dict[str, Any]:
        """评估时间风险"""
        
        deadline = task_params.get("deadline_hours", 48)
        estimated_time = task_params.get("estimated_time_hours", 24)
        user_availability = task_params.get("user_availability", 0.8)
        
        risk_score = 0.0
        
        # 时间紧张度
        time_ratio = estimated_time / deadline if deadline > 0 else 1.0
        if time_ratio > 0.9:
            risk_score += 0.6
        elif time_ratio > 0.7:
            risk_score += 0.3
        
        # 用户可用性风险
        if user_availability < 0.5:
            risk_score += 0.4
        
        return {
            "category": "time",
            "name": "时间风险",
            "score": min(risk_score, 1.0),
            "description": f"预估时间: {estimated_time}h, 截止时间: {deadline}h, 用户可用性: {user_availability:.0%}",
            "impact": "可能无法按时完成项目"
        }
    
    async def _assess_resource_risk(self, task_params: Dict[str, Any]) -> Dict[str, Any]:
        """评估资源风险"""
        
        literature_count = task_params.get("literature_count", 1000)
        concurrent_users = task_params.get("concurrent_users", 1)
        
        risk_score = 0.0
        
        # 计算资源需求
        if literature_count > 5000:
            risk_score += 0.4
        elif literature_count > 10000:
            risk_score += 0.6
        
        # 并发用户风险
        if concurrent_users > 10:
            risk_score += 0.3
        
        return {
            "category": "resource",
            "name": "资源需求风险",
            "score": min(risk_score, 1.0),
            "description": f"文献数量: {literature_count}, 并发用户: {concurrent_users}",
            "impact": "可能导致系统性能下降或资源不足"
        }
    
    async def _assess_user_experience_risk(self, task_params: Dict[str, Any]) -> Dict[str, Any]:
        """评估用户体验风险"""
        
        user_expertise = task_params.get("user_experience_score", 0.5)
        complexity = task_params.get("task_complexity", 0.5)
        
        risk_score = 0.0
        
        # 用户专业度与任务复杂度匹配
        expertise_gap = complexity - user_expertise
        if expertise_gap > 0.3:
            risk_score += 0.5
        elif expertise_gap > 0.1:
            risk_score += 0.3
        
        return {
            "category": "user_experience",
            "name": "用户体验风险",
            "score": min(risk_score, 1.0),
            "description": f"用户专业度: {user_expertise:.1f}, 任务复杂度: {complexity:.1f}",
            "impact": "可能导致用户困惑或操作失误"
        }
    
    def _generate_mitigation_strategies(self, risk_factors: List[Dict[str, Any]]) -> List[str]:
        """生成风险缓解策略"""
        
        strategies = []
        
        for risk in risk_factors:
            if risk["score"] > 0.6:  # 高风险
                category = risk["category"]
                
                if category == "data_quality":
                    strategies.append("建议增加数据预处理和质量检查环节")
                    strategies.append("考虑使用多个数据源进行交叉验证")
                elif category == "technical":
                    strategies.append("建议进行技术方案评审和测试")
                    strategies.append("准备备用技术方案")
                elif category == "time":
                    strategies.append("建议调整项目时间表或优先级")
                    strategies.append("考虑并行处理以提高效率")
                elif category == "resource":
                    strategies.append("建议评估和扩展系统资源")
                    strategies.append("考虑分批处理大量数据")
                elif category == "user_experience":
                    strategies.append("建议提供更多用户指导和支持")
                    strategies.append("考虑简化用户界面和操作流程")
        
        return list(set(strategies))[:5]  # 去重并限制数量


class PredictiveAnalyticsSystem:
    """预测性分析系统主控制器"""
    
    def __init__(self):
        self.time_predictor = TimePredictor()
        self.quality_predictor = QualityPredictor()
        self.risk_assessor = RiskAssessor()
        self.prediction_history = defaultdict(list)  # 存储预测历史
    
    async def comprehensive_prediction(self, 
                                     task_params: Dict[str, Any], 
                                     session_id: str) -> Dict[str, Any]:
        """综合预测分析"""
        
        # 并行执行各种预测
        tasks = [
            self._predict_all_time_estimates(task_params),
            self.quality_predictor.predict_final_quality(task_params),
            self.risk_assessor.assess_project_risks(task_params)
        ]
        
        results = await asyncio.gather(*tasks)
        time_estimates, quality_prediction, risk_assessment = results
        
        # 计算成功概率
        success_probability = await self._calculate_success_probability(
            quality_prediction, risk_assessment
        )
        
        # 生成综合建议
        recommendations = self._generate_comprehensive_recommendations(
            time_estimates, quality_prediction, risk_assessment
        )
        
        prediction_result = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "time_estimates": time_estimates,
            "quality_prediction": {
                "predicted_score": quality_prediction.predicted_score,
                "quality_level": quality_prediction.quality_level,
                "confidence": quality_prediction.confidence,
                "key_factors": quality_prediction.key_factors,
                "improvement_potential": quality_prediction.improvement_potential
            },
            "risk_assessment": {
                "overall_risk_level": risk_assessment.overall_risk_level.value,
                "risk_factors": risk_assessment.risk_factors,
                "mitigation_strategies": risk_assessment.mitigation_strategies,
                "probability_of_issues": risk_assessment.probability_of_issues
            },
            "success_probability": success_probability,
            "recommendations": recommendations
        }
        
        # 记录预测历史
        self.prediction_history[session_id].append(prediction_result)
        
        logger.info(f"Comprehensive prediction completed for session {session_id}")
        
        return prediction_result
    
    async def _predict_all_time_estimates(self, task_params: Dict[str, Any]) -> Dict[str, Any]:
        """预测所有阶段的时间"""
        
        collection_time = await self.time_predictor.predict_literature_collection_time(task_params)
        structuring_time = await self.time_predictor.predict_structuring_time(task_params)
        enhancement_time = await self.time_predictor.predict_experience_enhancement_time(task_params)
        
        total_time = (collection_time.estimated_minutes + 
                     structuring_time.estimated_minutes + 
                     enhancement_time.estimated_minutes)
        
        return {
            "literature_collection": {
                "estimated_minutes": collection_time.estimated_minutes,
                "confidence_interval": collection_time.confidence_interval,
                "confidence_score": collection_time.confidence_score,
                "factors": collection_time.factors_considered
            },
            "structuring": {
                "estimated_minutes": structuring_time.estimated_minutes,
                "confidence_interval": structuring_time.confidence_interval,
                "confidence_score": structuring_time.confidence_score,
                "factors": structuring_time.factors_considered,
                "breakdown": structuring_time.breakdown
            },
            "experience_enhancement": {
                "estimated_minutes": enhancement_time.estimated_minutes,
                "confidence_interval": enhancement_time.confidence_interval,
                "confidence_score": enhancement_time.confidence_score,
                "factors": enhancement_time.factors_considered,
                "breakdown": enhancement_time.breakdown
            },
            "total_estimated_minutes": total_time,
            "total_estimated_hours": total_time / 60
        }
    
    async def _calculate_success_probability(self, 
                                           quality_prediction: QualityPrediction,
                                           risk_assessment: RiskAssessment) -> float:
        """计算成功概率"""
        
        # 基于质量预测的成功概率
        quality_success = quality_prediction.predicted_score * quality_prediction.confidence
        
        # 基于风险评估的成功概率
        risk_success = 1.0 - risk_assessment.probability_of_issues
        
        # 综合成功概率
        overall_success = (quality_success * 0.6 + risk_success * 0.4)
        
        return min(overall_success, 0.95)  # 最高95%
    
    def _generate_comprehensive_recommendations(self, 
                                              time_estimates: Dict[str, Any],
                                              quality_prediction: QualityPrediction,
                                              risk_assessment: RiskAssessment) -> List[str]:
        """生成综合建议"""
        
        recommendations = []
        
        # 基于时间预测的建议
        total_hours = time_estimates["total_estimated_hours"]
        if total_hours > 8:
            recommendations.append(f"项目预计需要{total_hours:.1f}小时，建议分多天完成")
        
        # 基于质量预测的建议
        if quality_prediction.predicted_score < 0.7:
            recommendations.append("预测质量偏低，建议提高文献质量或增加迭代轮次")
        
        if quality_prediction.improvement_potential > 0.2:
            recommendations.append("存在较大改进空间，建议充分利用迭代优化")
        
        # 基于风险评估的建议
        if risk_assessment.overall_risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("项目风险较高，建议优先处理主要风险因素")
            recommendations.extend(risk_assessment.mitigation_strategies[:2])
        
        return recommendations[:5]  # 限制建议数量
    
    async def update_prediction_accuracy(self, 
                                       session_id: str, 
                                       actual_results: Dict[str, Any]) -> Dict[str, Any]:
        """更新预测准确性"""
        
        if session_id not in self.prediction_history:
            return {"error": "No prediction history found"}
        
        latest_prediction = self.prediction_history[session_id][-1]
        
        # 计算时间预测准确性
        time_accuracy = {}
        if "actual_time_minutes" in actual_results:
            predicted_time = latest_prediction["time_estimates"]["total_estimated_minutes"]
            actual_time = actual_results["actual_time_minutes"]
            time_accuracy = {
                "predicted": predicted_time,
                "actual": actual_time,
                "accuracy": 1.0 - abs(predicted_time - actual_time) / max(predicted_time, actual_time)
            }
        
        # 计算质量预测准确性
        quality_accuracy = {}
        if "actual_quality_score" in actual_results:
            predicted_quality = latest_prediction["quality_prediction"]["predicted_score"]
            actual_quality = actual_results["actual_quality_score"]
            quality_accuracy = {
                "predicted": predicted_quality,
                "actual": actual_quality,
                "accuracy": 1.0 - abs(predicted_quality - actual_quality)
            }
        
        accuracy_report = {
            "session_id": session_id,
            "prediction_timestamp": latest_prediction["timestamp"],
            "evaluation_timestamp": datetime.now().isoformat(),
            "time_accuracy": time_accuracy,
            "quality_accuracy": quality_accuracy,
            "overall_accuracy": np.mean([
                acc.get("accuracy", 0) for acc in [time_accuracy, quality_accuracy] if acc
            ]) if time_accuracy or quality_accuracy else 0
        }
        
        # 更新预测历史
        latest_prediction["accuracy_evaluation"] = accuracy_report
        
        logger.info(f"Updated prediction accuracy for session {session_id}")
        
        return accuracy_report
    
    async def get_prediction_insights(self, session_id: str) -> Dict[str, Any]:
        """获取预测洞察"""
        
        if session_id not in self.prediction_history:
            return {"error": "No prediction history found"}
        
        predictions = self.prediction_history[session_id]
        latest_prediction = predictions[-1]
        
        insights = {
            "session_id": session_id,
            "prediction_count": len(predictions),
            "latest_prediction_summary": {
                "total_estimated_hours": latest_prediction["time_estimates"]["total_estimated_hours"],
                "predicted_quality": latest_prediction["quality_prediction"]["predicted_score"],
                "risk_level": latest_prediction["risk_assessment"]["overall_risk_level"],
                "success_probability": latest_prediction["success_probability"]
            },
            "key_recommendations": latest_prediction["recommendations"],
            "confidence_scores": {
                "time": np.mean([
                    latest_prediction["time_estimates"]["literature_collection"]["confidence_score"],
                    latest_prediction["time_estimates"]["structuring"]["confidence_score"],
                    latest_prediction["time_estimates"]["experience_enhancement"]["confidence_score"]
                ]),
                "quality": latest_prediction["quality_prediction"]["confidence"]
            }
        }
        
        # 如果有多次预测，分析趋势
        if len(predictions) > 1:
            time_trend = [p["time_estimates"]["total_estimated_hours"] for p in predictions]
            quality_trend = [p["quality_prediction"]["predicted_score"] for p in predictions]
            
            insights["trends"] = {
                "time_estimate_trend": "increasing" if time_trend[-1] > time_trend[0] else "decreasing",
                "quality_prediction_trend": "improving" if quality_trend[-1] > quality_trend[0] else "declining"
            }
        
        return insights


# 全局预测分析系统实例
predictive_analytics = PredictiveAnalyticsSystem()