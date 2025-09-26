"""外部智能体编排客户端封装。"""

from __future__ import annotations

import asyncio
import json
import shlex
from typing import Any, Dict, Optional

import httpx
from loguru import logger

from app.core.config import settings


class CodeXClient:
    """封装对CodeX编排服务的HTTP调用。"""

    def __init__(self):
        self.base_url = settings.codex_api_url
        self.route = settings.codex_api_route
        self.api_key = settings.codex_api_key
        self.timeout = settings.codex_timeout

    def _build_url(self) -> str:
        if not self.base_url:
            raise RuntimeError("CodeX编排服务未配置，请设置 CODEX_API_URL 环境变量")

        if not self.route:
            return self.base_url

        return f"{self.base_url.rstrip('/')}/{self.route.lstrip('/')}"

    async def orchestrate(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        url = self._build_url()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "query": query,
            "context": context,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return {
            "success": data.get("success", True),
            "tool_plan": data.get("tool_plan", data),
            "execution_results": data.get("execution_results", []),
            "final_result": data.get("final_result", data),
            "raw_response": data,
        }


class GeminiCLIClient:
    """封装对Gemini CLI的子进程调用。"""

    def __init__(self):
        self.command = settings.gemini_cli_command
        self.timeout = settings.gemini_cli_timeout

    def _build_command(self) -> list[str]:
        if not self.command:
            raise RuntimeError("Gemini CLI 未配置，请设置 GEMINI_CLI_COMMAND 环境变量")

        return shlex.split(self.command)

    async def orchestrate(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        command = self._build_command()
        payload = json.dumps({"query": query, "context": context}, ensure_ascii=False)

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(payload),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            raise RuntimeError("Gemini CLI 执行超时") from exc

        if process.returncode != 0:
            logger.error("Gemini CLI 执行失败: %s", stderr.strip())
            raise RuntimeError(f"Gemini CLI 调用失败: {stderr.strip()}")

        stdout = stdout.strip()

        try:
            data: Dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("Gemini CLI 输出非JSON，将原始内容封装返回")
            data = {
                "success": True,
                "raw_output": stdout,
            }

        return {
            "success": data.get("success", True),
            "tool_plan": data.get("tool_plan", data),
            "execution_results": data.get("execution_results", []),
            "final_result": data.get("final_result", data),
            "raw_response": data,
        }

