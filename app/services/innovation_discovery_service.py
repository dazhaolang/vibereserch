"""
创新发现服务 - 课题发现与创新点挖掘
基于RAG技术和主经验分析，识别研究空白和创新机会
"""

import json
import asyncio
from typing import List, Dict, Optional, Any, Tuple, Set
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
import numpy as np
from collections import Counter, defaultdict

from app.core.config import settings
from app.services.ai_service import AIService
from app.services.rag_service import RAGService
from app.models.experience import MainExperience, ExperienceBook
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.models.user import User


class InnovationDiscoveryService:
    """创新发现服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.rag_service = RAGService(db)
        
        # 创新类型定义
        self.innovation_types = {
            "方法创新": {
                "description": "新的研究方法、制备工艺或技术路线",
                "keywords": ["方法", "工艺", "技术", "路线", "制备", "合成"],
                "weight": 0.3
            },
            "材料创新": {
                "description": "新材料、新组合或新结构设计",
                "keywords": ["材料", "组合", "结构", "设计", "新型", "复合"],
                "weight": 0.25
            },
            "应用创新": {
                "description": "新的应用领域或应用方式",
                "keywords": ["应用", "用途", "领域", "功能", "性能", "器件"],
                "weight": 0.2
            },
            "机理创新": {
                "description": "新的理论机理或作用原理",
                "keywords": ["机理", "原理", "理论", "模型", "机制", "作用"],
                "weight": 0.15
            },
            "交叉融合": {
                "description": "跨学科或跨领域的融合创新",
                "keywords": ["交叉", "融合", "结合", "协同", "多元", "集成"],
                "weight": 0.1
            }
        }
        
        # 研究趋势分析维度
        self.trend_dimensions = {
            "时间趋势": {
                "description": "基于时间序列分析研究发展趋势",
                "analysis_period": "最近5年"
            },
            "方法趋势": {
                "description": "研究方法和技术的发展趋势",
                "focus_areas": ["新技术", "新工艺", "新设备"]
            },
            "应用趋势": {
                "description": "应用领域和市场需求的变化趋势",
                "focus_areas": ["新应用", "新市场", "新需求"]
            },
            "性能趋势": {
                "description": "性能指标和质量要求的发展趋势",
                "focus_areas": ["性能提升", "质量改进", "效率优化"]
            }
        }
    
    async def discover_research_opportunities(
        self,
        project: Project,
        analysis_scope: str = "comprehensive",  # focused, comprehensive, exploratory
        innovation_focus: List[str] = None,
        progress_callback = None
    ) -> Dict:
        """
        发现研究机会和创新点
        
        Args:
            project: 项目对象
            analysis_scope: 分析范围
            innovation_focus: 创新关注点
            progress_callback: 进度回调函数
            
        Returns:
            研究机会发现结果
        """
        try:
            logger.info(f"开始发现研究机会 - 项目: {project.name}, 范围: {analysis_scope}")
            
            if progress_callback:
                await progress_callback("收集研究数据", 10, {"scope": analysis_scope})
            
            # 第一步：收集和整理研究数据
            research_data = await self._collect_research_data(project, analysis_scope)
            
            if progress_callback:
                await progress_callback("分析研究现状", 25, {})
            
            # 第二步：分析当前研究现状
            current_state_analysis = await self._analyze_current_research_state(
                research_data, project
            )
            
            if progress_callback:
                await progress_callback("识别研究空白", 45, {})
            
            # 第三步：识别研究空白和未探索领域
            research_gaps = await self._identify_research_gaps(
                current_state_analysis, research_data
            )
            
            if progress_callback:
                await progress_callback("挖掘创新机会", 65, {})
            
            # 第四步：挖掘创新机会
            innovation_opportunities = await self._mine_innovation_opportunities(
                research_gaps, current_state_analysis, innovation_focus
            )
            
            if progress_callback:
                await progress_callback("分析发展趋势", 80, {})
            
            # 第五步：分析研究趋势和前沿方向
            trend_analysis = await self._analyze_research_trends(
                research_data, current_state_analysis
            )
            
            if progress_callback:
                await progress_callback("生成创新建议", 95, {})
            
            # 第六步：生成具体的创新建议和实施路径
            innovation_recommendations = await self._generate_innovation_recommendations(
                innovation_opportunities, trend_analysis, project
            )
            
            if progress_callback:
                await progress_callback("发现完成", 100, {})
            
            return {
                "success": True,
                "project_info": {
                    "project_id": project.id,
                    "project_name": project.name,
                    "analysis_scope": analysis_scope,
                    "analysis_date": datetime.utcnow().isoformat()
                },
                "current_state_analysis": current_state_analysis,
                "research_gaps": research_gaps,
                "innovation_opportunities": innovation_opportunities,
                "trend_analysis": trend_analysis,
                "innovation_recommendations": innovation_recommendations,
                "data_sources": {
                    "literature_count": len(research_data.get("literature", [])),
                    "experience_books": len(research_data.get("experience_books", [])),
                    "main_experiences": len(research_data.get("main_experiences", []))
                }
            }
            
        except Exception as e:
            logger.error(f"发现研究机会失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def generate_research_proposals(
        self,
        innovation_opportunities: Dict,
        project: Project,
        proposal_count: int = 3,
        detail_level: str = "detailed"
    ) -> Dict:
        """
        生成具体的研究提案
        
        Args:
            innovation_opportunities: 创新机会分析结果
            project: 项目对象
            proposal_count: 生成提案数量
            detail_level: 详细程度
            
        Returns:
            研究提案生成结果
        """
        try:
            logger.info(f"生成研究提案 - 项目: {project.name}, 数量: {proposal_count}")
            
            proposals = []
            
            # 获取顶级创新机会
            top_opportunities = innovation_opportunities.get("ranked_opportunities", [])[:proposal_count]
            
            for i, opportunity in enumerate(top_opportunities):
                proposal = await self._generate_single_research_proposal(
                    opportunity, project, i + 1, detail_level
                )
                if proposal:
                    proposals.append(proposal)
            
            # 生成提案对比分析
            comparison_analysis = await self._compare_research_proposals(proposals)
            
            return {
                "success": True,
                "proposals": proposals,
                "comparison_analysis": comparison_analysis,
                "selection_guidance": await self._generate_proposal_selection_guidance(
                    proposals, comparison_analysis
                ),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"生成研究提案失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def analyze_innovation_feasibility(
        self,
        innovation_idea: Dict,
        project: Project,
        analysis_criteria: List[str] = None
    ) -> Dict:
        """
        分析创新想法的可行性
        
        Args:
            innovation_idea: 创新想法
            project: 项目对象
            analysis_criteria: 分析标准
            
        Returns:
            可行性分析结果
        """
        try:
            if analysis_criteria is None:
                analysis_criteria = [
                    "技术可行性", "资源可行性", "时间可行性", 
                    "市场可行性", "风险评估", "创新价值"
                ]
            
            feasibility_analysis = {}
            
            for criterion in analysis_criteria:
                analysis_result = await self._analyze_single_criterion(
                    innovation_idea, criterion, project
                )
                feasibility_analysis[criterion] = analysis_result
            
            # 综合可行性评估
            overall_assessment = await self._generate_overall_feasibility_assessment(
                feasibility_analysis, innovation_idea
            )
            
            return {
                "success": True,
                "innovation_idea": innovation_idea,
                "feasibility_analysis": feasibility_analysis,
                "overall_assessment": overall_assessment,
                "recommendations": await self._generate_feasibility_recommendations(
                    feasibility_analysis, overall_assessment
                ),
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"分析创新可行性失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _collect_research_data(self, project: Project, analysis_scope: str) -> Dict:
        """收集研究数据"""
        try:
            research_data = {
                "literature": [],
                "experience_books": [],
                "main_experiences": [],
                "literature_segments": []
            }
            
            # 根据分析范围确定数据收集策略
            if analysis_scope == "focused":
                literature_limit = 50
                segments_limit = 200
            elif analysis_scope == "comprehensive":
                literature_limit = 200
                segments_limit = 500
            else:  # exploratory
                literature_limit = 500
                segments_limit = 1000
            
            # 收集文献数据
            literature = self.db.query(Literature).filter(
                Literature.projects.any(Project.id == project.id)
            ).order_by(desc(Literature.citation_count)).limit(literature_limit).all()
            
            for lit in literature:
                research_data["literature"].append({
                    "id": lit.id,
                    "title": lit.title,
                    "abstract": lit.abstract,
                    "authors": [author.get("name", "") for author in lit.authors] if lit.authors else [],
                    "year": lit.year,
                    "journal": lit.journal,
                    "citation_count": lit.citation_count,
                    "keywords": lit.keywords
                })
            
            # 收集经验书
            experience_books = self.db.query(ExperienceBook).filter(
                ExperienceBook.project_id == project.id,
                ExperienceBook.status == "completed"
            ).order_by(desc(ExperienceBook.quality_score)).all()
            
            for book in experience_books:
                research_data["experience_books"].append({
                    "id": book.id,
                    "title": book.title,
                    "content": book.content,
                    "research_question": book.research_question,
                    "quality_score": book.quality_score,
                    "iteration_round": book.iteration_round
                })
            
            # 收集主经验
            main_experiences = self.db.query(MainExperience).filter(
                MainExperience.project_id == project.id,
                MainExperience.status == "active"
            ).all()
            
            for exp in main_experiences:
                research_data["main_experiences"].append({
                    "id": exp.id,
                    "experience_type": exp.experience_type,
                    "content": exp.content,
                    "methodology_summary": exp.methodology_summary,
                    "key_findings": exp.key_findings,
                    "practical_guidelines": exp.practical_guidelines,
                    "quality_score": exp.quality_score
                })
            
            # 收集文献段落
            segments = self.db.query(LiteratureSegment).filter(
                LiteratureSegment.project_id == project.id
            ).order_by(desc(LiteratureSegment.quality_score)).limit(segments_limit).all()
            
            for segment in segments:
                research_data["literature_segments"].append({
                    "id": segment.id,
                    "content": segment.content,
                    "segment_type": segment.segment_type,
                    "structured_data": segment.structured_data,
                    "quality_score": segment.quality_score
                })
            
            return research_data
            
        except Exception as e:
            logger.error(f"收集研究数据失败: {e}")
            return {"literature": [], "experience_books": [], "main_experiences": [], "literature_segments": []}
    
    async def _analyze_current_research_state(self, research_data: Dict, project: Project) -> Dict:
        """分析当前研究现状"""
        try:
            analysis_prompt = f"""
