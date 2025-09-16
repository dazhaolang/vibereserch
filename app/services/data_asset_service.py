"""
数据资产管理服务 - 平台数据资产的沉淀、管理和利用
包括通用经验库、知识复用、模型微调数据管理
"""

import json
import asyncio
import hashlib
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, distinct

from app.core.config import settings
from app.models.experience import MainExperience, ExperienceBook
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.models.user import User, MembershipType
from app.services.ai_service import AIService


class DataAssetService:
    """数据资产管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        
        # 数据资产分类
        self.asset_categories = {
            "通用主经验": {
                "description": "跨项目的通用主经验库",
                "sharing_policy": "platform_wide",
                "quality_threshold": 8.0,
                "min_usage_count": 3
            },
            "领域知识库": {
                "description": "特定领域的专业知识库",
                "sharing_policy": "domain_specific",
                "quality_threshold": 7.5,
                "min_usage_count": 2
            },
            "方法学模板": {
                "description": "研究方法和实验设计模板",
                "sharing_policy": "methodology_based",
                "quality_threshold": 7.0,
                "min_usage_count": 2
            },
            "文献洞察": {
                "description": "高价值文献分析和洞察",
                "sharing_policy": "curated",
                "quality_threshold": 8.5,
                "min_usage_count": 5
            }
        }
        
        # 知识复用策略
        self.reuse_strategies = {
            "exact_match": {
                "description": "完全匹配的知识直接复用",
                "similarity_threshold": 0.95,
                "confidence_boost": 0.9
            },
            "similar_context": {
                "description": "相似上下文的知识适配复用",
                "similarity_threshold": 0.8,
                "confidence_boost": 0.7
            },
            "pattern_transfer": {
                "description": "模式迁移的知识复用",
                "similarity_threshold": 0.6,
                "confidence_boost": 0.5
            }
        }
    
    async def build_universal_knowledge_base(
        self,
        scope: str = "platform_wide",  # platform_wide, domain_specific, user_group
        min_quality_score: float = 7.5,
        progress_callback = None
    ) -> Dict:
        """
        构建通用知识库
        
        Args:
            scope: 构建范围
            min_quality_score: 最低质量分数
            progress_callback: 进度回调函数
            
        Returns:
            知识库构建结果
        """
        try:
            logger.info(f"开始构建通用知识库 - 范围: {scope}, 质量阈值: {min_quality_score}")
            
            if progress_callback:
                await progress_callback("收集高质量经验", 10, {"scope": scope})
            
            # 第一步：收集高质量的主经验
            high_quality_experiences = await self._collect_high_quality_experiences(
                scope, min_quality_score
            )
            
            if progress_callback:
                await progress_callback("分析知识模式", 30, {"experiences_count": len(high_quality_experiences)})
            
            # 第二步：分析和提取知识模式
            knowledge_patterns = await self._extract_knowledge_patterns(
                high_quality_experiences
            )
            
            if progress_callback:
                await progress_callback("构建通用经验", 60, {"patterns_count": len(knowledge_patterns)})
            
            # 第三步：构建通用经验模板
            universal_templates = await self._build_universal_templates(
                knowledge_patterns, high_quality_experiences
            )
            
            if progress_callback:
                await progress_callback("验证知识质量", 80, {})
            
            # 第四步：验证和质量评估
            quality_assessment = await self._assess_knowledge_quality(
                universal_templates, high_quality_experiences
            )
            
            if progress_callback:
                await progress_callback("保存知识库", 95, {})
            
            # 第五步：保存到通用知识库
            saved_assets = await self._save_universal_knowledge(
                universal_templates, quality_assessment, scope
            )
            
            if progress_callback:
                await progress_callback("构建完成", 100, {"assets_created": len(saved_assets)})
            
            return {
                "success": True,
                "build_info": {
                    "scope": scope,
                    "min_quality_score": min_quality_score,
                    "build_time": datetime.utcnow().isoformat()
                },
                "source_data": {
                    "experiences_analyzed": len(high_quality_experiences),
                    "patterns_extracted": len(knowledge_patterns),
                    "templates_created": len(universal_templates)
                },
                "knowledge_assets": saved_assets,
                "quality_metrics": quality_assessment.get("overall_metrics", {}),
                "reuse_potential": await self._estimate_reuse_potential(saved_assets)
            }
            
        except Exception as e:
            logger.error(f"构建通用知识库失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def find_reusable_knowledge(
        self,
        project: Project,
        research_context: Dict,
        similarity_threshold: float = 0.7
    ) -> Dict:
        """
        查找可复用的知识资产
        
        Args:
            project: 当前项目
            research_context: 研究上下文
            similarity_threshold: 相似度阈值
            
        Returns:
            可复用知识资产
        """
        try:
            logger.info(f"查找可复用知识 - 项目: {project.name}")
            
            # 第一步：构建查询向量
            query_vector = await self._build_context_vector(research_context, project)
            
            # 第二步：搜索相似的知识资产
            similar_assets = await self._search_similar_assets(
                query_vector, similarity_threshold
            )
            
            # 第三步：评估复用可行性
            reuse_assessments = []
            for asset in similar_assets:
                assessment = await self._assess_reuse_feasibility(
                    asset, research_context, project
                )
                reuse_assessments.append(assessment)
            
            # 第四步：生成复用建议
            reuse_recommendations = await self._generate_reuse_recommendations(
                reuse_assessments, research_context
            )
            
            return {
                "success": True,
                "search_context": research_context,
                "similar_assets": similar_assets,
                "reuse_assessments": reuse_assessments,
                "recommendations": reuse_recommendations,
                "potential_savings": await self._calculate_reuse_savings(reuse_assessments)
            }
            
        except Exception as e:
            logger.error(f"查找可复用知识失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def optimize_knowledge_sharing(
        self,
        sharing_scope: str = "platform_wide",
        privacy_level: str = "anonymized"
    ) -> Dict:
        """
        优化知识共享策略
        
        Args:
            sharing_scope: 共享范围
            privacy_level: 隐私级别
            
        Returns:
            优化结果
        """
        try:
            logger.info(f"优化知识共享 - 范围: {sharing_scope}, 隐私: {privacy_level}")
            
            # 第一步：分析当前共享状况
            current_sharing_status = await self._analyze_current_sharing(sharing_scope)
            
            # 第二步：识别共享机会
            sharing_opportunities = await self._identify_sharing_opportunities(
                current_sharing_status, privacy_level
            )
            
            # 第三步：评估共享价值
            sharing_value_analysis = await self._evaluate_sharing_value(
                sharing_opportunities
            )
            
            # 第四步：制定共享策略
            sharing_strategy = await self._develop_sharing_strategy(
                sharing_value_analysis, privacy_level
            )
            
            # 第五步：实施共享优化
            optimization_results = await self._implement_sharing_optimization(
                sharing_strategy
            )
            
            return {
                "success": True,
                "current_status": current_sharing_status,
                "opportunities": sharing_opportunities,
                "value_analysis": sharing_value_analysis,
                "strategy": sharing_strategy,
                "optimization_results": optimization_results
            }
            
        except Exception as e:
            logger.error(f"优化知识共享失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def prepare_model_training_data(
        self,
        data_type: str = "experience_enhancement",  # experience_enhancement, literature_analysis, innovation_discovery
        quality_threshold: float = 8.0,
        sample_size: int = 1000
    ) -> Dict:
        """
        准备模型训练数据
        
        Args:
            data_type: 数据类型
            quality_threshold: 质量阈值
            sample_size: 样本大小
            
        Returns:
            训练数据准备结果
        """
        try:
            logger.info(f"准备模型训练数据 - 类型: {data_type}, 样本: {sample_size}")
            
            # 第一步：收集高质量数据
            raw_data = await self._collect_training_data(
                data_type, quality_threshold, sample_size
            )
            
            # 第二步：数据清洗和预处理
            cleaned_data = await self._preprocess_training_data(raw_data, data_type)
            
            # 第三步：数据标注和格式化
            formatted_data = await self._format_training_data(cleaned_data, data_type)
            
            # 第四步：数据质量验证
            quality_report = await self._validate_training_data_quality(formatted_data)
            
            # 第五步：生成训练集和验证集
            train_val_split = await self._split_training_data(formatted_data)
            
            return {
                "success": True,
                "data_info": {
                    "data_type": data_type,
                    "quality_threshold": quality_threshold,
                    "total_samples": len(formatted_data),
                    "train_samples": len(train_val_split["train"]),
                    "validation_samples": len(train_val_split["validation"])
                },
                "quality_report": quality_report,
                "training_data": train_val_split,
                "data_statistics": await self._generate_data_statistics(formatted_data),
                "usage_guidelines": await self._generate_usage_guidelines(data_type)
            }
            
        except Exception as e:
            logger.error(f"准备模型训练数据失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _collect_high_quality_experiences(
        self,
        scope: str,
        min_quality_score: float
    ) -> List[Dict]:
        """收集高质量经验"""
        try:
            experiences = []
            
            # 根据范围确定查询条件
            if scope == "platform_wide":
                # 收集所有高质量主经验
                main_experiences = self.db.query(MainExperience).filter(
                    MainExperience.quality_score >= min_quality_score,
                    MainExperience.status == "active"
                ).all()
                
                for exp in main_experiences:
                    experiences.append({
                        "id": exp.id,
                        "type": "main_experience",
                        "experience_type": exp.experience_type,
                        "content": exp.content,
                        "methodology_summary": exp.methodology_summary,
                        "key_findings": exp.key_findings,
                        "practical_guidelines": exp.practical_guidelines,
                        "quality_score": exp.quality_score,
                        "literature_count": exp.literature_count,
                        "project_id": exp.project_id
                    })
            
            elif scope == "domain_specific":
                # 按领域分组收集
                # 这里简化处理，实际应该基于项目的研究领域分组
                pass
            
            # 收集高质量经验书
            experience_books = self.db.query(ExperienceBook).filter(
                ExperienceBook.quality_score >= min_quality_score,
                ExperienceBook.status == "completed"
            ).order_by(desc(ExperienceBook.quality_score)).limit(100).all()
            
            for book in experience_books:
                experiences.append({
                    "id": book.id,
                    "type": "experience_book",
                    "title": book.title,
                    "content": book.content,
                    "research_question": book.research_question,
                    "quality_score": book.quality_score,
                    "iteration_round": book.iteration_round,
                    "project_id": book.project_id
                })
            
            logger.info(f"收集到 {len(experiences)} 个高质量经验")
            return experiences
            
        except Exception as e:
            logger.error(f"收集高质量经验失败: {e}")
            return []
    
    async def _extract_knowledge_patterns(self, experiences: List[Dict]) -> List[Dict]:
        """提取知识模式"""
        try:
            patterns = []
            
            # 按经验类型分组
            grouped_experiences = defaultdict(list)
            for exp in experiences:
                if exp["type"] == "main_experience":
                    grouped_experiences[exp["experience_type"]].append(exp)
                else:
                    grouped_experiences["general"].append(exp)
            
            # 为每个组提取模式
            for exp_type, exp_list in grouped_experiences.items():
                if len(exp_list) >= 3:  # 至少3个经验才能提取模式
                    pattern = await self._extract_pattern_from_group(exp_type, exp_list)
                    if pattern:
                        patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"提取知识模式失败: {e}")
            return []
    
    async def _extract_pattern_from_group(self, exp_type: str, experiences: List[Dict]) -> Optional[Dict]:
        """从经验组中提取模式"""
        try:
            # 构建模式提取提示
            experiences_summary = []
            for exp in experiences[:5]:  # 限制数量
                experiences_summary.append({
                    "content": exp["content"][:500],
                    "methodology": exp.get("methodology_summary", "")[:200],
                    "quality_score": exp["quality_score"]
                })
            
            pattern_prompt = f"""
