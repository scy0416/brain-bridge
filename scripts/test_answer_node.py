"""
scripts/test_answer_node.py

router_agent_node -> tool_execution_node -> answer_agent_node를 순서대로
이어서, 아직 StateGraph 배선 전이지만 전체 흐름(질문 -> 최종 답변)이
실제로 동작하는지 미리 확인한다.

사용법:
    docker compose up -d mcp-server
    docker compose run --rm app python scripts/test_answer_node.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.answer_node import answer_agent_node
from agent.router_node import router_agent_node
from agent.tool_node import tool_execution_node

TEST_QUESTIONS = [
    "서울 지역 매출 상위 5개 고객사를 알려줘",
    "Product-C1 설치 방법이 궁금해",
    "Client-A가 사용 중인 제품 목록은?",
    "2030년에 등록된 고객사는 몇 개야?",  # 빈 결과 케이스
]


async def run_pipeline(question: str) -> dict:
    state = {"question": question}

    router_result = await router_agent_node(state)
    state.update(router_result)

    tool_result = await tool_execution_node(state)
    state.update(tool_result)

    answer_result = answer_agent_node(state)  # 동기 함수
    state.update(answer_result)

    return state


async def main():
    for question in TEST_QUESTIONS:
        print("=" * 70)
        print(f"질문: {question}")
        state = await run_pipeline(question)

        print(f"  선택된 도구: {[t['name'] for t in state['router_tools']]}")
        print(f"  최종 답변:\n{state['final_answer']}")
        print()

        assert state.get("final_answer"), "최종 답변이 비어있습니다"

    print("✅ Router → Tool → Answer 전체 흐름 정상 동작 확인 (그래프 배선 전 미리보기)")


if __name__ == "__main__":
    asyncio.run(main())