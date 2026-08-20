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


def _extract_last_user_question(messages: list[dict]) -> str:
    """messages(OpenAI 포맷)에서 가장 최근 user 발화의 content를 추출한다.

    Base/Router Agent가 사용할 state["question"]을 채우기 위한 용도.
    문맥 의존적 후속 질문은 처리하지 않기로 한 설계 결정에 따라, 이전
    턴은 참고하지 않고 항상 마지막 user 메시지 하나만 사용한다.
    """
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content") or ""
    return ""


async def run_agent(messages: list[dict]) -> str:
    """Open WebUI(또는 다른 어떤 호출자든) 대화 히스토리를 받아 그래프를
    실행하고 최종 답변 문자열만 돌려주는 공통 진입점.

    FastAPI 어댑터의 /v1/chat/completions가 이 함수 하나만 호출하면
    되도록, "OpenAI 포맷 messages 리스트를 받아서 답변 문자열을 반환"
    하는 얇은 캡슐화 레이어로 둔다. 그래프 내부 구조(state 스키마,
    노드 구성)는 호출자가 알 필요 없게 여기서 전부 감춘다.

    :param messages: OpenAI 포맷 대화 히스토리
                      [{"role": "user"|"assistant"|"system", "content": "..."}, ...]
    :return: 최종 답변 문자열. 그래프가 답을 만들지 못한 경우
             (예: final_answer가 비어있는 예외적 상황)에도 빈 문자열
             대신 사용자에게 보여줄 수 있는 안내 문구를 반환한다.
    """
    question = _extract_last_user_question(messages)

    initial_state: GraphState = {
        "messages": messages,
        "question": question,
    }

    result_state = await graph.ainvoke(initial_state)

    final_answer = result_state.get("final_answer")
    if not final_answer:
        return "죄송합니다, 답변을 생성하지 못했습니다. 다시 시도해 주세요."

    return final_answer