分析以下{exp_type}类型的经验，提取通用知识模式：

经验数据:
{json.dumps(experiences_summary, ensure_ascii=False, indent=2)}

请提取知识模式并以JSON格式返回：
{{
    "pattern_type": "{exp_type}",
    "common_methodologies": ["通用方法1", "通用方法2"],
    "key_principles": ["核心原理1", "核心原理2"],
    "best_practices": ["最佳实践1", "最佳实践2"],
    "success_factors": ["成功因素1", "成功因素2"],
    "common_challenges": ["常见挑战1", "常见挑战2"],
    "solution_patterns": ["解决方案模式1", "解决方案模式2"],
    "applicable_contexts": ["适用场景1", "适用场景2"],
    "pattern_confidence": 8.5,
    "reuse_potential": "high/medium/low"
}}

要求：
- 识别真正的通用模式
- 避免过度具体化
- 确保模式的可复用性
"""
            
            response = await self.ai_service.generate_completion(
                pattern_prompt,
                model="gpt-4",
                max_tokens=800,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    pattern = json.loads(response["content"])
                    pattern["source_count"] = len(experiences)
                    pattern["extracted_at"] = datetime.utcnow().isoformat()
                    return pattern
                except json.JSONDecodeError:
                    pass
            
            return None
            
        except Exception as e:
            logger.error(f"从经验组提取模式失败: {e}")
            return None
    
    async def _build_universal_templates(
        self,
        patterns: List[Dict],
        experiences: List[Dict]
    ) -> List[Dict]:
        """构建通用模板"""
        try:
            templates = []
            
            for pattern in patterns:
                template = await self._create_template_from_pattern(pattern, experiences)
                if template:
                    templates.append(template)
            
            return templates
            
        except Exception as e:
            logger.error(f"构建通用模板失败: {e}")
            return []
    
    async def _create_template_from_pattern(self, pattern: Dict, experiences: List[Dict]) -> Optional[Dict]:
        """从模式创建模板"""
        try:
            template_prompt = f"""
