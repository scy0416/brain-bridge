"""
scripts/test_nl2sql_empty_result.py

실제로 0행이 나오는 질문으로 전체 파이프라인을 돌려서, 빈 결과가
에러 없이 정상적으로 처리되고 Answer Agent용 안내 문구가 붙는지 확인한다.

사용법:
    docker compose run --rm app python scripts/test_nl2sql_empty_result.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl2sql.execute import execute_query
from nl2sql.format import format_query_result
from nl2sql.generate import generate_sql
from nl2sql.parse import extract_sql
from nl2sql.safety import validate_select_only

# 데이터 기간(README 명시: 2024년 1월~2026년 6월)을 벗어난 연도라 0행이 나와야 정상
TEST_QUESTION = "2030년에 등록된 고객사 목록을 보여줘"


def main():
    print(f"질문: {TEST_QUESTION}\n")

    raw = generate_sql(TEST_QUESTION)
    sql = extract_sql(raw)
    validated = validate_select_only(sql)
    print(f"실행 SQL: {validated}\n")

    columns, rows = execute_query(validated)
    formatted = format_query_result(columns, rows)

    print("포맷 결과:")
    print(f"  row_count: {formatted['row_count']}")
    print(f"  is_empty: {formatted['is_empty']}")
    print(f"  rows: {formatted['rows']}")
    print(f"  note: {formatted.get('note')}")

    assert formatted["is_empty"] is True, "0행이 나와야 하는 질문인데 결과가 있습니다 (데이터 확인 필요)"
    assert formatted["row_count"] == 0
    assert formatted["rows"] == []
    assert "note" in formatted, "빈 결과에 안내 문구(note)가 없습니다"

    print("\n✅ 빈 결과 케이스 정상 처리 확인")


if __name__ == "__main__":
    main()