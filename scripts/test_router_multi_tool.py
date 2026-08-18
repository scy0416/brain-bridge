"""
scripts/test_router_multi_tool.py

한 질문에 서로 다른 두 도구가 동시에 필요한 "복합 질문"을 던져서,
RouterDecision.tools가 실제로 여러 개의 ToolCall을 담을 수 있는지 확인한다.

사용법:
    docker compose run --rm app python scripts/test_router_multi_tool.py
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from router.schema import parse_router_decision

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:e4b")

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

# 의도적으로 서로 다른 두 도구가 필요하도록 구성한 복합 질문
COMPOUND_QUESTIONS = [
    "Client-A가 사용 중인 제품 목록도 알려주고, 현재 활성 상태인 전체 계약 수도 알려줘",
    "Product-C1 설치 방법을 알려주고, Product-C1을 사용하는 고객사 목록도 같이 보여줘",
]


def call_router(question: str) -> dict:
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": LLM_MODEL,
            "think": False,
            "messages": [
                {
                    "role": "system",
                    "content": "사용자 질문에 답하기 위해 필요한 도구를 모두 호출하세요. "
                    "질문에 여러 요청이 섞여 있으면 각각에 필요한 도구를 전부 호출해도 됩니다.",
                },
                {"role": "user", "content": question},
            ],
            "tools": TOOLS,
            "stream": False,
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["message"]


def main():
    for question in COMPOUND_QUESTIONS:
        print(f"질문: {question}")
        message = call_router(question)
        decision = parse_router_decision(message)

        print(f"  호출된 도구 수: {len(decision.tools)}")
        for t in decision.tools:
            print(f"    - {t.name}({t.args})")
        print()

    print("(참고: 소형 모델이라 매번 2개를 다 부르지 않을 수 있음 — 결과를 보고 판단)")


if __name__ == "__main__":
    main()