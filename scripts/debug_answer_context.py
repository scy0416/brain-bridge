"""
scripts/debug_answer_context.py

빈 결과(2030년) 케이스에서 Answer Agent에게 실제로 어떤 텍스트가
전달되는지 그대로 출력해서, "오류"라는 표현이 프롬프트 해석 문제인지
데이터 자체의 문제인지 확인한다.

사용법:
    docker compose run --rm app python scripts/debug_answer_context.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.answer_prompt import format_tool_results
from agent.router_node import router_agent_node
from agent.tool_node import tool_execution_node

QUESTION = "2030년에 등록된 고객사는 몇 개야?"


async def main():
    state = {"question": QUESTION}

    router_result = await router_agent_node(state)
    state.update(router_result)
    print("선택된 도구:", state["router_tools"])

    tool_result = await tool_execution_node(state)
    state.update(tool_result)

    print("\n=== tool_results 원본 (success/error) ===")
    for r in state["tool_results"]:
        print(f"tool={r['tool']}, success={r['success']}")
        if not r["success"]:
            print(f"  error={r.get('error')}")

    print("\n=== Answer Agent에게 실제로 전달되는 컨텍스트 텍스트 ===")
    context_text = format_tool_results(state["tool_results"])
    print(context_text)


if __name__ == "__main__":
    asyncio.run(main())