"""统一的多智能体编排入口。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Callable

from loguru import logger

from app.services.claude_code_mcp_client import orchestrate_with_claude_code
from app.services.external_agent_clients import CodeXClient, GeminiCLIClient

ProgressCallback = Optional[Callable[[str, int], Any]]


class BaseAgentOrchestrator:
    """调度多个编排后端的抽象类。"""

    name: str = "base"

    async def orchestrate(
        self,
        user_query: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class ClaudeCodeAgentOrchestrator(BaseAgentOrchestrator):
    name = "claude"

    async def orchestrate(
        self,
        user_query: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
    ) -> Dict[str, Any]:
        logger.info("使用 Claude Code 进行智能工具编排")
        return await orchestrate_with_claude_code(user_query, context, progress_callback)


class CodeXAgentOrchestrator(BaseAgentOrchestrator):
    name = "codex"

    async def orchestrate(
        self,
        user_query: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
    ) -> Dict[str, Any]:
        logger.info("使用 CodeX 进行编排")
        client = CodeXClient()

        if progress_callback:
            await progress_callback("CodeX: 准备请求外部编排服务", 20)

        try:
            result = await client.orchestrate(user_query, context)
            if progress_callback:
                await progress_callback("CodeX: 编排完成", 95)
            result.setdefault("agent", self.name)
            return result
        except Exception as exc:
            logger.warning("CodeX编排失败，将使用本地回退计划: %s", exc)
            return await self._fallback_plan(progress_callback, error=str(exc))

    async def _fallback_plan(
        self,
        progress_callback: ProgressCallback,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        if progress_callback:
            await progress_callback("CodeX: 使用默认执行计划", 60)

        tools = ["collect_literature", "process_literature", "generate_experience"]
        plan = {
            "strategy": "codex_default",
            "tools": tools,
            "execution_plan": [
                {
                    "step": idx + 1,
                    "tool": tool,
                    "description": f"CodeX 模拟触发 {tool}",
                }
                for idx, tool in enumerate(tools)
            ],
        }

        return {
            "success": True,
            "tool_plan": plan,
            "execution_results": [],
            "final_result": {
                "message": "CodeX 规划完成，等待任务系统执行",
                "strategy": plan["strategy"],
            },
            "agent": self.name,
            "fallback": True,
            "error": error,
        }


class GeminiCLIAgentOrchestrator(BaseAgentOrchestrator):
    name = "gemini"

    async def orchestrate(
        self,
        user_query: str,
        context: Dict[str, Any],
        progress_callback: ProgressCallback = None,
    ) -> Dict[str, Any]:
        logger.info("使用 Gemini CLI 进行编排")
        client = GeminiCLIClient()

        if progress_callback:
            await progress_callback("Gemini CLI: 启动子进程", 30)

        try:
            result = await client.orchestrate(user_query, context)
            if progress_callback:
                await progress_callback("Gemini CLI: 编排完成", 90)
            result.setdefault("agent", self.name)
            return result
        except Exception as exc:
            logger.warning("Gemini CLI 编排失败，使用回退计划: %s", exc)
            return await self._fallback_plan(progress_callback, error=str(exc))

    async def _fallback_plan(
        self,
        progress_callback: ProgressCallback,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        if progress_callback:
            await progress_callback("Gemini CLI: 使用默认执行计划", 55)

        tools = ["collect_literature", "task_statistics", "generate_experience"]
        plan = {
            "strategy": "gemini_cli_hybrid",
            "tools": tools,
            "execution_plan": [
                {
                    "step": idx + 1,
                    "tool": tool,
                    "description": f"Gemini CLI 计划执行 {tool}",
                }
                for idx, tool in enumerate(tools)
            ],
        }

        return {
            "success": True,
            "tool_plan": plan,
            "execution_results": [],
            "final_result": {
                "message": "Gemini CLI 规划完成，等待任务系统执行",
                "strategy": plan["strategy"],
            },
            "agent": self.name,
            "fallback": True,
            "error": error,
        }


def get_agent_orchestrator(agent: Optional[str]) -> BaseAgentOrchestrator:
    normalized = (agent or "claude").lower()
    if normalized in {"codex", "code_x", "code-x"}:
        return CodeXAgentOrchestrator()
    if normalized in {"gemini", "geminicli", "gemini_cli"}:
        return GeminiCLIAgentOrchestrator()
    return ClaudeCodeAgentOrchestrator()
