"""
文献轻结构化数据库系统 - AI对话助手模块
提供全流程智能引导和交互支持
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio
import json
from pydantic import BaseModel
from enum import Enum


class TaskStage(Enum):
    """任务阶段枚举"""
    RESEARCH_DIRECTION = "research_direction"
    LITERATURE_COLLECTION = "literature_collection"
    LIGHTWEIGHT_STRUCTURING = "lightweight_structuring"
    EXPERIENCE_ENHANCEMENT = "experience_enhancement"
    SOLUTION_GENERATION = "solution_generation"


class UserLevel(Enum):
    """用户专业水平枚举"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class InteractionRequest(BaseModel):
    """AI交互请求模型"""
    user_id: str
    session_id: str
    stage: TaskStage
    message: str
    context: Dict[str, Any] = {}
    user_level: Optional[UserLevel] = None


class InteractionResponse(BaseModel):
    """AI交互响应模型"""
    response: str
    suggestions: List[str] = []
    next_actions: List[Dict[str, Any]] = []
    confidence_score: float = 0.0
    requires_confirmation: bool = False
    estimated_time: Optional[int] = None  # 预估时间（分钟）


class ResearchDirectionGuide:
    """研究方向智能引导模块"""
    
    def __init__(self):
        self.domain_keywords = {
            "材料科学": {
                "纳米材料": ["纳米颗粒", "纳米管", "纳米片", "量子点"],
                "电池材料": ["锂电池", "钠电池", "固态电池", "电解质"],
                "催化材料": ["光催化", "电催化", "异相催化", "单原子催化"],
                "复合材料": ["纤维复合", "金属基复合", "陶瓷基复合", "聚合物基复合"]
            },
            "化学": {
                "有机化学": ["有机合成", "药物化学", "天然产物", "有机催化"],
                "无机化学": ["配位化学", "固体化学", "材料化学", "生物无机化学"],
                "分析化学": ["光谱分析", "色谱分析", "电化学分析", "质谱分析"],
                "物理化学": ["表面化学", "胶体化学", "电化学", "热化学"]
            }
        }
    
    async def analyze_research_direction(self, user_input: str, uploaded_files: List[str] = None) -> Dict[str, Any]:
        """分析用户研究方向"""
        # 模拟AI分析过程
        await asyncio.sleep(0.1)
        
        analysis = {
            "identified_keywords": [],
            "suggested_refinements": [],
            "related_fields": [],
            "confidence": 0.8
        }
        
        # 简单关键词匹配（实际应用中会使用更复杂的NLP模型）
        for domain, categories in self.domain_keywords.items():
            for category, keywords in categories.items():
                for keyword in keywords:
                    if keyword.lower() in user_input.lower():
                        analysis["identified_keywords"].append({
                            "keyword": keyword,
                            "domain": domain,
                            "category": category
                        })
        
        # 生成细化建议
        if analysis["identified_keywords"]:
            refinements = []
            for kw in analysis["identified_keywords"][:2]:
                refinements.append(f"建议明确具体的{kw['keyword']}类型")
                refinements.append(f"可以考虑{kw['category']}领域的交叉研究")
            analysis["suggested_refinements"] = refinements
        
        return analysis
    
    async def generate_keyword_strategy(self, research_focus: str) -> Dict[str, Any]:
        """生成关键词搜索策略"""
        await asyncio.sleep(0.1)
        
        return {
            "primary_keywords": [research_focus],
            "secondary_keywords": ["synthesis", "characterization", "application"],
            "search_combinations": [
                f"{research_focus} synthesis",
                f"{research_focus} characterization",
                f"{research_focus} properties"
            ],
            "estimated_papers": 2500,
            "recommended_filters": ["recent_5_years", "high_impact"]
        }


class LiteratureQualityAssessor:
    """文献质量评估模块"""
    
    async def assess_literature_quality(self, literature_batch: List[Dict]) -> Dict[str, Any]:
        """评估文献质量"""
        await asyncio.sleep(0.2)
        
        total_papers = len(literature_batch)
        high_quality = int(total_papers * 0.3)
        medium_quality = int(total_papers * 0.5)
        low_quality = total_papers - high_quality - medium_quality
        
        return {
            "total_papers": total_papers,
            "quality_distribution": {
                "high": high_quality,
                "medium": medium_quality,
                "low": low_quality
            },
            "average_citation": 15.6,
            "recent_papers_ratio": 0.7,
            "top_journals_ratio": 0.4,
            "recommendation": "建议保留高质量和中等质量文献，过滤低质量文献"
        }
    
    async def predict_collection_outcome(self, keywords: List[str]) -> Dict[str, Any]:
        """预测采集结果"""
        await asyncio.sleep(0.1)
        
        return {
            "estimated_total": 3200,
            "estimated_relevant": 2400,
            "estimated_high_quality": 720,
            "estimated_time_minutes": 25,
            "confidence": 0.85,
            "potential_issues": [
                "部分关键词可能过于宽泛",
                "建议增加时间范围限制"
            ]
        }


