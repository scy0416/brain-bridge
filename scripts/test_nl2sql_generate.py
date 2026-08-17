"""
scripts/test_nl2sql_generate.py

단일 질문으로 SQL 생성을 테스트하고, 문법 오류가 없는지 수동으로 확인하기 위한 스크립트.
(아직 실제 DB 실행은 하지 않음 — 생성된 SQL 텍스트만 눈으로 검토)

사용법:
    docker compose run --rm app python scripts/test_nl2sql_generate.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl2sql.generate import generate_sql

TEST_QUESTION = "서울 지역 매출 상위 5개 고객사를 알려줘"


def main():
    print(f"질문: {TEST_QUESTION}\n")
    sql = generate_sql(TEST_QUESTION)
    print("생성된 SQL:")
    print("-" * 60)
    print(sql)
    print("-" * 60)
    print("\n위 SQL을 눈으로 확인하세요 — 다음 항목들을 점검:")
    print("  - SELECT 문인가?")
    print("  - 스키마에 실제 존재하는 테이블/컬럼만 썼는가?")
    print("  - 설명/마크다운 코드블록 없이 순수 SQL만 나왔는가?")
    print("  - 세미콜론으로 끝나는가?")


if __name__ == "__main__":
    main()