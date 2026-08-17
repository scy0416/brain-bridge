"""
src/nl2sql/execute.py

검증을 통과한 SQL을 실제 PostgreSQL에 실행한다. 타임아웃을 걸어서
LLM이 생성한 비효율적인 쿼리(예: 카티전 곱)가 무한정 자원을 잡아먹지 않도록 한다.
"""

from typing import List, Tuple

from graph.age_client import get_connection

QUERY_TIMEOUT_MS = 10_000  # 10초


class SQLExecutionError(Exception):
    """SQL 실행 실패(타임아웃 포함) 시 발생하는 예외."""


def execute_query(sql: str, timeout_ms: int = QUERY_TIMEOUT_MS) -> Tuple[List[str], List[tuple]]:
    """
    검증된 SELECT 쿼리를 실행한다. (safety.validate_select_only()를 먼저 통과시킨 SQL만 넘길 것)

    :param sql: 실행할 SQL (SELECT 또는 WITH...SELECT)
    :param timeout_ms: 쿼리 실행 제한 시간 (밀리초)
    :return: (컬럼명 리스트, 결과 행 리스트)
    :raises SQLExecutionError: 타임아웃 또는 기타 실행 오류 시
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 이 세션에서만 적용되는 쿼리 타임아웃 (다른 커넥션/세션에는 영향 없음)
            cur.execute(f"SET statement_timeout = {timeout_ms};")
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
        conn.commit()
        return columns, rows
    except Exception as e:
        conn.rollback()
        # psycopg2의 타임아웃 에러 메시지에는 "canceling statement due to statement timeout" 포함
        if "statement timeout" in str(e).lower():
            raise SQLExecutionError(f"쿼리 실행 시간 초과 ({timeout_ms}ms): {sql[:100]}...") from e
        raise SQLExecutionError(f"쿼리 실행 실패: {e}") from e
    finally:
        conn.close()