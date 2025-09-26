"""Registry for MCP-compatible tools"""

from typing import Any, Dict, Callable


ToolHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


class MCPToolRegistry:
    """Simple in-process registry for MCP tools."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        handler: ToolHandler,
        input_schema: Dict[str, Any],
    ) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "handler": handler,
            "input_schema": input_schema,
        }

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        return self._tools

    def run_tool(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._tools:
            raise ValueError(f"Unknown MCP tool: {name}")
        handler = self._tools[name]["handler"]
        return handler(payload)


mcp_tool_registry = MCPToolRegistry()
