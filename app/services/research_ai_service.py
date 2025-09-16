"""
统一的研究AI服务 - 合并重复的AI服务组件
替代: AIService, MultiModelAIService, LiteratureAIAssistant
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from loguru import logger
import openai
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import AIServiceError


class ResearchAIService:
    """统一的研究AI服务 - 简化架构，提高效率"""
    
    def __init__(self):
        """初始化统一的AI服务"""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.models = {
            "primary": "gpt-4",
            "fast": "gpt-3.5-turbo", 
            "analysis": "gpt-4",
            "embedding": "text-embedding-ada-002"
        }
        
        # 统一的请求配置
        self.default_config = {
            "temperature": 0.1,
            "max_tokens": 2000,
            "timeout": 60
        }
        
        # 请求缓存和限流
        self._request_cache = {}
        self._rate_limiter = {}
        
    async def evaluate_literature_quality(
        self, 
        title: str, 
        abstract: str, 
        authors: List[str], 
        journal: str = "",
        year: int = None
    ) -> Dict:
        """评估文献质量和相关性"""
        
        cache_key = f"quality_{hash(title + abstract)}"
        if cache_key in self._request_cache:
            return self._request_cache[cache_key]
        
        try:
            prompt = f"""
作为学术研究专家，请评估以下论文的质量和价值：

标题: {title}
摘要: {abstract}
作者: {', '.join(authors)}
期刊: {journal}
年份: {year}

请从以下维度评估并返回JSON格式：
{{
    "relevance_score": 0.85,  // 相关性评分 (0-1)
    "quality_score": 0.75,    // 质量评分 (0-1)
    "impact_score": 0.70,     // 影响力评分 (0-1)
    "novelty_score": 0.80,    // 创新性评分 (0-1)
    "overall_score": 0.77,    // 综合评分 (0-1)
    "key_contributions": ["贡献1", "贡献2"],
    "research_domains": ["领域1", "领域2"],
    "methodology_type": "实验研究",
    "confidence_level": 0.85,
    "evaluation_reason": "评估理由"
}}

要求：
1. 评分要客观准确
2. 考虑研究方法的严谨性
3. 评估结果的实用性
4. 分析创新点和局限性
"""
            
            response = await self._make_request(
                model=self.models["analysis"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # 解析JSON响应
            try:
                result = json.loads(response)
                result["success"] = True
            except json.JSONDecodeError:
                # 如果JSON解析失败，返回基本评估
                result = {
                    "success": True,
                    "relevance_score": 0.5,
                    "quality_score": 0.5,
                    "overall_score": 0.5,
                    "confidence_level": 0.3,
                    "evaluation_reason": "AI解析响应失败，使用默认评分"
                }
            
            # 缓存结果
            self._request_cache[cache_key] = result
            return result
            
        except Exception as e:
            logger.error(f"文献质量评估失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "relevance_score": 0.5,
                "quality_score": 0.5,
                "overall_score": 0.5
            }
    
    async def generate_research_insights(
        self, 
        query: str, 
        literature_contents: List[Dict],
        focus_areas: List[str] = None
    ) -> Dict:
        """生成研究洞察和建议"""
        
        try:
            # 构建上下文
            context_parts = []
            for i, lit in enumerate(literature_contents[:10]):  # 限制数量避免超长
                context_parts.append(f"""
文献 {i+1}:
标题: {lit.get('title', '未知')}
内容: {lit.get('content', '')[:500]}...
质量评分: {lit.get('quality_score', 'N/A')}
""")
            
            context = "\n".join(context_parts)
            focus_prompt = f"特别关注: {', '.join(focus_areas)}" if focus_areas else ""
            
            prompt = f"""
作为资深研究专家，基于以下文献为研究问题提供深入洞察：

研究问题: {query}
{focus_prompt}

相关文献:
{context}

请生成结构化的研究洞察报告，返回JSON格式：
{{
    "key_findings": [
        {{
            "finding": "关键发现1",
            "evidence": "支撑证据",
            "confidence": 0.85,
            "implications": "研究意义"
        }}
    ],
    "research_gaps": [
        {{
            "gap": "研究空白1", 
            "opportunity": "研究机会",
            "feasibility": 0.75
        }}
    ],
    "methodological_insights": [
        {{
            "method": "研究方法",
            "advantages": "优势",
            "limitations": "局限性",
            "applicability": 0.80
        }}
    ],
    "future_directions": ["方向1", "方向2"],
    "practical_applications": ["应用1", "应用2"],
    "overall_assessment": {{
        "maturity_level": "研究成熟度",
        "consensus_level": "共识程度", 
        "innovation_potential": 0.75
    }},
    "recommendations": [
        {{
            "recommendation": "建议1",
            "priority": "high",
            "rationale": "理由"
        }}
    ]
}}