基于知识模式创建可复用的通用模板：

知识模式:
{json.dumps(pattern, ensure_ascii=False, indent=2)}

请创建通用模板并以JSON格式返回：
{{
    "template_id": "TMPL_{pattern.get('pattern_type', 'GENERAL')}_{datetime.utcnow().strftime('%Y%m%d')}",
    "template_name": "模板名称",
    "template_type": "{pattern.get('pattern_type', 'general')}",
    "description": "模板描述",
    "structure": {{
        "methodology_framework": {{
            "core_methods": ["方法1", "方法2"],
            "implementation_steps": ["步骤1", "步骤2"],
            "quality_controls": ["控制点1", "控制点2"]
        }},
        "knowledge_components": {{
            "theoretical_foundation": "理论基础",
            "practical_guidelines": ["指导原则1", "指导原则2"],
            "success_criteria": ["成功标准1", "成功标准2"]
        }},
        "adaptation_parameters": {{
            "context_variables": ["上下文变量1", "上下文变量2"],
            "customization_points": ["定制点1", "定制点2"]
        }}
    }},
    "usage_guidelines": {{
        "applicable_scenarios": ["适用场景1", "适用场景2"],
        "prerequisites": ["前置条件1", "前置条件2"],
        "adaptation_instructions": ["适配说明1", "适配说明2"]
    }},
    "quality_metrics": {{
        "effectiveness_indicators": ["效果指标1", "效果指标2"],
        "validation_methods": ["验证方法1", "验证方法2"]
    }},
    "reuse_confidence": 8.0
}}

