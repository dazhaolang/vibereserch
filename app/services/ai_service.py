"""
AI服务 - 处理文献分析和经验生成
增强版本包含重试机制和错误处理
"""

import asyncio
from typing import List, Dict, Optional, Tuple
import openai
from openai import AsyncOpenAI
import json
from loguru import logger
import aiohttp

from app.core.config import settings
from app.utils.retry_handler import with_retry, RetryStrategy
from app.services.task_cost_tracker import task_cost_tracker

class AIService:
    """AI服务类"""
    
    def __init__(self):
        # 构建OpenAI客户端配置
        client_config = {
            "api_key": settings.openai_api_key
        }
        
        # 如果配置了base_url，则使用自定义的base_url
        if settings.openai_base_url:
            client_config["base_url"] = settings.openai_base_url
            
        self.client = AsyncOpenAI(**client_config)
        
    @with_retry("openai_api", max_attempts=3, base_delay=2.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF)
    async def screen_literature_relevance(
        self, 
        literature_data: Dict, 
        research_keywords: List[str]
    ) -> Dict:
        """
        文献初筛 - 评估文献与研究关键词的相关性
        
        Args:
            literature_data: 文献数据
            research_keywords: 研究关键词
            
        Returns:
            筛选结果
        """
        try:
            prompt = f"""
作为一个科研文献筛选专家，请评估以下文献与研究关键词的相关性。

研究关键词：{', '.join(research_keywords)}

文献信息：
标题：{literature_data.get('title', '')}
摘要：{literature_data.get('abstract', '')[:500]}
关键词：{', '.join(literature_data.get('keywords', []))}

请从以下维度评估相关性（0-10分）：
1. 标题相关性
2. 摘要相关性  
3. 研究方法相关性
4. 应用领域相关性

请以JSON格式返回结果：
{{
    "relevance_score": 总体相关性评分(0-10),
    "title_relevance": 标题相关性(0-10),
    "abstract_relevance": 摘要相关性(0-10),
    "method_relevance": 方法相关性(0-10),
    "domain_relevance": 领域相关性(0-10),
    "is_relevant": 是否相关(true/false),
    "reason": "评估理由"
}}
"""
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # 使用较便宜的模型进行初筛
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            self._record_usage("gpt-3.5-turbo", response)
            
            self._record_usage("gpt-3.5-turbo", response)
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            return {
                "success": True,
                "relevance_score": result.get("relevance_score", 0),
                "details": result,
                "is_relevant": result.get("relevance_score", 0) >= 6  # 6分以上认为相关
            }
            
        except Exception as e:
            logger.error(f"文献筛选失败: {e}")
            return {
                "success": False,
                "relevance_score": 0,
                "details": {},
                "is_relevant": False,
                "error": str(e)
            }
    
    async def generate_structure_template(
        self, 
        research_domain: str, 
        sample_literature: List[Dict]
    ) -> Dict:
        """
        自动生成轻结构化模板
        
        Args:
            research_domain: 研究领域
            sample_literature: 样本文献
            
        Returns:
            结构化模板
        """
        try:
            # 准备样本文献摘要
            literature_summaries = []
            for lit in sample_literature[:5]:  # 取前5篇作为样本
                summary = {
                    "title": lit.get("title", ""),
                    "abstract": lit.get("abstract", "")[:300]
                }
                literature_summaries.append(summary)
            
            prompt = f"""
作为一个科研文献结构化专家，请为"{research_domain}"研究领域设计一个轻结构化提取模板。

参考文献样本：
{json.dumps(literature_summaries, ensure_ascii=False, indent=2)}

请设计一个包含以下要素的结构化模板：
1. 主要板块（如制备、表征、应用等）
2. 每个板块的子类别
3. 每个类别的关键信息提取点
4. 对应的提示词模板

请以JSON格式返回：
{{
    "template_name": "模板名称",
    "research_domain": "研究领域",
    "sections": [
        {{
            "name": "板块名称",
            "description": "板块描述", 
            "subsections": [
                {{
                    "name": "子板块名称",
                    "keywords": ["关键词1", "关键词2"],
                    "extraction_points": ["提取要点1", "提取要点2"],
                    "prompt_template": "提取提示词模板"
                }}
            ]
        }}
    ]
}}
"""
            
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            self._record_usage(settings.openai_model, response)
            
            self._record_usage(settings.openai_model, response)
            result_text = response.choices[0].message.content
            template = json.loads(result_text)
            
            return {
                "success": True,
                "template": template
            }
            
        except Exception as e:
            logger.error(f"生成结构化模板失败: {e}")
            return {
                "success": False,
                "template": {},
                "error": str(e)
            }
    
    async def extract_structured_content(
        self, 
        text_content: str, 
        structure_template: Dict
    ) -> Dict:
        """
        基于模板提取结构化内容
        
        Args:
            text_content: 文本内容
            structure_template: 结构化模板
            
        Returns:
            结构化内容
        """
        try:
            extracted_content = {}
            
            sections = structure_template.get("sections", [])
            
            for section in sections:
                section_name = section["name"]
                subsections = section.get("subsections", [])
                
                section_content = {}
                
                for subsection in subsections:
                    subsection_name = subsection["name"]
                    prompt_template = subsection.get("prompt_template", "")
                    
                    # 构建提取提示词
                    extraction_prompt = f"""
基于以下文本内容，提取关于"{subsection_name}"的信息：

文本内容：
{text_content[:3000]}  # 限制长度避免token过多

提取要求：
{prompt_template}

请以总结式话术呈现核心信息，避免直接复制原文。如果没有相关信息，返回"无相关信息"。
"""
                    
                    # 调用AI提取
                    extracted_text = await self._extract_with_ai(extraction_prompt)
                    
                    if extracted_text and extracted_text != "无相关信息":
                        section_content[subsection_name] = extracted_text
                
                if section_content:
                    extracted_content[section_name] = section_content
            
            return {
                "success": True,
                "structured_content": extracted_content,
                "extraction_summary": {
                    "total_sections": len(extracted_content),
                    "extracted_sections": list(extracted_content.keys())
                }
            }
            
        except Exception as e:
            logger.error(f"结构化内容提取失败: {e}")
            return {
                "success": False,
                "structured_content": {},
                "error": str(e)
            }
    
    async def _extract_with_ai(self, prompt: str) -> str:
        """使用AI提取内容"""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800
            )
            
            self._record_usage("gpt-3.5-turbo", response)
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"AI提取失败: {e}")
            return ""
    
    async def generate_experience_book(
        self, 
        research_question: str,
        literature_contents: List[Dict],
        previous_experience: Optional[str] = None
    ) -> Dict:
        """
        生成经验书
        
        Args:
            research_question: 研究问题
            literature_contents: 文献内容列表
            previous_experience: 上一轮经验书内容
            
        Returns:
            经验书生成结果
        """
        try:
            # 准备文献内容摘要
            literature_summary = ""
            for i, lit in enumerate(literature_contents[:4], 1):  # 每轮4篇文献
                structured_content = lit.get("structured_content", {})
                content_text = self._flatten_structured_content(structured_content)
                literature_summary += f"\n文献{i}内容摘要：\n{content_text[:1000]}\n"
            
            # 构建提示词
            if previous_experience:
                prompt = f"""
作为科研专家，请基于新的文献内容更新现有经验书。

研究问题：{research_question}

现有经验书：
{previous_experience}

新增文献内容：
{literature_summary}

请更新经验书，要求：
1. 保留现有有效内容
2. 整合新文献的有价值信息
3. 避免重复内容
4. 以教科书风格呈现
5. 突出实用性和可操作性

请返回更新后的完整经验书内容。
"""
            else:
                prompt = f"""
作为科研专家，请基于提供的文献内容生成一本关于"{research_question}"的经验书。

文献内容：
{literature_summary}

请生成经验书，要求：
1. 以教科书风格组织内容
2. 突出实用性和可操作性
3. 包含方法论、注意事项、最佳实践
4. 结构清晰、逻辑严谨
5. 避免直接复制原文，用总结式话术

请生成完整的经验书内容。
"""
            
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=3000
            )
            self._record_usage(settings.openai_model, response)

            new_experience = response.choices[0].message.content
            
            # 计算信息增益
            information_gain = await self._calculate_information_gain(
                previous_experience, new_experience
            ) if previous_experience else 1.0
            
            return {
                "success": True,
                "experience_content": new_experience,
                "information_gain": information_gain,
                "metadata": {
                    "literature_count": len(literature_contents),
                    "has_previous": bool(previous_experience)
                }
            }
            
        except Exception as e:
            logger.error(f"经验书生成失败: {e}")
            return {
                "success": False,
                "experience_content": "",
                "information_gain": 0.0,
                "error": str(e)
            }
    
    async def _calculate_information_gain(
        self, 
        previous_content: str, 
        new_content: str
    ) -> float:
        """计算信息增益比例"""
        try:
            prompt = f"""
请比较以下两个版本的经验书内容，计算新版本相对于旧版本的信息增益比例。

旧版本内容：
{previous_content[:2000]}

新版本内容：
{new_content[:2000]}

请分析：
1. 新增了哪些信息
2. 修改了哪些内容
3. 信息增益比例（0-1之间的小数）

请以JSON格式返回：
{{
    "information_gain_ratio": 信息增益比例,
    "new_information": ["新增信息1", "新增信息2"],
    "modified_information": ["修改信息1", "修改信息2"],
    "analysis": "详细分析"
}}
"""
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000
            )
            self._record_usage("gpt-3.5-turbo", response)

            result = json.loads(response.choices[0].message.content)
            return result.get("information_gain_ratio", 0.0)
            
        except Exception as e:
            logger.error(f"计算信息增益失败: {e}")
            return 0.0
    
    def _flatten_structured_content(self, structured_content: Dict) -> str:
        """将结构化内容扁平化为文本"""
        text_parts = []
        
        def extract_text(data, prefix=""):
            if isinstance(data, dict):
                for key, value in data.items():
                    extract_text(value, f"{prefix}{key}: ")
            elif isinstance(data, list):
                for item in data:
                    extract_text(item, prefix)
            else:
                text_parts.append(f"{prefix}{str(data)}")
        
        extract_text(structured_content)
        return "\n".join(text_parts)
    
    async def generate_main_experience(
        self, 
        research_domain: str,
        all_literature_contents: List[Dict]
    ) -> Dict:
        """
        生成主经验
        
        Args:
            research_domain: 研究领域
            all_literature_contents: 所有文献内容
            
        Returns:
            主经验生成结果
        """
        try:
            # 聚合所有文献内容
            aggregated_content = ""
            for lit in all_literature_contents:
                structured_content = lit.get("structured_content", {})
                content_text = self._flatten_structured_content(structured_content)
                aggregated_content += content_text + "\n\n"
            
            prompt = f"""
作为科研专家，请基于大量文献内容生成一个关于"{research_domain}"的通用主经验库。

文献内容聚合：
{aggregated_content[:8000]}  # 限制长度

请生成主经验，要求：
1. 覆盖该领域的主要研究方法和技术路线
2. 包含通用的实验参数和操作要点
3. 总结常见问题和解决方案
4. 以结构化方式组织（方法论、参数、注意事项等）
5. 内容应具有通用性，适用于该领域的多种具体问题

请生成完整的主经验内容。
"""
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000
            )
            self._record_usage(settings.openai_model, response)

            main_experience = response.choices[0].message.content
            
            return {
                "success": True,
                "main_experience": main_experience,
                "coverage_scope": await self._extract_coverage_scope(main_experience),
                "metadata": {
                    "source_literature_count": len(all_literature_contents),
                    "domain": research_domain
                }
            }
            
        except Exception as e:
            logger.error(f"主经验生成失败: {e}")
            return {
                "success": False,
                "main_experience": "",
                "error": str(e)
            }
    
    async def _extract_coverage_scope(self, main_experience: str) -> List[str]:
        """提取主经验的覆盖范围"""
        try:
            prompt = f"""
请分析以下主经验内容，提取其覆盖的主要方法和技术范围。

主经验内容：
{main_experience[:2000]}

请以JSON格式返回覆盖范围：
{{
    "methods": ["方法1", "方法2"],
    "techniques": ["技术1", "技术2"],
    "applications": ["应用1", "应用2"]
}}
"""
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            self._record_usage("gpt-3.5-turbo", response)

            result = json.loads(response.choices[0].message.content)
            
            # 合并所有范围
            all_scope = []
            all_scope.extend(result.get("methods", []))
            all_scope.extend(result.get("techniques", []))
            all_scope.extend(result.get("applications", []))
            
            return all_scope
            
        except Exception as e:
            logger.error(f"提取覆盖范围失败: {e}")
            return []
    
    async def answer_research_question(
        self, 
        question: str,
        main_experience: str,
        relevant_segments: List[Dict] = None
    ) -> Dict:
        """
        基于主经验回答研究问题
        
        Args:
            question: 研究问题
            main_experience: 主经验内容
            relevant_segments: 相关文献段落
            
        Returns:
            回答结果
        """
        try:
            # 准备上下文
            context = f"主经验内容：\n{main_experience}\n\n"
            
            if relevant_segments:
                context += "相关文献段落：\n"
                for i, segment in enumerate(relevant_segments[:3], 1):
                    context += f"段落{i}：{segment.get('content', '')[:500]}\n\n"
            
            prompt = f"""
作为科研专家，请基于提供的主经验和相关文献段落，回答以下研究问题。

研究问题：{question}

参考资料：
{context}

请提供：
1. 直接回答问题的解决方案
2. 具体的实验参数建议
3. 操作要点和注意事项
4. 可能的创新点或改进方向

请确保回答具有实用性和可操作性。
"""
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            self._record_usage(settings.openai_model, response)

            answer = response.choices[0].message.content
            
            return {
                "success": True,
                "answer": answer,
                "confidence": 0.85,  # 基于主经验的回答置信度较高
                "sources_used": {
                    "main_experience": True,
                    "literature_segments": len(relevant_segments) if relevant_segments else 0
                }
            }
            
        except Exception as e:
            logger.error(f"问题回答失败: {e}")
            return {
                "success": False,
                "answer": "",
                "error": str(e)
            }
    
    async def generate_completion(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1000,
        temperature: float = 0.3
    ) -> Dict:
        """
        生成AI完成内容的通用方法
        
        Args:
            prompt: 提示词
            model: 模型名称（可选，默认使用配置的模型）
            max_tokens: 最大token数
            temperature: 温度参数
            
        Returns:
            生成结果
        """
        try:
            response = await self.client.chat.completions.create(
                model=model or settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            self._record_usage(model or settings.openai_model, response)

            content = response.choices[0].message.content
            
            return {
                "success": True,
                "content": content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return {
                "success": False,
                "content": "",
                "error": f"JSON解析失败: {str(e)}"
            }
        except Exception as e:
            logger.error(f"AI生成完成失败: {e}")
            return {
                "success": False,
                "content": "",
                "error": str(e)
            }

    @with_retry("openai_embedding", strategy=RetryStrategy.EXPONENTIAL_BACKOFF, max_attempts=3)
    async def get_embedding(self, text: str, model: str = None) -> List[float]:
        """
        获取文本的嵌入向量

        Args:
            text: 需要嵌入的文本
            model: 嵌入模型名称，默认使用配置中的模型

        Returns:
            嵌入向量列表
        """
        try:
            if not text or not text.strip():
                logger.warning("空文本，返回零向量")
                return [0.0] * 1536  # OpenAI text-embedding-ada-002 的维度

            # 清理文本
            cleaned_text = text.strip()[:8000]  # 限制最大长度

            # 使用配置的嵌入模型
            embedding_model = model or settings.openai_embedding_model

            response = await self.client.embeddings.create(
                input=cleaned_text,
                model=embedding_model
            )

            embedding = response.data[0].embedding
            logger.debug(f"成功获取嵌入向量，维度: {len(embedding)}")

            return embedding

        except Exception as e:
            logger.error(f"获取嵌入向量失败: {e}")
            # 返回零向量作为fallback
            return [0.0] * 1536

    def _record_usage(self, model: str, response) -> None:
        try:
            usage = getattr(response, "usage", None)
            if not usage:
                return
            usage_payload = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }
            task_cost_tracker.record_usage(model, usage_payload)
        except Exception as exc:
            logger.warning(f"记录token使用失败: {exc}")

    async def get_embeddings_batch(self, texts: List[str], model: str = None) -> List[List[float]]:
        """
        批量获取文本嵌入向量

        Args:
            texts: 文本列表
            model: 嵌入模型名称

        Returns:
            嵌入向量列表
        """
        try:
            if not texts:
                return []

            # 清理和限制文本
            cleaned_texts = [text.strip()[:8000] for text in texts if text and text.strip()]

            if not cleaned_texts:
                logger.warning("所有文本都为空")
                return [[0.0] * 1536] * len(texts)

            # 使用配置的嵌入模型
            embedding_model = model or settings.openai_embedding_model

            response = await self.client.embeddings.create(
                input=cleaned_texts,
                model=embedding_model
            )

            embeddings = [data.embedding for data in response.data]
            logger.info(f"成功批量获取 {len(embeddings)} 个嵌入向量")

            return embeddings

        except Exception as e:
            logger.error(f"批量获取嵌入向量失败: {e}")
            # 返回零向量作为fallback
            return [[0.0] * 1536] * len(texts)
