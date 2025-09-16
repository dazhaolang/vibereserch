"""
智能提示词模板服务 - 完全动态生成系统
实现从样本文献中自主发现研究重点，生成双重提示词系统
"""

import asyncio
import json
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from app.core.config import settings
from app.services.ai_service import AIService
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.models.user import User


class IntelligentTemplateService:
    """智能模板服务 - 完全动态生成系统"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        
    async def discover_research_patterns_from_literature(
        self,
        project: Project,
        sample_literature: List[Literature],
        progress_callback = None
    ) -> Dict:
        """
        从样本文献中完全自主发现研究模式
        
        这是核心方法：让AI从大量文献中发现该子领域真正关心的问题
        """
        logger.info(f"开始为项目 {project.id} 从 {len(sample_literature)} 篇文献中发现研究模式")
        
        if progress_callback:
            await progress_callback("智能筛选代表性文献", 5.0, {"total_literature": len(sample_literature)})
        
        # 1. 智能选择最具代表性的文献样本
        representative_literature = await self._select_representative_literature(
            sample_literature, target_count=5
        )
        
        if progress_callback:
            await progress_callback("分析文献全文内容", 15.0, {"selected_literature": len(representative_literature)})
        
        # 2. 提取全文内容进行深度分析
        full_contents = []
        for lit in representative_literature:
            content = await self._extract_full_literature_content(lit)
            if content:
                full_contents.append({
                    "title": lit.title,
                    "content": content[:8000],  # 限制长度避免token过多
                    "citation_count": lit.citation_count or 0,
                    "impact_factor": lit.impact_factor or 0.0
                })
        
        if progress_callback:
            await progress_callback("AI自主发现研究重点", 40.0, {"analyzing_contents": len(full_contents)})
        
        # 3. 让AI完全自主发现该领域的研究重点
        research_discovery = await self._discover_field_research_focus(
            project.keywords, full_contents
        )
        
        if progress_callback:
            await progress_callback("生成智能提取策略", 70.0, {"discovered_patterns": len(research_discovery.get("research_areas", []))})
        
        # 4. 基于发现的重点生成提取策略
        extraction_strategy = await self._generate_extraction_strategy(
            research_discovery, full_contents
        )
        
        if progress_callback:
            await progress_callback("创建双重提示词系统", 90.0, {})
        
        # 5. 生成双重提示词系统
        dual_prompt_system = await self._create_dual_prompt_system(
            research_discovery, extraction_strategy
        )
        
        if progress_callback:
            await progress_callback("完成智能模板生成", 100.0, {})
        
        return {
            "success": True,
            "research_discovery": research_discovery,
            "extraction_strategy": extraction_strategy,
            "dual_prompt_system": dual_prompt_system,
            "representative_literature": [lit.id for lit in representative_literature],
            "metadata": {
                "total_literature_analyzed": len(sample_literature),
                "representative_selected": len(representative_literature),
                "discovery_confidence": research_discovery.get("confidence", 0.0)
            }
        }
    
    async def _select_representative_literature(
        self, 
        literature_list: List[Literature], 
        target_count: int = 5
    ) -> List[Literature]:
        """智能选择最具代表性的文献样本"""
        try:
            # 如果文献数量不多，直接返回
            if len(literature_list) <= target_count:
                return literature_list
            
            # 构建文献分析提示
            literature_summaries = []
            for lit in literature_list[:20]:  # 分析前20篇进行筛选
                summary = {
                    "id": lit.id,
                    "title": lit.title,
                    "abstract": lit.abstract[:300] if lit.abstract else "",
                    "citation_count": lit.citation_count or 0,
                    "year": lit.publication_year or 0
                }
                literature_summaries.append(summary)
            
            selection_prompt = f"""
作为科研文献分析专家，请从以下文献中选择最具代表性的{target_count}篇，用于深度分析该研究领域的核心问题。

文献列表：
{json.dumps(literature_summaries, ensure_ascii=False, indent=2)}

选择标准：
1. 覆盖该领域的主要研究方向
2. 引用量和影响力较高
3. 研究方法和应用场景的多样性
4. 能代表该领域的典型问题和解决方案

