"""
智能交互API端点
实现类似天工Skywork的澄清机制API路由
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import logging
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.project import Project
from app.models.interaction import InteractionSession, ClarificationCard, InteractionAnalytics
from app.services.intelligent_interaction_engine import IntelligentInteractionEngine
from app.schemas.interaction_schemas import (
    InteractionStartRequest, InteractionStartResponse,
    SelectionRequest, SelectionResponse,
    TimeoutRequest, TimeoutResponse,
    CustomInputRequest, CustomInputResponse,
    ClarificationResponse, SessionStatusResponse,
    EndSessionRequest, EndSessionResponse,
    ClarificationCardModel, ClarificationOptionModel,
    SessionInfo, SessionStatistics
)
from app.core.exceptions import ApplicationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interaction", tags=["intelligent_interaction"])


@router.post("/start", response_model=InteractionStartResponse)
async def start_intelligent_interaction(
    request: InteractionStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    启动智能交互会话

    实现类似天工Skywork的智能澄清机制：
    1. 分析用户输入的意图和模糊程度
    2. 如果需要澄清，生成AI动态选项
    3. 如果意图明确，直接执行工作流
    """
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == request.project_id,
            Project.owner_id == current_user.id
        ).first()

        if not project:
            raise ApplicationError("PROJECT_4001", "项目不存在或无权限访问")

        # 初始化智能交互引擎
        interaction_engine = IntelligentInteractionEngine(db)

        # 创建交互会话
        result = await interaction_engine.create_interaction_session(
            user_id=current_user.id,
            project_id=request.project_id,
            context_type=request.context_type,
            user_input=request.user_input,
            additional_context=request.additional_context
        )

        return InteractionStartResponse(**result)

    except ApplicationError as e:
        logger.error(f"启动智能交互失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"启动智能交互系统错误: {e}")
        raise HTTPException(status_code=500, detail="智能交互系统暂时不可用")


@router.get("/{session_id}/clarifications", response_model=ClarificationResponse)
async def get_clarification_cards(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取指定会话的澄清卡片信息"""
    try:
        # 验证会话权限
        session = db.query(InteractionSession).filter(
            InteractionSession.session_id == session_id,
            InteractionSession.user_id == current_user.id,
            InteractionSession.is_active == True
        ).first()

        if not session:
            raise ApplicationError("INTERACTION_3001", "交互会话不存在或已结束")

        # 获取澄清卡片
        clarification_cards = db.query(ClarificationCard).filter(
            ClarificationCard.session_id == session_id
        ).order_by(ClarificationCard.created_at.desc()).all()

        # 转换为响应模型
        card_models = []
        for card in clarification_cards:
            card_model = ClarificationCardModel(
                session_id=card.session_id,
                stage=card.stage,
                question=card.question,
                options=[ClarificationOptionModel(**opt) for opt in card.options],
                recommended_option_id=card.recommended_option_id,
                timeout_seconds=card.timeout_seconds,
                custom_input_allowed=card.custom_input_allowed,
                context=card.context,
                created_at=card.created_at.isoformat()
            )
            card_models.append(card_model)

        return ClarificationResponse(
            success=True,
            clarification_cards=card_models,
            current_stage=session.current_stage,
            interaction_history=session.interaction_history
        )

    except ApplicationError as e:
        logger.error(f"获取澄清卡片失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取澄清卡片系统错误: {e}")
        raise HTTPException(status_code=500, detail="获取澄清卡片失败")


@router.post("/{session_id}/select", response_model=SelectionResponse)
async def handle_user_selection(
    session_id: str,
    request: SelectionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    处理用户的选择操作

    支持：
    1. 用户主动选择选项
    2. 记录选择时间和响应数据
    3. 决定下一步操作（继续澄清或执行工作流）
    """
    try:
        # 验证会话权限
        session = db.query(InteractionSession).filter(
            InteractionSession.session_id == session_id,
            InteractionSession.user_id == current_user.id,
            InteractionSession.is_active == True
        ).first()

        if not session:
            raise ApplicationError("INTERACTION_3001", "交互会话不存在或已结束")

        # 初始化智能交互引擎
        interaction_engine = IntelligentInteractionEngine(db)

        # 处理用户选择
        selection_data = {
            "option_id": request.option_id,
            "selection_type": "manual",
            "selection_data": request.selection_data,
            "client_timestamp": request.client_timestamp
        }

        result = await interaction_engine.handle_user_selection(
            session_id=session_id,
            selection=selection_data
        )

        # 后台任务：发送WebSocket通知
        background_tasks.add_task(
            _send_websocket_notification,
            "option_selected",
            session_id,
            result
        )

        return SelectionResponse(**result)

    except ApplicationError as e:
        logger.error(f"处理用户选择失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"处理用户选择系统错误: {e}")
        raise HTTPException(status_code=500, detail="处理选择失败")


@router.post("/{session_id}/timeout", response_model=TimeoutResponse)
async def handle_timeout_selection(
    session_id: str,
    request: TimeoutRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    处理5秒超时后的自动选择

    功能：
    1. 自动选择推荐选项
    2. 记录为超时选择
    3. 继续工作流处理
    """
    try:
        # 验证会话权限
        session = db.query(InteractionSession).filter(
            InteractionSession.session_id == session_id,
            InteractionSession.user_id == current_user.id,
            InteractionSession.is_active == True
        ).first()

        if not session:
            raise ApplicationError("INTERACTION_3001", "交互会话不存在或已结束")

        # 获取当前澄清卡片
        current_card = db.query(ClarificationCard).filter(
            ClarificationCard.session_id == session_id,
            ClarificationCard.resolved_at.is_(None)
        ).first()

        if not current_card:
            raise ApplicationError("INTERACTION_3002", "没有待处理的澄清卡片")

        # 初始化智能交互引擎
        interaction_engine = IntelligentInteractionEngine(db)

        # 自动选择推荐选项
        auto_selected_option_id = (
            request.auto_selected_option_id or
            current_card.recommended_option_id
        )

        selection_data = {
            "option_id": auto_selected_option_id,
            "selection_type": "auto",
            "timeout_timestamp": request.timeout_timestamp,
            "auto_selection_reason": "5秒超时自动选择推荐项"
        }

        result = await interaction_engine.handle_user_selection(
            session_id=session_id,
            selection=selection_data
        )

        # 获取被选择的选项信息
        selected_option = None
        for option_data in current_card.options:
            if option_data.get("option_id") == auto_selected_option_id:
                selected_option = ClarificationOptionModel(**option_data)
                break

        # 构建超时响应
        timeout_response = TimeoutResponse(
            **result,
            auto_selected=True,
            selected_option=selected_option
        )

        # 后台任务：发送WebSocket通知
        background_tasks.add_task(
            _send_websocket_notification,
            "auto_selected",
            session_id,
            {
                "selected_option": selected_option.dict() if selected_option else {},
                "auto_selection_reason": "5秒超时自动选择",
                "processing_result": result
            }
        )

        return timeout_response

    except ApplicationError as e:
        logger.error(f"处理超时选择失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"处理超时选择系统错误: {e}")
        raise HTTPException(status_code=500, detail="处理超时选择失败")


@router.post("/{session_id}/custom", response_model=CustomInputResponse)
async def handle_custom_input(
    session_id: str,
    request: CustomInputRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    处理用户的自定义输入

    当提供的选项不满足用户需求时，用户可以输入自定义内容
    """
    try:
        # 验证会话权限
        session = db.query(InteractionSession).filter(
            InteractionSession.session_id == session_id,
            InteractionSession.user_id == current_user.id,
            InteractionSession.is_active == True
        ).first()

        if not session:
            raise ApplicationError("INTERACTION_3001", "交互会话不存在或已结束")

        # 获取当前澄清卡片
        current_card = db.query(ClarificationCard).filter(
            ClarificationCard.session_id == session_id,
            ClarificationCard.resolved_at.is_(None)
        ).first()

        if not current_card:
            raise ApplicationError("INTERACTION_3002", "没有待处理的澄清卡片")

        if not current_card.custom_input_allowed:
            raise ApplicationError("INTERACTION_3006", "当前阶段不允许自定义输入")

        # 初始化智能交互引擎
        interaction_engine = IntelligentInteractionEngine(db)

        # 处理自定义输入
        selection_data = {
            "custom_input": request.custom_input,
            "selection_type": "custom",
            "context": request.context,
            "client_timestamp": request.client_timestamp
        }

        result = await interaction_engine.handle_user_selection(
            session_id=session_id,
            selection=selection_data
        )

        # AI解释用户输入（可选功能）
        ai_interpretation = f"用户自定义输入：{request.custom_input}"

        custom_response = CustomInputResponse(
            success=result["success"],
            input_processed=True,
            ai_interpretation=ai_interpretation,
            next_action=result["next_action"],
            next_clarification_card=result.get("next_clarification_card"),
            workflow_result=result.get("workflow_result")
        )

        # 后台任务：发送WebSocket通知
        background_tasks.add_task(
            _send_websocket_notification,
            "custom_input_processed",
            session_id,
            {
                "original_input": request.custom_input,
                "ai_interpretation": ai_interpretation,
                "processing_result": result
            }
        )

        return custom_response

    except ApplicationError as e:
        logger.error(f"处理自定义输入失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"处理自定义输入系统错误: {e}")
        raise HTTPException(status_code=500, detail="处理自定义输入失败")


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """获取交互会话的当前状态"""
    try:
        # 验证会话权限
        session = db.query(InteractionSession).filter(
            InteractionSession.session_id == session_id,
            InteractionSession.user_id == current_user.id
        ).first()

        if not session:
            raise ApplicationError("INTERACTION_3001", "交互会话不存在")

        # 统计交互数据
        analytics = db.query(InteractionAnalytics).filter(
            InteractionAnalytics.session_id == session_id
        ).all()

        # 计算统计信息
        total_rounds = len([a for a in analytics if a.event_type == "select"])
        user_selections = len([a for a in analytics if a.event_type == "select" and "manual" in str(a.event_data)])
        auto_selections = len([a for a in analytics if a.event_type == "select" and "auto" in str(a.event_data)])
        custom_inputs = len([a for a in analytics if a.event_type == "custom_input"])

        response_times = [a.response_time_ms for a in analytics if a.response_time_ms]
        avg_response_time = sum(response_times) / len(response_times) / 1000 if response_times else 0.0

        session_info = SessionInfo(
            session_id=session.session_id,
            user_id=session.user_id,
            project_id=session.project_id,
            context_type=session.context_type,
            current_stage=session.current_stage,
            is_active=session.is_active,
            created_at=session.created_at.isoformat(),
            last_activity=session.updated_at.isoformat(),
            timeout_at=session.expires_at.isoformat() if session.expires_at else None
        )

        statistics = SessionStatistics(
            total_rounds=total_rounds,
            user_selections=user_selections,
            auto_selections=auto_selections,
            custom_inputs=custom_inputs,
            average_response_time=avg_response_time
        )

        return SessionStatusResponse(
            success=True,
            session=session_info,
            statistics=statistics
        )

    except ApplicationError as e:
        logger.error(f"获取会话状态失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取会话状态系统错误: {e}")
        raise HTTPException(status_code=500, detail="获取会话状态失败")


@router.post("/{session_id}/end", response_model=EndSessionResponse)
async def end_interaction_session(
    session_id: str,
    request: EndSessionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """主动结束交互会话"""
    try:
        # 验证会话权限
        session = db.query(InteractionSession).filter(
            InteractionSession.session_id == session_id,
            InteractionSession.user_id == current_user.id,
            InteractionSession.is_active == True
        ).first()

        if not session:
            raise ApplicationError("INTERACTION_3001", "交互会话不存在或已结束")

        # 计算会话时长
        duration = (datetime.utcnow() - session.created_at).total_seconds()

        # 统计完成轮次
        completed_rounds = len([
            item for item in session.interaction_history
            if item.get("action") == "user_selection"
        ])

        # 结束会话
        session.is_active = False
        session.updated_at = datetime.utcnow()

        # 记录结束事件
        end_analytics = InteractionAnalytics(
            session_id=session_id,
            user_id=session.user_id,
            event_type="end_session",
            event_data={
                "reason": request.reason,
                "feedback": request.feedback,
                "duration_seconds": duration
            }
        )
        db.add(end_analytics)

        # 会话摘要
        from app.schemas.interaction_schemas import SessionSummary
        session_summary = SessionSummary(
            session_id=session_id,
            total_duration=duration,
            rounds_completed=completed_rounds,
            final_result={"status": "ended", "reason": request.reason}
        )

        db.commit()

        # 后台任务：清理会话资源
        background_tasks.add_task(_cleanup_session_resources, session_id)

        # 后台任务：发送WebSocket通知
        background_tasks.add_task(
            _send_websocket_notification,
            "interaction_completed",
            session_id,
            {
                "final_result": session_summary.final_result,
                "session_summary": session_summary.dict(),
                "next_action": "refresh"
            }
        )

        return EndSessionResponse(
            success=True,
            session_summary=session_summary,
            cleanup_status="completed"
        )

    except ApplicationError as e:
        db.rollback()
        logger.error(f"结束交互会话失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"结束交互会话系统错误: {e}")
        raise HTTPException(status_code=500, detail="结束交互会话失败")


# 辅助函数
async def _send_websocket_notification(event_type: str, session_id: str, data: Dict):
    """发送WebSocket通知（后台任务）"""
    try:
        # 这里集成现有的WebSocket广播系统
        from app.services.stream_progress_service import StreamProgressService

        progress_service = StreamProgressService()

        # 构建WebSocket事件数据
        websocket_data = {
            "type": event_type,
            "session_id": session_id,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            **data
        }

        # 广播到对应的WebSocket连接
        await progress_service.broadcast_to_session(session_id, websocket_data)

        logger.info(f"WebSocket通知已发送: {event_type} for session {session_id}")

    except Exception as e:
        logger.error(f"发送WebSocket通知失败: {e}")


async def _cleanup_session_resources(session_id: str):
    """清理会话资源（后台任务）"""
    try:
        # 清理临时文件、缓存等资源
        logger.info(f"清理会话资源: {session_id}")

        # 这里可以添加具体的清理逻辑
        # 例如：清理Redis缓存、临时文件等

    except Exception as e:
        logger.error(f"清理会话资源失败: {e}")
