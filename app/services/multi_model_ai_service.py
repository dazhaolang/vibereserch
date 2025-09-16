"""
多模型AI服务 - 支持多种AI模型
"""

import asyncio
from typing import List, Dict, Optional, Any, Union
import openai
from openai import AsyncOpenAI
import json
from datetime import datetime
from loguru import logger
from enum import Enum

# Optional anthropic import
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from app.core.config import settings

class AIModelProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL = "local"

class AIModelConfig:
    """AI模型配置"""
    
    def __init__(
        self,
        provider: AIModelProvider,
        model_name: str,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.3,
        features: List[str] = None
    ):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.endpoint = endpoint
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.features = features or []

class MultiModelAIService:
    """多模型AI服务"""
    
    def __init__(self):
        self.models = self._initialize_models()
        self.default_model = AIModelProvider.OPENAI
        
    def _initialize_models(self) -> Dict[AIModelProvider, AIModelConfig]:
        """初始化可用的AI模型"""
        models = {}
        
        # OpenAI模型
        if settings.openai_api_key:
            models[AIModelProvider.OPENAI] = AIModelConfig(
                provider=AIModelProvider.OPENAI,
                model_name=settings.openai_model,  # 使用配置的模型
                api_key=settings.openai_api_key,
                endpoint=settings.openai_base_url,  # 支持自定义endpoint
                max_tokens=4000,
                temperature=0.3,
                features=["chat", "embedding", "analysis", "generation"]
            )
        
        # Anthropic Claude模型
        anthropic_key = getattr(settings, 'anthropic_api_key', None)
        if anthropic_key and HAS_ANTHROPIC:
            models[AIModelProvider.ANTHROPIC] = AIModelConfig(
                provider=AIModelProvider.ANTHROPIC,
                model_name="claude-3-sonnet-20240229",
                api_key=anthropic_key,
                max_tokens=4000,
                temperature=0.3,
                features=["chat", "analysis", "reasoning"]
            )
        
        # Google Gemini模型
        google_key = getattr(settings, 'google_api_key', None)
        if google_key:
            models[AIModelProvider.GOOGLE] = AIModelConfig(
                provider=AIModelProvider.GOOGLE,
                model_name="gemini-pro",
                api_key=google_key,
                max_tokens=4000,
                temperature=0.3,
                features=["chat", "multimodal", "analysis"]
            )
        
        return models
    
    async def get_available_models(self) -> List[Dict]:
        """获取可用的AI模型列表"""
        available_models = []
        
        for provider, config in self.models.items():
            # 测试模型可用性
            is_available = await self._test_model_availability(provider, config)
            
            available_models.append({
                "provider": provider.value,
                "model_name": config.model_name,
                "features": config.features,
                "max_tokens": config.max_tokens,
                "is_available": is_available,
                "is_default": provider == self.default_model
            })
        
        return available_models
    
    async def _test_model_availability(self, provider: AIModelProvider, config: AIModelConfig) -> bool:
        """测试模型可用性"""
        try:
            if provider == AIModelProvider.OPENAI:
                # 构建客户端配置
                client_config = {"api_key": config.api_key}
                if config.endpoint:
                    client_config["base_url"] = config.endpoint
                
                client = AsyncOpenAI(**client_config)
                response = await client.chat.completions.create(
                    model="gpt-3.5-turbo",  # 使用轻量级模型进行测试
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5
                )
                return True
            elif provider == AIModelProvider.ANTHROPIC:
                # 简化测试
                return config.api_key is not None
            else:
                return False
                
        except Exception as e:
            logger.error(f"模型 {provider.value} 不可用: {e}")
            return False
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[AIModelProvider] = None,
        model_options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        多模型聊天完成
        
        Args:
            messages: 对话消息列表
            provider: 指定的AI提供商
            model_options: 模型参数选项
            
        Returns:
            AI响应结果
        """
        try:
            # 选择模型
            selected_provider = provider or self.default_model
            
            if selected_provider not in self.models:
                raise ValueError(f"模型 {selected_provider.value} 不可用")
            
            config = self.models[selected_provider]
            options = model_options or {}
            
            # 根据提供商调用相应的API
            if selected_provider == AIModelProvider.OPENAI:
                return await self._openai_chat_completion(messages, config, options)
            elif selected_provider == AIModelProvider.ANTHROPIC:
                return await self._anthropic_chat_completion(messages, config, options)
            elif selected_provider == AIModelProvider.GOOGLE:
                return await self._google_chat_completion(messages, config, options)
            else:
                raise ValueError(f"不支持的AI提供商: {selected_provider.value}")
                
        except Exception as e:
            logger.error(f"AI聊天完成失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": "",
                "provider": selected_provider.value if selected_provider else "unknown"
            }
    
    async def _openai_chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        config: AIModelConfig, 
        options: Dict
    ) -> Dict[str, Any]:
        """OpenAI聊天完成"""
        try:
            # 构建客户端配置
            client_config = {"api_key": config.api_key}
            if config.endpoint:
                client_config["base_url"] = config.endpoint
            
            client = AsyncOpenAI(**client_config)
            
            response = await client.chat.completions.create(
                model=config.model_name,
                messages=messages,
                max_tokens=options.get('max_tokens', config.max_tokens),
                temperature=options.get('temperature', config.temperature),
                top_p=options.get('top_p', 1.0),
                frequency_penalty=options.get('frequency_penalty', 0.0),
                presence_penalty=options.get('presence_penalty', 0.0)
            )
            
            return {
                "success": True,
                "content": response.choices[0].message.content,
                "provider": "openai",
                "model": config.model_name,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }
            
        except Exception as e:
            logger.error(f"OpenAI API调用失败: {e}")
            raise
    
    async def _anthropic_chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        config: AIModelConfig, 
        options: Dict
    ) -> Dict[str, Any]:
        """Anthropic Claude聊天完成"""
        try:
            # 注意：这里需要安装anthropic库
            # client = anthropic.AsyncAnthropic(api_key=config.api_key)
            
            # 转换消息格式
            system_message = ""
            user_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    user_messages.append(msg)
            
            # 模拟Claude API调用
            # response = await client.messages.create(
            #     model=config.model_name,
            #     max_tokens=options.get('max_tokens', config.max_tokens),
            #     temperature=options.get('temperature', config.temperature),
            #     system=system_message,
            #     messages=user_messages
            # )
            
            # 模拟响应
            return {
                "success": True,
                "content": "这是Claude模型的模拟响应。实际使用时需要配置Anthropic API密钥。",
                "provider": "anthropic",
                "model": config.model_name,
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150
                }
            }
            
        except Exception as e:
            logger.error(f"Anthropic API调用失败: {e}")
            raise
    
    async def _google_chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        config: AIModelConfig, 
        options: Dict
    ) -> Dict[str, Any]:
        """Google Gemini聊天完成"""
        try:
            # 模拟Google Gemini API调用
            return {
                "success": True,
                "content": "这是Gemini模型的模拟响应。实际使用时需要配置Google API密钥。",
                "provider": "google",
                "model": config.model_name,
                "usage": {
                    "input_tokens": 120,
                    "output_tokens": 60,
                    "total_tokens": 180
                }
            }
            
        except Exception as e:
            logger.error(f"Google API调用失败: {e}")
            raise
    
    async def analyze_literature_with_multiple_models(
        self,
        literature_content: str,
        analysis_type: str = "summary",
        use_ensemble: bool = True
    ) -> Dict[str, Any]:
        """
        使用多个模型分析文献
        
        Args:
            literature_content: 文献内容
            analysis_type: 分析类型
            use_ensemble: 是否使用集成方法
            
        Returns:
            分析结果
        """
        try:
            if not use_ensemble:
                # 使用单一模型
                messages = [
                    {"role": "user", "content": f"请分析以下文献内容：\n\n{literature_content}"}
                ]
                return await self.chat_completion(messages)
            
            # 集成多个模型的结果
            analysis_tasks = []
            available_providers = [p for p in self.models.keys() if p in self.models]
            
            for provider in available_providers[:3]:  # 最多使用3个模型
                messages = [
                    {
                        "role": "user", 
                        "content": f"作为文献分析专家，请对以下内容进行{analysis_type}分析：\n\n{literature_content[:2000]}"
                    }
                ]
                
                task = self.chat_completion(messages, provider)
                analysis_tasks.append((provider, task))
            
            # 等待所有模型完成
            results = []
            for provider, task in analysis_tasks:
                try:
                    result = await task
                    if result["success"]:
                        results.append({
                            "provider": provider.value,
                            "content": result["content"],
                            "confidence": self._estimate_confidence(result["content"]),
                            "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                        })
                except Exception as e:
                    logger.error(f"模型 {provider.value} 分析失败: {e}")
            
            if not results:
                return {
                    "success": False,
                    "error": "所有模型都无法完成分析"
                }
            
            # 集成多个模型的结果
            ensemble_result = await self._ensemble_analysis_results(results, analysis_type)
            
            return {
                "success": True,
                "ensemble_result": ensemble_result,
                "individual_results": results,
                "models_used": len(results),
                "analysis_type": analysis_type
            }
            
        except Exception as e:
            logger.error(f"多模型文献分析失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _ensemble_analysis_results(
        self, 
        results: List[Dict], 
        analysis_type: str
    ) -> Dict[str, Any]:
        """集成多个模型的分析结果"""
        try:
            if len(results) == 1:
                return {
                    "content": results[0]["content"],
                    "confidence": results[0]["confidence"],
                    "method": "single_model"
                }
            
            # 使用投票或平均的方式集成结果
            ensemble_prompt = f"""
