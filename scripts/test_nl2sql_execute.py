"""
scripts/test_nl2sql_execute.py

generate_sql → extract_sql → validate_select_only → execute_query를
수동으로 이어서 실행해보는 end-to-end 확인 스크립트.
(아직 nl2sql_tool()로 캡슐화하기 전, 각 조각이 실제로 맞물리는지 확인하는 단계)

사용법:
    docker compose run --rm app python scripts/test_nl2sql_execute.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl2sql.execute import execute_query
from nl2sql.generate import generate_sql
from nl2sql.parse import extract_sql
from nl2sql.safety import validate_select_only

TEST_QUESTION = "현재 활성 상태인 계약 수는 몇 개야?"


def main():
    print(f"질문: {TEST_QUESTION}\n")

    print("[1/4] SQL 생성")
    raw = generate_sql(TEST_QUESTION)
    print(f"    원시 출력: {raw!r}")

    print("\n[2/4] 파싱")
    sql = extract_sql(raw)
    print(f"    추출된 SQL: {sql!r}")

    print("\n[3/4] 안전 검증")
    validated = validate_select_only(sql)
    print(f"    검증 통과: {validated!r}")

    print("\n[4/4] 실행")
    columns, rows = execute_query(validated)
    print(f"    컬럼: {columns}")
    print(f"    결과: {rows}")

    print("\n✅ SQL 생성→파싱→검증→실행 전체 파이프라인 정상 동작")


if __name__ == "__main__":
    main()