class StructuringFormatOptimizer:
    """轻结构化格式优化模块"""
    
    def __init__(self):
        self.domain_templates = {
            "材料科学": {
                "制备与表征": ["原料准备", "制备方法", "工艺参数", "表征技术", "性能测试"],
                "应用研究": ["应用场景", "性能指标", "对比分析", "优化策略"],
                "机理研究": ["反应机理", "计算模拟", "理论分析", "验证实验"]
            },
            "化学": {
                "合成研究": ["合成路线", "反应条件", "产率优化", "产物分离"],
                "分析表征": ["结构确认", "纯度分析", "性质测定", "稳定性研究"],
                "机理探索": ["反应机理", "动力学研究", "热力学分析", "计算化学"]
            }
        }
    
    async def generate_structure_template(self, domain: str, literature_sample: List[Dict]) -> Dict[str, Any]:
        """生成结构化模板"""
        await asyncio.sleep(0.1)
        
        template = self.domain_templates.get(domain, self.domain_templates["材料科学"])
        
        return {
            "template_structure": template,
            "customization_suggestions": [
                "可根据具体研究内容调整二级分类",
                "建议增加'实验条件'子类别",
                "可考虑添加'结果讨论'板块"
            ],
            "adaptation_confidence": 0.9,
            "estimated_extraction_time": 45
        }
    
    async def evaluate_structure_fitness(self, structure: Dict, sample_papers: List[Dict]) -> Dict[str, Any]:
        """评估结构适配性"""
        await asyncio.sleep(0.1)
        
        return {
            "fitness_score": 0.87,
            "coverage_analysis": {
                "well_covered": ["制备方法", "表征技术"],
                "partially_covered": ["性能测试"],
                "missing_coverage": ["成本分析"]
            },
            "optimization_suggestions": [
                "建议在'制备方法'下增加'设备要求'子类",
                "可考虑添加'商业化前景'分析板块"
            ]
        }


class ExperienceEnhancementMonitor:
    """经验增强迭代监控模块"""
    
    async def monitor_iteration_quality(self, iteration_data: Dict) -> Dict[str, Any]:
        """监控迭代质量"""
        await asyncio.sleep(0.1)
        
        current_round = iteration_data.get("current_round", 1)
        content_size = iteration_data.get("content_size", 1000)
        
        return {
            "current_round": current_round,
            "quality_score": min(0.6 + current_round * 0.1, 0.95),
            "content_growth_rate": max(0.15 - current_round * 0.02, 0.03),
            "estimated_remaining_rounds": max(8 - current_round, 0),
            "stop_recommendation": current_round >= 3 and (0.15 - current_round * 0.02) < 0.05,
            "improvement_areas": [
                "机理解释部分可进一步完善",
                "实验参数优化建议需要更具体"
            ]
        }
    
    async def predict_final_quality(self, current_state: Dict) -> Dict[str, Any]:
        """预测最终质量"""
        await asyncio.sleep(0.1)
        
        return {
            "predicted_final_score": 0.92,
            "estimated_completion_time": 35,
            "expected_improvements": [
                "知识覆盖度将提升至95%",
                "实用性评分预计达到4.5/5",
                "专家认可度预计超过90%"
            ],
            "confidence": 0.88
        }