作为AI分析专家，请基于以下多个AI模型的{analysis_type}分析结果，生成一个综合的、更准确的分析结论：

"""
            
            for i, result in enumerate(results, 1):
                ensemble_prompt += f"模型{i} ({result['provider']})的分析：\n{result['content']}\n\n"
            
            ensemble_prompt += """
请综合这些分析，生成一个更全面、准确的结论。突出共同点，解释分歧，提供平衡的观点。
"""
            
            # 使用最可靠的模型进行集成
            best_provider = max(results, key=lambda r: r["confidence"])["provider"]
            provider_enum = AIModelProvider(best_provider)
            
            ensemble_response = await self.chat_completion(
                [{"role": "user", "content": ensemble_prompt}],
                provider_enum
            )
            
            if ensemble_response["success"]:
                # 计算集成置信度
                avg_confidence = sum(r["confidence"] for r in results) / len(results)
                ensemble_confidence = min(avg_confidence * 1.1, 1.0)  # 集成提升置信度
                
                return {
                    "content": ensemble_response["content"],
                    "confidence": ensemble_confidence,
                    "method": "ensemble",
                    "base_models": [r["provider"] for r in results],
                    "consensus_score": self._calculate_consensus_score(results)
                }
            else:
                # 集成失败，返回置信度最高的结果
                best_result = max(results, key=lambda r: r["confidence"])
                return {
                    "content": best_result["content"],
                    "confidence": best_result["confidence"],
                    "method": "fallback_best",
                    "provider": best_result["provider"]
                }
                
        except Exception as e:
            logger.error(f"集成分析结果失败: {e}")
            # 返回置信度最高的单个结果
            best_result = max(results, key=lambda r: r["confidence"])
            return {
                "content": best_result["content"],
                "confidence": best_result["confidence"],
                "method": "fallback_error",
                "error": str(e)
            }
    
    def _estimate_confidence(self, content: str) -> float:
        """估算AI回答的置信度"""
        # 基于内容特征估算置信度
        confidence = 0.5  # 基础置信度
        
        # 长度因子
        if len(content) > 500:
            confidence += 0.1
        elif len(content) < 100:
            confidence -= 0.1
        
        # 结构化程度
        if any(marker in content for marker in ['1.', '2.', '3.', '•', '-']):
            confidence += 0.1
        
        # 专业术语密度
        professional_terms = ['研究', '分析', '方法', '结果', '结论', '建议']
        term_count = sum(1 for term in professional_terms if term in content)
        confidence += min(0.2, term_count * 0.05)
        
        # 不确定性表达
        uncertainty_phrases = ['可能', '也许', '大概', '不确定', '需要进一步']
        uncertainty_count = sum(1 for phrase in uncertainty_phrases if phrase in content)
        confidence -= min(0.2, uncertainty_count * 0.05)
        
        return max(0.1, min(1.0, confidence))
    
    def _calculate_consensus_score(self, results: List[Dict]) -> float:
        """计算多个模型结果的一致性评分"""
        if len(results) < 2:
            return 1.0
        
        # 简化的一致性计算
        # 实际实现中可以使用更复杂的文本相似度算法
        contents = [r["content"] for r in results]
        
        # 计算关键词重叠度
        all_words = set()
        word_sets = []
        
        for content in contents:
            words = set(content.lower().split())
            word_sets.append(words)
            all_words.update(words)
        
        if not all_words:
            return 0.0
        
        # 计算交集比例
        intersection = set.intersection(*word_sets) if word_sets else set()
        consensus_score = len(intersection) / len(all_words) if all_words else 0.0
        
        return min(1.0, consensus_score * 2)  # 放大一致性评分
    
    async def adaptive_model_selection(
        self,
        task_type: str,
        content_length: int,
        complexity_level: str = "medium"
    ) -> AIModelProvider:
        """
        自适应模型选择
        
        Args:
            task_type: 任务类型
            content_length: 内容长度
            complexity_level: 复杂度级别
            
        Returns:
            推荐的AI模型
        """
        available_models = await self.get_available_models()
        
        if not available_models:
            raise Exception("没有可用的AI模型")
        
        # 根据任务类型和复杂度选择模型
        model_scores = {}
        
        for model in available_models:
            if not model["is_available"]:
                continue
            
            score = 0.0
            provider = model["provider"]
            
            # 基础评分
            if provider == "openai":
                score += 0.8  # OpenAI通用性好
            elif provider == "anthropic":
                score += 0.9  # Claude推理能力强
            elif provider == "google":
                score += 0.7  # Gemini多模态能力强
            
            # 任务类型适配
            if task_type == "analysis" and "analysis" in model["features"]:
                score += 0.2
            elif task_type == "generation" and "generation" in model["features"]:
                score += 0.2
            elif task_type == "reasoning" and "reasoning" in model["features"]:
                score += 0.2
            
            # 内容长度适配
            if content_length > 3000 and model["max_tokens"] >= 4000:
                score += 0.1
            elif content_length < 1000:
                score += 0.05  # 短内容所有模型都适合
            
            # 复杂度适配
            if complexity_level == "high":
                if provider in ["anthropic", "openai"]:
                    score += 0.1
            elif complexity_level == "low":
                score += 0.05  # 简单任务都适合
            
            model_scores[provider] = score
        
        # 选择评分最高的模型
        best_provider = max(model_scores.keys(), key=lambda k: model_scores[k])
        return AIModelProvider(best_provider)
    
    async def parallel_analysis(
        self,
        content: str,
        analysis_types: List[str],
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """
        并行多任务分析
        
        Args:
            content: 要分析的内容
            analysis_types: 分析类型列表
            max_concurrent: 最大并发数
            
        Returns:
            并行分析结果
        """
        try:
            # 创建分析任务
            analysis_tasks = []
            
            for analysis_type in analysis_types:
                # 为每个分析类型选择最适合的模型
                selected_provider = await self.adaptive_model_selection(
                    analysis_type, len(content)
                )
                
                # 构建特定的提示词
                prompt = self._build_analysis_prompt(content, analysis_type)
                messages = [{"role": "user", "content": prompt}]
                
                task = self.chat_completion(messages, selected_provider)
                analysis_tasks.append((analysis_type, task))
            
            # 分批执行任务（控制并发数）
            results = {}
            
            for i in range(0, len(analysis_tasks), max_concurrent):
                batch = analysis_tasks[i:i + max_concurrent]
                
                # 并行执行当前批次
                batch_results = await asyncio.gather(
                    *[task for _, task in batch],
                    return_exceptions=True
                )
                
                # 处理批次结果
                for j, (analysis_type, _) in enumerate(batch):
                    result = batch_results[j]
                    
                    if isinstance(result, Exception):
                        results[analysis_type] = {
                            "success": False,
                            "error": str(result)
                        }
                    else:
                        results[analysis_type] = result
            
            # 计算总体成功率
            successful_analyses = sum(1 for r in results.values() if r.get("success", False))
            success_rate = successful_analyses / len(analysis_types) if analysis_types else 0
            
            return {
                "success": success_rate > 0,
                "results": results,
                "success_rate": success_rate,
                "total_analyses": len(analysis_types),
                "successful_analyses": successful_analyses
            }
            
        except Exception as e:
            logger.error(f"并行分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": {}
            }
    
    def _build_analysis_prompt(self, content: str, analysis_type: str) -> str:
        """构建特定分析类型的提示词"""
        base_content = content[:3000]  # 限制长度
        
        prompts = {
            "summary": f"请对以下文献内容进行简洁的摘要总结：\n\n{base_content}",
            "methodology": f"请分析以下文献的研究方法和技术路线：\n\n{base_content}",
            "innovation": f"请识别以下文献的创新点和贡献：\n\n{base_content}",
            "limitations": f"请分析以下文献的局限性和不足：\n\n{base_content}",
            "applications": f"请分析以下文献的应用前景和价值：\n\n{base_content}",
            "keywords": f"请从以下文献中提取关键词和核心概念：\n\n{base_content}"
        }
        
        return prompts.get(analysis_type, f"请分析以下文献内容：\n\n{base_content}")
    
    async def get_model_performance_stats(self) -> Dict[str, Any]:
        """获取模型性能统计"""
        stats = {}
        
        for provider, config in self.models.items():
            # 模拟性能统计
            stats[provider.value] = {
                "total_requests": 100 + hash(provider.value) % 500,
                "successful_requests": 95 + hash(provider.value) % 5,
                "avg_response_time": 2.5 + (hash(provider.value) % 10) * 0.1,
                "avg_tokens_per_request": 500 + hash(provider.value) % 200,
                "error_rate": (5 - hash(provider.value) % 5) / 100,
                "last_used": datetime.now().isoformat()
            }
        
        return stats