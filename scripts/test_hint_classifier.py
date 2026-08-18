"""
scripts/test_hint_classifier.py

data/questions.json 30개 전체에 대해 hint_classifier.classify()의
1위 제안 도구가 정답 도구와 일치하는지 확인한다 (참고용 힌트의 baseline 정확도 측정).

사용법:
    docker compose run --rm app python scripts/test_hint_classifier.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from router.hint_classifier import classify

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")

TOOL_NAME_MAP = {
    "nl2sql": "nl2sql_tool",
    "vector_search": "vector_search_tool",
    "knowledge_graph": "knowledge_graph_tool",
}


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    correct = 0
    by_confidence = {"high": [0, 0], "medium": [0, 0], "low": [0, 0]}  # [맞음, 전체]

    for q in questions:
        question = q["q"]
        expected = TOOL_NAME_MAP[q["tool"]]

        result = classify(question)
        top_tool = result["suggested_tools"][0] if result["suggested_tools"] else None
        confidence = result["confidence"]

        is_correct = top_tool == expected
        correct += is_correct
        by_confidence[confidence][1] += 1
        by_confidence[confidence][0] += is_correct

        status = "OK" if is_correct else "MISS"
        print(f"[{status}] ({confidence}) {question}")
        print(f"       기대={expected}, 1위 제안={top_tool}, "
              f"전체 제안={result['suggested_tools']}, 매칭={result['matched_keywords']}")

    print(f"\n전체 정확도(1위 제안 기준): {correct}/{len(questions)}")
    print("신뢰도별 정확도:")
    for conf, (ok, total) in by_confidence.items():
        if total:
            print(f"  {conf}: {ok}/{total} ({ok/total*100:.0f}%)")


if __name__ == "__main__":
    main()