基于以下研究数据，分析当前研究现状：

项目信息:
- 项目名称: {project.name}
- 研究关键词: {', '.join(project.keywords or [])}
- 研究方向: {project.research_direction or '未指定'}

数据统计:
- 文献数量: {len(research_data.get('literature', []))}
- 经验书数量: {len(research_data.get('experience_books', []))}
- 主经验数量: {len(research_data.get('main_experiences', []))}
- 文献段落数量: {len(research_data.get('literature_segments', []))}

主要文献摘要:
{json.dumps([lit['title'] + ': ' + (lit['abstract'] or '')[:200] for lit in research_data.get('literature', [])[:10]], ensure_ascii=False, indent=2)}

主经验摘要:
{json.dumps([exp['experience_type'] + ': ' + exp['methodology_summary'][:200] for exp in research_data.get('main_experiences', [])], ensure_ascii=False, indent=2)}

请分析当前研究现状并以JSON格式返回：
{{
    "research_maturity": {{
        "overall_maturity": "emerging/developing/mature",
        "maturity_score": 7.5,
        "maturity_indicators": ["指标1", "指标2"]
    }},
    "research_hotspots": [
        {{
            "topic": "研究热点",
            "frequency": 15,
            "trend": "increasing/stable/decreasing",
            "key_papers": ["重要论文1", "重要论文2"]
        }}
    ],
    "methodology_landscape": {{
        "dominant_methods": ["主流方法1", "主流方法2"],
        "emerging_methods": ["新兴方法1", "新兴方法2"],
        "method_evolution": "方法演进趋势描述"
    }},
    "application_domains": [
        {{
            "domain": "应用领域",
            "penetration": "high/medium/low",
            "growth_potential": "high/medium/low",
            "key_challenges": ["挑战1", "挑战2"]
        }}
    ],
    "research_community": {{
        "active_researchers": 50,
        "key_institutions": ["机构1", "机构2"],
        "collaboration_patterns": "合作模式描述",
        "geographic_distribution": "地理分布描述"
    }},
    "knowledge_structure": {{
        "core_concepts": ["核心概念1", "核心概念2"],
        "theoretical_foundations": ["理论基础1", "理论基础2"],
        "knowledge_gaps": ["知识空白1", "知识空白2"]
    }}
}}

