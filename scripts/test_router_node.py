"""
scripts/test_router_node.py

router_agent_node()를 GraphState와 함께 직접 호출해서 검증한다.
(아직 전체 그래프 배선 전이라, 노드 함수를 단독으로 테스트)
router_agent_node는 이제 MCP 서버에서 실시간으로 도구 스키마를 가져오므로,
mcp-server 컨테이너가 먼저 떠 있어야 한다.

사용법:
    docker compose up -d mcp-server
    docker compose run --rm app python scripts/test_router_node.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent.router_node import router_agent_node

TEST_QUESTIONS = [
    "Product-C1 설치 방법이 궁금해",
    "서울 지역 매출 상위 5개 고객사를 알려줘",
    "Client-A가 사용 중인 제품 목록도 알려주고, 현재 활성 상태인 전체 계약 수도 알려줘",
]


async def main():
    for question in TEST_QUESTIONS:
        state = {"question": question}
        result = await router_agent_node(state)

        print(f"질문: {question}")
        print(f"  router_tools: {result['router_tools']}")
        print()

        assert "router_tools" in result
        assert isinstance(result["router_tools"], list)
        assert len(result["router_tools"]) > 0, "도구가 하나도 선택되지 않았습니다 (되묻기 회귀 가능성)"
        for t in result["router_tools"]:
            assert "name" in t and "args" in t

    print("✅ Router Agent 노드 검증 완료 (MCP 서버에서 도구 스키마 실시간 조회)")


if __name__ == "__main__":
    asyncio.run(main())