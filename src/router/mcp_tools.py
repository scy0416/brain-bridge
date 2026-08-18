"""
src/router/mcp_tools.py

MCP 서버(별도 컨테이너, tool_node.py와 동일한 서버)에 tools/list를 요청해서
도구 스키마를 실시간으로 가져오고, Ollama의 tools 파라미터 형식으로 변환한다.

이걸로 tool_specs.py(수동 작성 사본)가 필요 없어진다 — MCP 서버에 등록된
스키마가 유일한 진실이 되고, Router Agent는 항상 그걸 그대로 반영한다.
"""

import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:8100/mcp")


async def fetch_tools_from_mcp() -> list:
    """
    MCP 서버에 접속해서 tools/list로 등록된 도구 전체를 가져와,
    Ollama /api/chat의 tools 파라미터 형식으로 변환해서 반환한다.

    :return: [{"type": "function", "function": {"name":..., "description":...,
               "parameters": <JSON Schema>}}, ...]
    """
    async with streamable_http_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = await session.list_tools()

    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in mcp_tools.tools
    ]