要求：
- 基于实际数据进行分析
- 识别研究的成熟度和发展阶段
- 分析研究热点和趋势
- 评估方法学现状
- 识别应用领域和市场
"""
            
            response = await self.ai_service.generate_completion(
                analysis_prompt,
                model="gpt-4",
                max_tokens=2000,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            # 默认分析结果
            return {
                "research_maturity": {"overall_maturity": "developing", "maturity_score": 6.0},
                "research_hotspots": [],
                "methodology_landscape": {"dominant_methods": [], "emerging_methods": []},
                "application_domains": [],
                "research_community": {"active_researchers": 0},
                "knowledge_structure": {"core_concepts": [], "knowledge_gaps": []}
            }
            
        except Exception as e:
            logger.error(f"分析当前研究现状失败: {e}")
            return {"research_maturity": {"overall_maturity": "unknown"}}
    
    async def _identify_research_gaps(self, current_state: Dict, research_data: Dict) -> Dict:
        """识别研究空白"""
        try:
            gaps_prompt = f"""
基于当前研究现状分析，识别研究空白和未探索领域：

当前研究现状:
{json.dumps(current_state, ensure_ascii=False, indent=2)[:2000]}

请识别研究空白并以JSON格式返回：
{{
    "methodology_gaps": [
        {{
            "gap_type": "方法空白类型",
            "description": "详细描述",
            "potential_impact": "high/medium/low",
            "difficulty_level": "high/medium/low",
            "required_expertise": ["需要的专业知识1", "需要的专业知识2"],
            "potential_solutions": ["可能的解决方案1", "可能的解决方案2"]
        }}
    ],
    "application_gaps": [
        {{
            "gap_type": "应用空白类型",
            "description": "详细描述",
            "market_potential": "high/medium/low",
            "technical_barriers": ["技术壁垒1", "技术壁垒2"],
            "target_applications": ["目标应用1", "目标应用2"]
        }}
    ],
    "theoretical_gaps": [
        {{
            "gap_type": "理论空白类型",
            "description": "详细描述",
            "fundamental_questions": ["基础问题1", "基础问题2"],
            "research_approaches": ["研究方法1", "研究方法2"]
        }}
    ],
    "interdisciplinary_gaps": [
        {{
            "gap_type": "交叉学科空白",
            "disciplines_involved": ["学科1", "学科2"],
            "integration_opportunities": ["融合机会1", "融合机会2"],
            "potential_breakthroughs": ["潜在突破1", "潜在突破2"]
        }}
    ],
    "temporal_gaps": [
        {{
            "gap_type": "时间维度空白",
            "time_horizon": "short-term/medium-term/long-term",
            "description": "详细描述",
            "enabling_technologies": ["使能技术1", "使能技术2"]
        }}
    ],
    "gap_prioritization": [
        {{
            "gap_id": "空白标识",
            "priority_score": 8.5,
            "priority_rationale": "优先级理由",
            "resource_requirements": "资源需求评估"
        }}
    ]
}}

