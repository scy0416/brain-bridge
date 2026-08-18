"""
scripts/test_tool_node_multi.py

Router Agent의 복수 도구 선택이 확률적으로 불안정하다는 걸 이미 확인했으므로,
Router Agent를 거치지 않고 router_tools를 직접 2개짜리로 구성해서
tool_execution_node()가 실제로 MCP 서버에 순차적으로 tools/call을 두 번
날리고 둘 다 정상 처리하는지 직접 검증한다.

사용법:
    docker compose run --rm app python scripts/test_tool_node_multi.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.tool_node import tool_execution_node


async def main():
    # Router Agent 없이, 서로 다른 도구 2개를 직접 지정
    state = {
        "question": "테스트: 단일 요청에서 두 개 도구",
        "router_tools": [
            {"name": "nl2sql_tool", "args": {"question": "현재 활성 상태인 계약 수는 몇 개야?"}},
            {"name": "knowledge_graph_tool", "args": {"question": "Client-A가 사용 중인 제품 목록은?"}},
        ],
    }

    result = await tool_execution_node(state)
    tool_results = result["tool_results"]

    print(f"입력한 도구 수: {len(state['router_tools'])}")
    print(f"실행 결과 수: {len(tool_results)}")
    for r in tool_results:
        print(f"  - {r['tool']}: success={r['success']}")

    assert len(tool_results) == 2, "2개 도구 실행 결과가 모두 나와야 함"
    assert all(r["success"] for r in tool_results), "두 도구 호출이 모두 성공해야 함"
    assert tool_results[0]["tool"] == "nl2sql_tool"
    assert tool_results[1]["tool"] == "knowledge_graph_tool"

    # 단일 도구(1개)도 같은 함수로 문제없이 처리되는지 함께 재확인
    single_state = {
        "question": "단일 도구 테스트",
        "router_tools": [{"name": "vector_search_tool", "args": {"question": "백업 정책은?"}}],
    }
    single_result = await tool_execution_node(single_state)
    assert len(single_result["tool_results"]) == 1
    assert single_result["tool_results"][0]["success"]

    print("\n✅ 단일/복수 도구 분기 모두 동일한 코드 경로로 정상 처리됨을 확인")


if __name__ == "__main__":
    asyncio.run(main())