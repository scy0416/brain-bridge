"""
agent/base_node.py

Base Agent(기본 에이전트) 노드.

그래프의 진입점(START 바로 다음)으로, 사용자의 최신 발화(state["question"])
하나만 보고 도구가 필요한 질문인지 판단해 state["needs_tools"]를 채운다.
이 값은 이후 add_conditional_edges에서 라우팅 에이전트로 갈지, 곧장 답변
생성 에이전트로 갈지를 결정하는 분기 기준으로 쓰인다.

Router Agent(agent/router_node.py)와 동일하게 Ollama /api/chat을 감싼
call_chat()을 재사용한다 (call_chat은 동기 함수이며, 도구 스키마 없이
호출 시 assistant 메시지 딕셔너리 {"content": "...", ...}를 그대로
반환한다 — router_node.py의 사용 방식과 동일).

진행상황 스트리밍: 노드 시작/종료 시점에 dispatch_custom_event("progress", ...)
로 짧은 상태 메시지를 발행한다. 구독자(graph.astream_events)가 없으면
아무 효과가 없으므로 graph.ainvoke() 기반의 기존 호출 경로(run_agent,
테스트 스크립트들)에는 영향이 없다.
"""

import json
import logging

from langchain_core.callbacks.manager import dispatch_custom_event

from agent.base_prompt import build_base_messages
from agent.state import GraphState
from router.ollama_client import call_chat

logger = logging.getLogger(__name__)

# Ollama 응답이 비정상(파싱 실패, 빈 응답 등)일 때의 기본값.
# 안전 방향: 도구 없이 답하면 안 되는 조회성 질문을 놓치는 것이
# 불필요하게 라우터를 한 번 더 거치는 것보다 리스크가 크므로,
# 판단 실패 시에는 도구가 필요하다고 보수적으로 가정한다.
DEFAULT_NEEDS_TOOLS = True


def _parse_needs_tools(raw_content: str) -> bool:
    """Ollama 응답 문자열에서 needs_tools 불리언 값을 파싱한다.

    모델이 코드펜스(```json ... ```)를 붙이거나 앞뒤에 잡텍스트를 섞어
    보내는 경우를 대비해, 문자열 내 첫 '{'부터 마지막 '}'까지만 잘라
    JSON으로 파싱을 시도한다. 그래도 실패하면 DEFAULT_NEEDS_TOOLS로
    폴백한다.
    """
    text = (raw_content or "").strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        logger.warning(
            "base_node: 응답에서 JSON 객체를 찾지 못함, 기본값(%s)으로 폴백. raw=%r",
            DEFAULT_NEEDS_TOOLS,
            raw_content,
        )
        return DEFAULT_NEEDS_TOOLS

    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        logger.warning(
            "base_node: JSON 파싱 실패, 기본값(%s)으로 폴백. raw=%r",
            DEFAULT_NEEDS_TOOLS,
            raw_content,
        )
        return DEFAULT_NEEDS_TOOLS

    value = parsed.get("needs_tools")
    if not isinstance(value, bool):
        logger.warning(
            "base_node: needs_tools 필드가 없거나 bool이 아님, 기본값(%s)으로 폴백. parsed=%r",
            DEFAULT_NEEDS_TOOLS,
            parsed,
        )
        return DEFAULT_NEEDS_TOOLS

    return value


def base_agent_node(state: GraphState) -> dict:
    """Base Agent 노드 본체.

    state["question"]만 참조하며(대화 히스토리는 사용하지 않음),
    state 갱신분(dict)만 반환한다 — LangGraph 노드 관례에 따라 전체
    state가 아닌 변경된 키만 돌려준다.

    router_agent_node와 달리 도구 스키마(tools=...)를 넘기지 않는다 —
    이 노드는 도구를 고르는 게 아니라 "도구가 필요한가"만 판단하면
    되므로 function-calling이 아닌 일반 텍스트(JSON) 응답으로 처리한다.
    """
    question = state["question"]

    dispatch_custom_event("progress", {"message": "🧭 질문 유형을 확인하는 중입니다..."})

    messages = build_base_messages(question)
    message = call_chat(messages, think=False)

    raw_content = message.get("content") or ""
    needs_tools = _parse_needs_tools(raw_content)

    return {"needs_tools": needs_tools}