要求：
- 基于现状分析识别真实的研究空白
- 评估空白的重要性和可行性
- 考虑不同维度的空白（方法、应用、理论等）
- 提供优先级排序和资源评估
"""
            
            response = await self.ai_service.generate_completion(
                gaps_prompt,
                model="gpt-4",
                max_tokens=2000,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {
                "methodology_gaps": [],
                "application_gaps": [],
                "theoretical_gaps": [],
                "interdisciplinary_gaps": [],
                "temporal_gaps": [],
                "gap_prioritization": []
            }
            
        except Exception as e:
            logger.error(f"识别研究空白失败: {e}")
            return {"methodology_gaps": []}
    
    async def _mine_innovation_opportunities(
        self,
        research_gaps: Dict,
        current_state: Dict,
        innovation_focus: List[str]
    ) -> Dict:
        """挖掘创新机会"""
        try:
            opportunities_prompt = f"""
基于研究空白和当前状态，挖掘具体的创新机会：

研究空白:
{json.dumps(research_gaps, ensure_ascii=False, indent=2)[:1500]}

当前研究状态:
{json.dumps(current_state, ensure_ascii=False, indent=2)[:1000]}

创新关注点: {innovation_focus or ['全面分析']}

请挖掘创新机会并以JSON格式返回：
{{
    "innovation_opportunities": [
        {{
            "opportunity_id": "OP001",
            "title": "创新机会标题",
            "innovation_type": "方法创新/材料创新/应用创新/机理创新/交叉融合",
            "description": "详细描述",
            "innovation_level": "incremental/significant/breakthrough",
            "target_gaps": ["解决的空白1", "解决的空白2"],
            "technical_approach": {{
                "core_concept": "核心概念",
                "key_technologies": ["关键技术1", "关键技术2"],
                "implementation_strategy": "实施策略",
                "expected_outcomes": ["预期结果1", "预期结果2"]
            }},
            "feasibility_assessment": {{
                "technical_feasibility": 8.0,
                "resource_feasibility": 7.0,
                "time_feasibility": 6.0,
                "overall_feasibility": 7.0
            }},
            "impact_potential": {{
                "scientific_impact": 8.5,
                "technological_impact": 7.5,
                "economic_impact": 6.5,
                "social_impact": 5.5,
                "overall_impact": 7.0
            }},
            "competitive_advantages": ["竞争优势1", "竞争优势2"],
            "risk_factors": ["风险因素1", "风险因素2"],
            "resource_requirements": {{
                "human_resources": "人力资源需求",
                "financial_resources": "资金需求",
                "equipment_resources": "设备需求",
                "time_resources": "时间需求"
            }}
        }}
    ],
    "opportunity_clusters": [
        {{
            "cluster_name": "机会集群名称",
            "opportunities": ["OP001", "OP002"],
            "synergy_potential": "协同潜力描述",
            "integrated_approach": "集成方法建议"
        }}
    ],
    "ranked_opportunities": [
        {{
            "opportunity_id": "OP001",
            "rank": 1,
            "composite_score": 8.2,
            "ranking_rationale": "排名理由"
        }}
    ]
}}

要求：
- 基于研究空白提出具体的创新机会
- 评估创新的可行性和影响潜力
- 考虑不同类型的创新
- 提供优先级排序和实施建议
"""
            
            response = await self.ai_service.generate_completion(
                opportunities_prompt,
                model="gpt-4",
                max_tokens=2500,
                temperature=0.4
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {
                "innovation_opportunities": [],
                "opportunity_clusters": [],
                "ranked_opportunities": []
            }
            
        except Exception as e:
            logger.error(f"挖掘创新机会失败: {e}")
            return {"innovation_opportunities": []}
    
    async def _analyze_research_trends(self, research_data: Dict, current_state: Dict) -> Dict:
        """分析研究趋势"""
        try:
            # 基于文献年份分析时间趋势
            literature = research_data.get("literature", [])
            year_distribution = {}
            
            for lit in literature:
                year = lit.get("year")
                if year and isinstance(year, int) and 2000 <= year <= 2024:
                    year_distribution[year] = year_distribution.get(year, 0) + 1
            
            # 分析关键词趋势
            keyword_trends = self._analyze_keyword_trends(literature)
            
            # 分析方法趋势
            method_trends = self._analyze_method_trends(research_data)
            
            trends_prompt = f"""
