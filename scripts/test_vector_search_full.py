"""
scripts/test_vector_search_full.py

data/questions.json의 vector_search 타입 질문 10개 전체를 vector_search_tool()로
테스트하고, hint(기대 근거)와 실제 1위 결과를 대조한다.

사용법:
    docker compose run --rm app python scripts/test_vector_search_full.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools.vector_search_tool import vector_search_tool

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        all_questions = json.load(f)

    vector_questions = [q for q in all_questions if q["tool"] == "vector_search"]
    print(f"==> vector_search 타입 질문 {len(vector_questions)}개 테스트\n")

    for i, q in enumerate(vector_questions, start=1):
        question = q["q"]
        hint = q["hint"]

        result = vector_search_tool(question, k=3)
        top = result["results"][0] if result["results"] else None

        print(f"[{i}/10] 질문: {question}")
        print(f"       힌트: {hint}")
        if top:
            print(f"       1위: {top['doc_id']} ({top['type']}) distance={top['distance']:.4f}")
            print(f"            {top['title_path']}")
            print(f"            {top['content'][:70]}...")
        else:
            print("       ⚠️  결과 없음")
        print()

    print("✅ vector_search 10개 질문 테스트 완료 — 위 결과를 힌트와 대조해서 수작업 판정하세요")


if __name__ == "__main__":
    main()