"""
scripts/test_router_retry.py

router_agent_node의 재시도/폴백 로직을 검증한다. 실제 LLM이 매번 실패하게
만들기는 어려우니, call_chat을 모킹해서 "도구 호출 없음" 상황을 강제로
재현하고, 재시도 후 성공하는 경우와 끝까지 실패해서 힌트로 폴백하는
경우를 각각 확인한다.

사용법:
    docker compose run --rm app python scripts/test_router_retry.py
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.router_node import router_agent_node

EMPTY_MESSAGE = {"role": "assistant", "content": "죄송합니다, 잘 모르겠어요."}
TOOL_CALL_MESSAGE = {
    "role": "assistant",
    "content": "",
    "tool_calls": [
        {"id": "1", "function": {"name": "nl2sql_tool", "arguments": {"question": "테스트"}}}
    ],
}


async def test_retry_then_success():
    """1차 실패 → 2차 성공 시나리오."""
    with patch("agent.router_node.call_chat", side_effect=[EMPTY_MESSAGE, TOOL_CALL_MESSAGE]) as mock_call, \
         patch("agent.router_node.fetch_tools_from_mcp", new=AsyncMock(return_value=[])):
        result = await router_agent_node({"question": "테스트 질문"})

    print("[재시도 후 성공] router_tools:", result["router_tools"])
    assert mock_call.call_count == 2, f"call_chat이 2번 호출됐어야 함, 실제 {mock_call.call_count}번"
    assert result["router_tools"] == [{"name": "nl2sql_tool", "args": {"question": "테스트"}}]
    print("  -> 통과")


async def test_all_fail_fallback_to_hint():
    """MAX_RETRIES까지 전부 실패 → 규칙 기반 힌트로 폴백."""
    with patch("agent.router_node.call_chat", return_value=EMPTY_MESSAGE) as mock_call, \
         patch("agent.router_node.fetch_tools_from_mcp", new=AsyncMock(return_value=[])):
        result = await router_agent_node({"question": "서울 지역 매출 상위 5개 고객사를 알려줘"})

    print("[전부 실패 -> 힌트 폴백] router_tools:", result["router_tools"])
    assert mock_call.call_count == 3, f"call_chat이 3번(최초+재시도 2회) 호출됐어야 함, 실제 {mock_call.call_count}번"
    assert len(result["router_tools"]) > 0, "폴백도 실패해서 도구가 비어있음"
    assert result["router_tools"][0]["name"] == "nl2sql_tool", "힌트 분류기 기준 nl2sql_tool이 나와야 함"
    print("  -> 통과")


async def main():
    await test_retry_then_success()
    await test_all_fail_fallback_to_hint()
    print("\n✅ Router Agent 재시도/폴백 로직 검증 완료")


if __name__ == "__main__":
    asyncio.run(main())