基于研究数据分析研究趋势：

年份分布:
{json.dumps(year_distribution, ensure_ascii=False, indent=2)}

关键词趋势:
{json.dumps(keyword_trends, ensure_ascii=False, indent=2)}

方法趋势:
{json.dumps(method_trends, ensure_ascii=False, indent=2)}

当前状态:
{json.dumps(current_state, ensure_ascii=False, indent=2)[:1000]}

请分析研究趋势并以JSON格式返回：
{{
    "temporal_trends": {{
        "publication_trend": "increasing/stable/decreasing",
        "growth_rate": 12.5,
        "trend_analysis": "趋势分析描述",
        "future_projection": "未来发展预测"
    }},
    "thematic_trends": [
        {{
            "theme": "主题名称",
            "trend": "emerging/growing/mature/declining",
            "momentum": "high/medium/low",
            "key_drivers": ["驱动因素1", "驱动因素2"],
            "future_potential": "high/medium/low"
        }}
    ],
    "methodological_trends": [
        {{
            "method_category": "方法类别",
            "evolution_pattern": "演进模式描述",
            "emerging_techniques": ["新兴技术1", "新兴技术2"],
            "obsolete_techniques": ["过时技术1", "过时技术2"]
        }}
    ],
    "application_trends": [
        {{
            "application_area": "应用领域",
            "market_trend": "expanding/stable/contracting",
            "innovation_drivers": ["创新驱动因素1", "创新驱动因素2"],
            "barriers_to_adoption": ["采用障碍1", "采用障碍2"]
        }}
    ],
    "frontier_directions": [
        {{
            "direction": "前沿方向",
            "maturity": "very_early/early/emerging/developing",
            "breakthrough_potential": "high/medium/low",
            "key_challenges": ["关键挑战1", "关键挑战2"],
            "timeline_to_impact": "short-term/medium-term/long-term"
        }}
    ]
}}
"""
            
            response = await self.ai_service.generate_completion(
                trends_prompt,
                model="gpt-4",
                max_tokens=1500,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {
                "temporal_trends": {"publication_trend": "stable"},
                "thematic_trends": [],
                "methodological_trends": [],
                "application_trends": [],
                "frontier_directions": []
            }
            
        except Exception as e:
            logger.error(f"分析研究趋势失败: {e}")
            return {"temporal_trends": {"publication_trend": "unknown"}}
    
    def _analyze_keyword_trends(self, literature: List[Dict]) -> Dict:
        """分析关键词趋势"""
        try:
            keyword_counts = Counter()
            keyword_years = defaultdict(list)
            
            for lit in literature:
                year = lit.get("year")
                keywords = lit.get("keywords", [])
                
                if year and isinstance(year, int) and keywords:
                    for keyword in keywords:
                        if isinstance(keyword, str):
                            keyword_counts[keyword.lower()] += 1
                            keyword_years[keyword.lower()].append(year)
            
            # 计算关键词的年份分布
            keyword_trends = {}
            for keyword, years in keyword_years.items():
                if len(years) >= 3:  # 至少出现3次
                    recent_years = [y for y in years if y >= 2020]
                    early_years = [y for y in years if y < 2020]
                    
                    trend = "stable"
                    if len(recent_years) > len(early_years):
                        trend = "increasing"
                    elif len(recent_years) < len(early_years):
                        trend = "decreasing"
                    
                    keyword_trends[keyword] = {
                        "total_count": keyword_counts[keyword],
                        "trend": trend,
                        "recent_frequency": len(recent_years),
                        "early_frequency": len(early_years)
                    }
            
            return dict(sorted(keyword_trends.items(), key=lambda x: x[1]["total_count"], reverse=True)[:20])
            
        except Exception as e:
            logger.error(f"分析关键词趋势失败: {e}")
            return {}
    
    def _analyze_method_trends(self, research_data: Dict) -> Dict:
        """分析方法趋势"""
        try:
            method_keywords = [
                "合成", "制备", "表征", "测试", "分析", "计算", "模拟", 
                "实验", "理论", "优化", "设计", "控制"
            ]
            
            method_trends = {}
            
            # 从主经验中提取方法信息
            main_experiences = research_data.get("main_experiences", [])
            for exp in main_experiences:
                methodology = exp.get("methodology_summary", "")
                for method in method_keywords:
                    if method in methodology:
                        if method not in method_trends:
                            method_trends[method] = {"count": 0, "contexts": []}
                        method_trends[method]["count"] += 1
                        method_trends[method]["contexts"].append(exp.get("experience_type", ""))
            
            return method_trends
            
        except Exception as e:
            logger.error(f"分析方法趋势失败: {e}")
            return {}
    
    async def _generate_innovation_recommendations(
        self,
        opportunities: Dict,
        trends: Dict,
        project: Project
    ) -> Dict:
        """生成创新建议"""
        try:
            recommendations_prompt = f"""