要求：
1. 基于文献内容生成洞察，不要编造
2. 提供具体可行的研究建议
3. 指出研究机会和潜在风险
4. 评估不同方法的适用性
"""
            
            response = await self._make_request(
                model=self.models["primary"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.2
            )
            
            try:
                result = json.loads(response)
                result["success"] = True
                result["generated_at"] = datetime.utcnow().isoformat()
            except json.JSONDecodeError:
                result = {
                    "success": True,
                    "content": response,
                    "key_findings": [],
                    "research_gaps": [],
                    "recommendations": [],
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            return result
            
        except Exception as e:
            logger.error(f"研究洞察生成失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def extract_literature_keywords(
        self, 
        title: str, 
        abstract: str, 
        content: str = ""
    ) -> Dict:
        """提取文献关键词和主题"""
        
        try:
            text = f"{title}\n{abstract}\n{content[:1000]}"
            
            prompt = f"""
分析以下学术文献，提取关键信息：

文献内容:
{text}

请提取并返回JSON格式：
{{
    "primary_keywords": ["关键词1", "关键词2"],
    "secondary_keywords": ["次要词1", "次要词2"], 
    "research_domains": ["领域1", "领域2"],
    "methodology_keywords": ["方法1", "方法2"],
    "application_areas": ["应用1", "应用2"],
    "main_topics": [
        {{
            "topic": "主题1",
            "relevance": 0.90,
            "description": "主题描述"
        }}
    ]
}}

要求：
1. 关键词要准确反映内容主题
2. 按重要性排序
3. 区分研究方法和应用领域
4. 提供主题的相关性评分
"""
            
            response = await self._make_request(
                model=self.models["fast"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            try:
                result = json.loads(response)
                result["success"] = True
            except json.JSONDecodeError:
                # 提供基本的关键词提取
                words = text.lower().split()
                common_words = set(['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'])
                keywords = [w for w in set(words) if len(w) > 3 and w not in common_words][:10]
                
                result = {
                    "success": True,
                    "primary_keywords": keywords[:5],
                    "secondary_keywords": keywords[5:10],
                    "research_domains": [],
                    "main_topics": []
                }
            
            return result
            
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "primary_keywords": [],
                "secondary_keywords": []
            }
    
    async def _make_request(
        self, 
        model: str, 
        messages: List[Dict], 
        **kwargs
    ) -> str:
        """统一的AI请求处理"""
        
        # 应用默认配置
        config = {**self.default_config, **kwargs}
        
        try:
            # 检查速率限制
            await self._check_rate_limit(model)
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **config
            )
            
            return response.choices[0].message.content
            
        except openai.RateLimitError as e:
            logger.warning(f"API速率限制: {e}")
            # 等待后重试
            await asyncio.sleep(60)
            return await self._make_request(model, messages, **kwargs)
            
        except openai.APIError as e:
            logger.error(f"OpenAI API错误: {e}")
            raise AIServiceError(f"AI服务错误: {str(e)}")
            
        except Exception as e:
            logger.error(f"AI请求失败: {e}")
            raise AIServiceError(f"AI请求异常: {str(e)}")
    
    async def _check_rate_limit(self, model: str):
        """检查和控制请求速率"""
        now = datetime.utcnow()
        
        if model not in self._rate_limiter:
            self._rate_limiter[model] = []
        
        # 清理1分钟前的记录
        self._rate_limiter[model] = [
            req_time for req_time in self._rate_limiter[model] 
            if now - req_time < timedelta(minutes=1)
        ]
        
        # 检查速率限制 (每分钟最多20个请求)
        if len(self._rate_limiter[model]) >= 20:
            wait_time = 60 - (now - self._rate_limiter[model][0]).total_seconds()
            if wait_time > 0:
                logger.info(f"速率限制，等待 {wait_time:.1f} 秒")
                await asyncio.sleep(wait_time)
        
        self._rate_limiter[model].append(now)
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """获取文本嵌入向量"""
        try:
            response = await self.client.embeddings.create(
                model=self.models["embedding"],
                input=texts
            )
            
            return [data.embedding for data in response.data]
            
        except Exception as e:
            logger.error(f"获取嵌入向量失败: {e}")
            raise AIServiceError(f"嵌入向量生成失败: {str(e)}")
    
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
            
            response = await self._make_request(
                model=self.models["primary"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            try:
                template = json.loads(response)
                result = {
                    "success": True,
                    "template": template
                }
            except json.JSONDecodeError:
                result = {
                    "success": True,
                    "template": {"template_name": research_domain, "sections": []}
                }
            
            return result
            
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
            response = await self._make_request(
                model=self.models["fast"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800
            )
            
            return response.strip()
            
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
            
            response = await self._make_request(
                model=self.models["primary"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=3000
            )
            
            new_experience = response
            
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
            
            response = await self._make_request(
                model=self.models["fast"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000
            )
            
            try:
                result = json.loads(response)
                return result.get("information_gain_ratio", 0.0)
            except json.JSONDecodeError:
                return 0.0
            
        except Exception as e:
            logger.error(f"计算信息增益失败: {e}")
            return 0.0
    
    def clear_cache(self):
        """清理缓存"""
        self._request_cache.clear()
        logger.info("AI服务缓存已清理")


# 全局单例
research_ai_service = ResearchAIService()