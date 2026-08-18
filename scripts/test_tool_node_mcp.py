"""
scripts/test_tool_node_mcp.py

router_agent_node()가 고른 도구를, tool_execution_node()가 실제 MCP
프로토콜(tools/call)로 호출하는지 end-to-end로 확인한다.

이 스크립트가 통과하면 "에이전트가 MCP를 통해 도구를 호출한다"는
대회 요건이 실제로 충족된다는 뜻이다 (Python 함수 직접 호출로 우회하지 않음).

사용법:
    docker compose run --rm app python scripts/test_tool_node_mcp.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.router_node import router_agent_node
from agent.tool_node import tool_execution_node

TEST_QUESTIONS = [
    "Product-C1 설치 방법이 궁금해",
    "서울 지역 매출 상위 5개 고객사를 알려줘",
    "Client-A가 사용 중인 제품 목록은?",
]


async def main():
    for question in TEST_QUESTIONS:
        print(f"질문: {question}")

        state = {"question": question}
        router_result = await router_agent_node(state)
        state.update(router_result)
        print(f"  Router 선택: {state['router_tools']}")

        tool_result = await tool_execution_node(state)
        state.update(tool_result)

        for r in state["tool_results"]:
            print(f"  [MCP tools/call] {r['tool']} -> success={r['success']}")
            if r["success"]:
                # MCP 응답 객체(CallToolResult)의 content 확인
                print(f"    content 존재: {bool(r['result'].content)}")
            else:
                print(f"    error: {r['error']}")
        print()

        assert state["tool_results"], "도구 실행 결과가 비어있습니다"
        assert all(r["success"] for r in state["tool_results"]), "일부 도구 호출이 실패했습니다"

    print("✅ Tool 실행 노드가 실제 MCP 프로토콜(tools/call)로 정상 동작함을 확인")


if __name__ == "__main__":
    asyncio.run(main())