基于创新机会和趋势分析，生成具体的创新建议：

项目信息:
- 项目名称: {project.name}
- 研究关键词: {', '.join(project.keywords or [])}

创新机会摘要:
{json.dumps(opportunities.get('ranked_opportunities', [])[:5], ensure_ascii=False, indent=2)}

趋势分析摘要:
{json.dumps(trends.get('frontier_directions', [])[:3], ensure_ascii=False, indent=2)}

请生成创新建议并以JSON格式返回：
{{
    "strategic_recommendations": [
        {{
            "recommendation_id": "REC001",
            "title": "建议标题",
            "category": "short-term/medium-term/long-term",
            "priority": "high/medium/low",
            "description": "详细描述",
            "rationale": "建议理由",
            "implementation_steps": ["步骤1", "步骤2"],
            "expected_outcomes": ["预期结果1", "预期结果2"],
            "success_metrics": ["成功指标1", "成功指标2"],
            "resource_requirements": "资源需求",
            "risk_mitigation": ["风险缓解措施1", "风险缓解措施2"]
        }}
    ],
    "collaboration_opportunities": [
        {{
            "collaboration_type": "学术合作/产业合作/跨学科合作",
            "target_partners": ["潜在合作伙伴1", "潜在合作伙伴2"],
            "collaboration_focus": "合作重点",
            "mutual_benefits": ["互利点1", "互利点2"]
        }}
    ],
    "funding_strategies": [
        {{
            "funding_source": "资金来源",
            "application_focus": "申请重点",
            "competitive_advantages": ["竞争优势1", "竞争优势2"],
            "proposal_timeline": "申请时间线"
        }}
    ],
    "technology_roadmap": {{
        "milestones": [
            {{
                "milestone": "里程碑名称",
                "timeline": "时间线",
                "deliverables": ["交付物1", "交付物2"],
                "success_criteria": ["成功标准1", "成功标准2"]
            }}
        ],
        "critical_path": ["关键路径步骤1", "关键路径步骤2"],
        "contingency_plans": ["应急计划1", "应急计划2"]
    }},
    "implementation_priorities": [
        {{
            "priority_level": 1,
            "focus_area": "重点领域",
            "justification": "优先级理由",
            "immediate_actions": ["即时行动1", "即时行动2"]
        }}
    ]
}}

要求：
- 提供可操作的具体建议
- 考虑项目的实际情况和资源
- 平衡创新性和可行性
- 提供清晰的实施路径
"""
            
            response = await self.ai_service.generate_completion(
                recommendations_prompt,
                model="gpt-4",
                max_tokens=2000,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {
                "strategic_recommendations": [],
                "collaboration_opportunities": [],
                "funding_strategies": [],
                "technology_roadmap": {"milestones": []},
                "implementation_priorities": []
            }
            
        except Exception as e:
            logger.error(f"生成创新建议失败: {e}")
            return {"strategic_recommendations": []}
    
    async def _generate_single_research_proposal(
        self,
        opportunity: Dict,
        project: Project,
        proposal_number: int,
        detail_level: str
    ) -> Optional[Dict]:
        """生成单个研究提案"""
        try:
            proposal_prompt = f"""
基于创新机会生成详细的研究提案：

创新机会:
{json.dumps(opportunity, ensure_ascii=False, indent=2)}

项目背景:
- 项目名称: {project.name}
- 研究方向: {project.research_direction or '未指定'}

详细程度: {detail_level}

请生成研究提案并以JSON格式返回：
{{
    "proposal_info": {{
        "proposal_id": "PROP{proposal_number:03d}",
        "title": "研究提案标题",
        "category": "基础研究/应用研究/开发研究",
        "innovation_level": "incremental/significant/breakthrough"
    }},
    "research_objectives": {{
        "primary_objective": "主要目标",
        "secondary_objectives": ["次要目标1", "次要目标2"],
        "research_questions": ["研究问题1", "研究问题2"]
    }},
    "methodology": {{
        "research_approach": "研究方法",
        "experimental_design": "实验设计",
        "data_collection": "数据收集方法",
        "analysis_methods": ["分析方法1", "分析方法2"]
    }},
    "innovation_aspects": {{
        "novelty_claims": ["创新声明1", "创新声明2"],
        "differentiation": "与现有研究的差异",
        "potential_breakthroughs": ["潜在突破1", "潜在突破2"]
    }},
    "expected_outcomes": {{
        "scientific_contributions": ["科学贡献1", "科学贡献2"],
        "practical_applications": ["实际应用1", "实际应用2"],
        "intellectual_property": ["知识产权1", "知识产权2"]
    }},
    "implementation_plan": {{
        "timeline": [
            {{"phase": "阶段1", "duration": "6个月", "activities": ["活动1", "活动2"]}}
        ],
        "resource_requirements": {{
            "personnel": "人员需求",
            "equipment": "设备需求",
            "materials": "材料需求",
            "budget_estimate": "预算估计"
        }},
        "risk_assessment": {{
            "technical_risks": ["技术风险1", "技术风险2"],
            "mitigation_strategies": ["缓解策略1", "缓解策略2"]
        }}
    }},
    "impact_assessment": {{
        "scientific_impact": 8.0,
        "technological_impact": 7.5,
        "economic_impact": 6.5,
        "social_impact": 5.0,
        "overall_impact": 7.0
    }}
}}

