"""
scripts/test_nl2sql_parse.py

src/nl2sql/parse.py의 extract_sql()이 다양한 LLM 이탈 패턴에서
SQL을 올바르게 추출하는지 확인하는 단위 테스트.

사용법:
    docker compose run --rm app python scripts/test_nl2sql_parse.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl2sql.parse import SQLParseError, extract_sql

EXPECTED_SQL = "SELECT * FROM clients;"

# (설명, 원시 입력, 기대 결과 — None이면 SQLParseError가 나야 함)
CASES = [
    ("이미 깔끔한 SQL", "SELECT * FROM clients;", EXPECTED_SQL),
    ("NO_QUERY 그대로 통과",
     "NO_QUERY", "NO_QUERY"),
    ("```sql 코드블록",
     "```sql\nSELECT * FROM clients;\n```", EXPECTED_SQL),
    ("``` 코드블록 (언어 태그 없음)",
     "```\nSELECT * FROM clients;\n```", EXPECTED_SQL),
    ("앞에 설명 문장이 붙은 경우",
     "네, 아래 쿼리로 조회할 수 있습니다:\nSELECT * FROM clients;", EXPECTED_SQL),
    ("뒤에 설명 문장이 붙은 경우",
     "SELECT * FROM clients; 이 쿼리는 전체 고객사를 조회합니다.", EXPECTED_SQL),
    ("코드블록 앞뒤에 설명까지 겹친 경우",
     "물론입니다.\n```sql\nSELECT * FROM clients;\n```\n이상입니다.", EXPECTED_SQL),
    ("세미콜론 없는 경우 (전체를 그대로 사용)",
     "SELECT * FROM clients", "SELECT * FROM clients"),

    ("SQL을 전혀 찾을 수 없는 경우", "죄송합니다, 답변할 수 없습니다.", None),
]


def main():
    passed = 0
    failed = []

    for desc, raw, expected in CASES:
        try:
            result = extract_sql(raw)
            ok = (expected is not None) and (result == expected)
            status = "OK" if ok else "FAIL"
            print(f"[{status}] {desc} — 기대={expected!r}, 실제={result!r}")
        except SQLParseError as e:
            ok = expected is None
            status = "OK" if ok else "FAIL"
            print(f"[{status}] {desc} — 기대={expected!r}, 실제=SQLParseError({e})")

        if ok:
            passed += 1
        else:
            failed.append(desc)

    print(f"\n{passed}/{len(CASES)} 통과")
    if failed:
        print("실패한 케이스:", failed)
        sys.exit(1)
    print("✅ SQL 파싱 후처리 테스트 전부 통과")


if __name__ == "__main__":
    main()