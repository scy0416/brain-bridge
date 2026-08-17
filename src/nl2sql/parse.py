"""
src/nl2sql/parse.py

LLM이 프롬프트 지시(순수 SQL만 출력)를 완벽히 지키지 않았을 때를 대비한 후처리.
마크다운 코드블록에 SQL을 감싸거나, 앞뒤에 설명 문장을 붙이는 흔한 이탈 패턴에서
실제 SQL 부분만 정규식으로 뽑아낸다.
"""

import re

NO_QUERY_MARKER = "NO_QUERY"

# ```sql ... ``` 또는 ``` ... ``` 코드블록
CODE_FENCE_RE = re.compile(r"```(?:sql)?\s*\n?(.*?)```", re.IGNORECASE | re.DOTALL)

# SELECT 또는 WITH로 시작하는 지점을 찾기 위한 패턴
SQL_START_RE = re.compile(r"(SELECT|WITH)\b", re.IGNORECASE)


class SQLParseError(Exception):
    """응답에서 SQL을 추출할 수 없을 때 발생하는 예외."""


def extract_sql(raw: str) -> str:
    """
    LLM 원시 출력에서 실행 가능한 SQL 텍스트만 추출한다.

    처리 순서:
    1. 정확히 "NO_QUERY"인 경우 그대로 반환 (호출한 쪽에서 별도 처리)
    2. 마크다운 코드블록(```sql ... ``` 등)이 있으면 그 안의 내용을 사용
    3. 코드블록이 없으면, 첫 SELECT/WITH 등장 지점부터 끝까지를 후보로 삼음
    4. 후보 텍스트에서 첫 세미콜론까지만 잘라내어(그 뒤의 설명 문장 등을 제거) 반환
       세미콜론이 없으면 후보 텍스트 전체를 그대로 사용

    :param raw: LLM이 반환한 원시 텍스트
    :raises SQLParseError: SELECT/WITH를 어디에서도 찾지 못한 경우
    """
    text = raw.strip()

    if text == NO_QUERY_MARKER:
        return NO_QUERY_MARKER

    # 1. 코드블록 우선 시도
    fence_match = CODE_FENCE_RE.search(text)
    candidate = fence_match.group(1).strip() if fence_match else text

    # 2. 코드블록이 없거나, 코드블록 안에도 SQL 시작점이 없으면 원문 전체에서 탐색
    start_match = SQL_START_RE.search(candidate)
    if not start_match:
        start_match = SQL_START_RE.search(text)
        candidate = text

    if not start_match:
        raise SQLParseError(f"응답에서 SQL(SELECT/WITH)을 찾을 수 없습니다: {raw[:100]}...")

    sql_body = candidate[start_match.start():]

    # 3. 세미콜론 뒤에 붙은 설명 문장 등을 제거 (첫 세미콜론까지만 사용)
    semicolon_idx = sql_body.find(";")
    if semicolon_idx != -1:
        sql_body = sql_body[: semicolon_idx + 1]

    return sql_body.strip()