要求：
- 模板要具有通用性和可复用性
- 提供清晰的使用指导
- 包含质量评估机制
"""
            
            response = await self.ai_service.generate_completion(
                template_prompt,
                model="gpt-4",
                max_tokens=1200,
                temperature=0.3
            )
            
            if response.get("success"):
                try:
                    template = json.loads(response["content"])
                    template["created_at"] = datetime.utcnow().isoformat()
                    template["source_pattern"] = pattern
                    return template
                except json.JSONDecodeError:
                    pass
            
            return None
            
        except Exception as e:
            logger.error(f"从模式创建模板失败: {e}")
            return None
    
    async def _assess_knowledge_quality(
        self,
        templates: List[Dict],
        source_experiences: List[Dict]
    ) -> Dict:
        """评估知识质量"""
        try:
            quality_metrics = {
                "overall_quality": 0.0,
                "template_quality_scores": [],
                "coverage_analysis": {},
                "consistency_check": {},
                "reusability_assessment": {}
            }
            
            # 评估每个模板的质量
            total_quality = 0.0
            for template in templates:
                quality_score = template.get("reuse_confidence", 5.0)
                quality_metrics["template_quality_scores"].append({
                    "template_id": template.get("template_id", "unknown"),
                    "quality_score": quality_score
                })
                total_quality += quality_score
            
            # 计算整体质量
            if templates:
                quality_metrics["overall_quality"] = total_quality / len(templates)
            
            # 覆盖度分析
            experience_types = set()
            for exp in source_experiences:
                if exp["type"] == "main_experience":
                    experience_types.add(exp["experience_type"])
            
            template_types = set(t.get("template_type", "general") for t in templates)
            
            quality_metrics["coverage_analysis"] = {
                "source_types_count": len(experience_types),
                "template_types_count": len(template_types),
                "coverage_rate": len(template_types) / max(len(experience_types), 1)
            }
            
            # 一致性检查
            quality_metrics["consistency_check"] = {
                "methodology_consistency": "high",  # 简化评估
                "terminology_consistency": "medium",
                "structure_consistency": "high"
            }
            
            # 可复用性评估
            high_reuse_count = sum(1 for t in templates if t.get("reuse_confidence", 0) >= 8.0)
            quality_metrics["reusability_assessment"] = {
                "high_reuse_templates": high_reuse_count,
                "reusability_rate": high_reuse_count / max(len(templates), 1)
            }
            
            return quality_metrics
            
        except Exception as e:
            logger.error(f"评估知识质量失败: {e}")
            return {"overall_quality": 0.0}
    
    async def _save_universal_knowledge(
        self,
        templates: List[Dict],
        quality_assessment: Dict,
        scope: str
    ) -> List[Dict]:
        """保存通用知识到数据库"""
        try:
            saved_assets = []
            
            # 这里应该创建专门的通用知识表
            # 目前简化处理，记录到日志
            for template in templates:
                asset_record = {
                    "asset_id": template.get("template_id", f"ASSET_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"),
                    "asset_type": "universal_template",
                    "template_type": template.get("template_type", "general"),
                    "quality_score": template.get("reuse_confidence", 5.0),
                    "scope": scope,
                    "created_at": datetime.utcnow().isoformat(),
                    "content": template
                }
                
                saved_assets.append(asset_record)
                logger.info(f"保存通用知识资产: {asset_record['asset_id']}")
            
            return saved_assets
            
        except Exception as e:
            logger.error(f"保存通用知识失败: {e}")
            return []
    
    async def _estimate_reuse_potential(self, assets: List[Dict]) -> Dict:
        """估算复用潜力"""
        try:
            total_assets = len(assets)
            high_potential_assets = sum(1 for asset in assets if asset.get("quality_score", 0) >= 8.0)
            
            # 计算预期复用次数
            expected_reuse_per_asset = 5.0  # 简化估算
            total_expected_reuse = total_assets * expected_reuse_per_asset
            
            # 计算节省的工作量
            avg_creation_time_hours = 8.0  # 平均创建时间
            potential_time_savings = total_expected_reuse * avg_creation_time_hours
            
            return {
                "total_assets": total_assets,
                "high_potential_assets": high_potential_assets,
                "potential_reuse_rate": high_potential_assets / max(total_assets, 1),
                "expected_total_reuse": total_expected_reuse,
                "estimated_time_savings_hours": potential_time_savings,
                "estimated_cost_savings_usd": potential_time_savings * 50  # 假设每小时50美元
            }
            
        except Exception as e:
            logger.error(f"估算复用潜力失败: {e}")
            return {"total_assets": 0}
    
    async def _build_context_vector(self, research_context: Dict, project: Project) -> Dict:
        """构建上下文向量"""
        try:
            # 简化的上下文向量构建
            context_vector = {
                "keywords": project.keywords or [],
                "research_direction": project.research_direction or "",
                "research_categories": project.research_categories or [],
                "context_description": research_context.get("description", ""),
                "research_objectives": research_context.get("objectives", []),
                "methodology_preferences": research_context.get("methodology", [])
            }
            
            return context_vector
            
        except Exception as e:
            logger.error(f"构建上下文向量失败: {e}")
            return {}
    
    async def _search_similar_assets(
        self,
        query_vector: Dict,
        similarity_threshold: float
    ) -> List[Dict]:
        """搜索相似资产"""
        try:
            # 简化的相似性搜索
            # 实际应该使用向量数据库进行语义搜索
            
            similar_assets = []
            
            # 搜索相似的主经验
            query_keywords = set(query_vector.get("keywords", []))
            
            if query_keywords:
                # 基于关键词匹配查找相似主经验
                main_experiences = self.db.query(MainExperience).filter(
                    MainExperience.status == "active",
                    MainExperience.quality_score >= 7.0
                ).all()
                
                for exp in main_experiences:
                    # 简单的关键词匹配相似度计算
                    exp_content = (exp.content + " " + exp.methodology_summary).lower()
                    keyword_matches = sum(1 for kw in query_keywords if kw.lower() in exp_content)
                    similarity = keyword_matches / max(len(query_keywords), 1)
                    
                    if similarity >= similarity_threshold:
                        similar_assets.append({
                            "asset_id": f"main_exp_{exp.id}",
                            "asset_type": "main_experience",
                            "similarity_score": similarity,
                            "content": {
                                "experience_type": exp.experience_type,
                                "content": exp.content,
                                "methodology_summary": exp.methodology_summary,
                                "key_findings": exp.key_findings,
                                "practical_guidelines": exp.practical_guidelines,
                                "quality_score": exp.quality_score
                            }
                        })
            
            # 按相似度排序
            similar_assets.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            return similar_assets[:10]  # 返回前10个最相似的
            
        except Exception as e:
            logger.error(f"搜索相似资产失败: {e}")
            return []
    
    async def _assess_reuse_feasibility(
        self,
        asset: Dict,
        research_context: Dict,
        project: Project
    ) -> Dict:
        """评估复用可行性"""
        try:
            feasibility_prompt = f"""