请返回JSON格式：
{{
    "selected_literature_ids": [文献ID列表],
    "selection_reasoning": "选择理由"
}}
"""
            
            response = await self.ai_service.generate_completion(
                selection_prompt,
                model="gpt-4",
                max_tokens=800,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    result = json.loads(response["content"])
                    selected_ids = result.get("selected_literature_ids", [])
                    
                    # 根据选择的ID返回文献对象
                    selected_literature = [
                        lit for lit in literature_list 
                        if lit.id in selected_ids
                    ]
                    
                    if len(selected_literature) >= 3:  # 至少需要3篇
                        logger.info(f"AI选择了 {len(selected_literature)} 篇代表性文献: {result.get('selection_reasoning', '')}")
                        return selected_literature
                        
                except json.JSONDecodeError:
                    pass
            
            # 如果AI选择失败，使用规则方式
            return self._fallback_literature_selection(literature_list, target_count)
            
        except Exception as e:
            logger.error(f"智能文献选择失败: {e}")
            return literature_list[:target_count]
    
    def _fallback_literature_selection(
        self, 
        literature_list: List[Literature], 
        target_count: int
    ) -> List[Literature]:
        """备用文献选择策略"""
        # 按引用量和发表年份排序
        sorted_literature = sorted(
            literature_list,
            key=lambda x: (x.citation_count or 0, x.publication_year or 0),
            reverse=True
        )
        return sorted_literature[:target_count]
    
    async def _extract_full_literature_content(self, literature: Literature) -> Optional[str]:
        """提取文献全文内容"""
        try:
            # 优先使用解析后的内容
            if literature.parsed_content:
                return literature.parsed_content
            
            # 否则组合标题和摘要
            content_parts = []
            if literature.title:
                content_parts.append(f"Title: {literature.title}")
            if literature.abstract:
                content_parts.append(f"Abstract: {literature.abstract}")
            
            return "\n\n".join(content_parts) if content_parts else None
            
        except Exception as e:
            logger.error(f"提取文献内容失败: {e}")
            return None
    
    async def _discover_field_research_focus(
        self, 
        project_keywords: List[str], 
        full_contents: List[Dict]
    ) -> Dict:
        """让AI完全自主发现该领域的研究重点"""
        try:
            # 构建发现提示 - 完全开放式，不给任何预设暗示
            discovery_prompt = f"""
作为顶级科研领域分析专家，请深度分析以下文献内容，完全自主地发现这个研究领域真正关心的核心问题。

项目关键词：{', '.join(project_keywords)}

文献内容：
{json.dumps(full_contents, ensure_ascii=False, indent=2)[:12000]}

请完全从文献中发现，不要有任何预设假设，分析：

1. 这个领域的研究者真正在解决什么问题？
2. 他们用什么方法来解决这些问题？
3. 他们最关心什么样的实验数据和结果？
4. 什么样的参数、条件、性能指标是关键的？
5. 这个领域有哪些独特的研究范式和思路？

请以JSON格式返回发现结果：
{{
    "field_name": "准确的研究领域名称",
    "core_research_questions": [
        "核心研究问题1",
        "核心研究问题2",
        ...
    ],
    "research_areas": [
        {{
            "area_name": "研究方向名称",
            "key_questions": ["具体问题1", "具体问题2"],
            "critical_parameters": ["关键参数1", "关键参数2"],
            "typical_methods": ["常用方法1", "常用方法2"],
            "success_metrics": ["成功指标1", "成功指标2"]
        }}
    ],
    "unique_characteristics": [
        "该领域独特特征1",
        "该领域独特特征2"
    ],
    "confidence": 0.95
}}

要求：
- 完全基于文献内容，不要臆测
- 发现真实的研究逻辑，不要套用模板
- 识别该领域的独特性，避免通用化
"""
            
            response = await self.ai_service.generate_completion(
                discovery_prompt,
                model="gpt-4",
                max_tokens=2000,
                temperature=0.1
            )
            
            if response.get("success"):
                try:
                    discovery_result = json.loads(response["content"])
                    logger.info(f"成功发现研究重点: {discovery_result.get('field_name', 'Unknown')}")
                    return discovery_result
                except json.JSONDecodeError:
                    pass
            
            # 如果失败，返回基础结构
            return {
                "field_name": "未知领域",
                "core_research_questions": ["待发现"],
                "research_areas": [],
                "unique_characteristics": [],
                "confidence": 0.0
            }
            
        except Exception as e:
            logger.error(f"发现研究重点失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_extraction_strategy(
        self, 
        research_discovery: Dict, 
        full_contents: List[Dict]
    ) -> Dict:
        """基于发现的重点生成针对性提取策略"""
        try:
            strategy_prompt = f"""
