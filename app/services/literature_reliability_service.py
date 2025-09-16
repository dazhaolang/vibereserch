"""
文献可靠性评估和排序服务
基于影响因子、出处可靠性等因素对文献进行排序和评估
"""

import asyncio
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app.models.literature import Literature, LiteratureSegment
from app.models.experience import MainExperience
from app.services.ai_service import AIService


class LiteratureReliabilityService:
    """文献可靠性评估和排序服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        
        # 期刊影响因子阈值配置
        self.impact_factor_thresholds = {
            "high": 5.0,      # 高影响因子
            "medium": 2.0,    # 中等影响因子
            "low": 0.5        # 低影响因子
        }
        
        # 来源可靠性权重配置
        self.source_reliability_weights = {
            "high": 1.0,      # Nature, Science, Cell等顶级期刊
            "medium": 0.7,    # 一般SCI期刊
            "low": 0.4,       # 预印本、会议论文等
            "unknown": 0.5    # 未知来源
        }
        
        # 综合可靠性评分权重
        self.reliability_weights = {
            "impact_factor": 0.4,    # 影响因子权重
            "citation_count": 0.3,   # 引用数权重
            "source_reliability": 0.2, # 来源可靠性权重
            "publication_year": 0.1   # 发表年份权重（越新越好）
        }
        
        # 经验偏离度阈值
        self.deviation_thresholds = {
            "high_reliability": 0.8,   # 高可靠性文献偏离阈值
            "medium_reliability": 0.6, # 中等可靠性文献偏离阈值
            "low_reliability": 0.4     # 低可靠性文献偏离阈值
        }
    
    async def evaluate_literature_reliability(self, literature: Literature) -> Dict:
        """
        评估单个文献的可靠性
        
        Args:
            literature: 文献对象
            
        Returns:
            可靠性评估结果
        """
        try:
            # 1. 影响因子评分 (0-1)
            impact_score = self._calculate_impact_factor_score(literature.impact_factor)
            
            # 2. 引用数评分 (0-1)
            citation_score = self._calculate_citation_score(literature.citation_count)
            
            # 3. 来源可靠性评分 (0-1)
            source_score = self._calculate_source_reliability_score(literature)
            
            # 4. 发表年份评分 (0-1)
            year_score = self._calculate_publication_year_score(literature.publication_year)
            
            # 5. 计算综合可靠性评分
            reliability_score = (
                impact_score * self.reliability_weights["impact_factor"] +
                citation_score * self.reliability_weights["citation_count"] +
                source_score * self.reliability_weights["source_reliability"] +
                year_score * self.reliability_weights["publication_year"]
            )
            
            # 6. 确定可靠性等级
            reliability_level = self._determine_reliability_level(reliability_score)
            
            # 7. 更新文献记录
            literature.reliability_score = reliability_score
            literature.source_reliability = reliability_level
            
            return {
                "success": True,
                "reliability_score": reliability_score,
                "reliability_level": reliability_level,
                "components": {
                    "impact_score": impact_score,
                    "citation_score": citation_score,
                    "source_score": source_score,
                    "year_score": year_score
                }
            }
            
        except Exception as e:
            logger.error(f"评估文献可靠性失败: {e}")
            return {"success": False, "error": str(e)}
    
    def sort_literature_by_reliability(
        self, 
        literature_list: List[Literature],
        prioritize_high_reliability: bool = True
    ) -> List[Literature]:
        """
        按可靠性排序文献列表
        
        Args:
            literature_list: 文献列表
            prioritize_high_reliability: 是否优先处理高可靠性文献
            
        Returns:
            排序后的文献列表
        """
        try:
            # 确保所有文献都有可靠性评分
            for lit in literature_list:
                if lit.reliability_score is None:
                    # 如果没有可靠性评分，进行实时评估
                    asyncio.create_task(self.evaluate_literature_reliability(lit))
                    lit.reliability_score = lit.reliability_score or 0.5
            
            # 按可靠性评分排序
            if prioritize_high_reliability:
                # 高可靠性优先：按可靠性评分降序，然后按影响因子降序
                sorted_literature = sorted(
                    literature_list,
                    key=lambda x: (
                        x.reliability_score or 0.5,
                        x.impact_factor or 0.0,
                        x.citation_count or 0
                    ),
                    reverse=True
                )
            else:
                # 低可靠性优先：按可靠性评分升序
                sorted_literature = sorted(
                    literature_list,
                    key=lambda x: x.reliability_score or 0.5
                )
            
            logger.info(f"文献排序完成，共 {len(sorted_literature)} 篇文献")
            return sorted_literature
            
        except Exception as e:
            logger.error(f"文献排序失败: {e}")
            return literature_list
    
    async def calculate_experience_deviation(
        self,
        new_literature_content: str,
        existing_experience: str,
        research_domain: str
    ) -> Dict:
        """
        计算新文献内容与现有经验的偏离度
        
        Args:
            new_literature_content: 新文献内容
            existing_experience: 现有经验内容
            research_domain: 研究领域
            
        Returns:
            偏离度计算结果
        """
        try:
            # 使用AI评估偏离度
            deviation_prompt = f"""
