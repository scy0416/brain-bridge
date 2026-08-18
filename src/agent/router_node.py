"""
src/agent/router_node.py

Router Agent를 LangGraph 노드 함수로 구현. state의 question을 받아
MCP 서버에서 실시간으로 가져온 도구 스키마와 함께 Ollama에 요청하고,
선택된 도구 목록을 state에 채워 반환한다.

검증/재시도: 모델이 도구를 하나도 선택하지 않으면(스키마 위반 —
"반드시 도구를 호출하라"는 프롬프트 지시를 어긴 것) 최대 2회 재시도하고,
그래도 실패하면 규칙 기반 힌트 분류기의 1위 제안으로 폴백한다
(파이프라인이 조용히 끊기지 않도록 하는 안전장치).
"""

from agent.state import GraphState
from router.hint_classifier import classify
from router.mcp_tools import fetch_tools_from_mcp
from router.ollama_client import call_chat
from router.prompt import build_system_prompt
from router.schema import parse_router_decision

MAX_RETRIES = 2
RETRY_REMINDER = (
    "방금 응답에는 도구 호출이 없었습니다. 이는 허용되지 않습니다. "
    "반드시 제공된 도구 중 하나 이상을 선택해서 호출하세요. 텍스트로 답하지 마세요."
)


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

    decision = None
    for attempt in range(MAX_RETRIES + 1):
        message = call_chat(messages, tools=tools, think=False)
        decision = parse_router_decision(message)

        if decision.tools:
            break

        # 검증 실패(도구 0개): 대화 맥락에 상황을 남기고 강하게 재요청
        if attempt < MAX_RETRIES:
            messages.append({"role": "assistant", "content": message.get("content") or ""})
            messages.append({"role": "user", "content": RETRY_REMINDER})

    router_tools = [{"name": t.name, "args": t.args} for t in decision.tools] if decision.tools else []

    if not router_tools:
        # 최종 폴백: 재시도까지 실패하면, 규칙 기반 힌트의 1위 제안으로 진행
        # (파이프라인이 끊기는 것보다, 근사치라도 도구를 실행하는 게 낫다는 판단)
        hint = classify(question)
        if hint["suggested_tools"]:
            fallback_tool = hint["suggested_tools"][0]
            router_tools = [{"name": fallback_tool, "args": {"question": question}}]

    return {"router_tools": router_tools}