class LiteratureAIAssistant:
    """文献AI助手主控制器"""
    
    def __init__(self):
        self.research_guide = ResearchDirectionGuide()
        self.quality_assessor = LiteratureQualityAssessor()
        self.format_optimizer = StructuringFormatOptimizer()
        self.enhancement_monitor = ExperienceEnhancementMonitor()
        self.user_sessions = {}  # 存储用户会话状态
    
    async def handle_interaction(self, request: InteractionRequest) -> InteractionResponse:
        """处理用户交互请求"""
        
        # 更新用户会话状态
        if request.session_id not in self.user_sessions:
            self.user_sessions[request.session_id] = {
                "start_time": datetime.now(),
                "stage_history": [],
                "user_level": request.user_level or UserLevel.INTERMEDIATE,
                "context": {}
            }
        
        session = self.user_sessions[request.session_id]
        session["context"].update(request.context)
        
        # 根据不同阶段处理请求
        if request.stage == TaskStage.RESEARCH_DIRECTION:
            return await self._handle_research_direction(request, session)
        elif request.stage == TaskStage.LITERATURE_COLLECTION:
            return await self._handle_literature_collection(request, session)
        elif request.stage == TaskStage.LIGHTWEIGHT_STRUCTURING:
            return await self._handle_structuring(request, session)
        elif request.stage == TaskStage.EXPERIENCE_ENHANCEMENT:
            return await self._handle_enhancement(request, session)
        elif request.stage == TaskStage.SOLUTION_GENERATION:
            return await self._handle_solution_generation(request, session)
        else:
            return InteractionResponse(
                response="抱歉，我无法处理这个阶段的请求。",
                confidence_score=0.0
            )
    
    async def _handle_research_direction(self, request: InteractionRequest, session: Dict) -> InteractionResponse:
        """处理研究方向确定阶段"""
        
        # 分析研究方向
        analysis = await self.research_guide.analyze_research_direction(request.message)
        
        if analysis["confidence"] < 0.5:
            return InteractionResponse(
                response="我需要更多信息来理解您的研究方向。能否详细描述一下您的研究目标？",
                suggestions=[
                    "请描述具体的研究对象（如材料、化合物等）",
                    "请说明研究的主要目的（如制备、表征、应用等）",
                    "可以上传相关的项目书或申请书"
                ],
                requires_confirmation=False,
                confidence_score=analysis["confidence"]
            )
        
        # 生成关键词策略
        if analysis["identified_keywords"]:
            main_keyword = analysis["identified_keywords"][0]["keyword"]
            keyword_strategy = await self.research_guide.generate_keyword_strategy(main_keyword)
            
            response = f"我理解您的研究方向是关于{main_keyword}。基于分析，我为您生成了以下搜索策略：\n\n"
            response += f"• 主要关键词：{', '.join(keyword_strategy['primary_keywords'])}\n"
            response += f"• 辅助关键词：{', '.join(keyword_strategy['secondary_keywords'])}\n"
            response += f"• 预估可获取文献数量：{keyword_strategy['estimated_papers']}篇\n\n"
            response += "您觉得这个策略合适吗？我们可以根据需要进行调整。"
            
            return InteractionResponse(
                response=response,
                suggestions=analysis["suggested_refinements"],
                next_actions=[
                    {"action": "confirm_strategy", "label": "确认搜索策略"},
                    {"action": "refine_keywords", "label": "调整关键词"},
                    {"action": "upload_documents", "label": "上传参考文档"}
                ],
                requires_confirmation=True,
                estimated_time=30,
                confidence_score=analysis["confidence"]
            )
        
        return InteractionResponse(
            response="请提供更具体的研究信息，以便我为您制定合适的文献搜索策略。",
            confidence_score=0.3
        )
    
    async def _handle_literature_collection(self, request: InteractionRequest, session: Dict) -> InteractionResponse:
        """处理文献采集阶段"""
        
        if "confirm_collection" in request.message.lower():
            # 预测采集结果
            keywords = session["context"].get("keywords", ["default"])
            prediction = await self.quality_assessor.predict_collection_outcome(keywords)
            
            response = f"文献采集预测结果：\n\n"
            response += f"• 预计总文献数：{prediction['estimated_total']}篇\n"
            response += f"• 预计相关文献：{prediction['estimated_relevant']}篇\n"
            response += f"• 预计高质量文献：{prediction['estimated_high_quality']}篇\n"
            response += f"• 预计采集时间：{prediction['estimated_time_minutes']}分钟\n\n"
            
            if prediction['potential_issues']:
                response += "潜在问题提醒：\n"
                for issue in prediction['potential_issues']:
                    response += f"• {issue}\n"
            
            return InteractionResponse(
                response=response,
                next_actions=[
                    {"action": "start_collection", "label": "开始采集"},
                    {"action": "adjust_strategy", "label": "调整策略"}
                ],
                estimated_time=prediction['estimated_time_minutes'],
                confidence_score=prediction['confidence']
            )
        
        # 模拟文献质量评估
        mock_literature = [{"title": f"Paper {i}", "citations": i*10} for i in range(100)]
        quality_assessment = await self.quality_assessor.assess_literature_quality(mock_literature)
        
        response = f"文献质量评估完成：\n\n"
        response += f"• 总文献数：{quality_assessment['total_papers']}篇\n"
        response += f"• 高质量文献：{quality_assessment['quality_distribution']['high']}篇\n"
        response += f"• 中等质量文献：{quality_assessment['quality_distribution']['medium']}篇\n"
        response += f"• 平均引用次数：{quality_assessment['average_citation']}\n\n"
        response += f"建议：{quality_assessment['recommendation']}"
        
        return InteractionResponse(
            response=response,
            next_actions=[
                {"action": "proceed_structuring", "label": "进入结构化处理"},
                {"action": "adjust_filters", "label": "调整筛选条件"}
            ],
            confidence_score=0.85
        )
    
    async def _handle_structuring(self, request: InteractionRequest, session: Dict) -> InteractionResponse:
        """处理轻结构化阶段"""
        
        domain = session["context"].get("domain", "材料科学")
        mock_papers = [{"title": "Sample paper", "abstract": "Sample abstract"}]
        
        # 生成结构化模板
        template = await self.format_optimizer.generate_structure_template(domain, mock_papers)
        
        response = f"为您生成了适合{domain}领域的结构化模板：\n\n"
        for category, subcategories in template["template_structure"].items():
            response += f"📁 {category}\n"
            for sub in subcategories:
                response += f"  └─ {sub}\n"
        
        response += f"\n适配置信度：{template['adaptation_confidence']:.0%}\n"
        response += f"预估处理时间：{template['estimated_extraction_time']}分钟"
        
        return InteractionResponse(
            response=response,
            suggestions=template["customization_suggestions"],
            next_actions=[
                {"action": "confirm_template", "label": "确认模板"},
                {"action": "customize_template", "label": "自定义调整"},
                {"action": "preview_extraction", "label": "预览提取效果"}
            ],
            estimated_time=template["estimated_extraction_time"],
            confidence_score=template["adaptation_confidence"]
        )
    
    async def _handle_enhancement(self, request: InteractionRequest, session: Dict) -> InteractionResponse:
        """处理经验增强阶段"""
        
        current_round = session["context"].get("enhancement_round", 1)
        mock_iteration_data = {
            "current_round": current_round,
            "content_size": 1000 + current_round * 200
        }
        
        quality_monitor = await self.enhancement_monitor.monitor_iteration_quality(mock_iteration_data)
        
        response = f"经验增强迭代监控 - 第{current_round}轮：\n\n"
        response += f"• 当前质量评分：{quality_monitor['quality_score']:.0%}\n"
        response += f"• 内容增长率：{quality_monitor['content_growth_rate']:.0%}\n"
        response += f"• 预计剩余轮次：{quality_monitor['estimated_remaining_rounds']}轮\n\n"
        
        if quality_monitor['stop_recommendation']:
            response += "🎯 建议停止迭代：增量收益已低于阈值\n"
            
            # 预测最终质量
            final_prediction = await self.enhancement_monitor.predict_final_quality(mock_iteration_data)
            response += f"\n最终质量预测：{final_prediction['predicted_final_score']:.0%}"
            
            return InteractionResponse(
                response=response,
                next_actions=[
                    {"action": "stop_iteration", "label": "停止迭代"},
                    {"action": "continue_iteration", "label": "继续1轮"},
                    {"action": "view_experience_book", "label": "查看经验书"}
                ],
                confidence_score=0.9
            )
        else:
            if quality_monitor['improvement_areas']:
                response += "改进建议：\n"
                for area in quality_monitor['improvement_areas']:
                    response += f"• {area}\n"
            
            return InteractionResponse(
                response=response,
                next_actions=[
                    {"action": "continue_iteration", "label": "继续下一轮"},
                    {"action": "view_current_progress", "label": "查看当前进度"}
                ],
                estimated_time=15,
                confidence_score=quality_monitor['quality_score']
            )
    
    async def _handle_solution_generation(self, request: InteractionRequest, session: Dict) -> InteractionResponse:
        """处理方案生成阶段"""
        
        user_question = request.message
        
        response = f"基于您的问题：「{user_question}」\n\n"
        response += "我已从经验库中检索到相关信息，正在为您生成解决方案...\n\n"
        response += "💡 解决方案建议：\n"
        response += "1. 优化制备工艺参数（温度、时间、压力）\n"
        response += "2. 改进原料预处理方法\n"
        response += "3. 引入新型添加剂或催化剂\n\n"
        response += "📊 可行性评估：高（85%）\n"
        response += "⏱️ 预计实验周期：2-3周\n"
        response += "💰 预估成本：中等"
        
        return InteractionResponse(
            response=response,
            suggestions=[
                "需要更详细的实验方案吗？",
                "要查看相关文献支撑吗？",
                "需要风险评估报告吗？"
            ],
            next_actions=[
                {"action": "detailed_protocol", "label": "获取详细实验方案"},
                {"action": "view_references", "label": "查看参考文献"},
                {"action": "risk_assessment", "label": "风险评估"},
                {"action": "export_report", "label": "导出完整报告"}
            ],
            confidence_score=0.85
        )
    
    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        if session_id not in self.user_sessions:
            return {"error": "Session not found"}
        
        session = self.user_sessions[session_id]
        return {
            "session_id": session_id,
            "start_time": session["start_time"].isoformat(),
            "current_stage": session.get("current_stage"),
            "user_level": session["user_level"].value,
            "progress": session.get("progress", 0),
            "context_keys": list(session["context"].keys())
        }


# 全局AI助手实例
ai_assistant = LiteratureAIAssistant()