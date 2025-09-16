"""
智能AI路由器
提供模型选择策略、提示工程优化、结果质量评估
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from loguru import logger
import json
import re
from datetime import datetime, timedelta

from app.core.config import settings
from app.utils.retry_handler import with_retry, RetryStrategy
from app.core.intelligent_cache import cached

class ModelType(Enum):
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo-preview"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_HAIKU = "claude-3-haiku"

class TaskComplexity(Enum):
    SIMPLE = "simple"          # 简单任务：关键词提取、格式转换
    MEDIUM = "medium"          # 中等任务：文献总结、相关性判断
    COMPLEX = "complex"        # 复杂任务：深度分析、创新发现
    CRITICAL = "critical"      # 关键任务：重要决策、质量评估

@dataclass
class ModelCapability:
    model_type: ModelType
    cost_per_1k_tokens: float
    max_tokens: int
    quality_score: float       # 0-1
    speed_score: float         # 0-1
    reasoning_ability: float   # 0-1
    creativity_score: float    # 0-1
    supported_languages: List[str]

@dataclass
class TaskRequirement:
    complexity: TaskComplexity
    max_budget: Optional[float] = None
    max_latency: Optional[float] = None  # 秒
    quality_threshold: float = 0.8
    creativity_needed: bool = False
    reasoning_needed: bool = False
    language: str = "zh"

class IntelligentAIRouter:
    """智能AI模型路由器"""
    
    def __init__(self):
        # 模型能力配置
        self.model_capabilities = {
            ModelType.GPT_4: ModelCapability(
                model_type=ModelType.GPT_4,
                cost_per_1k_tokens=0.06,
                max_tokens=8192,
                quality_score=0.95,
                speed_score=0.6,
                reasoning_ability=0.95,
                creativity_score=0.9,
                supported_languages=["zh", "en", "ja", "ko", "fr", "de", "es"]
            ),
            ModelType.GPT_4_TURBO: ModelCapability(
                model_type=ModelType.GPT_4_TURBO,
                cost_per_1k_tokens=0.03,
                max_tokens=128000,
                quality_score=0.93,
                speed_score=0.8,
                reasoning_ability=0.92,
                creativity_score=0.88,
                supported_languages=["zh", "en", "ja", "ko", "fr", "de", "es"]
            ),
            ModelType.GPT_3_5_TURBO: ModelCapability(
                model_type=ModelType.GPT_3_5_TURBO,
                cost_per_1k_tokens=0.002,
                max_tokens=16384,
                quality_score=0.82,
                speed_score=0.95,
                reasoning_ability=0.75,
                creativity_score=0.7,
                supported_languages=["zh", "en", "ja", "ko", "fr", "de", "es"]
            )
        }
        
        # 任务类型到模型的映射策略
        self.task_model_preferences = {
            "literature_screening": {
                "preferred_models": [ModelType.GPT_3_5_TURBO, ModelType.GPT_4_TURBO],
                "fallback_models": [ModelType.GPT_4]
            },
            "experience_generation": {
                "preferred_models": [ModelType.GPT_4_TURBO, ModelType.GPT_4],
                "fallback_models": [ModelType.GPT_3_5_TURBO]
            },
            "innovation_discovery": {
                "preferred_models": [ModelType.GPT_4, ModelType.GPT_4_TURBO],
                "fallback_models": []
            },
            "simple_qa": {
                "preferred_models": [ModelType.GPT_3_5_TURBO],
                "fallback_models": [ModelType.GPT_4_TURBO]
            }
        }
        
        # 模型性能统计
        self.model_stats = defaultdict(lambda: {
            'total_requests': 0,
            'successful_requests': 0,
            'average_latency': 0.0,
            'average_quality': 0.0,
            'total_cost': 0.0
        })
    
    async def select_optimal_model(
        self, 
        task_type: str, 
        requirement: TaskRequirement,
        context: Optional[Dict] = None
    ) -> Tuple[ModelType, float]:
        """选择最优模型"""
        
        # 获取候选模型
        candidates = self._get_candidate_models(task_type, requirement)
        
        if not candidates:
            # 默认回退到GPT-3.5
            return ModelType.GPT_3_5_TURBO, 0.8
        
        # 计算每个模型的综合评分
        best_model = None
        best_score = -1
        
        for model_type in candidates:
            capability = self.model_capabilities[model_type]
            score = await self._calculate_model_score(capability, requirement, context)
            
            logger.debug(f"模型 {model_type.value} 评分: {score:.3f}")
            
            if score > best_score:
                best_score = score
                best_model = model_type
        
        confidence = min(1.0, best_score)
        logger.info(f"选择模型: {best_model.value} (置信度: {confidence:.3f})")
        
        return best_model, confidence
    
    def _get_candidate_models(self, task_type: str, requirement: TaskRequirement) -> List[ModelType]:
        """获取候选模型列表"""
        # 基于任务类型获取首选模型
        task_config = self.task_model_preferences.get(task_type, {})
        candidates = task_config.get("preferred_models", list(self.model_capabilities.keys()))
        
        # 基于需求筛选
        filtered_candidates = []
        for model_type in candidates:
            capability = self.model_capabilities[model_type]
            
            # 预算筛选
            if requirement.max_budget and capability.cost_per_1k_tokens > requirement.max_budget:
                continue
            
            # 质量筛选
            if capability.quality_score < requirement.quality_threshold:
                continue
            
            # 语言支持筛选
            if requirement.language not in capability.supported_languages:
                continue
            
            filtered_candidates.append(model_type)
        
        # 如果没有合适的首选模型，尝试回退模型
        if not filtered_candidates:
            fallback_models = task_config.get("fallback_models", [])
            for model_type in fallback_models:
                capability = self.model_capabilities[model_type]
                if capability.quality_score >= requirement.quality_threshold * 0.9:  # 稍微放宽要求
                    filtered_candidates.append(model_type)
        
        return filtered_candidates
    
    async def _calculate_model_score(
        self, 
        capability: ModelCapability, 
        requirement: TaskRequirement,
        context: Optional[Dict] = None
    ) -> float:
        """计算模型综合评分"""
        score = 0.0
        
        # 质量权重 (40%)
        quality_weight = 0.4
        quality_score = capability.quality_score
        score += quality_weight * quality_score
        
        # 成本权重 (25%)
        cost_weight = 0.25
        if requirement.max_budget:
            cost_score = max(0, 1 - (capability.cost_per_1k_tokens / requirement.max_budget))
        else:
            # 没有预算限制时，成本越低越好
            max_cost = max(cap.cost_per_1k_tokens for cap in self.model_capabilities.values())
            cost_score = 1 - (capability.cost_per_1k_tokens / max_cost)
        score += cost_weight * cost_score
        
        # 速度权重 (20%)
        speed_weight = 0.2
        if requirement.max_latency:
            # 根据历史性能数据评估速度
            expected_latency = self._estimate_latency(capability.model_type, context)
            speed_score = max(0, 1 - (expected_latency / requirement.max_latency))
        else:
            speed_score = capability.speed_score
        score += speed_weight * speed_score
        
        # 特殊能力权重 (15%)
        ability_weight = 0.15
        ability_score = 0.0
        if requirement.creativity_needed:
            ability_score += capability.creativity_score * 0.5
        if requirement.reasoning_needed:
            ability_score += capability.reasoning_ability * 0.5
        if not requirement.creativity_needed and not requirement.reasoning_needed:
            ability_score = (capability.creativity_score + capability.reasoning_ability) / 2
        score += ability_weight * ability_score
        
        # 历史性能加权
        model_stats = self.model_stats[capability.model_type]
        if model_stats['total_requests'] > 10:
            historical_weight = 0.1
            success_rate = model_stats['successful_requests'] / model_stats['total_requests']
            historical_quality = model_stats.get('average_quality', 0.8)
            historical_score = (success_rate + historical_quality) / 2
            score = score * 0.9 + historical_score * historical_weight
        
        return score
    
    def _estimate_latency(self, model_type: ModelType, context: Optional[Dict] = None) -> float:
        """估算模型延迟"""
        base_latencies = {
            ModelType.GPT_4: 8.0,
            ModelType.GPT_4_TURBO: 5.0,
            ModelType.GPT_3_5_TURBO: 2.0
        }
        
        base_latency = base_latencies.get(model_type, 5.0)
        
        # 根据上下文调整延迟估算
        if context:
            token_count = context.get('estimated_tokens', 1000)
            # 更多token需要更长时间
            latency_multiplier = 1 + (token_count - 1000) / 10000
            base_latency *= max(1.0, latency_multiplier)
        
        return base_latency
    
    async def adaptive_prompt_engineering(
        self, 
        base_prompt: str, 
        task_type: str,
        context: Dict,
        model_type: ModelType
    ) -> str:
        """自适应提示工程"""
        
        # 基础提示模板
        prompt_templates = {
            "literature_screening": """
