"""
scripts/test_router_schema.py

실제 Ollama 네이티브 tool-calling 응답을 parse_router_decision()으로
파싱해서 RouterDecision(tools/args/reasoning) 스키마가 잘 동작하는지 확인한다.

사용법:
    docker compose run --rm app python scripts/test_router_schema.py
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from router.schema import parse_router_decision

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:e4b")

# MCP 서버에 등록한 3개 도구와 동일한 이름/설명으로 구성 (Router Agent가 실제로 볼 스키마)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "nl2sql_tool",
            "description": "정형(테이블) 데이터베이스에 대한 질문에 답한다. 집계/필터링이 필요한 질문에 사용.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vector_search_tool",
            "description": "비정형 문서(장애보고서/기술문서/회의록/제안서)에서 관련 내용을 검색한다.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_graph_tool",
            "description": "조직/고객/제품 간의 관계(사용/담당/소속/리드 등)를 조회한다.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
]


def call_router(question: str) -> dict:
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": LLM_MODEL,
            "think": False,
            "messages": [{"role": "user", "content": question}],
            "tools": TOOLS,
            "stream": False,
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["message"]


def main():
    test_questions = [
        "서울 지역 매출 상위 5개 고객사를 알려줘",
        "Product-C1 설치 방법이 궁금해",
        "Client-A가 사용 중인 제품 목록은?",
    ]

    for question in test_questions:
        print(f"질문: {question}")
        message = call_router(question)
        decision = parse_router_decision(message)

        print(f"  needs_tools: {decision.needs_tools}")
        print(f"  tools: {[(t.name, t.args) for t in decision.tools]}")
        print(f"  reasoning: {decision.reasoning}")
        print()

        assert isinstance(decision.tools, list)
        for t in decision.tools:
            assert isinstance(t.name, str) and t.name
            assert isinstance(t.args, dict)

    print("✅ RouterDecision 스키마 파싱 검증 완료")


if __name__ == "__main__":
    main()