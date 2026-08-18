"""
src/agent/router_node.py

Router Agent를 LangGraph 노드 함수로 구현. state의 question을 받아
MCP 서버에서 실시간으로 가져온 도구 스키마와 함께 Ollama에 요청하고,
선택된 도구 목록을 state에 채워 반환한다.
"""

from agent.state import GraphState
from router.mcp_tools import fetch_tools_from_mcp
from router.ollama_client import call_chat
from router.prompt import build_system_prompt
from router.schema import parse_router_decision


async def router_agent_node(state: GraphState) -> dict:
    """
    LangGraph 노드: 질문을 분석해서 호출할 도구(들)를 결정한다.
    이 노드는 답변을 생성하지 않고, 오직 "어떤 도구를 부를지"만 state에 채운다.
    도구 스키마는 매 호출 시 MCP 서버에서 실시간으로 가져온다(tools/list).

    :param state: GraphState (최소 "question" 키 필요)
    :return: state에 병합될 부분 딕셔너리 {"router_tools": [...]}
    """
    question = state["question"]

    tools = await fetch_tools_from_mcp()

    system_prompt = build_system_prompt(question)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    message = call_chat(messages, tools=tools, think=False)
    decision = parse_router_decision(message)

    router_tools = [{"name": t.name, "args": t.args} for t in decision.tools]

    return {"router_tools": router_tools}