作为科研文献筛选专家，请仔细评估以下文献与研究主题的相关性。

评估标准：
1. 标题相关性 (权重30%)
2. 摘要相关性 (权重40%) 
3. 研究方法相关性 (权重20%)
4. 应用领域相关性 (权重10%)

请提供：
- 总体相关性评分 (0-10分)
- 各维度详细评分
- 推荐理由（不超过100字）

{base_prompt}
""",
            "experience_generation": """
作为资深科研专家，请基于提供的文献内容生成结构化的研究经验。

输出要求：
1. 核心方法总结
2. 关键参数范围
3. 成功要素分析
4. 常见问题及解决方案
5. 创新改进建议

请确保内容：
- 准确性：基于文献事实
- 实用性：可指导实际研究
- 完整性：覆盖关键环节
- 创新性：提出改进思路

{base_prompt}
""",
            "innovation_discovery": """
作为创新研究顾问，请分析文献内容并识别创新机会。

分析维度：
1. 技术空白点识别
2. 方法组合创新
3. 跨领域应用机会
4. 参数优化空间
5. 工程化改进方向

输出格式：
- 创新想法（3-5个）
- 可行性评估
- 实施难度分析
- 预期影响评估

{base_prompt}
"""
        }
        
        # 获取基础模板
        template = prompt_templates.get(task_type, "{base_prompt}")
        enhanced_prompt = template.format(base_prompt=base_prompt)
        
        # 根据模型类型调整提示
        if model_type in [ModelType.GPT_4, ModelType.GPT_4_TURBO]:
            # GPT-4系列：可以使用更复杂的指令
            enhanced_prompt = self._add_advanced_instructions(enhanced_prompt, task_type)
        elif model_type == ModelType.GPT_3_5_TURBO:
            # GPT-3.5：使用更简洁明确的指令
            enhanced_prompt = self._simplify_instructions(enhanced_prompt, task_type)
        
        # 添加上下文信息
        if context:
            context_prompt = self._build_context_prompt(context)
            enhanced_prompt = f"{context_prompt}\n\n{enhanced_prompt}"
        
        # 添加输出格式约束
        format_constraint = self._get_format_constraint(task_type)
        enhanced_prompt = f"{enhanced_prompt}\n\n{format_constraint}"
        
        return enhanced_prompt
    
    def _add_advanced_instructions(self, prompt: str, task_type: str) -> str:
        """为高级模型添加复杂指令"""
        advanced_instructions = {
            "literature_screening": """
