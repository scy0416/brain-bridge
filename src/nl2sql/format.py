"""
src/nl2sql/format.py

execute_query()가 반환한 (컬럼명, 행 튜플) 원시 결과를,
Answer Agent가 자연어 답변을 생성할 때 바로 쓸 수 있는 JSON 직렬화 가능한
중간 포맷(레코드 리스트)으로 변환한다.
"""

import datetime
from decimal import Decimal
from typing import Any, List, Tuple

MAX_ROWS = 50  # Answer Agent 프롬프트에 넣기에 과도하게 크지 않도록 상한


def _to_json_safe(value: Any) -> Any:
    """psycopg2가 반환하는 값(Decimal, date, datetime 등)을 JSON 직렬화 가능한 값으로 변환한다."""
    if isinstance(value, Decimal):
        # 정수형 금액이 대부분이라 int로, 소수점이 있으면 float로
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def format_query_result(columns: List[str], rows: List[Tuple], max_rows: int = MAX_ROWS) -> dict:
    """
    쿼리 실행 결과를 자연어 요약(Answer Agent)에 바로 쓸 수 있는 중간 포맷으로 변환한다.

    :param columns: execute_query()가 반환한 컬럼명 리스트
    :param rows: execute_query()가 반환한 행 튜플 리스트
    :param max_rows: 포함할 최대 행 수 (초과분은 잘라내고 truncated 플래그로 표시)
    :return: {
        "row_count": 전체 행 수,
        "columns": 컬럼명 리스트,
        "rows": [{컬럼명: 값, ...}, ...] (JSON 직렬화 가능한 값으로 변환됨, 최대 max_rows개),
        "truncated": max_rows를 넘어서 일부만 포함됐는지 여부,
        "is_empty": 결과가 0행인지 여부
    }
    """
    total_count = len(rows)
    limited_rows = rows[:max_rows]
    is_empty = total_count == 0

    records = [
        {col: _to_json_safe(val) for col, val in zip(columns, row)}
        for row in limited_rows
    ]

    result = {
        "row_count": total_count,
        "columns": columns,
        "rows": records,
        "truncated": total_count > max_rows,
        "is_empty": is_empty,
    }

    # 빈 결과는 "조회 실패"가 아니라 "조건에 맞는 데이터가 없음"이라는 걸
    # Answer Agent가 명확히 구분해서 답변하도록 안내 문구를 별도로 붙인다.
    if is_empty:
        result["note"] = (
            "조회는 정상적으로 실행되었으나 조건에 맞는 데이터가 없습니다. "
            "이 사실을 사용자에게 명확히 안내하고, 데이터가 있다고 추측하거나 지어내지 마세요."
        )

    return result