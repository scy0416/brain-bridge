"""
scripts/test_kg_tool.py

knowledge_graph_tool(question) 하나로 questions.json의 knowledge_graph
10개 질문 전체를 자동 라우팅해서 처리한다 (더 이상 수동 매핑 없음).

사용법:
    docker compose run --rm app python scripts/test_kg_tool.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools.knowledge_graph_tool import knowledge_graph_tool

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        all_questions = json.load(f)

    kg_questions = [q for q in all_questions if q["tool"] == "knowledge_graph"]
    print(f"==> knowledge_graph_tool()로 {len(kg_questions)}개 질문 자동 라우팅 테스트\n")

    success_count = 0
    for i, q in enumerate(kg_questions, start=1):
        question = q["q"]
        hint = q["hint"]
        result = knowledge_graph_tool(question)

        status = "✅" if result["success"] else "⚠️ "
        print(f"[{i}/{len(kg_questions)}] {status} 질문: {question}")
        print(f"       힌트: {hint}")
        print(f"       query_type: {result['query_type']}, relation: {result['relation']}, "
              f"count: {result['count']}")
        if result["results"]:
            print(f"       결과 샘플: {result['results'][:2]}")
        if result["note"]:
            print(f"       note: {result['note']}")
        print()

        if result["success"] and not result["is_empty"]:
            success_count += 1

    print(f"==> {success_count}/{len(kg_questions)}개 질문에서 실제 결과 도출 성공")
    print("(나머지는 의도된 한계 사례(예: 데이터에 없는 서사적 이름) 또는 실패 — note 참고)")


if __name__ == "__main__":
    main()