请使用多层次思维分析：
1. 首先进行字面匹配分析
2. 然后进行语义关联分析
3. 最后进行潜在价值评估
4. 综合三个层面给出最终判断
""",
            "experience_generation": """
请采用系统化分析方法：
1. 归纳共性规律
2. 识别关键变量
3. 分析因果关系
4. 提炼最佳实践
5. 预测发展趋势
""",
            "innovation_discovery": """
请运用创新思维框架：
1. SCAMPER技术分析
2. 跨领域类比思考
3. 反向思维探索
4. 系统性创新机会识别
"""
        }
        
        instruction = advanced_instructions.get(task_type, "")
        return f"{instruction}\n\n{prompt}" if instruction else prompt
    
    def _simplify_instructions(self, prompt: str, task_type: str) -> str:
        """为简单模型简化指令"""
        # 移除复杂的分析要求，保留核心任务
        simplified_prompt = re.sub(r'请.*?分析.*?：\n.*?\n', '', prompt, flags=re.DOTALL)
        simplified_prompt = re.sub(r'分析维度：.*?\n', '', simplified_prompt, flags=re.DOTALL)
        
        return simplified_prompt
    
    def _build_context_prompt(self, context: Dict) -> str:
        """构建上下文提示"""
        context_parts = []
        
        if context.get('user_expertise'):
            context_parts.append(f"用户专业水平: {context['user_expertise']}")
        
        if context.get('research_field'):
            context_parts.append(f"研究领域: {context['research_field']}")
        
        if context.get('previous_results'):
            context_parts.append(f"相关历史结果: {context['previous_results'][:200]}...")
        
        if context.get('time_constraint'):
            context_parts.append(f"时间要求: {context['time_constraint']}")
        
        if context_parts:
            return f"背景信息：\n" + "\n".join(context_parts)
        
        return ""
    
    def _get_format_constraint(self, task_type: str) -> str:
        """获取输出格式约束"""
        format_constraints = {
            "literature_screening": """
请严格按照以下JSON格式输出：
{
    "relevance_score": 8.5,
    "dimension_scores": {
        "title_relevance": 9.0,
        "abstract_relevance": 8.0,
        "method_relevance": 8.5,
        "application_relevance": 8.0
    },
    "recommendation": "推荐理由",
    "confidence": 0.85
}""",
            "experience_generation": """
