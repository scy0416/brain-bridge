"""
scripts/test_nl2sql_safety.py

src/nl2sql/safety.py의 validate_select_only()가 안전한 쿼리는 통과시키고
파괴적인 쿼리는 정확히 차단하는지 확인하는 단위 테스트.

사용법:
    docker compose run --rm app python scripts/test_nl2sql_safety.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl2sql.safety import SQLSafetyError, validate_select_only

# (설명, SQL, 통과해야 하는가)
CASES = [
    ("정상 SELECT", "SELECT * FROM clients WHERE region = '서울';", True),
    ("WITH CTE", "WITH t AS (SELECT * FROM sales) SELECT * FROM t;", True),
    ("세미콜론 없는 SELECT", "SELECT count(*) FROM employees", True),

    ("DROP TABLE", "DROP TABLE clients;", False),
    ("DELETE", "DELETE FROM sales WHERE id = 1;", False),
    ("UPDATE", "UPDATE employees SET salary = 0;", False),
    ("INSERT", "INSERT INTO clients (name) VALUES ('hacked');", False),
    ("TRUNCATE", "TRUNCATE TABLE support_tickets;", False),
    ("ALTER", "ALTER TABLE clients ADD COLUMN hacked TEXT;", False),
    ("stacked query (SELECT + DROP)",
     "SELECT * FROM clients; DROP TABLE clients;", False),
    ("SELECT처럼 시작하지만 실제론 아님", "SELECTED_ROWS", False),
    ("빈 문자열", "", False),

    # 컬럼명에 금지 키워드가 부분 포함된 경우 오탐되면 안 됨
    ("컬럼명에 UPDATE 부분 포함 (오탐 방지 확인)",
     "SELECT updated_at FROM clients;", True),
]


def main():
    passed = 0
    failed = []

    for desc, sql, should_pass in CASES:
        try:
            validate_select_only(sql)
            actual_pass = True
        except SQLSafetyError:
            actual_pass = False

        ok = actual_pass == should_pass
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {desc} — 기대={'통과' if should_pass else '차단'}, "
              f"실제={'통과' if actual_pass else '차단'}")
        if ok:
            passed += 1
        else:
            failed.append(desc)

    print(f"\n{passed}/{len(CASES)} 통과")
    if failed:
        print("실패한 케이스:", failed)
        sys.exit(1)
    print("✅ SELECT 검증 필터 테스트 전부 통과")


if __name__ == "__main__":
    main()