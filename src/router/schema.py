"""
src/router/schema.py

Router Agent(Ollama 네이티브 function-calling, tools 파라미터 방식)의 출력을
그래프 내부에서 다루기 위한 표준 표현.

주의: 이건 LLM에게 강제로 뱉게 하는 JSON 스키마(format)가 아니다.
Router Agent는 Ollama의 tools 파라미터로 도구를 호출하고, 그 응답(message.tool_calls)을
이 모듈이 파싱해서 tools/args/reasoning 형태로 정리한다.
(참고: 실측 결과 네이티브 tool-calling 시 message.content는 보통 빈 문자열로
 옴 — reasoning은 항상 채워지는 필드가 아니라 선택적 필드로 설계함)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """단일 도구 호출 — 도구 이름과 인자."""

    name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouterDecision:
    """
    Router Agent의 최종 판단.

    :param tools: 호출할 도구 목록 (0개=도구 불필요, 1개=단일 도구,
                   2개 이상=복합 질문에 대한 병렬 도구 호출)
    :param reasoning: 모델이 tool_calls와 함께 남긴 부가 설명(있는 경우).
                       네이티브 tool-calling에서는 보통 비어있다.
    """

    tools: List[ToolCall]
    reasoning: Optional[str] = None

    @property
    def needs_tools(self) -> bool:
        return len(self.tools) > 0


def parse_router_decision(message: dict) -> RouterDecision:
    """
    Ollama /api/chat 응답의 message 딕셔너리에서 RouterDecision을 추출한다.

    기대하는 입력 형태 (Ollama 네이티브 tool-calling 응답):
    {
        "role": "assistant",
        "content": "",  # 보통 비어있음
        "tool_calls": [
            {"id": "...", "function": {"name": "nl2sql_tool", "arguments": {"question": "..."}}}
        ]
    }

    :param message: Ollama 응답의 "message" 필드
    :return: 파싱된 RouterDecision
    """
    raw_tool_calls = message.get("tool_calls") or []

    tools = [
        ToolCall(
            name=tc["function"]["name"],
            args=tc["function"].get("arguments", {}) or {},
        )
        for tc in raw_tool_calls
    ]

    content = message.get("content")
    reasoning = content if content else None

    return RouterDecision(tools=tools, reasoning=reasoning)