"""
src/agent/graph.py

Brain Bridge 에이전트 그래프 배선.

구조 (HANDOFF.md 원본 다이어그램 기준):

    START
      -> base_agent (질문/비질문 판단, 조건부 분기)
           - needs_tools=True  -> router_agent -> tool_exec -> answer_agent -> END
           - needs_tools=False -> answer_agent -> END (Tool 실행 없이 바로 진입)

주의: base_agent_node/answer_agent_node는 동기 함수, router_agent_node/
tool_execution_node는 비동기 함수로 구현돼 있다 (각 노드 파일 참고).
LangGraph는 동기/비동기 노드가 섞인 그래프를 문제없이 실행하지만, 그래프
전체를 실행할 때는 반드시 graph.ainvoke() / graph.astream_events() 등
비동기 실행 경로를 사용해야 한다 — router_agent/tool_exec이 내부적으로
MCP 서버에 네트워크 호출(await)을 하기 때문에, graph.invoke()(동기
실행)로 부르면 이 두 노드에서 오류가 난다.
"""

from langgraph.graph import END, START, StateGraph

from agent.answer_node import answer_agent_node
from agent.base_node import base_agent_node
from agent.router_node import router_agent_node
from agent.state import GraphState
from agent.tool_node import tool_execution_node


def _route_after_base(state: GraphState) -> str:
    """base_agent 이후 분기 결정.

    state["needs_tools"]는 base_agent_node가 항상 채워서 반환하므로
    (파싱 실패 시에도 DEFAULT_NEEDS_TOOLS로 폴백) 키 부재를 걱정할
    필요는 없지만, 방어적으로 기본값 True를 둔다.
    """
    return "router_agent" if state.get("needs_tools", True) else "answer_agent"


def build_graph():
    """GraphState 기반 StateGraph를 조립하고 컴파일해서 반환한다."""
    builder = StateGraph(GraphState)

    builder.add_node("base_agent", base_agent_node)
    builder.add_node("router_agent", router_agent_node)
    builder.add_node("tool_exec", tool_execution_node)
    builder.add_node("answer_agent", answer_agent_node)

    builder.add_edge(START, "base_agent")

    builder.add_conditional_edges(
        "base_agent",
        _route_after_base,
        {
            "router_agent": "router_agent",
            "answer_agent": "answer_agent",
        },
    )

    builder.add_edge("router_agent", "tool_exec")
    builder.add_edge("tool_exec", "answer_agent")
    builder.add_edge("answer_agent", END)

    return builder.compile()


# 그래프 인스턴스 (FastAPI 어댑터 등에서 import해서 사용)
graph = build_graph()