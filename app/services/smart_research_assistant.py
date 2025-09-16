"""
Smart Research Assistant - AI-powered intelligent research assistant
智能科研助手 - 基于AI的智能文献研究助手
"""

import asyncio
import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import numpy as np
from collections import defaultdict, Counter

from app.core.database import get_db
from app.models.literature import Literature, LiteratureSegment
from app.models.project import Project
from app.services.multi_model_ai_service import MultiModelAIService
from app.services.literature_ai_assistant import LiteratureAIAssistant
from app.core.config import settings


class SmartResearchAssistant:
    """
    智能科研助手 - 突破性功能实现

    核心功能:
    1. 深度文献问答 - 基于多篇论文的复杂问题回答
    2. 研究假设生成 - 自动发现研究空白并生成假设
    3. 跨文献知识整合 - 整合多篇文献的知识点
    4. 智能研究建议 - 基于现有文献提供研究方向建议
    5. 实时协作问答 - 支持团队协作的智能问答
    """

    def __init__(self):
        self.ai_service = MultiModelAIService()
        self.literature_assistant = LiteratureAIAssistant()
        self.conversation_memory = {}  # 会话记忆

    async def answer_complex_research_question(
        self,
        question: str,
        project_id: int,
        user_id: int,
        context_literature_ids: List[int] = None,
        max_literature_count: int = 10
    ) -> Dict[str, Any]:
        """
        回答复杂的研究问题

        突破性功能:
        - 跨多篇文献的深度分析
        - 基于语义相似度的智能文献选择
        - 结构化的分层答案生成
        - 引用溯源和可信度评估
        """
        try:
            # 1. 智能选择相关文献
            relevant_literature = await self._select_relevant_literature(
                question, project_id, context_literature_ids, max_literature_count
            )

            if not relevant_literature:
                return {
                    "answer": "抱歉，在当前项目的文献中没有找到与您问题相关的内容。建议添加更多相关文献。",
                    "confidence": 0.0,
                    "sources": [],
                    "suggestions": ["添加更多相关文献", "尝试使用更具体的问题"]
                }

            # 2. 提取关键信息和证据
            evidence_analysis = await self._extract_evidence_from_literature(
                question, relevant_literature
            )

            # 3. 生成多层次答案
            comprehensive_answer = await self._generate_comprehensive_answer(
                question, evidence_analysis, relevant_literature
            )

            # 4. 生成研究建议和后续问题
            research_suggestions = await self._generate_research_suggestions(
                question, comprehensive_answer, evidence_analysis
            )

            # 5. 构建结构化回答
            result = {
                "question": question,
                "answer": comprehensive_answer["main_answer"],
                "detailed_analysis": comprehensive_answer["detailed_analysis"],
                "key_findings": comprehensive_answer["key_findings"],
                "confidence": comprehensive_answer["confidence"],
                "sources": self._format_sources(relevant_literature, evidence_analysis),
                "research_gaps": research_suggestions["research_gaps"],
                "next_questions": research_suggestions["next_questions"],
                "methodology_suggestions": research_suggestions["methodology_suggestions"],
                "timestamp": datetime.now().isoformat(),
                "literature_count": len(relevant_literature)
            }

            # 6. 保存对话历史
            await self._save_conversation_history(user_id, project_id, question, result)

            return result

        except Exception as e:
            logger.error(f"回答研究问题时出错: {e}")
            return {
                "error": str(e),
                "question": question,
                "answer": "处理问题时遇到技术错误，请稍后重试。",
                "confidence": 0.0
            }

    async def generate_research_hypotheses(
        self,
        project_id: int,
        research_domain: str,
        literature_scope: str = "all"  # all, recent, high_impact
    ) -> Dict[str, Any]:
        """
        自动生成研究假设

        突破性功能:
        - 基于文献空白的自动假设生成
        - 跨学科知识整合
        - 创新性评估和可行性分析
        - 实验设计建议
        """
        try:
            # 1. 分析项目文献的研究现状
            literature_analysis = await self._analyze_literature_landscape(
                project_id, research_domain, literature_scope
            )

            # 2. 识别研究空白和矛盾
            research_gaps = await self._identify_research_gaps(
                literature_analysis, research_domain
            )

            # 3. 生成创新性假设
            hypotheses = await self._generate_innovative_hypotheses(
                research_gaps, literature_analysis, research_domain
            )

            # 4. 评估假设的可行性和创新性
            evaluated_hypotheses = await self._evaluate_hypotheses(
                hypotheses, literature_analysis
            )

            # 5. 生成实验设计建议
            experimental_designs = await self._suggest_experimental_designs(
                evaluated_hypotheses, research_domain
            )

            return {
                "research_domain": research_domain,
                "literature_summary": literature_analysis["summary"],
                "identified_gaps": research_gaps,
                "generated_hypotheses": evaluated_hypotheses,
                "experimental_designs": experimental_designs,
                "innovation_opportunities": literature_analysis["innovation_opportunities"],
                "collaboration_suggestions": literature_analysis["collaboration_opportunities"],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"生成研究假设时出错: {e}")
            return {"error": str(e)}

    async def create_intelligent_literature_summary(
        self,
        project_id: int,
        summary_type: str = "comprehensive",  # comprehensive, methodology, findings, trends
        grouping_method: str = "thematic"  # thematic, chronological, methodology
    ) -> Dict[str, Any]:
        """
        创建智能文献综述

        突破性功能:
        - 自动主题聚类和组织
        - 多维度分析(方法、发现、趋势)
        - 智能引用网络分析
        - 自动生成综述结构
        """
        try:
            db = next(get_db())

            # 1. 获取项目所有文献
            literature_list = db.query(Literature).filter(
                Literature.projects.any(id=project_id)
            ).all()

            if not literature_list:
                return {"error": "项目中没有文献数据"}

            # 2. 基于嵌入向量进行主题聚类
            thematic_clusters = await self._cluster_literature_by_themes(literature_list)

            # 3. 分析研究方法和技术演进
            methodology_evolution = await self._analyze_methodology_evolution(literature_list)

            # 4. 识别关键发现和趋势
            key_findings_trends = await self._identify_key_findings_and_trends(literature_list)

            # 5. 构建引用网络分析
            citation_network = await self._build_citation_network_analysis(literature_list)

            # 6. 生成结构化综述
            structured_summary = await self._generate_structured_summary(
                thematic_clusters,
                methodology_evolution,
                key_findings_trends,
                citation_network,
                summary_type,
                grouping_method
            )

            return {
                "summary_type": summary_type,
                "grouping_method": grouping_method,
                "literature_count": len(literature_list),
                "thematic_clusters": thematic_clusters,
                "methodology_evolution": methodology_evolution,
                "key_findings": key_findings_trends,
                "citation_analysis": citation_network,
                "structured_summary": structured_summary,
                "research_timeline": await self._create_research_timeline(literature_list),
                "collaboration_network": await self._analyze_collaboration_patterns(literature_list),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"创建文献综述时出错: {e}")
            return {"error": str(e)}

    async def analyze_research_trends(
        self,
        project_id: int,
        time_window: str = "5_years",  # 1_year, 3_years, 5_years, all
        trend_aspects: List[str] = None  # keywords, methods, collaborations, citations
    ) -> Dict[str, Any]:
        """
        分析研究趋势

        突破性功能:
        - 多维度趋势分析
        - 新兴技术识别
        - 研究热点预测
        - 协作网络演化
        """
        if trend_aspects is None:
            trend_aspects = ["keywords", "methods", "collaborations", "citations"]

        try:
            # 1. 获取时间窗口内的文献
            literature_list = await self._get_literature_by_time_window(project_id, time_window)

            trend_analysis = {}

            # 2. 关键词趋势分析
            if "keywords" in trend_aspects:
                trend_analysis["keyword_trends"] = await self._analyze_keyword_trends(literature_list)

            # 3. 研究方法趋势
            if "methods" in trend_aspects:
                trend_analysis["methodology_trends"] = await self._analyze_methodology_trends(literature_list)

            # 4. 协作网络趋势
            if "collaborations" in trend_aspects:
                trend_analysis["collaboration_trends"] = await self._analyze_collaboration_trends(literature_list)

            # 5. 引用网络趋势
            if "citations" in trend_aspects:
                trend_analysis["citation_trends"] = await self._analyze_citation_trends(literature_list)

            # 6. 预测未来趋势
            future_predictions = await self._predict_future_trends(trend_analysis, literature_list)

            return {
                "time_window": time_window,
                "literature_count": len(literature_list),
                "trend_analysis": trend_analysis,
                "emerging_topics": await self._identify_emerging_topics(literature_list),
                "declining_topics": await self._identify_declining_topics(literature_list),
                "future_predictions": future_predictions,
                "innovation_opportunities": await self._identify_innovation_opportunities(trend_analysis),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"分析研究趋势时出错: {e}")
            return {"error": str(e)}

    # =============== 私有辅助方法 ===============

    async def _select_relevant_literature(
        self,
        question: str,
        project_id: int,
        context_literature_ids: List[int] = None,
        max_count: int = 10
    ) -> List[Literature]:
        """使用语义相似度选择相关文献"""
        try:
            db = next(get_db())

            # 生成问题的嵌入向量
            question_embedding = await self.ai_service.generate_embedding(question)

            if context_literature_ids:
                # 使用指定的文献
                literature_query = db.query(Literature).filter(
                    Literature.id.in_(context_literature_ids)
                )
            else:
                # 使用项目中的所有文献
                literature_query = db.query(Literature).filter(
                    Literature.projects.any(id=project_id)
                )

            literature_list = literature_query.all()

            # 计算相似度并排序
            literature_scores = []
            for lit in literature_list:
                if lit.title_embedding and lit.abstract_embedding:
                    # 计算标题和摘要的相似度
                    title_sim = self._cosine_similarity(question_embedding, lit.title_embedding)
                    abstract_sim = self._cosine_similarity(question_embedding, lit.abstract_embedding)

                    # 综合相似度分数
                    total_sim = (title_sim * 0.3 + abstract_sim * 0.7)
                    literature_scores.append((lit, total_sim))

            # 按相似度排序并返回前N个
            literature_scores.sort(key=lambda x: x[1], reverse=True)
            return [lit for lit, score in literature_scores[:max_count]]

        except Exception as e:
            logger.error(f"选择相关文献时出错: {e}")
            return []

    async def _extract_evidence_from_literature(
        self,
        question: str,
        literature_list: List[Literature]
    ) -> Dict[str, Any]:
        """从文献中提取相关证据"""
        evidence = {
            "direct_answers": [],
            "supporting_evidence": [],
            "contradictory_evidence": [],
            "methodological_insights": [],
            "confidence_scores": {}
        }

        for literature in literature_list:
            try:
                # 使用AI提取相关信息
                extraction_prompt = f"""
                基于以下问题分析这篇文献:
                问题: {question}

                文献标题: {literature.title}
                摘要: {literature.abstract}

                请提取:
                1. 直接回答问题的信息
                2. 支持性证据
                3. 矛盾性证据
                4. 相关的研究方法
                5. 置信度评估(0-1)

                以JSON格式返回结果。
                """

                response = await self.ai_service.chat_completion(
                    [{"role": "user", "content": extraction_prompt}],
                    temperature=0.3
                )

                if response and response.get("choices"):
                    content = response["choices"][0]["message"]["content"]
                    try:
                        extracted_data = json.loads(content)

                        # 整合提取的证据
                        if "direct_answers" in extracted_data:
                            evidence["direct_answers"].extend(extracted_data["direct_answers"])
                        if "supporting_evidence" in extracted_data:
                            evidence["supporting_evidence"].extend(extracted_data["supporting_evidence"])
                        if "contradictory_evidence" in extracted_data:
                            evidence["contradictory_evidence"].extend(extracted_data["contradictory_evidence"])
                        if "methodological_insights" in extracted_data:
                            evidence["methodological_insights"].extend(extracted_data["methodological_insights"])

                        # 记录置信度
                        confidence = extracted_data.get("confidence", 0.5)
                        evidence["confidence_scores"][literature.id] = confidence

                    except json.JSONDecodeError:
                        logger.warning(f"无法解析文献{literature.id}的提取结果")

            except Exception as e:
                logger.error(f"从文献{literature.id}提取证据时出错: {e}")
                continue

        return evidence

    async def _generate_comprehensive_answer(
        self,
        question: str,
        evidence: Dict[str, Any],
        literature_list: List[Literature]
    ) -> Dict[str, Any]:
        """生成综合性答案"""
        try:
            # 构建综合分析提示
            analysis_prompt = f"""
            作为一个专业的科研助手，请基于以下证据回答研究问题:

            问题: {question}

            直接证据: {json.dumps(evidence["direct_answers"], ensure_ascii=False)}
            支持性证据: {json.dumps(evidence["supporting_evidence"], ensure_ascii=False)}
            矛盾性证据: {json.dumps(evidence["contradictory_evidence"], ensure_ascii=False)}
            方法学见解: {json.dumps(evidence["methodological_insights"], ensure_ascii=False)}

            基于{len(literature_list)}篇文献，请提供:
            1. 主要答案 (简洁明确)
            2. 详细分析 (包含各种观点和证据)
            3. 关键发现 (要点总结)
            4. 置信度评估 (0-1)

            请以JSON格式返回，确保答案科学严谨。
            """

            response = await self.ai_service.chat_completion(
                [{"role": "user", "content": analysis_prompt}],
                temperature=0.2
            )

            if response and response.get("choices"):
                content = response["choices"][0]["message"]["content"]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # 如果JSON解析失败，返回原始文本
                    return {
                        "main_answer": content,
                        "detailed_analysis": content,
                        "key_findings": [],
                        "confidence": 0.7
                    }

            return {
                "main_answer": "抱歉，无法生成答案。",
                "detailed_analysis": "处理过程中遇到技术问题。",
                "key_findings": [],
                "confidence": 0.0
            }

        except Exception as e:
            logger.error(f"生成综合答案时出错: {e}")
            return {
                "main_answer": f"生成答案时出错: {str(e)}",
                "detailed_analysis": "",
                "key_findings": [],
                "confidence": 0.0
            }

    async def _generate_research_suggestions(
        self,
        question: str,
        answer: Dict[str, Any],
        evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成研究建议和后续问题"""
        try:
            suggestion_prompt = f"""
            基于刚才的问题和回答，请提供研究建议:

            原问题: {question}
            主要答案: {answer.get("main_answer", "")}

            请提供:
            1. 研究空白 (当前研究未覆盖的领域)
            2. 后续问题 (值得进一步探索的问题)
            3. 方法学建议 (建议的研究方法和技术)

            以JSON格式返回。
            """

            response = await self.ai_service.chat_completion(
                [{"role": "user", "content": suggestion_prompt}],
                temperature=0.4
            )

            if response and response.get("choices"):
                content = response["choices"][0]["message"]["content"]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {
                        "research_gaps": ["需要更多研究"],
                        "next_questions": ["如何深入这个问题？"],
                        "methodology_suggestions": ["建议使用更多文献"]
                    }

            return {
                "research_gaps": [],
                "next_questions": [],
                "methodology_suggestions": []
            }

        except Exception as e:
            logger.error(f"生成研究建议时出错: {e}")
            return {
                "research_gaps": [],
                "next_questions": [],
                "methodology_suggestions": []
            }

    def _format_sources(
        self,
        literature_list: List[Literature],
        evidence: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """格式化文献来源"""
        sources = []
        for lit in literature_list:
            confidence = evidence["confidence_scores"].get(lit.id, 0.5)
            sources.append({
                "id": lit.id,
                "title": lit.title,
                "authors": lit.authors,
                "year": lit.publication_year,
                "journal": lit.journal,
                "doi": lit.doi,
                "confidence": confidence,
                "relevance": "high" if confidence > 0.7 else "medium" if confidence > 0.4 else "low"
            })

        # 按置信度排序
        sources.sort(key=lambda x: x["confidence"], reverse=True)
        return sources

    async def _save_conversation_history(
        self,
        user_id: int,
        project_id: int,
        question: str,
        result: Dict[str, Any]
    ):
        """保存对话历史"""
        try:
            # 这里可以保存到数据库或缓存中
            conversation_key = f"user_{user_id}_project_{project_id}"
            if conversation_key not in self.conversation_memory:
                self.conversation_memory[conversation_key] = []

            self.conversation_memory[conversation_key].append({
                "timestamp": datetime.now().isoformat(),
                "question": question,
                "answer": result,
                "type": "research_question"
            })

            # 保持最近50条记录
            if len(self.conversation_memory[conversation_key]) > 50:
                self.conversation_memory[conversation_key] = self.conversation_memory[conversation_key][-50:]

        except Exception as e:
            logger.error(f"保存对话历史时出错: {e}")

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        try:
            a_np = np.array(a)
            b_np = np.array(b)
            return np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np))
        except:
            return 0.0

    # =============== 其他分析方法的占位符 ===============
    # 这些方法将在后续实现中完善

    async def _analyze_literature_landscape(self, project_id: int, domain: str, scope: str):
        """分析文献全景"""
        return {"summary": "文献分析结果", "innovation_opportunities": [], "collaboration_opportunities": []}

    async def _identify_research_gaps(self, analysis: Dict, domain: str):
        """识别研究空白"""
        return ["空白1", "空白2"]

    async def _generate_innovative_hypotheses(self, gaps: List, analysis: Dict, domain: str):
        """生成创新假设"""
        return ["假设1", "假设2"]

    async def _evaluate_hypotheses(self, hypotheses: List, analysis: Dict):
        """评估假设"""
        return [{"hypothesis": h, "feasibility": 0.8, "innovation": 0.7} for h in hypotheses]

    async def _suggest_experimental_designs(self, hypotheses: List, domain: str):
        """建议实验设计"""
        return ["设计1", "设计2"]

    async def _cluster_literature_by_themes(self, literature: List):
        """按主题聚类文献"""
        return {"cluster_1": {"theme": "主题1", "papers": []}}

    async def _analyze_methodology_evolution(self, literature: List):
        """分析方法学演进"""
        return {"evolution": "方法演进分析"}

    async def _identify_key_findings_and_trends(self, literature: List):
        """识别关键发现和趋势"""
        return {"findings": [], "trends": []}

    async def _build_citation_network_analysis(self, literature: List):
        """构建引用网络分析"""
        return {"network": "引用网络"}

    async def _generate_structured_summary(self, clusters, evolution, findings, network, summary_type, grouping):
        """生成结构化综述"""
        return {"summary": "结构化综述"}

    async def _create_research_timeline(self, literature: List):
        """创建研究时间线"""
        return {"timeline": "研究时间线"}

    async def _analyze_collaboration_patterns(self, literature: List):
        """分析协作模式"""
        return {"patterns": "协作模式"}

    async def _get_literature_by_time_window(self, project_id: int, time_window: str):
        """按时间窗口获取文献"""
        return []

    async def _analyze_keyword_trends(self, literature: List):
        """分析关键词趋势"""
        return {"trends": "关键词趋势"}

    async def _analyze_methodology_trends(self, literature: List):
        """分析方法趋势"""
        return {"trends": "方法趋势"}

    async def _analyze_collaboration_trends(self, literature: List):
        """分析协作趋势"""
        return {"trends": "协作趋势"}

    async def _analyze_citation_trends(self, literature: List):
        """分析引用趋势"""
        return {"trends": "引用趋势"}

    async def _predict_future_trends(self, analysis: Dict, literature: List):
        """预测未来趋势"""
        return {"predictions": "未来趋势预测"}

    async def _identify_emerging_topics(self, literature: List):
        """识别新兴主题"""
        return ["新兴主题1", "新兴主题2"]

    async def _identify_declining_topics(self, literature: List):
        """识别衰落主题"""
        return ["衰落主题1", "衰落主题2"]

    async def _identify_innovation_opportunities(self, analysis: Dict):
        """识别创新机会"""
        return ["创新机会1", "创新机会2"]


# 创建全局实例
smart_research_assistant = SmartResearchAssistant()