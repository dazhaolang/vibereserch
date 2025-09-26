"""Pydantic schemas for MCP tool API"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MCPToolSchema(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPToolListResponse(BaseModel):
    tools: List[MCPToolSchema]


class MCPInvokeRequest(BaseModel):
    tool: str
    parameters: Optional[Dict[str, Any]] = None


class MCPInvokeResponse(BaseModel):
    success: bool
    result: Dict[str, Any]