作为科研专家，请评估新文献内容与现有经验知识的偏离程度。

研究领域: {research_domain}

现有经验知识:
{existing_experience[:1500]}

新文献内容:
{new_literature_content[:1000]}

请从以下维度评估偏离度（0-1，0表示完全一致，1表示完全偏离）：

1. 方法学偏离度：新文献提出的方法与现有经验中的方法差异程度
2. 结论偏离度：新文献的结论与现有经验结论的矛盾程度  
3. 数据偏离度：新文献的实验数据与现有经验数据的差异程度
4. 理论偏离度：新文献的理论基础与现有经验理论的冲突程度

请返回JSON格式：
{{
    "overall_deviation": 0.25,
    "methodology_deviation": 0.2,
    "conclusion_deviation": 0.3,
    "data_deviation": 0.15,
    "theory_deviation": 0.35,
    "deviation_reasons": ["具体偏离原因1", "具体偏离原因2"],
    "consistency_points": ["一致性要点1", "一致性要点2"],
    "recommendation": "merge/skip/review"
}}

推荐动作说明：
- merge: 偏离度低，可以合并
- skip: 偏离度过高，应该跳过
- review: 偏离度中等，需要人工审查
"""
            
            response = await self.ai_service.generate_completion(
                deviation_prompt,
                model="gpt-4",
                max_tokens=800,
                temperature=0.2
            )
            
            if response.get("success"):
                import json
                try:
                    deviation_result = json.loads(response["content"])
                    deviation_result["success"] = True
                    return deviation_result
                except json.JSONDecodeError:
                    logger.error("解析偏离度评估结果JSON失败")
                    return {
                        "success": False,
                        "error": "AI响应格式错误",
                        "overall_deviation": 0.5  # 默认中等偏离
                    }
            
            return {"success": False, "error": "AI评估失败"}
            
        except Exception as e:
            logger.error(f"计算经验偏离度失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "overall_deviation": 0.5
            }
    
    async def should_skip_literature(
        self,
        literature: Literature,
        deviation_result: Dict,
        reliability_threshold: float = 0.6
    ) -> Dict:
        """
        判断是否应该跳过某篇文献
        
        Args:
            literature: 文献对象
            deviation_result: 偏离度评估结果
            reliability_threshold: 可靠性阈值
            
        Returns:
            跳过判断结果
        """
        try:
            reliability_score = literature.reliability_score or 0.5
            overall_deviation = deviation_result.get("overall_deviation", 0.5)
            
            # 根据文献可靠性确定偏离度阈值
            if reliability_score >= 0.8:
                # 高可靠性文献：偏离度阈值较高
                deviation_threshold = self.deviation_thresholds["high_reliability"]
            elif reliability_score >= 0.5:
                # 中等可靠性文献：偏离度阈值中等
                deviation_threshold = self.deviation_thresholds["medium_reliability"]
            else:
                # 低可靠性文献：偏离度阈值较低
                deviation_threshold = self.deviation_thresholds["low_reliability"]
            
            # 判断是否跳过
            should_skip = False
            skip_reasons = []
            
            # 1. 低可靠性 + 高偏离度 = 跳过
            if reliability_score < reliability_threshold and overall_deviation > deviation_threshold:
                should_skip = True
                skip_reasons.append(f"低可靠性({reliability_score:.2f}) + 高偏离度({overall_deviation:.2f})")
            
            # 2. 极低影响因子 + 中高偏离度 = 跳过
            impact_factor = literature.impact_factor or 0.0
            if impact_factor < self.impact_factor_thresholds["low"] and overall_deviation > 0.5:
                should_skip = True
                skip_reasons.append(f"极低影响因子({impact_factor}) + 中高偏离度({overall_deviation:.2f})")
            
            # 3. 来源不可靠 + 高偏离度 = 跳过
            if literature.source_reliability == "low" and overall_deviation > 0.6:
                should_skip = True
                skip_reasons.append(f"不可靠来源 + 高偏离度({overall_deviation:.2f})")
            
            return {
                "should_skip": should_skip,
                "skip_reasons": skip_reasons,
                "reliability_score": reliability_score,
                "deviation_threshold": deviation_threshold,
                "overall_deviation": overall_deviation,
                "recommendation": deviation_result.get("recommendation", "review")
            }
            
        except Exception as e:
            logger.error(f"判断是否跳过文献失败: {e}")
            return {
                "should_skip": False,
                "error": str(e)
            }
    
    def _calculate_impact_factor_score(self, impact_factor: Optional[float]) -> float:
        """计算影响因子评分 (0-1)"""
        if not impact_factor or impact_factor <= 0:
            return 0.1  # 无影响因子的最低分
        
        # 使用对数缩放，避免极高影响因子主导评分
        if impact_factor >= 10:
            return 1.0
        elif impact_factor >= 5:
            return 0.8 + 0.2 * (impact_factor - 5) / 5
        elif impact_factor >= 2:
            return 0.5 + 0.3 * (impact_factor - 2) / 3
        elif impact_factor >= 0.5:
            return 0.2 + 0.3 * (impact_factor - 0.5) / 1.5
        else:
            return 0.1 + 0.1 * impact_factor / 0.5
    
    def _calculate_citation_score(self, citation_count: Optional[int]) -> float:
        """计算引用数评分 (0-1)"""
        if not citation_count or citation_count <= 0:
            return 0.1
        
        # 使用对数缩放
        if citation_count >= 1000:
            return 1.0
        elif citation_count >= 100:
            return 0.8 + 0.2 * (citation_count - 100) / 900
        elif citation_count >= 10:
            return 0.5 + 0.3 * (citation_count - 10) / 90
        else:
            return 0.1 + 0.4 * citation_count / 10
    
    def _calculate_source_reliability_score(self, literature: Literature) -> float:
        """计算来源可靠性评分 (0-1)"""
        # 基于期刊名称判断来源可靠性
        journal = (literature.journal or "").lower()
        
        # 顶级期刊列表
        top_journals = [
            "nature", "science", "cell", "nature materials", "nature nanotechnology",
            "advanced materials", "journal of the american chemical society", "angewandte chemie"
        ]
        
        # 优质期刊关键词
        quality_keywords = ["nature", "science", "advanced", "acs", "rsc", "wiley", "elsevier"]
        
        if any(top_journal in journal for top_journal in top_journals):
            return 1.0
        elif any(keyword in journal for keyword in quality_keywords):
            return 0.7
        elif journal:
            return 0.5  # 有期刊名但不在已知列表中
        else:
            return 0.3  # 无期刊信息
    
    def _calculate_publication_year_score(self, publication_year: Optional[int]) -> float:
        """计算发表年份评分 (0-1)，越新越好"""
        if not publication_year:
            return 0.5
        
        current_year = datetime.now().year
        years_ago = current_year - publication_year
        
        if years_ago <= 0:
            return 1.0  # 当年或未来
        elif years_ago <= 2:
            return 0.9  # 2年内
        elif years_ago <= 5:
            return 0.7  # 5年内
        elif years_ago <= 10:
            return 0.5  # 10年内
        else:
            return max(0.1, 0.5 - (years_ago - 10) * 0.02)  # 10年以上递减
    
    def _determine_reliability_level(self, reliability_score: float) -> str:
        """根据可靠性评分确定等级"""
        if reliability_score >= 0.8:
            return "high"
        elif reliability_score >= 0.5:
            return "medium"
        else:
            return "low"
    
    async def batch_evaluate_literature_reliability(
        self, 
        literature_list: List[Literature],
        progress_callback = None
    ) -> Dict:
        """
        批量评估文献可靠性
        
        Args:
            literature_list: 文献列表
            progress_callback: 进度回调函数
            
        Returns:
            批量评估结果
        """
        try:
            total_count = len(literature_list)
            processed_count = 0
            results = []
            
            for i, literature in enumerate(literature_list):
                result = await self.evaluate_literature_reliability(literature)
                results.append({
                    "literature_id": literature.id,
                    "title": literature.title[:100],
                    "result": result
                })
                
                processed_count += 1
                
                # 更新进度
                if progress_callback:
                    progress = (processed_count / total_count) * 100
                    await progress_callback(
                        f"评估文献可靠性: {processed_count}/{total_count}",
                        progress,
                        {"processed": processed_count, "total": total_count}
                    )
            
            # 保存到数据库
            self.db.commit()
            
            return {
                "success": True,
                "total_processed": processed_count,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"批量评估文献可靠性失败: {e}")
            return {"success": False, "error": str(e)}