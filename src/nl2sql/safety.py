"""
src/nl2sql/safety.py

LLM이 생성한 SQL이 실제로 실행되기 전에 거치는 안전장치.
SELECT(또는 SELECT로 끝나는 WITH CTE)만 허용하고, 데이터를 변경/삭제하거나
여러 문장을 이어붙이는(stacked query) 시도를 차단한다.
"""

import re

FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE",
    "GRANT", "REVOKE", "EXECUTE", "CALL", "COPY", "VACUUM", "REINDEX",
    "MERGE", "REPLACE", "LOCK",
]

# 각 키워드를 단어 경계 기준으로 매칭 (예: "UPDATED_AT" 컬럼명이 UPDATE로 오탐되지 않도록)
FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE
)

ALLOWED_START_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


class SQLSafetyError(Exception):
    """생성된 SQL이 안전 검증을 통과하지 못했을 때 발생하는 예외."""


def validate_select_only(sql: str) -> str:
    """
    SQL 텍스트가 안전한 단일 SELECT(또는 WITH ... SELECT) 문인지 검증한다.
    통과하면 앞뒤 공백을 정리한 SQL을 그대로 반환하고, 아니면 SQLSafetyError를 발생시킨다.

    :param sql: 검증할 SQL 텍스트
    :return: 검증을 통과한 SQL (원본에서 앞뒤 공백만 제거)
    :raises SQLSafetyError: SELECT/WITH로 시작하지 않거나, 금지 키워드가 있거나,
                             세미콜론으로 구분된 여러 문장이 있는 경우
    """
    if not sql or not sql.strip():
        raise SQLSafetyError("빈 SQL은 실행할 수 없습니다")

    cleaned = sql.strip()

    # 1. SELECT 또는 WITH(CTE)로 시작해야 함
    if not ALLOWED_START_RE.match(cleaned):
        raise SQLSafetyError(
            f"SELECT 문이 아닙니다 (SELECT 또는 WITH로 시작해야 함): {cleaned[:50]}..."
        )

    # 2. 금지 키워드(데이터 변경/삭제/DDL 등) 포함 여부
    forbidden_found = FORBIDDEN_RE.findall(cleaned)
    if forbidden_found:
        raise SQLSafetyError(
            f"금지된 키워드가 포함되어 있습니다: {set(k.upper() for k in forbidden_found)}"
        )

    # 3. 여러 문장을 세미콜론으로 이어붙인 stacked query 차단
    #    (끝에 세미콜론 하나는 허용, 그 뒤에 추가 내용이 있으면 차단)
    trailing = cleaned.rstrip()
    if trailing.endswith(";"):
        body = trailing[:-1]
    else:
        body = trailing
    if ";" in body:
        raise SQLSafetyError("세미콜론으로 구분된 여러 SQL 문장은 허용되지 않습니다 (단일 쿼리만 실행 가능)")

    return cleaned