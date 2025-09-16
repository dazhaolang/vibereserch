"""
智能质量控制系统
实现多维度质量评估、实时监控和智能优化建议
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import json
import numpy as np
from pydantic import BaseModel
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """质量评估指标枚举"""
    RELEVANCE = "relevance"  # 相关性
    COMPLETENESS = "completeness"  # 完整性
    ACCURACY = "accuracy"  # 准确性
    CONSISTENCY = "consistency"  # 一致性
    TIMELINESS = "timeliness"  # 时效性
    USABILITY = "usability"  # 可用性


class QualityLevel(Enum):
    """质量等级枚举"""
    EXCELLENT = "excellent"  # 优秀 (90-100%)
    GOOD = "good"  # 良好 (80-89%)
    FAIR = "fair"  # 一般 (70-79%)
    POOR = "poor"  # 较差 (60-69%)
    UNACCEPTABLE = "unacceptable"  # 不可接受 (<60%)


class QualityAssessment(BaseModel):
    """质量评估结果模型"""
    overall_score: float
    metric_scores: Dict[str, float]
    quality_level: QualityLevel
    issues: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    confidence: float = 0.0
    timestamp: datetime = datetime.now()


class LiteratureQualityAnalyzer:
    """文献质量分析器"""
    
    def __init__(self):
        self.quality_weights = {
            QualityMetric.RELEVANCE: 0.25,
            QualityMetric.COMPLETENESS: 0.20,
            QualityMetric.ACCURACY: 0.20,
            QualityMetric.CONSISTENCY: 0.15,
            QualityMetric.TIMELINESS: 0.10,
            QualityMetric.USABILITY: 0.10
        }
    
    async def analyze_literature_batch(self, literature_data: List[Dict]) -> QualityAssessment:
        """分析文献批次质量"""
        
        if not literature_data:
            return QualityAssessment(
                overall_score=0.0,
                metric_scores={},
                quality_level=QualityLevel.UNACCEPTABLE,
                issues=[{"type": "empty_data", "message": "文献数据为空"}]
            )
        
        # 并行分析各项指标
        tasks = [
            self._analyze_relevance(literature_data),
            self._analyze_completeness(literature_data),
            self._analyze_accuracy(literature_data),
            self._analyze_consistency(literature_data),
            self._analyze_timeliness(literature_data),
            self._analyze_usability(literature_data)
        ]
        
        results = await asyncio.gather(*tasks)
        
        metric_scores = {
            QualityMetric.RELEVANCE.value: results[0],
            QualityMetric.COMPLETENESS.value: results[1],
            QualityMetric.ACCURACY.value: results[2],
            QualityMetric.CONSISTENCY.value: results[3],
            QualityMetric.TIMELINESS.value: results[4],
            QualityMetric.USABILITY.value: results[5]
        }
        
        # 计算总体评分
        overall_score = sum(
            score * self.quality_weights[QualityMetric(metric)]
            for metric, score in metric_scores.items()
        )
        
        # 确定质量等级
        quality_level = self._determine_quality_level(overall_score)
        
        # 生成问题和建议
        issues = self._identify_issues(metric_scores)
        recommendations = self._generate_recommendations(metric_scores, issues)
        
        return QualityAssessment(
            overall_score=overall_score,
            metric_scores=metric_scores,
            quality_level=quality_level,
            issues=issues,
            recommendations=recommendations,
            confidence=0.85
        )
    
    async def _analyze_relevance(self, literature_data: List[Dict]) -> float:
        """分析相关性"""
        await asyncio.sleep(0.1)  # 模拟分析时间
        
        # 模拟相关性分析逻辑
        relevant_count = 0
        total_count = len(literature_data)
        
        for paper in literature_data:
            title = paper.get("title", "").lower()
            abstract = paper.get("abstract", "").lower()
            
            # 简单的相关性检查（实际应用中会使用更复杂的NLP模型）
            if any(keyword in title + abstract for keyword in ["synthesis", "characterization", "nanomaterial"]):
                relevant_count += 1
        
        return min(relevant_count / total_count * 100, 100) if total_count > 0 else 0
    
    async def _analyze_completeness(self, literature_data: List[Dict]) -> float:
        """分析完整性"""
        await asyncio.sleep(0.1)
        
        required_fields = ["title", "authors", "journal", "year", "abstract"]
        completeness_scores = []
        
        for paper in literature_data:
            present_fields = sum(1 for field in required_fields if paper.get(field))
            completeness = (present_fields / len(required_fields)) * 100
            completeness_scores.append(completeness)
        
        return np.mean(completeness_scores) if completeness_scores else 0
    
    async def _analyze_accuracy(self, literature_data: List[Dict]) -> float:
        """分析准确性"""
        await asyncio.sleep(0.1)
        
        # 模拟准确性检查
        accurate_count = 0
        total_count = len(literature_data)
        
        for paper in literature_data:
            # 检查年份格式
            year = paper.get("year")
            if year and isinstance(year, int) and 1900 <= year <= datetime.now().year:
                accurate_count += 0.3
            
            # 检查DOI格式
            doi = paper.get("doi", "")
            if doi and ("10." in doi):
                accurate_count += 0.3
            
            # 检查作者信息
            authors = paper.get("authors", [])
            if authors and len(authors) > 0:
                accurate_count += 0.4
        
        return min(accurate_count / total_count * 100, 100) if total_count > 0 else 0
    
    async def _analyze_consistency(self, literature_data: List[Dict]) -> float:
        """分析一致性"""
        await asyncio.sleep(0.1)
        
        # 检查数据格式一致性
        field_consistency = {}
        
        for paper in literature_data:
            for field, value in paper.items():
                if field not in field_consistency:
                    field_consistency[field] = type(value)
                elif field_consistency[field] != type(value):
                    field_consistency[field] = "inconsistent"
        
        consistent_fields = sum(1 for t in field_consistency.values() if t != "inconsistent")
        total_fields = len(field_consistency)
        
        return (consistent_fields / total_fields * 100) if total_fields > 0 else 100
    
    async def _analyze_timeliness(self, literature_data: List[Dict]) -> float:
        """分析时效性"""
        await asyncio.sleep(0.1)
        
        current_year = datetime.now().year
        recent_papers = 0
        total_papers = 0
        
        for paper in literature_data:
            year = paper.get("year")
            if year and isinstance(year, int):
                total_papers += 1
                if current_year - year <= 5:  # 5年内的文献
                    recent_papers += 1
        
        return (recent_papers / total_papers * 100) if total_papers > 0 else 0
    
    async def _analyze_usability(self, literature_data: List[Dict]) -> float:
        """分析可用性"""
        await asyncio.sleep(0.1)
        
        usable_count = 0
        total_count = len(literature_data)
        
        for paper in literature_data:
            usability_score = 0
            
            # 有摘要
            if paper.get("abstract"):
                usability_score += 0.3
            
            # 有完整引用信息
            if paper.get("journal") and paper.get("year"):
                usability_score += 0.3
            
            # 有DOI或URL
            if paper.get("doi") or paper.get("url"):
                usability_score += 0.2
            
            # 有关键词
            if paper.get("keywords"):
                usability_score += 0.2
            
            usable_count += usability_score
        
        return min(usable_count / total_count * 100, 100) if total_count > 0 else 0
    
    def _determine_quality_level(self, score: float) -> QualityLevel:
        """确定质量等级"""
        if score >= 90:
            return QualityLevel.EXCELLENT
        elif score >= 80:
            return QualityLevel.GOOD
        elif score >= 70:
            return QualityLevel.FAIR
        elif score >= 60:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNACCEPTABLE
    
    def _identify_issues(self, metric_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        """识别质量问题"""
        issues = []
        
        for metric, score in metric_scores.items():
            if score < 60:
                issues.append({
                    "type": "low_quality",
                    "metric": metric,
                    "score": score,
                    "severity": "high",
                    "message": f"{metric}评分过低 ({score:.1f}%)"
                })
            elif score < 80:
                issues.append({
                    "type": "medium_quality",
                    "metric": metric,
                    "score": score,
                    "severity": "medium",
                    "message": f"{metric}评分需要改进 ({score:.1f}%)"
                })
        
        return issues
    
    def _generate_recommendations(self, metric_scores: Dict[str, float], issues: List[Dict]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        for issue in issues:
            metric = issue["metric"]
            
            if metric == "relevance":
                recommendations.append("建议调整关键词搜索策略，提高文献相关性")
            elif metric == "completeness":
                recommendations.append("建议补充缺失的文献元数据信息")
            elif metric == "accuracy":
                recommendations.append("建议验证和清理不准确的数据字段")
            elif metric == "consistency":
                recommendations.append("建议统一数据格式，确保字段一致性")
            elif metric == "timeliness":
                recommendations.append("建议增加近期文献的比例")
            elif metric == "usability":
                recommendations.append("建议提高文献的可访问性和完整性")
        
        # 添加通用建议
        overall_score = sum(metric_scores.values()) / len(metric_scores)
        if overall_score < 70:
            recommendations.append("建议重新评估文献采集策略")
        
        return list(set(recommendations))  # 去重


class StructuringQualityMonitor:
    """结构化质量监控器"""
    
    async def monitor_structuring_process(self, 
                                        structured_data: List[Dict], 
                                        original_papers: List[Dict]) -> QualityAssessment:
        """监控结构化过程质量"""
        
        # 并行分析各项指标
        tasks = [
            self._analyze_extraction_completeness(structured_data, original_papers),
            self._analyze_structure_consistency(structured_data),
            self._analyze_content_accuracy(structured_data, original_papers),
            self._analyze_format_compliance(structured_data)
        ]
        
        results = await asyncio.gather(*tasks)
        
        metric_scores = {
            "extraction_completeness": results[0],
            "structure_consistency": results[1],
            "content_accuracy": results[2],
            "format_compliance": results[3]
        }
        
        overall_score = np.mean(list(metric_scores.values()))
        quality_level = self._determine_quality_level(overall_score)
        
        issues = []
        recommendations = []
        
        # 基于评分生成问题和建议
        for metric, score in metric_scores.items():
            if score < 70:
                issues.append({
                    "type": "structuring_issue",
                    "metric": metric,
                    "score": score,
                    "severity": "high" if score < 60 else "medium"
                })
        
        if issues:
            recommendations.extend([
                "建议检查结构化模板的适配性",
                "建议优化提取算法的准确性",
                "建议增加人工审核环节"
            ])
        
        return QualityAssessment(
            overall_score=overall_score,
            metric_scores=metric_scores,
            quality_level=quality_level,
            issues=issues,
            recommendations=recommendations,
            confidence=0.8
        )
    
    async def _analyze_extraction_completeness(self, structured_data: List[Dict], original_papers: List[Dict]) -> float:
        """分析提取完整性"""
        await asyncio.sleep(0.1)
        
        if not original_papers:
            return 0
        
        extraction_rate = len(structured_data) / len(original_papers)
        return min(extraction_rate * 100, 100)
    
    async def _analyze_structure_consistency(self, structured_data: List[Dict]) -> float:
        """分析结构一致性"""
        await asyncio.sleep(0.1)
        
        if not structured_data:
            return 0
        
        # 检查所有条目是否具有相同的结构
        first_item_keys = set(structured_data[0].keys()) if structured_data else set()
        consistent_count = 0
        
        for item in structured_data:
            if set(item.keys()) == first_item_keys:
                consistent_count += 1
        
        return (consistent_count / len(structured_data) * 100) if structured_data else 0
    
    async def _analyze_content_accuracy(self, structured_data: List[Dict], original_papers: List[Dict]) -> float:
        """分析内容准确性"""
        await asyncio.sleep(0.1)
        
        # 模拟内容准确性检查
        # 实际应用中会使用更复杂的文本相似度算法
        return 85.0  # 模拟值
    
    async def _analyze_format_compliance(self, structured_data: List[Dict]) -> float:
        """分析格式合规性"""
        await asyncio.sleep(0.1)
        
        if not structured_data:
            return 0
        
        compliant_count = 0
        required_sections = ["preparation", "characterization", "application"]
        
        for item in structured_data:
            compliance_score = 0
            for section in required_sections:
                if section in item and item[section]:
                    compliance_score += 1
            
            if compliance_score == len(required_sections):
                compliant_count += 1
        
        return (compliant_count / len(structured_data) * 100) if structured_data else 0
    
    def _determine_quality_level(self, score: float) -> QualityLevel:
        """确定质量等级"""
        if score >= 90:
            return QualityLevel.EXCELLENT
        elif score >= 80:
            return QualityLevel.GOOD
        elif score >= 70:
            return QualityLevel.FAIR
        elif score >= 60:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNACCEPTABLE


class ExperienceQualityTracker:
    """经验质量跟踪器"""
    
    def __init__(self):
        self.iteration_history = []
    
    async def track_iteration_quality(self, 
                                    iteration_round: int, 
                                    experience_content: str,
                                    source_papers: List[Dict]) -> QualityAssessment:
        """跟踪迭代质量"""
        
        # 分析当前迭代的质量
        tasks = [
            self._analyze_content_richness(experience_content),
            self._analyze_knowledge_coverage(experience_content, source_papers),
            self._analyze_logical_coherence(experience_content),
            self._analyze_practical_value(experience_content)
        ]
        
        results = await asyncio.gather(*tasks)
        
        metric_scores = {
            "content_richness": results[0],
            "knowledge_coverage": results[1],
            "logical_coherence": results[2],
            "practical_value": results[3]
        }
        
        overall_score = np.mean(list(metric_scores.values()))
        
        # 记录历史
        iteration_data = {
            "round": iteration_round,
            "score": overall_score,
            "metrics": metric_scores,
            "timestamp": datetime.now(),
            "content_length": len(experience_content)
        }
        self.iteration_history.append(iteration_data)
        
        # 分析改进趋势
        improvement_rate = self._calculate_improvement_rate()
        stop_recommendation = self._should_stop_iteration(improvement_rate, iteration_round)
        
        quality_level = self._determine_quality_level(overall_score)
        
        recommendations = []
        if stop_recommendation:
            recommendations.append("建议停止迭代：质量改进已达到收敛状态")
        else:
            recommendations.extend([
                "可继续迭代以进一步提升质量",
                "建议关注实用性和逻辑连贯性的提升"
            ])
        
        return QualityAssessment(
            overall_score=overall_score,
            metric_scores=metric_scores,
            quality_level=quality_level,
            recommendations=recommendations,
            confidence=0.9
        )
    
    async def _analyze_content_richness(self, content: str) -> float:
        """分析内容丰富度"""
        await asyncio.sleep(0.1)
        
        # 简单的内容丰富度分析
        word_count = len(content.split())
        sentence_count = content.count('。') + content.count('.')
        
        # 基于长度和结构复杂度评分
        richness_score = min((word_count / 1000) * 50 + (sentence_count / 50) * 50, 100)
        return richness_score
    
    async def _analyze_knowledge_coverage(self, content: str, source_papers: List[Dict]) -> float:
        """分析知识覆盖度"""
        await asyncio.sleep(0.1)
        
        # 模拟知识覆盖度分析
        # 实际应用中会分析内容是否涵盖了源文献的主要知识点
        coverage_keywords = ["synthesis", "characterization", "application", "mechanism", "optimization"]
        covered_count = sum(1 for keyword in coverage_keywords if keyword in content.lower())
        
        return (covered_count / len(coverage_keywords)) * 100
    
    async def _analyze_logical_coherence(self, content: str) -> float:
        """分析逻辑连贯性"""
        await asyncio.sleep(0.1)
        
        # 简单的逻辑连贯性检查
        # 实际应用中会使用更复杂的NLP模型
        coherence_indicators = ["因此", "所以", "由于", "然而", "此外", "另外", "综上"]
        indicator_count = sum(content.count(indicator) for indicator in coherence_indicators)
        
        # 基于连接词密度评估逻辑性
        word_count = len(content.split())
        coherence_score = min((indicator_count / word_count) * 1000, 100) if word_count > 0 else 0
        
        return max(coherence_score, 70)  # 设置最低分数
    
    async def _analyze_practical_value(self, content: str) -> float:
        """分析实用价值"""
        await asyncio.sleep(0.1)
        
        # 检查实用性指标
        practical_keywords = ["参数", "条件", "方法", "步骤", "建议", "注意", "优化"]
        practical_count = sum(content.count(keyword) for keyword in practical_keywords)
        
        # 基于实用性关键词密度评分
        word_count = len(content.split())
        practical_score = min((practical_count / word_count) * 500, 100) if word_count > 0 else 0
        
        return max(practical_score, 60)  # 设置最低分数
    
    def _calculate_improvement_rate(self) -> float:
        """计算改进率"""
        if len(self.iteration_history) < 2:
            return 100  # 初始迭代，改进率设为最大
        
        recent_scores = [item["score"] for item in self.iteration_history[-3:]]
        if len(recent_scores) < 2:
            return 100
        
        # 计算最近几轮的平均改进率
        improvements = []
        for i in range(1, len(recent_scores)):
            improvement = recent_scores[i] - recent_scores[i-1]
            improvements.append(improvement)
        
        return np.mean(improvements) if improvements else 0
    
    def _should_stop_iteration(self, improvement_rate: float, current_round: int) -> bool:
        """判断是否应该停止迭代"""
        # 连续3轮改进率小于5%，或者已经进行了10轮以上
        return improvement_rate < 5.0 and current_round >= 3 or current_round >= 10
    
    def _determine_quality_level(self, score: float) -> QualityLevel:
        """确定质量等级"""
        if score >= 90:
            return QualityLevel.EXCELLENT
        elif score >= 80:
            return QualityLevel.GOOD
        elif score >= 70:
            return QualityLevel.FAIR
        elif score >= 60:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNACCEPTABLE


class QualityControlSystem:
    """质量控制系统主控制器"""
    
    def __init__(self):
        self.literature_analyzer = LiteratureQualityAnalyzer()
        self.structuring_monitor = StructuringQualityMonitor()
        self.experience_tracker = ExperienceQualityTracker()
        self.quality_history = {}  # 存储历史质量数据
    
    async def assess_literature_quality(self, 
                                      literature_data: List[Dict], 
                                      session_id: str) -> QualityAssessment:
        """评估文献质量"""
        
        assessment = await self.literature_analyzer.analyze_literature_batch(literature_data)
        
        # 记录质量历史
        if session_id not in self.quality_history:
            self.quality_history[session_id] = []
        
        self.quality_history[session_id].append({
            "stage": "literature_collection",
            "assessment": assessment,
            "timestamp": datetime.now()
        })
        
        logger.info(f"Literature quality assessment completed for session {session_id}: {assessment.overall_score:.1f}%")
        
        return assessment
    
    async def monitor_structuring_quality(self, 
                                        structured_data: List[Dict], 
                                        original_papers: List[Dict],
                                        session_id: str) -> QualityAssessment:
        """监控结构化质量"""
        
        assessment = await self.structuring_monitor.monitor_structuring_process(
            structured_data, original_papers
        )
        
        # 记录质量历史
        if session_id not in self.quality_history:
            self.quality_history[session_id] = []
        
        self.quality_history[session_id].append({
            "stage": "structuring",
            "assessment": assessment,
            "timestamp": datetime.now()
        })
        
        logger.info(f"Structuring quality assessment completed for session {session_id}: {assessment.overall_score:.1f}%")
        
        return assessment
    
    async def track_experience_quality(self, 
                                     iteration_round: int,
                                     experience_content: str,
                                     source_papers: List[Dict],
                                     session_id: str) -> QualityAssessment:
        """跟踪经验质量"""
        
        assessment = await self.experience_tracker.track_iteration_quality(
            iteration_round, experience_content, source_papers
        )
        
        # 记录质量历史
        if session_id not in self.quality_history:
            self.quality_history[session_id] = []
        
        self.quality_history[session_id].append({
            "stage": "experience_enhancement",
            "round": iteration_round,
            "assessment": assessment,
            "timestamp": datetime.now()
        })
        
        logger.info(f"Experience quality tracking completed for session {session_id}, round {iteration_round}: {assessment.overall_score:.1f}%")
        
        return assessment
    
    async def generate_quality_report(self, session_id: str) -> Dict[str, Any]:
        """生成质量报告"""
        
        if session_id not in self.quality_history:
            return {"error": "No quality data found for session"}
        
        history = self.quality_history[session_id]
        
        # 统计各阶段质量
        stage_quality = {}
        for record in history:
            stage = record["stage"]
            if stage not in stage_quality:
                stage_quality[stage] = []
            stage_quality[stage].append(record["assessment"].overall_score)
        
        # 计算总体趋势
        overall_scores = [record["assessment"].overall_score for record in history]
        quality_trend = "improving" if len(overall_scores) > 1 and overall_scores[-1] > overall_scores[0] else "stable"
        
        # 收集所有建议
        all_recommendations = []
        for record in history:
            all_recommendations.extend(record["assessment"].recommendations)
        
        # 去重并保留最重要的建议
        unique_recommendations = list(set(all_recommendations))[:10]
        
        return {
            "session_id": session_id,
            "overall_quality_trend": quality_trend,
            "stage_quality_summary": {
                stage: {
                    "average_score": np.mean(scores),
                    "latest_score": scores[-1] if scores else 0,
                    "improvement": scores[-1] - scores[0] if len(scores) > 1 else 0
                }
                for stage, scores in stage_quality.items()
            },
            "key_recommendations": unique_recommendations,
            "total_assessments": len(history),
            "report_generated_at": datetime.now().isoformat()
        }
    
    async def get_real_time_quality_metrics(self, session_id: str) -> Dict[str, Any]:
        """获取实时质量指标"""
        
        if session_id not in self.quality_history:
            return {"error": "No quality data found for session"}
        
        recent_assessments = self.quality_history[session_id][-5:]  # 最近5次评估
        
        if not recent_assessments:
            return {"error": "No recent assessments found"}
        
        latest_assessment = recent_assessments[-1]["assessment"]
        
        # 计算质量趋势
        if len(recent_assessments) > 1:
            scores = [a["assessment"].overall_score for a in recent_assessments]
            trend_slope = np.polyfit(range(len(scores)), scores, 1)[0]
            trend = "improving" if trend_slope > 1 else "declining" if trend_slope < -1 else "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "current_quality_score": latest_assessment.overall_score,
            "quality_level": latest_assessment.quality_level.value,
            "quality_trend": trend,
            "active_issues": len(latest_assessment.issues),
            "pending_recommendations": len(latest_assessment.recommendations),
            "confidence": latest_assessment.confidence,
            "last_updated": latest_assessment.timestamp.isoformat()
        }


# 全局质量控制系统实例
quality_control_system = QualityControlSystem()