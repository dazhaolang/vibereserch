"""
智能交互引擎 - 核心服务类
实现类似天工Skywork的智能澄清机制
"""

import uuid
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.interaction import InteractionSession, ClarificationCard, InteractionAnalytics
from app.models.project import Project
from app.models.user import User
from app.services.ai_service import AIService
from app.services.multi_model_ai_service import MultiModelAIService
from app.core.exceptions import ApplicationError

logger = logging.getLogger(__name__)


class IntentAnalysis:
    """意图分析结果"""
    def __init__(self, user_input: str, intent_confidence: float, ambiguity_score: float,
                 clarification_needed: bool, extracted_entities: Dict,
                 suggested_clarifications: List[str], ai_reasoning: str):
        self.user_input = user_input
        self.intent_confidence = intent_confidence
        self.ambiguity_score = ambiguity_score
        self.clarification_needed = clarification_needed
        self.extracted_entities = extracted_entities
        self.suggested_clarifications = suggested_clarifications
        self.ai_reasoning = ai_reasoning


class ClarificationOption:
    """澄清选项数据结构"""
    def __init__(self, option_id: str, title: str, description: str,
                 icon: Optional[str] = None, estimated_time: Optional[str] = None,
                 estimated_results: Optional[str] = None, confidence_score: float = 0.0,
                 implications: List[str] = None, is_recommended: bool = False,
                 metadata: Dict = None):
        self.option_id = option_id
        self.title = title
        self.description = description
        self.icon = icon
        self.estimated_time = estimated_time
        self.estimated_results = estimated_results
        self.confidence_score = confidence_score
        self.implications = implications or []
        self.is_recommended = is_recommended
        self.metadata = metadata or {}

    def to_dict(self) -> Dict:
        return {
            "option_id": self.option_id,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "estimated_time": self.estimated_time,
            "estimated_results": self.estimated_results,
            "confidence_score": self.confidence_score,
            "implications": self.implications,
            "is_recommended": self.is_recommended,
            "metadata": self.metadata
        }


