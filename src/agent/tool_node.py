"""
src/agent/tool_node.py

Router Agent가 선택한 도구들을, 별도 컨테이너("mcp-server" 서비스)로 구동 중인
MCP 서버에 네트워크(Streamable HTTP)로 접속해서 실제 MCP 프로토콜(tools/call)로
호출하는 LangGraph 노드.
"""

import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from agent.state import GraphState
from utils.logging_config import log_stage

# "mcp-server"는 docker-compose.yml에 정의된 별도 컨테이너의 서비스 이름.
# app 컨테이너에서는 Compose 네트워크를 통해 이 이름으로 접근한다.
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp-server:8100/mcp")


async def _call_tool_via_mcp(name: str, args: dict) -> dict:
    """MCP 클라이언트로 별도 컨테이너의 MCP 서버에 접속해서 도구 하나를 tools/call로 호출한다."""
    async with streamable_http_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments=args)
            return result


async def tool_execution_node(state: GraphState) -> dict:
    """
    LangGraph 노드: state["router_tools"]에 담긴 도구 호출 목록을 순서대로
    실제 MCP 서버에 tools/call로 요청해서 실행하고, 결과를 state에 채운다.

    :param state: GraphState (router_tools 키 필요)
    :return: state에 병합될 부분 딕셔너리 {"tool_results": [...]}
    """
    router_tools = state.get("router_tools", [])
    request_id = state["request_id"]
    tool_results = []

    for call in router_tools:
        name = call["name"]
        args = call["args"]

        with log_stage("mcp_tool_call", request_id, tool_name=name, args=args) as log_result:
            try:
                # request_id를 args에 섞어서 mcp-server 컨테이너의 도구 함수(예:
                # knowledge_graph_tool)까지 전달한다. 도구 쪽에서 request_id를
                # 별도 키워드 인자로 꺼내 쓰고, 실제 도구 로직에는 넘기지 않도록
                # 각 tools/*.py 구현에서 pop 처리가 필요하다.
                mcp_result = await _call_tool_via_mcp(name, {**args, "request_id": request_id})
                log_result["result_size_chars"] = len(str(mcp_result))
                tool_results.append(
                    {
                        "tool": name,
                        "args": args,
                        "success": True,
                        "result": mcp_result,
                    }
                )
            except Exception as e:
                log_result["error"] = str(e)
                tool_results.append(
                    {
                        "tool": name,
                        "args": args,
                        "success": False,
                        "error": str(e),
                    }
                )

    return {"tool_results": tool_results}