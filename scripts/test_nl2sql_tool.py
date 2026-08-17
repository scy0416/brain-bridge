"""
scripts/test_nl2sql_tool.py

nl2sql_tool(question) 캡슐화 함수가 정상 케이스/빈 결과 케이스를
문제없이 처리하는지 최종 확인한다.

사용법:
    docker compose run --rm app python scripts/test_nl2sql_tool.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tools.nl2sql_tool import nl2sql_tool

CASES = [
    "현재 활성 상태인 계약 수는 몇 개야?",
    "2030년에 등록된 고객사 목록을 보여줘",  # 0행 케이스
]


def main():
    for question in CASES:
        print(f"질문: {question}")
        result = nl2sql_tool(question)
        print(f"  success: {result['success']}")
        print(f"  sql: {result['sql']}")
        print(f"  row_count: {result['row_count']}")
        print(f"  rows: {result['rows']}")
        print(f"  note: {result['note']}")
        print()

        assert result["success"] is True
        assert "question" in result and result["question"] == question

    print("✅ nl2sql_tool() 캡슐화 테스트 통과")


if __name__ == "__main__":
    main()