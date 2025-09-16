"""
Claude Code集成API路由
提供前端调用Claude Code + MCP工具编排的API接口
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.services.claude_code_mcp_client import orchestrate_with_claude_code
from app.services.stream_progress_service import stream_progress_service

logger = logging.getLogger(__name__)

router = APIRouter()

class ClaudeCodeRequest(BaseModel):
    """Claude Code请求模型"""
    query: str = Field(..., description="用户查询")
    context: Optional[Dict[str, Any]] = Field(default=None, description="上下文信息")
    project_id: Optional[int] = Field(default=None, description="项目ID")
    enable_progress: bool = Field(default=True, description="是否启用进度跟踪")
    mode: Optional[str] = Field(default="auto", description="执行模式: auto/simple/deep")

class ClaudeCodeResponse(BaseModel):
    """Claude Code响应模型"""
    success: bool
    task_id: Optional[str] = None
    query_analysis: Optional[Dict[str, Any]] = None
    tool_plan: Optional[Dict[str, Any]] = None
    execution_results: Optional[List[Dict[str, Any]]] = None
    final_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str

class ProgressStatus(BaseModel):
    """进度状态模型"""
    task_id: str
    status: str
    progress: int
    message: str
    results: Optional[Dict[str, Any]] = None
    timestamp: str

@router.post("/claude-code/orchestrate", response_model=ClaudeCodeResponse)
async def claude_code_orchestrate(
    request: ClaudeCodeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_db)
):
    """
    使用Claude Code进行智能工具编排

    这个端点模拟完整的Claude Code + MCP工具调度流程：
    1. 接收前端请求
    2. 调用Claude Code进行智能分析和工具选择
    3. 通过MCP协议调用相应工具
    4. 返回整合后的结果

    Args:
        request: Claude Code请求
        background_tasks: 后台任务
        current_user: 当前用户
        db: 数据库连接

    Returns:
        编排结果或任务ID（异步模式）
    """
    try:
        # 创建任务ID用于进度跟踪
        task_id = f"claude_code_{int(datetime.now().timestamp())}"

        # 准备上下文信息
        context = request.context or {}
        context.update({
            "user_id": current_user.id,
            "project_id": request.project_id,
            "mode": request.mode,
            "timestamp": datetime.now().isoformat()
        })

        if request.enable_progress:
            # 异步执行，返回任务ID
            background_tasks.add_task(
                _execute_claude_code_orchestration,
                task_id,
                request.query,
                context
            )

            return ClaudeCodeResponse(
                success=True,
                task_id=task_id,
                timestamp=datetime.now().isoformat()
            )
        else:
            # 同步执行，直接返回结果
            result = await orchestrate_with_claude_code(
                user_query=request.query,
                context=context
            )

            return ClaudeCodeResponse(
                success=result["success"],
                query_analysis=result.get("query_analysis"),
                tool_plan=result.get("tool_plan"),
                execution_results=result.get("execution_results"),
                final_result=result.get("final_result"),
                error=result.get("error"),
                timestamp=result["timestamp"]
            )

    except Exception as e:
        logger.error(f"Claude Code编排失败: {e}")
        raise HTTPException(status_code=500, detail=f"Claude Code编排失败: {str(e)}")

@router.get("/claude-code/progress/{task_id}", response_model=ProgressStatus)
async def get_claude_code_progress(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取Claude Code任务执行进度

    Args:
        task_id: 任务ID
        current_user: 当前用户

    Returns:
        任务进度状态
    """
    try:
        # 从进度服务获取任务状态
        task_info = await stream_progress_service.get_task_info(task_id)

        if not task_info:
            raise HTTPException(status_code=404, detail="任务不存在")

        return ProgressStatus(
            task_id=task_id,
            status=task_info.get("status", "unknown"),
            progress=task_info.get("progress", 0),
            message=task_info.get("message", ""),
            results=task_info.get("results"),
            timestamp=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取进度失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取进度失败: {str(e)}")

@router.get("/claude-code/capabilities")
async def get_claude_code_capabilities():
    """
    获取Claude Code + MCP系统能力说明

    Returns:
        系统能力描述
    """
    return {
        "system_name": "Claude Code + MCP 智能工具编排系统",
        "version": "1.0.0",
        "description": "基于Claude Code的智能AI工具编排和MCP协议集成",
        "capabilities": {
            "intelligent_orchestration": {
                "description": "智能工具编排",
                "features": [
                    "查询意图分析",
                    "复杂度评估",
                    "最优工具选择",
                    "执行序列优化",
                    "结果智能整合"
                ]
            },
            "mcp_integration": {
                "description": "MCP协议集成",
                "features": [
                    "标准MCP协议通信",
                    "工具动态发现",
                    "参数验证",
                    "错误处理",
                    "降级机制"
                ]
            },
            "available_tools": [
                {
                    "name": "collect_literature",
                    "description": "采集科研文献并进行智能筛选",
                    "complexity": "medium"
                },
                {
                    "name": "structure_literature",
                    "description": "对文献进行轻结构化处理",
                    "complexity": "medium"
                },
                {
                    "name": "generate_experience",
                    "description": "基于结构化文献生成研究经验",
                    "complexity": "high"
                },
                {
                    "name": "query_knowledge",
                    "description": "基于经验库和文献库进行智能问答",
                    "complexity": "low"
                },
                {
                    "name": "create_project",
                    "description": "创建新的研究项目",
                    "complexity": "low"
                },
                {
                    "name": "get_project_status",
                    "description": "获取项目状态和进度",
                    "complexity": "low"
                }
            ]
        },
        "workflow_examples": [
            {
                "scenario": "简单问答",
                "query": "什么是机器学习？",
                "tools": ["query_knowledge"],
                "estimated_time": "30秒"
            },
            {
                "scenario": "文献研究",
                "query": "请分析深度学习在计算机视觉中的应用",
                "tools": ["collect_literature", "structure_literature"],
                "estimated_time": "2-3分钟"
            },
            {
                "scenario": "完整研究",
                "query": "我需要对AI领域进行系统性研究",
                "tools": ["collect_literature", "structure_literature", "generate_experience"],
                "estimated_time": "5-10分钟"
            }
        ],
        "performance_metrics": {
            "avg_response_time": "1-30秒",
            "success_rate": ">95%",
            "max_concurrent_tasks": 10,
            "supported_languages": ["中文", "英文"]
        }
    }

@router.post("/claude-code/test-workflow")
async def test_claude_code_workflow(
    current_user: User = Depends(get_current_active_user)
):
    """
    测试Claude Code + MCP完整工作流

    这是一个测试端点，用于验证整个系统的集成状态
    """
    try:
        test_scenarios = [
            {
                "name": "简单查询测试",
                "query": "什么是深度学习？",
                "expected_tools": ["query_knowledge"]
            },
            {
                "name": "复杂研究测试",
                "query": "请分析机器学习在医疗诊断中的应用并生成研究经验",
                "expected_tools": ["collect_literature", "structure_literature", "generate_experience"]
            }
        ]

        test_results = []

        for scenario in test_scenarios:
            try:
                result = await orchestrate_with_claude_code(
                    user_query=scenario["query"],
                    context={"test_mode": True, "user_id": current_user.id}
                )

                test_results.append({
                    "scenario": scenario["name"],
                    "success": result["success"],
                    "tools_used": result.get("tool_plan", {}).get("tools", []),
                    "expected_tools": scenario["expected_tools"],
                    "response_preview": result.get("final_result", {}).get("integrated_response", "")[:200]
                })

            except Exception as e:
                test_results.append({
                    "scenario": scenario["name"],
                    "success": False,
                    "error": str(e)
                })

        return {
            "test_summary": {
                "total_scenarios": len(test_scenarios),
                "successful_scenarios": sum(1 for r in test_results if r.get("success", False)),
                "timestamp": datetime.now().isoformat()
            },
            "test_results": test_results,
            "system_status": "operational" if all(r.get("success", False) for r in test_results) else "degraded"
        }

    except Exception as e:
        logger.error(f"工作流测试失败: {e}")
        raise HTTPException(status_code=500, detail=f"工作流测试失败: {str(e)}")

async def _execute_claude_code_orchestration(
    task_id: str,
    query: str,
    context: Dict[str, Any]
):
    """
    后台执行Claude Code编排任务

    Args:
        task_id: 任务ID
        query: 用户查询
        context: 上下文信息
    """
    try:
        # 创建进度跟踪任务
        await stream_progress_service.create_workflow_task(
            task_id,
            f"Claude Code编排: {query[:50]}...",
            ["analysis", "orchestration", "execution", "integration"],
            context
        )

        # 定义进度回调函数
        async def progress_callback(message: str, progress: int):
            current_stage = "orchestration"
            if progress <= 25:
                current_stage = "analysis"
            elif progress <= 50:
                current_stage = "orchestration"
            elif progress <= 80:
                current_stage = "execution"
            else:
                current_stage = "integration"

            await stream_progress_service.update_stage_progress(
                task_id, current_stage, progress, message
            )

        # 执行Claude Code编排
        result = await orchestrate_with_claude_code(
            user_query=query,
            context=context,
            progress_callback=progress_callback
        )

        # 完成任务
        if result["success"]:
            await stream_progress_service.complete_stage(
                task_id, "integration",
                results_data=result,
                final_message="Claude Code编排完成"
            )
        else:
            await stream_progress_service.update_stage_progress(
                task_id, "integration", -1,
                f"编排失败: {result.get('error', '未知错误')}",
                status="failed"
            )

    except Exception as e:
        logger.error(f"后台编排任务失败: {e}")
        await stream_progress_service.update_stage_progress(
            task_id, "execution", -1,
            f"后台任务异常: {str(e)}",
            status="failed"
        )