要求：
- 基于创新机会生成具体可行的提案
- 根据detail_level调整详细程度
- 确保提案的科学性和创新性
- 提供清晰的实施计划和影响评估
"""
            
            response = await self.ai_service.generate_completion(
                proposal_prompt,
                model="gpt-4",
                max_tokens=1800 if detail_level == "detailed" else 1200,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return None
            
        except Exception as e:
            logger.error(f"生成研究提案失败: {e}")
            return None
    
    async def _compare_research_proposals(self, proposals: List[Dict]) -> Dict:
        """对比研究提案"""
        try:
            if not proposals:
                return {"comparison_matrix": [], "recommendations": []}
            
            comparison_criteria = [
                "创新性", "可行性", "影响力", "资源需求", "风险水平", "时间周期"
            ]
            
            comparison_matrix = []
            for proposal in proposals:
                proposal_id = proposal.get("proposal_info", {}).get("proposal_id", "未知")
                title = proposal.get("proposal_info", {}).get("title", "未知提案")
                
                comparison_row = {
                    "proposal_id": proposal_id,
                    "title": title,
                    "scores": {}
                }
                
                # 从提案中提取评分
                impact_assessment = proposal.get("impact_assessment", {})
                comparison_row["scores"]["创新性"] = impact_assessment.get("scientific_impact", 5.0)
                comparison_row["scores"]["影响力"] = impact_assessment.get("overall_impact", 5.0)
                
                # 简化的评分逻辑（实际应该更复杂）
                comparison_row["scores"]["可行性"] = 7.0  # 默认值
                comparison_row["scores"]["资源需求"] = 6.0  # 默认值
                comparison_row["scores"]["风险水平"] = 5.0  # 默认值
                comparison_row["scores"]["时间周期"] = 6.0  # 默认值
                
                comparison_matrix.append(comparison_row)
            
            # 生成对比建议
            recommendations = [
                f"提案 {proposals[0].get('proposal_info', {}).get('proposal_id', '1')} 在创新性方面表现突出",
                "建议优先考虑可行性高且资源需求适中的提案",
                "可以考虑将多个提案的优点结合，形成综合方案"
            ]
            
            return {
                "comparison_matrix": comparison_matrix,
                "comparison_criteria": comparison_criteria,
                "recommendations": recommendations,
                "best_overall": comparison_matrix[0]["proposal_id"] if comparison_matrix else None
            }
            
        except Exception as e:
            logger.error(f"对比研究提案失败: {e}")
            return {"comparison_matrix": [], "recommendations": []}
    
    async def _generate_proposal_selection_guidance(
        self,
        proposals: List[Dict],
        comparison: Dict
    ) -> Dict:
        """生成提案选择指导"""
        try:
            if not proposals:
                return {"selection_criteria": [], "recommendations": []}
            
            guidance = {
                "selection_criteria": [
                    {
                        "criterion": "战略匹配度",
                        "description": "与项目整体战略目标的匹配程度",
                        "weight": 0.3
                    },
                    {
                        "criterion": "创新价值",
                        "description": "科学和技术创新的价值和影响",
                        "weight": 0.25
                    },
                    {
                        "criterion": "实施可行性",
                        "description": "在现有资源条件下的可实施性",
                        "weight": 0.2
                    },
                    {
                        "criterion": "风险可控性",
                        "description": "项目风险的可预测性和可控性",
                        "weight": 0.15
                    },
                    {
                        "criterion": "资源效率",
                        "description": "投入产出比和资源利用效率",
                        "weight": 0.1
                    }
                ],
                "selection_recommendations": [
                    "优先选择与项目核心目标高度匹配的提案",
                    "平衡创新性和可行性，避免过度冒险",
                    "考虑分阶段实施，降低整体风险",
                    "建立清晰的成功指标和里程碑",
                    "预留足够的资源缓冲和时间余量"
                ],
                "decision_framework": {
                    "step1": "评估战略匹配度和创新价值",
                    "step2": "分析实施可行性和资源需求",
                    "step3": "评估风险因素和缓解措施",
                    "step4": "计算综合得分和排序",
                    "step5": "制定实施计划和监控机制"
                }
            }
            
            return guidance
            
        except Exception as e:
            logger.error(f"生成选择指导失败: {e}")
            return {"selection_criteria": [], "recommendations": []}
    
    async def _analyze_single_criterion(
        self,
        innovation_idea: Dict,
        criterion: str,
        project: Project
    ) -> Dict:
        """分析单个可行性标准"""
        try:
            analysis_prompt = f"""