class IntelligentInteractionEngine:
    """智能交互引擎 - 类似天工Skywork的澄清机制"""

    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.multi_model_service = MultiModelAIService()

    async def analyze_user_intent(
        self,
        user_input: str,
        context: Dict,
        project: Project
    ) -> IntentAnalysis:
        """分析用户意图，判断是否需要澄清"""
        try:
            # 构建意图分析提示词
            analysis_prompt = self._build_intent_analysis_prompt(
                user_input, context, project
            )

            # 使用AI服务分析用户意图
            analysis_result = await self.ai_service.generate_response(
                prompt=analysis_prompt,
                temperature=0.3,  # 较低温度确保分析稳定性
                max_tokens=800
            )

            # 解析AI分析结果
            parsed_result = self._parse_intent_analysis(analysis_result)

            return IntentAnalysis(
                user_input=user_input,
                intent_confidence=parsed_result.get("intent_confidence", 0.0),
                ambiguity_score=parsed_result.get("ambiguity_score", 0.0),
                clarification_needed=parsed_result.get("clarification_needed", False),
                extracted_entities=parsed_result.get("extracted_entities", {}),
                suggested_clarifications=parsed_result.get("suggested_clarifications", []),
                ai_reasoning=parsed_result.get("ai_reasoning", "")
            )

        except Exception as e:
            logger.error(f"意图分析失败: {e}")
            # 降级处理：如果AI服务失败，默认需要澄清
            return IntentAnalysis(
                user_input=user_input,
                intent_confidence=0.3,
                ambiguity_score=0.8,
                clarification_needed=True,
                extracted_entities={},
                suggested_clarifications=["请提供更多详细信息"],
                ai_reasoning="AI服务暂时不可用，建议澄清用户需求"
            )

    async def generate_clarification_options(
        self,
        intent: IntentAnalysis,
        context: Dict,
        stage: str  # search/structuring/experience
    ) -> List[ClarificationOption]:
        """AI动态生成澄清选择项"""
        try:
            # 构建选项生成提示词
            generation_prompt = self._build_option_generation_prompt(
                intent, context, stage
            )

            # 使用AI生成选择项
            options_result = await self.ai_service.generate_response(
                prompt=generation_prompt,
                temperature=0.7,  # 适中温度，平衡创造性和稳定性
                max_tokens=1200
            )

            # 解析生成的选项
            parsed_options = self._parse_generated_options(options_result)

            # 创建ClarificationOption对象
            clarification_options = []
            for i, option_data in enumerate(parsed_options):
                option = ClarificationOption(
                    option_id=f"option_{uuid.uuid4().hex[:8]}",
                    title=option_data.get("title", f"选项 {i+1}"),
                    description=option_data.get("description", ""),
                    icon=option_data.get("icon"),
                    estimated_time=option_data.get("estimated_time"),
                    estimated_results=option_data.get("estimated_results"),
                    confidence_score=option_data.get("confidence_score", 0.0),
                    implications=option_data.get("implications", []),
                    is_recommended=option_data.get("is_recommended", False),
                    metadata=option_data.get("metadata", {})
                )
                clarification_options.append(option)

            # 确保至少有一个推荐选项
            if clarification_options and not any(opt.is_recommended for opt in clarification_options):
                clarification_options[0].is_recommended = True

            return clarification_options

        except Exception as e:
            logger.error(f"选项生成失败: {e}")
            # 降级处理：返回预设的通用选项
            return self._get_fallback_options(stage)

    async def handle_user_selection(
        self,
        session_id: str,
        selection: Dict
    ) -> Dict:
        """处理用户选择或超时自动选择"""
        try:
            # 获取交互会话
            session = self.db.query(InteractionSession).filter(
                InteractionSession.session_id == session_id,
                InteractionSession.is_active == True
            ).first()

            if not session:
                raise ApplicationError("INTERACTION_3001", "交互会话不存在或已结束")

            # 获取当前澄清卡片
            current_card = self.db.query(ClarificationCard).filter(
                ClarificationCard.session_id == session_id,
                ClarificationCard.resolved_at.is_(None)
            ).first()

            if not current_card:
                raise ApplicationError("INTERACTION_3002", "没有待处理的澄清卡片")

            # 记录用户选择
            selection_data = {
                "option_id": selection.get("option_id"),
                "selection_type": selection.get("selection_type", "manual"),
                "custom_input": selection.get("custom_input"),
                "selection_time": datetime.utcnow().isoformat(),
                "client_timestamp": selection.get("client_timestamp")
            }

            # 更新澄清卡片
            current_card.user_selection = selection_data
            current_card.resolved_at = datetime.utcnow()
            current_card.resolution_type = selection.get("selection_type", "selection")
            current_card.is_auto_selected = selection.get("selection_type") == "auto"

            # 更新会话历史
            session.interaction_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "action": "user_selection",
                "data": selection_data,
                "card_id": current_card.card_id
            })

            # 记录分析数据
            analytics = InteractionAnalytics(
                session_id=session_id,
                user_id=session.user_id,
                event_type="select",
                event_data=selection_data,
                response_time_ms=self._calculate_response_time(current_card, selection),
                user_confidence=selection.get("selection_confidence")
            )
            self.db.add(analytics)

            # 判断是否需要下一轮澄清
            next_action = await self._determine_next_action(session, current_card, selection_data)

            self.db.commit()

            return {
                "success": True,
                "next_action": next_action["action"],
                "next_clarification_card": next_action.get("clarification_card"),
                "workflow_result": next_action.get("workflow_result"),
                "progress_update": next_action.get("progress_update")
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"处理用户选择失败: {e}")
            raise ApplicationError("INTERACTION_3003", f"处理选择失败: {str(e)}")

    async def create_interaction_session(
        self,
        user_id: int,
        project_id: int,
        context_type: str,
        user_input: str,
        additional_context: Dict = None
    ) -> Dict:
        """创建智能交互会话"""
        additional_context = additional_context or {}

        try:
            # 创建新会话
            session = InteractionSession(
                user_id=user_id,
                project_id=project_id,
                context_type=context_type,
                current_stage="initial_analysis",
                user_preferences=additional_context.get("user_preferences", {}),
                expires_at=datetime.utcnow() + timedelta(hours=2)  # 2小时会话超时
            )
            self.db.add(session)
            self.db.flush()  # 获取session_id

            # 获取项目信息
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ApplicationError("INTERACTION_3004", "项目不存在")

            # 分析用户意图
            intent = await self.analyze_user_intent(
                user_input,
                additional_context,
                project
            )

            # 如果需要澄清，生成澄清卡片
            if intent.clarification_needed:
                clarification_options = await self.generate_clarification_options(
                    intent, additional_context, context_type
                )

                # 创建澄清卡片
                clarification_card = ClarificationCard(
                    session_id=session.session_id,
                    stage="initial_clarification",
                    question=self._generate_clarification_question(intent, context_type),
                    options=[opt.to_dict() for opt in clarification_options],
                    recommended_option_id=next(
                        (opt.option_id for opt in clarification_options if opt.is_recommended),
                        clarification_options[0].option_id if clarification_options else None
                    ),
                    ai_generation_prompt=user_input,
                    generation_confidence=intent.intent_confidence,
                    context=additional_context
                )
                self.db.add(clarification_card)

                self.db.commit()

                self._schedule_auto_timeout(session.session_id, clarification_card)

                return {
                    "success": True,
                    "session_id": session.session_id,
                    "requires_clarification": True,
                    "clarification_card": {
                        "session_id": session.session_id,
                        "stage": clarification_card.stage,
                        "question": clarification_card.question,
                        "options": clarification_card.options,
                        "recommended_option_id": clarification_card.recommended_option_id,
                        "timeout_seconds": clarification_card.timeout_seconds,
                        "custom_input_allowed": clarification_card.custom_input_allowed,
                        "context": clarification_card.context,
                        "created_at": clarification_card.created_at.isoformat()
                    }
                }
            else:
                # 不需要澄清，直接执行工作流
                self.db.commit()
                workflow_result = await self._execute_direct_workflow(session, intent, user_input)

                return {
                    "success": True,
                    "session_id": session.session_id,
                    "requires_clarification": False,
                    "direct_result": workflow_result
                }

        except Exception as e:
            self.db.rollback()
            logger.error(f"创建交互会话失败: {e}")
            raise ApplicationError("INTERACTION_3005", f"创建会话失败: {str(e)}")

    def _build_intent_analysis_prompt(self, user_input: str, context: Dict, project: Project) -> str:
        """构建意图分析提示词"""
        return f"""
作为科研文献智能分析专家，请分析用户的输入意图。

用户输入: "{user_input}"
项目背景: {project.title} - {project.description}
研究领域: {getattr(project, 'research_domain', '未指定')}
上下文信息: {json.dumps(context, ensure_ascii=False)}

请分析以下几个方面：
1. 用户意图的明确性程度 (0-1评分)
2. 输入的模糊度评分 (0-1评分，越高越模糊)
3. 是否需要进一步澄清 (true/false)
4. 提取的关键实体 (关键词、领域、参数等)
5. 建议的澄清方向
6. AI推理过程

请以JSON格式返回结果：
{{
    "intent_confidence": 0.0-1.0,
    "ambiguity_score": 0.0-1.0,
    "clarification_needed": boolean,
    "extracted_entities": {{
        "keywords": ["关键词1", "关键词2"],
        "domain": "研究领域",
        "parameters": {{"参数名": "参数值"}}
    }},
    "suggested_clarifications": ["澄清方向1", "澄清方向2"],
    "ai_reasoning": "详细推理过程"
}}
"""

    def _build_option_generation_prompt(self, intent: IntentAnalysis, context: Dict, stage: str) -> str:
        """构建选项生成提示词"""
        stage_descriptions = {
            "search": "文献搜索和收集",
            "structuring": "结构化数据处理",
            "experience": "经验生成和知识提炼"
        }

        return f"""
作为科研文献智能助手，请为"{stage_descriptions.get(stage, stage)}"场景生成澄清选择项。

用户原始输入: "{intent.user_input}"
意图分析结果: 置信度{intent.intent_confidence}, 模糊度{intent.ambiguity_score}
提取的实体: {json.dumps(intent.extracted_entities, ensure_ascii=False)}
澄清方向: {intent.suggested_clarifications}

请生成3-5个具体的选择项，每个选项应该：
1. 针对用户的具体需求场景
2. 提供明确的处理方向
3. 包含预期结果和时间估计
4. 标注推荐程度和置信度

请以JSON格式返回：
[
    {{
        "title": "选项标题",
        "description": "详细描述处理方式和目标",
        "icon": "图标名称(可选)",
        "estimated_time": "预估处理时间",
        "estimated_results": "预期结果描述",
        "confidence_score": 0.0-1.0,
        "implications": ["选择此项的影响1", "影响2"],
        "is_recommended": boolean,
        "metadata": {{"additional_info": "额外信息"}}
    }}
]
"""

    def _parse_intent_analysis(self, analysis_result: str) -> Dict:
        """解析AI意图分析结果"""
        try:
            # 尝试解析JSON
            if analysis_result.strip().startswith('{'):
                return json.loads(analysis_result)
            else:
                # 如果不是JSON格式，尝试提取关键信息
                return {
                    "intent_confidence": 0.5,
                    "ambiguity_score": 0.7,
                    "clarification_needed": True,
                    "extracted_entities": {},
                    "suggested_clarifications": ["请提供更多详细信息"],
                    "ai_reasoning": analysis_result
                }
        except json.JSONDecodeError:
            logger.warning(f"无法解析AI分析结果: {analysis_result}")
            return {
                "intent_confidence": 0.3,
                "ambiguity_score": 0.8,
                "clarification_needed": True,
                "extracted_entities": {},
                "suggested_clarifications": ["请明确您的具体需求"],
                "ai_reasoning": "解析失败，建议澄清"
            }

    def _parse_generated_options(self, options_result: str) -> List[Dict]:
        """解析AI生成的选项"""
        try:
            # 尝试解析JSON数组
            if options_result.strip().startswith('['):
                return json.loads(options_result)
            elif options_result.strip().startswith('{'):
                # 单个对象，包装成数组
                return [json.loads(options_result)]
            else:
                # 非JSON格式，返回默认选项
                return []
        except json.JSONDecodeError:
            logger.warning(f"无法解析AI生成选项: {options_result}")
            return []

    def _get_fallback_options(self, stage: str) -> List[ClarificationOption]:
        """获取降级处理的预设选项"""
        fallback_options = {
            "search": [
                ClarificationOption(
                    option_id="fallback_search_1",
                    title="标准文献搜索",
                    description="执行常规的文献搜索和筛选",
                    estimated_time="5-10分钟",
                    estimated_results="50-200篇相关文献",
                    is_recommended=True
                ),
                ClarificationOption(
                    option_id="fallback_search_2",
                    title="深度专业搜索",
                    description="使用专业数据库进行深度搜索",
                    estimated_time="10-15分钟",
                    estimated_results="20-100篇高质量文献"
                )
            ],
            "structuring": [
                ClarificationOption(
                    option_id="fallback_struct_1",
                    title="标准结构化处理",
                    description="使用通用模板进行结构化提取",
                    estimated_time="3-5分钟",
                    is_recommended=True
                )
            ],
            "experience": [
                ClarificationOption(
                    option_id="fallback_exp_1",
                    title="标准经验生成",
                    description="基于现有文献生成通用经验",
                    estimated_time="5-8分钟",
                    is_recommended=True
                )
            ]
        }
        return fallback_options.get(stage, [])

    def _generate_clarification_question(self, intent: IntentAnalysis, context_type: str) -> str:
        """生成澄清问题"""
        context_questions = {
            "search": f"关于\"{intent.user_input}\"的文献搜索，您希望我如何处理？",
            "structuring": f"对于\"{intent.user_input}\"的结构化处理，请选择处理方式：",
            "experience": f"基于\"{intent.user_input}\"，您希望生成什么类型的经验？"
        }
        return context_questions.get(context_type, f"关于\"{intent.user_input}\"，请选择最符合您需求的处理方式：")

    async def _determine_next_action(self, session: InteractionSession, card: ClarificationCard, selection: Dict) -> Dict:
        """确定下一步操作"""
        # 根据选择结果决定是否需要继续澄清或执行工作流
        if selection.get("option_id") and not selection.get("custom_input"):
            # 用户选择了选项，执行相应的工作流
            return {
                "action": "complete_interaction",
                "workflow_result": {"message": "开始执行您选择的工作流..."}
            }
        elif selection.get("custom_input"):
            # 用户提供了自定义输入，可能需要进一步澄清
            return {
                "action": "continue_workflow",
                "workflow_result": {"message": "基于您的自定义输入开始处理..."}
            }
        else:
            # 超时自动选择
            return {
                "action": "complete_interaction",
                "workflow_result": {"message": "使用推荐选项开始处理..."}
            }

    def _schedule_auto_timeout(self, session_id: str, card: ClarificationCard) -> None:
        """在超时阈值到达时自动选择推荐选项"""
        try:
            from app.tasks.celery_tasks import auto_select_clarification_card
        except Exception as scheduling_error:
            logger.warning(f"自动澄清超时任务调度失败: {scheduling_error}")
            return

        timeout_seconds = max(0, card.timeout_seconds or 0)
        if timeout_seconds <= 0:
            return

        has_option = bool(card.recommended_option_id)
        if not has_option:
            for option in card.options or []:
                if option.get("option_id"):
                    has_option = True
                    break
        if not has_option:
            logger.info(
                "跳过自动超时处理，澄清卡片缺少可用选项 | session=%s card=%s",
                session_id,
                card.card_id,
            )
            return

        countdown = max(1, timeout_seconds)
        auto_select_clarification_card.apply_async(
            args=[session_id, card.card_id],
            countdown=countdown,
        )

    async def _execute_direct_workflow(self, session: InteractionSession, intent: IntentAnalysis, user_input: str) -> Dict:
        """直接执行工作流（不需要澄清的情况）"""
        return {
            "message": "意图明确，直接开始处理",
            "workflow_type": session.context_type,
            "processing_status": "started"
        }

    def _calculate_response_time(self, card: ClarificationCard, selection: Dict) -> Optional[int]:
        """计算用户响应时间"""
        try:
            if selection.get("client_timestamp"):
                client_time = datetime.fromisoformat(selection["client_timestamp"].replace('Z', '+00:00'))
                response_time = (client_time - card.created_at).total_seconds() * 1000
                return int(response_time)
        except:
            pass
        return None

    async def analyze_query(
        self,
        query: str,
        project_id: int,
        context: Dict = None
    ) -> Dict[str, Any]:
        """
        分析查询问题，进行拆解和模式推荐
        用于替换前端mock数据
        """
        try:
            # 获取项目信息
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"项目不存在: {project_id}")

            # 构建问题分析提示词
            analysis_prompt = f"""
作为一个智能研究助手，请分析以下研究查询：

查询问题: {query}
项目背景: {project.title}
项目描述: {project.description or "无描述"}

请提供以下分析结果（以JSON格式返回）：
1. recommended_mode: 推荐的研究模式 (rag|deep|auto)
   - rag: 适合基于现有文献库的快速查询
   - deep: 适合需要深度分析和经验迭代的复杂问题
   - auto: 适合需要自动搜集文献和全流程处理的新问题
2. sub_questions: 将主问题拆解成的3-5个子问题
3. complexity_score: 问题复杂度评分 (0-1)
4. estimated_resources: 预估资源需求 {{time: "预估时间", tokens: "预估token消耗", literature_count: "建议文献数量"}}
5. reasoning: 推荐理由和分析思路
6. suggested_keywords: 建议的搜索关键词 (3-8个)
7. processing_suggestions: 处理建议配置

返回标准JSON格式，不要包含任何其他内容。
"""

            # 使用AI服务进行分析
            analysis_result = await self.ai_service.generate_response(
                prompt=analysis_prompt,
                temperature=0.3,
                max_tokens=1500
            )

            # 解析JSON结果
            try:
                parsed_result = json.loads(analysis_result)
            except json.JSONDecodeError:
                # 如果解析失败，返回默认值
                parsed_result = {
                    "recommended_mode": "rag",
                    "sub_questions": [query],
                    "complexity_score": 0.5,
                    "estimated_resources": {"time": "5-10分钟", "tokens": "1000-3000", "literature_count": "5-10"},
                    "reasoning": "AI分析结果解析失败，返回默认推荐",
                    "suggested_keywords": [],
                    "processing_suggestions": {}
                }

            # 确保必要字段存在
            parsed_result.setdefault("recommended_mode", "rag")
            parsed_result.setdefault("sub_questions", [query])
            parsed_result.setdefault("complexity_score", 0.5)
            parsed_result.setdefault("estimated_resources", {})
            parsed_result.setdefault("reasoning", "")
            parsed_result.setdefault("suggested_keywords", [])
            parsed_result.setdefault("processing_suggestions", {})

            return parsed_result

        except Exception as e:
            logger.error(f"查询分析失败: {e}")
            # 返回默认分析结果
            return {
                "recommended_mode": "rag",
                "sub_questions": [query],
                "complexity_score": 0.5,
                "estimated_resources": {"time": "未知", "tokens": "未知", "literature_count": "5-10"},
                "reasoning": f"分析过程中出现错误: {str(e)}",
                "suggested_keywords": [],
                "processing_suggestions": {}
            }