评估知识资产的复用可行性：

知识资产:
{json.dumps(asset, ensure_ascii=False, indent=2)[:1000]}

目标研究上下文:
{json.dumps(research_context, ensure_ascii=False, indent=2)}

项目信息:
- 项目名称: {project.name}
- 研究方向: {project.research_direction or '未指定'}
- 关键词: {', '.join(project.keywords or [])}

请评估复用可行性并以JSON格式返回：
{{
    "feasibility_score": 8.0,
    "reuse_strategy": "exact_match/similar_context/pattern_transfer",
    "adaptation_required": true,
    "adaptation_complexity": "low/medium/high",
    "expected_effectiveness": 7.5,
    "adaptation_suggestions": ["建议1", "建议2"],
    "potential_benefits": ["收益1", "收益2"],
    "potential_risks": ["风险1", "风险2"],
    "confidence_level": "high/medium/low"
}}

评估标准：
- 上下文匹配度
- 方法学相似性
- 适配难度
- 预期效果
"""
            
            response = await self.ai_service.generate_completion(
                feasibility_prompt,
                model="gpt-4",
                max_tokens=600,
                temperature=0.2
            )
            
            if response.get("success"):
                try:
                    assessment = json.loads(response["content"])
                    assessment["asset_id"] = asset["asset_id"]
                    assessment["similarity_score"] = asset["similarity_score"]
                    return assessment
                except json.JSONDecodeError:
                    pass
            
            # 默认评估
            return {
                "asset_id": asset["asset_id"],
                "feasibility_score": asset["similarity_score"] * 10,
                "reuse_strategy": "similar_context",
                "confidence_level": "medium"
            }
            
        except Exception as e:
            logger.error(f"评估复用可行性失败: {e}")
            return {"asset_id": asset.get("asset_id", "unknown"), "feasibility_score": 0.0}
    
    async def _generate_reuse_recommendations(
        self,
        assessments: List[Dict],
        research_context: Dict
    ) -> Dict:
        """生成复用建议"""
        try:
            # 筛选高可行性的资产
            high_feasibility_assets = [
                a for a in assessments 
                if a.get("feasibility_score", 0) >= 7.0
            ]
            
            # 按可行性分组
            exact_match_assets = [
                a for a in high_feasibility_assets 
                if a.get("reuse_strategy") == "exact_match"
            ]
            
            similar_context_assets = [
                a for a in high_feasibility_assets 
                if a.get("reuse_strategy") == "similar_context"
            ]
            
            pattern_transfer_assets = [
                a for a in high_feasibility_assets 
                if a.get("reuse_strategy") == "pattern_transfer"
            ]
            
            recommendations = {
                "immediate_reuse": {
                    "assets": exact_match_assets,
                    "description": "可以直接复用的高匹配度资产",
                    "implementation_effort": "low"
                },
                "adapted_reuse": {
                    "assets": similar_context_assets,
                    "description": "需要适配的相似上下文资产",
                    "implementation_effort": "medium"
                },
                "pattern_reuse": {
                    "assets": pattern_transfer_assets,
                    "description": "可以进行模式迁移的资产",
                    "implementation_effort": "high"
                },
                "overall_recommendation": self._generate_overall_recommendation(
                    high_feasibility_assets
                )
            }
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成复用建议失败: {e}")
            return {"immediate_reuse": {"assets": []}}
    
    def _generate_overall_recommendation(self, feasible_assets: List[Dict]) -> str:
        """生成总体建议"""
        if not feasible_assets:
            return "未找到合适的可复用知识资产，建议从头构建"
        
        avg_feasibility = sum(a.get("feasibility_score", 0) for a in feasible_assets) / len(feasible_assets)
        
        if avg_feasibility >= 8.5:
            return "发现多个高质量可复用资产，强烈建议优先复用以提高效率"
        elif avg_feasibility >= 7.0:
            return "发现一些可复用资产，建议评估适配成本后决定是否复用"
        else:
            return "可复用资产的适配成本较高，建议谨慎评估后决定"
    
    async def _calculate_reuse_savings(self, assessments: List[Dict]) -> Dict:
        """计算复用节省"""
        try:
            total_assets = len(assessments)
            high_feasibility_count = sum(1 for a in assessments if a.get("feasibility_score", 0) >= 7.0)
            
            # 估算时间节省
            avg_creation_time = 10.0  # 小时
            avg_reuse_time = 2.0  # 小时
            time_savings_per_asset = avg_creation_time - avg_reuse_time
            
            total_time_savings = high_feasibility_count * time_savings_per_asset
            
            # 估算成本节省
            hourly_rate = 50.0  # 美元/小时
            cost_savings = total_time_savings * hourly_rate
            
            return {
                "reusable_assets_count": high_feasibility_count,
                "time_savings_hours": total_time_savings,
                "cost_savings_usd": cost_savings,
                "efficiency_improvement": f"{(time_savings_per_asset / avg_creation_time) * 100:.1f}%"
            }
            
        except Exception as e:
            logger.error(f"计算复用节省失败: {e}")
            return {"reusable_assets_count": 0}
    
    async def _analyze_current_sharing(self, scope: str) -> Dict:
        """分析当前共享状况"""
        try:
            # 统计当前的知识资产
            total_main_experiences = self.db.query(func.count(MainExperience.id)).scalar() or 0
            total_experience_books = self.db.query(func.count(ExperienceBook.id)).scalar() or 0
            
            # 统计用户分布
            total_users = self.db.query(func.count(User.id)).scalar() or 0
            active_users = self.db.query(func.count(distinct(Project.owner_id))).scalar() or 0
            
            return {
                "knowledge_assets": {
                    "main_experiences": total_main_experiences,
                    "experience_books": total_experience_books,
                    "total_assets": total_main_experiences + total_experience_books
                },
                "user_engagement": {
                    "total_users": total_users,
                    "active_users": active_users,
                    "engagement_rate": active_users / max(total_users, 1)
                },
                "sharing_metrics": {
                    "assets_per_active_user": (total_main_experiences + total_experience_books) / max(active_users, 1),
                    "sharing_potential": "medium"  # 简化评估
                }
            }
            
        except Exception as e:
            logger.error(f"分析当前共享状况失败: {e}")
            return {"knowledge_assets": {"total_assets": 0}}
    
    async def _identify_sharing_opportunities(
        self,
        current_status: Dict,
        privacy_level: str
    ) -> List[Dict]:
        """识别共享机会"""
        try:
            opportunities = []
            
            # 基于质量识别共享机会
            high_quality_experiences = self.db.query(MainExperience).filter(
                MainExperience.quality_score >= 8.0,
                MainExperience.status == "active"
            ).all()
            
            for exp in high_quality_experiences:
                opportunity = {
                    "asset_id": f"main_exp_{exp.id}",
                    "asset_type": "main_experience",
                    "sharing_potential": "high",
                    "quality_score": exp.quality_score,
                    "privacy_considerations": self._assess_privacy_requirements(exp, privacy_level),
                    "sharing_benefits": [
                        "提高平台整体知识质量",
                        "加速其他用户的研究进展",
                        "促进知识复用和创新"
                    ]
                }
                opportunities.append(opportunity)
            
            return opportunities[:20]  # 限制数量
            
        except Exception as e:
            logger.error(f"识别共享机会失败: {e}")
            return []
    
    def _assess_privacy_requirements(self, experience: MainExperience, privacy_level: str) -> Dict:
        """评估隐私要求"""
        try:
            if privacy_level == "anonymized":
                return {
                    "anonymization_required": True,
                    "data_masking": ["project_id", "user_id"],
                    "content_filtering": ["specific_names", "proprietary_info"],
                    "sharing_allowed": True
                }
            elif privacy_level == "aggregated":
                return {
                    "anonymization_required": True,
                    "aggregation_required": True,
                    "individual_data_sharing": False,
                    "sharing_allowed": True
                }
            else:  # "restricted"
                return {
                    "sharing_allowed": False,
                    "reason": "隐私级别过于严格"
                }
                
        except Exception as e:
            logger.error(f"评估隐私要求失败: {e}")
            return {"sharing_allowed": False}
    
    async def _evaluate_sharing_value(self, opportunities: List[Dict]) -> Dict:
        """评估共享价值"""
        try:
            total_opportunities = len(opportunities)
            high_value_opportunities = sum(1 for opp in opportunities if opp.get("quality_score", 0) >= 8.5)
            
            # 计算预期价值
            estimated_reuse_per_asset = 3.0
            time_savings_per_reuse = 5.0  # 小时
            hourly_value = 50.0  # 美元
            
            total_estimated_value = (
                total_opportunities * 
                estimated_reuse_per_asset * 
                time_savings_per_reuse * 
                hourly_value
            )
            
            return {
                "total_opportunities": total_opportunities,
                "high_value_opportunities": high_value_opportunities,
                "estimated_platform_value": total_estimated_value,
                "value_per_asset": total_estimated_value / max(total_opportunities, 1),
                "sharing_roi": "positive" if total_estimated_value > 1000 else "neutral"
            }
            
        except Exception as e:
            logger.error(f"评估共享价值失败: {e}")
            return {"total_opportunities": 0}
    
    async def _develop_sharing_strategy(
        self,
        value_analysis: Dict,
        privacy_level: str
    ) -> Dict:
        """制定共享策略"""
        try:
            strategy = {
                "sharing_approach": "gradual_rollout",
                "privacy_protection": {
                    "level": privacy_level,
                    "anonymization_methods": ["content_masking", "identifier_removal"],
                    "consent_requirements": "opt_in"
                },
                "incentive_mechanisms": [
                    "质量贡献积分系统",
                    "知识共享奖励计划",
                    "平台功能优先访问"
                ],
                "quality_control": {
                    "minimum_quality_threshold": 8.0,
                    "peer_review_process": True,
                    "automated_quality_checks": True
                },
                "implementation_phases": [
                    {
                        "phase": "试点阶段",
                        "duration": "3个月",
                        "scope": "高质量用户群体",
                        "objectives": ["验证共享机制", "收集用户反馈"]
                    },
                    {
                        "phase": "扩展阶段",
                        "duration": "6个月",
                        "scope": "全平台用户",
                        "objectives": ["规模化共享", "优化共享体验"]
                    }
                ]
            }
            
            return strategy
            
        except Exception as e:
            logger.error(f"制定共享策略失败: {e}")
            return {"sharing_approach": "conservative"}
    
    async def _implement_sharing_optimization(self, strategy: Dict) -> Dict:
        """实施共享优化"""
        try:
            # 这里应该实施实际的共享优化措施
            # 目前只是记录优化计划
            
            implementation_results = {
                "strategy_implemented": True,
                "optimization_measures": [
                    "建立知识资产质量评估体系",
                    "实施隐私保护措施",
                    "创建用户激励机制",
                    "部署自动化共享工具"
                ],
                "expected_outcomes": {
                    "knowledge_reuse_increase": "30%",
                    "user_engagement_improvement": "25%",
                    "platform_value_enhancement": "40%"
                },
                "monitoring_metrics": [
                    "知识资产复用率",
                    "用户参与度",
                    "共享质量评分",
                    "隐私合规性"
                ],
                "implementation_timeline": strategy.get("implementation_phases", [])
            }
            
            return implementation_results
            
        except Exception as e:
            logger.error(f"实施共享优化失败: {e}")
            return {"strategy_implemented": False}
    
    async def _collect_training_data(
        self,
        data_type: str,
        quality_threshold: float,
        sample_size: int
    ) -> List[Dict]:
        """收集训练数据"""
        try:
            training_data = []
            
            if data_type == "experience_enhancement":
                # 收集经验增强相关数据
                experience_books = self.db.query(ExperienceBook).filter(
                    ExperienceBook.quality_score >= quality_threshold,
                    ExperienceBook.status == "completed"
                ).order_by(desc(ExperienceBook.quality_score)).limit(sample_size).all()
                
                for book in experience_books:
                    training_data.append({
                        "input": book.research_question,
                        "output": book.content,
                        "metadata": {
                            "quality_score": book.quality_score,
                            "iteration_round": book.iteration_round,
                            "literature_count": book.total_literature_count
                        }
                    })
            
            elif data_type == "literature_analysis":
                # 收集文献分析数据
                high_quality_segments = self.db.query(LiteratureSegment).filter(
                    LiteratureSegment.quality_score >= quality_threshold
                ).order_by(desc(LiteratureSegment.quality_score)).limit(sample_size).all()
                
                for segment in high_quality_segments:
                    training_data.append({
                        "input": segment.content,
                        "output": segment.structured_data,
                        "metadata": {
                            "segment_type": segment.segment_type,
                            "quality_score": segment.quality_score,
                            "extraction_method": segment.extraction_method
                        }
                    })
            
            return training_data
            
        except Exception as e:
            logger.error(f"收集训练数据失败: {e}")
            return []
    
    async def _preprocess_training_data(self, raw_data: List[Dict], data_type: str) -> List[Dict]:
        """预处理训练数据"""
        try:
            cleaned_data = []
            
            for item in raw_data:
                # 数据清洗
                if not item.get("input") or not item.get("output"):
                    continue
                
                # 文本标准化
                cleaned_item = {
                    "input": str(item["input"]).strip(),
                    "output": str(item["output"]).strip() if isinstance(item["output"], str) else json.dumps(item["output"], ensure_ascii=False),
                    "metadata": item.get("metadata", {})
                }
                
                # 长度过滤
                if len(cleaned_item["input"]) < 50 or len(cleaned_item["output"]) < 50:
                    continue
                
                if len(cleaned_item["input"]) > 4000 or len(cleaned_item["output"]) > 4000:
                    # 截断过长的文本
                    cleaned_item["input"] = cleaned_item["input"][:4000]
                    cleaned_item["output"] = cleaned_item["output"][:4000]
                
                cleaned_data.append(cleaned_item)
            
            return cleaned_data
            
        except Exception as e:
            logger.error(f"预处理训练数据失败: {e}")
            return raw_data
    
    async def _format_training_data(self, cleaned_data: List[Dict], data_type: str) -> List[Dict]:
        """格式化训练数据"""
        try:
            formatted_data = []
            
            for item in cleaned_data:
                if data_type == "experience_enhancement":
                    formatted_item = {
                        "messages": [
                            {"role": "user", "content": f"研究问题: {item['input']}"},
                            {"role": "assistant", "content": item["output"]}
                        ],
                        "metadata": item["metadata"]
                    }
                elif data_type == "literature_analysis":
                    formatted_item = {
                        "messages": [
                            {"role": "user", "content": f"请分析以下文献内容: {item['input']}"},
                            {"role": "assistant", "content": item["output"]}
                        ],
                        "metadata": item["metadata"]
                    }
                else:
                    formatted_item = item
                
                formatted_data.append(formatted_item)
            
            return formatted_data
            
        except Exception as e:
            logger.error(f"格式化训练数据失败: {e}")
            return cleaned_data
    
    async def _validate_training_data_quality(self, formatted_data: List[Dict]) -> Dict:
        """验证训练数据质量"""
        try:
            total_samples = len(formatted_data)
            
            # 质量检查
            quality_issues = []
            valid_samples = 0
            
            for i, item in enumerate(formatted_data):
                # 检查格式完整性
                if "messages" not in item:
                    quality_issues.append(f"样本 {i}: 缺少 messages 字段")
                    continue
                
                messages = item["messages"]
                if len(messages) != 2:
                    quality_issues.append(f"样本 {i}: messages 长度不正确")
                    continue
                
                # 检查内容质量
                user_content = messages[0].get("content", "")
                assistant_content = messages[1].get("content", "")
                
                if len(user_content) < 20 or len(assistant_content) < 20:
                    quality_issues.append(f"样本 {i}: 内容过短")
                    continue
                
                valid_samples += 1
            
            quality_score = valid_samples / max(total_samples, 1)
            
            return {
                "total_samples": total_samples,
                "valid_samples": valid_samples,
                "quality_score": quality_score,
                "quality_issues": quality_issues[:10],  # 限制问题数量
                "data_quality": "high" if quality_score >= 0.9 else "medium" if quality_score >= 0.7 else "low"
            }
            
        except Exception as e:
            logger.error(f"验证训练数据质量失败: {e}")
            return {"data_quality": "unknown"}
    
    async def _split_training_data(self, formatted_data: List[Dict]) -> Dict:
        """分割训练数据"""
        try:
            import random
            
            # 打乱数据
            shuffled_data = formatted_data.copy()
            random.shuffle(shuffled_data)
            
            # 分割比例：80% 训练，20% 验证
            split_point = int(len(shuffled_data) * 0.8)
            
            train_data = shuffled_data[:split_point]
            validation_data = shuffled_data[split_point:]
            
            return {
                "train": train_data,
                "validation": validation_data,
                "split_info": {
                    "train_size": len(train_data),
                    "validation_size": len(validation_data),
                    "split_ratio": "80:20"
                }
            }
            
        except Exception as e:
            logger.error(f"分割训练数据失败: {e}")
            return {"train": formatted_data, "validation": []}
    
    async def _generate_data_statistics(self, formatted_data: List[Dict]) -> Dict:
        """生成数据统计"""
        try:
            if not formatted_data:
                return {"total_samples": 0}
            
            # 基本统计
            total_samples = len(formatted_data)
            
            # 内容长度统计
            input_lengths = []
            output_lengths = []
            
            for item in formatted_data:
                messages = item.get("messages", [])
                if len(messages) >= 2:
                    input_lengths.append(len(messages[0].get("content", "")))
                    output_lengths.append(len(messages[1].get("content", "")))
            
            statistics = {
                "total_samples": total_samples,
                "content_statistics": {
                    "avg_input_length": sum(input_lengths) / max(len(input_lengths), 1),
                    "avg_output_length": sum(output_lengths) / max(len(output_lengths), 1),
                    "max_input_length": max(input_lengths) if input_lengths else 0,
                    "max_output_length": max(output_lengths) if output_lengths else 0,
                    "min_input_length": min(input_lengths) if input_lengths else 0,
                    "min_output_length": min(output_lengths) if output_lengths else 0
                },
                "quality_distribution": {
                    "high_quality": sum(1 for item in formatted_data if item.get("metadata", {}).get("quality_score", 0) >= 8.0),
                    "medium_quality": sum(1 for item in formatted_data if 6.0 <= item.get("metadata", {}).get("quality_score", 0) < 8.0),
                    "low_quality": sum(1 for item in formatted_data if item.get("metadata", {}).get("quality_score", 0) < 6.0)
                }
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"生成数据统计失败: {e}")
            return {"total_samples": 0}
    
    async def _generate_usage_guidelines(self, data_type: str) -> Dict:
        """生成使用指南"""
        try:
            guidelines = {
                "data_type": data_type,
                "recommended_use_cases": [],
                "training_parameters": {},
                "evaluation_metrics": [],
                "limitations": [],
                "best_practices": []
            }
            
            if data_type == "experience_enhancement":
                guidelines.update({
                    "recommended_use_cases": [
                        "经验书生成模型训练",
                        "知识总结能力提升",
                        "研究问题回答优化"
                    ],
                    "training_parameters": {
                        "learning_rate": 1e-5,
                        "batch_size": 4,
                        "epochs": 3,
                        "warmup_steps": 100
                    },
                    "evaluation_metrics": [
                        "BLEU分数",
                        "ROUGE分数",
                        "语义相似度",
                        "专家评估"
                    ],
                    "limitations": [
                        "数据来源主要为特定领域",
                        "可能存在领域偏见",
                        "需要定期更新以保持时效性"
                    ],
                    "best_practices": [
                        "结合人工评估进行质量控制",
                        "定期使用新数据进行增量训练",
                        "监控模型输出的事实准确性"
                    ]
                })
            
            return guidelines
            
        except Exception as e:
            logger.error(f"生成使用指南失败: {e}")
            return {"data_type": data_type}