分析创新想法在"{criterion}"方面的可行性：

创新想法:
{json.dumps(innovation_idea, ensure_ascii=False, indent=2)}

项目背景:
- 项目名称: {project.name}
- 研究方向: {project.research_direction or '未指定'}

请分析{criterion}并以JSON格式返回：
{{
    "criterion": "{criterion}",
    "score": 7.5,
    "assessment": "详细评估描述",
    "strengths": ["优势1", "优势2"],
    "weaknesses": ["劣势1", "劣势2"],
    "requirements": ["需求1", "需求2"],
    "recommendations": ["建议1", "建议2"],
    "confidence_level": "high/medium/low"
}}

评估要求：
- 技术可行性：评估技术实现的难度和可能性
- 资源可行性：评估所需资源的可获得性
- 时间可行性：评估实施时间的合理性
- 市场可行性：评估市场接受度和商业价值
- 风险评估：识别和评估主要风险因素
- 创新价值：评估创新的科学和实用价值
"""
            
            response = await self.ai_service.generate_completion(
                analysis_prompt,
                model="gpt-4",
                max_tokens=600,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    return json.loads(response["content"])
                except json.JSONDecodeError:
                    pass
            
            return {
                "criterion": criterion,
                "score": 5.0,
                "assessment": "评估失败",
                "confidence_level": "low"
            }
            
        except Exception as e:
            logger.error(f"分析可行性标准失败: {e}")
            return {"criterion": criterion, "score": 0.0}
    
    async def _generate_overall_feasibility_assessment(
        self,
        feasibility_analysis: Dict,
        innovation_idea: Dict
    ) -> Dict:
        """生成总体可行性评估"""
        try:
            # 计算加权平均分
            weights = {
                "技术可行性": 0.3,
                "资源可行性": 0.25,
                "时间可行性": 0.15,
                "市场可行性": 0.2,
                "风险评估": 0.1
            }
            
            total_score = 0.0
            total_weight = 0.0
            
            for criterion, analysis in feasibility_analysis.items():
                weight = weights.get(criterion, 0.1)
                score = analysis.get("score", 5.0)
                total_score += score * weight
                total_weight += weight
            
            overall_score = total_score / total_weight if total_weight > 0 else 5.0
            
            # 确定可行性等级
            if overall_score >= 8.0:
                feasibility_level = "高可行性"
            elif overall_score >= 6.0:
                feasibility_level = "中等可行性"
            else:
                feasibility_level = "低可行性"
            
            return {
                "overall_score": round(overall_score, 1),
                "feasibility_level": feasibility_level,
                "key_strengths": [
                    analysis.get("strengths", [])
                    for analysis in feasibility_analysis.values()
                ][0][:3] if feasibility_analysis else [],
                "key_challenges": [
                    analysis.get("weaknesses", [])
                    for analysis in feasibility_analysis.values()
                ][0][:3] if feasibility_analysis else [],
                "critical_success_factors": [
                    "技术突破的实现",
                    "充足资源的保障",
                    "有效的风险管控"
                ],
                "go_no_go_recommendation": "建议实施" if overall_score >= 6.0 else "需要进一步评估"
            }
            
        except Exception as e:
            logger.error(f"生成总体可行性评估失败: {e}")
            return {"overall_score": 5.0, "feasibility_level": "未知"}
    
    async def _generate_feasibility_recommendations(
        self,
        feasibility_analysis: Dict,
        overall_assessment: Dict
    ) -> List[str]:
        """生成可行性建议"""
        try:
            recommendations = []
            
            overall_score = overall_assessment.get("overall_score", 5.0)
            
            if overall_score >= 8.0:
                recommendations.extend([
                    "该创新想法具有很高的可行性，建议优先实施",
                    "制定详细的实施计划和时间表",
                    "确保充足的资源配置和团队支持"
                ])
            elif overall_score >= 6.0:
                recommendations.extend([
                    "该创新想法具有中等可行性，建议谨慎实施",
                    "重点关注关键风险因素的缓解措施",
                    "考虑分阶段实施以降低风险"
                ])
            else:
                recommendations.extend([
                    "该创新想法可行性较低，建议深入评估后再决定",
                    "优先解决关键技术和资源瓶颈",
                    "考虑寻找合作伙伴共同分担风险"
                ])
            
            # 基于具体分析添加针对性建议
            for criterion, analysis in feasibility_analysis.items():
                score = analysis.get("score", 5.0)
                if score < 6.0:
                    recommendations.extend(analysis.get("recommendations", [])[:2])
            
            return recommendations[:8]  # 限制建议数量
            
        except Exception as e:
            logger.error(f"生成可行性建议失败: {e}")
            return ["建议进行更详细的可行性分析"]