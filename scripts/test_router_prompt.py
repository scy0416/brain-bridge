"""
scripts/test_router_prompt.py

Router Agent 시스템 프롬프트(build_system_prompt)를 적용했을 때,
지난번 발견했던 "도구 호출 없이 되묻는" 문제가 해결됐는지 재검증한다.

사용법:
    docker compose run --rm app python scripts/test_router_prompt.py
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from router.prompt import build_system_prompt
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

# 지난번 도구 호출 없이 되물었던 바로 그 질문 포함
TEST_QUESTIONS = [
    "Product-C1 설치 방법이 궁금해",  # 지난번 실패 사례 재현
    "서울 지역 매출 상위 5개 고객사를 알려줘",
    "Client-A가 사용 중인 제품 목록은?",
]


def call_router(question: str) -> dict:
    system_prompt = build_system_prompt(question)
    response = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": LLM_MODEL,
            "think": False,
            "messages": [
                {"role": "system", "content": system_prompt},
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
    all_called_tools = True

    for question in TEST_QUESTIONS:
        print(f"질문: {question}")
        message = call_router(question)
        decision = parse_router_decision(message)

        print(f"  needs_tools: {decision.needs_tools}")
        print(f"  tools: {[(t.name, t.args) for t in decision.tools]}")
        if decision.reasoning:
            print(f"  reasoning(비어있지 않음, 확인 필요): {decision.reasoning}")
        print()

        if not decision.needs_tools:
            all_called_tools = False

    if all_called_tools:
        print("✅ 모든 질문에서 도구 호출 발생 — 되묻기 문제 해결 확인")
    else:
        print("⚠️  일부 질문에서 여전히 도구 호출 없이 넘어감 — 프롬프트 추가 보강 필요")


if __name__ == "__main__":
    main()