请使用结构化格式输出，包含：
1. 核心方法 (methods)
2. 关键参数 (parameters)  
3. 成功要素 (success_factors)
4. 常见问题 (common_issues)
5. 改进建议 (improvements)
""",
            "innovation_discovery": """
请按照以下格式输出创新想法：
{
    "innovations": [
        {
            "title": "创新想法标题",
            "description": "详细描述",
            "feasibility": 0.8,
            "impact": 0.9,
            "difficulty": 0.6
        }
    ]
}"""
        }
        
        return format_constraints.get(task_type, "请提供结构化的输出结果。")
    
    @cached("ai_result:{task_type}:{hash}", ttl=3600)
    async def process_with_optimal_model(
        self,
        task_type: str,
        prompt: str,
        requirement: TaskRequirement,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """使用最优模型处理任务"""
        
        start_time = time.time()
        
        try:
            # 选择最优模型
            model_type, confidence = await self.select_optimal_model(task_type, requirement, context)
            
            # 自适应提示工程
            enhanced_prompt = await self.adaptive_prompt_engineering(
                prompt, task_type, context or {}, model_type
            )
            
            # 执行AI调用
            result = await self._call_model(model_type, enhanced_prompt, context)
            
            # 质量评估
            quality_score = await self._assess_result_quality(result, task_type, requirement)
            
            # 记录性能统计
            latency = time.time() - start_time
            await self._record_model_performance(model_type, latency, quality_score, True)
            
            return {
                "result": result,
                "model_used": model_type.value,
                "model_confidence": confidence,
                "quality_score": quality_score,
                "latency": latency,
                "enhanced_prompt": enhanced_prompt if context and context.get('debug') else None
            }
            
        except Exception as e:
            # 记录失败统计
            latency = time.time() - start_time
            await self._record_model_performance(model_type, latency, 0.0, False)
            
            logger.error(f"AI处理失败: {e}")
            raise
    
    @with_retry("ai_model_call", max_attempts=3, base_delay=2.0)
    async def _call_model(self, model_type: ModelType, prompt: str, context: Optional[Dict] = None) -> str:
        """调用AI模型"""
        # 这里应该根据model_type调用相应的API
        # 暂时使用OpenAI API作为示例
        
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        try:
            response = await client.chat.completions.create(
                model=model_type.value,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"模型调用失败 {model_type.value}: {e}")
            raise
    
    async def _assess_result_quality(
        self, 
        result: str, 
        task_type: str, 
        requirement: TaskRequirement
    ) -> float:
        """评估结果质量"""
        
        quality_score = 0.0
        
        # 基础质量检查
        if not result or len(result.strip()) < 50:
            return 0.1
        
        # 长度合理性 (20%)
        ideal_length = {"simple": 200, "medium": 500, "complex": 1000, "critical": 1500}
        target_length = ideal_length.get(requirement.complexity.value, 500)
        length_score = min(1.0, len(result) / target_length)
        if length_score > 2.0:  # 过长也不好
            length_score = 2.0 - length_score
        quality_score += 0.2 * max(0.1, length_score)
        
        # 结构化程度 (30%)
        structure_indicators = [
            r'\d+\.', r'[一二三四五六七八九十]+[、.]', r'[（\(][一二三四五六七八九十\d]+[）\)]',
            r'[\n\r]', r'：', r'总结', r'分析', r'建议', r'结论'
        ]
        structure_score = sum(1 for indicator in structure_indicators if re.search(indicator, result))
        structure_score = min(1.0, structure_score / len(structure_indicators))
        quality_score += 0.3 * structure_score
        
        # 专业术语密度 (25%)
        professional_terms = [
            '研究', '分析', '方法', '实验', '数据', '结果', '结论', '假设',
            '理论', '模型', '算法', '参数', '优化', '性能', '效果', '影响'
        ]
        term_count = sum(1 for term in professional_terms if term in result)
        term_score = min(1.0, term_count / 10)
        quality_score += 0.25 * term_score
        
        # JSON格式正确性 (25%, 如果需要JSON输出)
        if task_type in ["literature_screening", "innovation_discovery"]:
            try:
                json.loads(result)
                format_score = 1.0
            except:
                # 尝试提取JSON部分
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    try:
                        json.loads(json_match.group())
                        format_score = 0.8
                    except:
                        format_score = 0.3
                else:
                    format_score = 0.1
            quality_score += 0.25 * format_score
        else:
            # 非JSON任务，检查逻辑连贯性
            sentences = re.split(r'[。！？\.\!\?]', result)
            coherence_score = min(1.0, len([s for s in sentences if len(s.strip()) > 10]) / 5)
            quality_score += 0.25 * coherence_score
        
        return min(1.0, quality_score)
    
    async def _record_model_performance(
        self, 
        model_type: ModelType, 
        latency: float, 
        quality_score: float, 
        success: bool
    ):
        """记录模型性能统计"""
        stats = self.model_stats[model_type]
        
        stats['total_requests'] += 1
        if success:
            stats['successful_requests'] += 1
        
        # 更新平均延迟
        if stats['total_requests'] == 1:
            stats['average_latency'] = latency
        else:
            stats['average_latency'] = (
                stats['average_latency'] * (stats['total_requests'] - 1) + latency
            ) / stats['total_requests']
        
        # 更新平均质量
        if success:
            if stats['successful_requests'] == 1:
                stats['average_quality'] = quality_score
            else:
                stats['average_quality'] = (
                    stats['average_quality'] * (stats['successful_requests'] - 1) + quality_score
                ) / stats['successful_requests']
        
        # 更新成本
        capability = self.model_capabilities[model_type]
        estimated_tokens = len(str(latency)) * 4  # 粗略估算
        cost = (estimated_tokens / 1000) * capability.cost_per_1k_tokens
        stats['total_cost'] += cost
        
        # 记录到Redis
        try:
            perf_key = f"ai_performance:{model_type.value}:{int(time.time())}"
            perf_data = {
                "model_type": model_type.value,
                "latency": latency,
                "quality_score": quality_score,
                "success": success,
                "cost": cost,
                "timestamp": datetime.utcnow().isoformat()
            }
            await redis_client.setex(perf_key, 86400, json.dumps(perf_data))
        except Exception as e:
            logger.error(f"记录AI性能数据失败: {e}")
    
    async def get_model_recommendations(self, task_history: List[Dict]) -> Dict[str, Any]:
        """基于历史任务获取模型使用建议"""
        
        # 分析历史任务模式
        task_patterns = defaultdict(list)
        for task in task_history:
            task_type = task.get('task_type')
            if task_type:
                task_patterns[task_type].append(task)
        
        recommendations = {}
        
        for task_type, tasks in task_patterns.items():
            # 计算平均质量和成本
            avg_quality = sum(t.get('quality_score', 0.8) for t in tasks) / len(tasks)
            avg_cost = sum(t.get('cost', 0.01) for t in tasks) / len(tasks)
            avg_latency = sum(t.get('latency', 3.0) for t in tasks) / len(tasks)
            
            # 生成建议
            if avg_quality < 0.7:
                recommendations[task_type] = {
                    "suggestion": "建议使用更高级的模型提升质量",
                    "recommended_model": ModelType.GPT_4.value,
                    "reason": f"当前平均质量: {avg_quality:.2f}，低于期望值"
                }
            elif avg_cost > 0.05:
                recommendations[task_type] = {
                    "suggestion": "建议使用更经济的模型降低成本",
                    "recommended_model": ModelType.GPT_3_5_TURBO.value,
                    "reason": f"当前平均成本: ${avg_cost:.4f}，可以优化"
                }
            elif avg_latency > 10.0:
                recommendations[task_type] = {
                    "suggestion": "建议使用更快速的模型提升响应速度",
                    "recommended_model": ModelType.GPT_3_5_TURBO.value,
                    "reason": f"当前平均延迟: {avg_latency:.2f}秒，较慢"
                }
            else:
                recommendations[task_type] = {
                    "suggestion": "当前模型选择合适，无需调整",
                    "recommended_model": "current",
                    "reason": f"质量: {avg_quality:.2f}, 成本: ${avg_cost:.4f}, 延迟: {avg_latency:.2f}s"
                }
        
        return {
            "recommendations": recommendations,
            "overall_stats": {
                "total_tasks": len(task_history),
                "avg_quality": sum(t.get('quality_score', 0.8) for t in task_history) / len(task_history),
                "total_cost": sum(t.get('cost', 0.01) for t in task_history),
                "avg_latency": sum(t.get('latency', 3.0) for t in task_history) / len(task_history)
            }
        }

# 全局AI路由器实例
ai_router = IntelligentAIRouter()

# 使用示例装饰器
def with_intelligent_ai(task_type: str):
    """智能AI处理装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 从参数中提取需求
            requirement = kwargs.get('requirement', TaskRequirement(TaskComplexity.MEDIUM))
            context = kwargs.get('context', {})
            
            # 获取原始提示
            prompt = kwargs.get('prompt') or args[0] if args else ""
            
            # 使用智能路由器处理
            result = await ai_router.process_with_optimal_model(
                task_type, prompt, requirement, context
            )
            
            return result
        return wrapper
    return decorator