基于以下对研究领域的深度分析，设计精确的信息提取策略。

研究领域发现结果：
{json.dumps(research_discovery, ensure_ascii=False, indent=2)}

请为每个研究方向设计具体的提取策略：

{{
    "extraction_sections": [
        {{
            "section_name": "提取板块名称",
            "target_questions": ["要回答的具体问题"],
            "key_information_types": ["需要提取的信息类型"],
            "critical_data_points": ["关键数据点"],
            "context_requirements": ["上下文要求"]
        }}
    ],
    "special_requirements": [
        "特殊提取要求1",
        "特殊提取要求2"
    ]
}}

要求：
- 针对该领域的特定需求
- 确保提取的信息能回答核心研究问题
- 注重实验细节和关键数据
"""
            
            response = await self.ai_service.generate_completion(
                strategy_prompt,
                model="gpt-4",
                max_tokens=1500,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {"extraction_sections": [], "special_requirements": []}
            
        except Exception as e:
            logger.error(f"生成提取策略失败: {e}")
            return {"extraction_sections": [], "special_requirements": []}
    
    async def _create_dual_prompt_system(
        self, 
        research_discovery: Dict, 
        extraction_strategy: Dict
    ) -> Dict:
        """创建双重提示词系统：用户友好版本 + 技术执行版本"""
        try:
            dual_system_prompt = f"""
基于以下研究分析和提取策略，创建双重提示词系统：

研究发现：
{json.dumps(research_discovery, ensure_ascii=False, indent=2)}

提取策略：
{json.dumps(extraction_strategy, ensure_ascii=False, indent=2)}

请创建两套提示词：

1. 用户友好版本 - 用于前端展示和用户理解
2. 技术执行版本 - 用于实际的AI提取操作

{{
    "user_friendly_prompts": [
        {{
            "section_name": "板块名称",
            "display_title": "用户看到的标题",
            "description": "这个板块要提取什么内容的简单说明",
            "examples": ["示例1", "示例2"],
            "user_configurable": true
        }}
    ],
    "technical_prompts": [
        {{
            "section_name": "板块名称",
            "system_prompt": "给AI的详细技术提示词",
            "extraction_rules": ["具体提取规则1", "具体提取规则2"],
            "output_format": "期望的输出格式",
            "fallback_instructions": "无相关内容时的处理方式"
        }}
    ],
    "prompt_mapping": {{
        "user_section_name": "technical_section_name"
    }}
}}
"""
            
            response = await self.ai_service.generate_completion(
                dual_system_prompt,
                model="gpt-4",
                max_tokens=2500,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {
                "user_friendly_prompts": [],
                "technical_prompts": [],
                "prompt_mapping": {}
            }
            
        except Exception as e:
            logger.error(f"创建双重提示词系统失败: {e}")
            return {"user_friendly_prompts": [], "technical_prompts": [], "prompt_mapping": {}}
    
    async def update_prompts_based_on_user_feedback(
        self,
        project_id: int,
        user_feedback: Dict,
        current_prompts: Dict
    ) -> Dict:
        """基于用户反馈更新提示词"""
        try:
            logger.info(f"为项目 {project_id} 基于用户反馈更新提示词")
            
            feedback_prompt = f"""
用户对当前提示词系统提供了反馈，请基于反馈进行优化：

当前提示词系统：
{json.dumps(current_prompts, ensure_ascii=False, indent=2)}

用户反馈：
{json.dumps(user_feedback, ensure_ascii=False, indent=2)}

请根据用户反馈优化提示词系统，返回改进后的版本：

{{
    "updated_user_friendly_prompts": [...],
    "updated_technical_prompts": [...],
    "changes_made": ["改动说明1", "改动说明2"],
    "optimization_notes": "优化说明"
}}
"""
            
            response = await self.ai_service.generate_completion(
                feedback_prompt,
                model="gpt-4",
                max_tokens=2000,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {"success": False, "error": "反馈处理失败"}
            
        except Exception as e:
            logger.error(f"基于用户反馈更新提示词失败: {e}")
            return {"success": False, "error": str(e)}