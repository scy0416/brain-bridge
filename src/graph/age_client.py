"""
Apache AGE Cypher 실행 헬퍼

전용 드라이버(apache-age-python) 대신 psycopg2로 cypher() SQL 함수를
직접 호출하는 raw SQL 래핑 방식을 사용한다.
(결정 근거: apache-age-python이 0.0.7 버전으로 아직 미성숙하고 유지보수가
 활발하지 않아 보여, 이미 프로젝트 전반에 쓰는 psycopg2로 통일함)
"""

import json
import os
import re
from contextlib import contextmanager
from typing import Any, List, Optional, Tuple

import psycopg2

GRAPH_NAME = os.environ.get("AGE_GRAPH_NAME", "companyx_graph")

_AGTYPE_SUFFIX_RE = re.compile(r"::(vertex|edge|path)$")


def get_connection():
    """환경변수(.env)로 postgres 커넥션을 생성한다."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


@contextmanager
def age_session(conn):
    """
    AGE는 세션(커넥션)마다 LOAD 'age'와 search_path 설정이 필요하다.
    커넥션을 받아서 매번 이 초기화를 보장해주는 컨텍스트 매니저.
    """
    with conn.cursor() as cur:
        cur.execute("LOAD 'age';")
        cur.execute('SET search_path = ag_catalog, "$user", public;')
    yield conn


def parse_agtype(value: str) -> Any:
    """
    agtype 결과 문자열(예: '{"id": ..., "label": "Client", "properties": {...}}::vertex')을
    파이썬 객체로 파싱한다. ::vertex/::edge/::path 접미사를 제거하고 JSON으로 로드한다.
    """
    if value is None:
        return None
    cleaned = _AGTYPE_SUFFIX_RE.sub("", value)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 숫자/불리언 등 단순 스칼라 agtype은 JSON이 아닐 수 있으므로 원본 문자열 반환
        return cleaned


def to_cypher_literal(value: Any) -> str:
    """파이썬 값을 Cypher 리터럴 문자열로 변환한다. (고정 데이터셋 대상이라 단순 이스케이프로 충분)"""
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def to_cypher_map(props: dict) -> str:
    """{key: value, ...} 형태의 Cypher 맵 리터럴 문자열을 만든다."""
    parts = [f"{key}: {to_cypher_literal(val)}" for key, val in props.items()]
    return "{" + ", ".join(parts) + "}"


def run_cypher(
    conn,
    cypher_query: str,
    return_cols: str = "v agtype",
    graph_name: str = GRAPH_NAME,
    params: Optional[dict] = None,
) -> List[Tuple[Any, ...]]:
    """
    Cypher 쿼리를 실행하고, 각 결과 컬럼을 parse_agtype으로 파싱해서 반환한다.

    :param conn: psycopg2 커넥션
    :param cypher_query: Cypher 쿼리 문자열 (예: "MATCH (n:Client) RETURN n")
    :param return_cols: cypher() 함수의 AS 절 (예: "v agtype", "a agtype, b agtype")
    :param graph_name: 대상 그래프 이름
    :param params: 안전하게 값을 바인딩하고 싶을 때 사용 (문자열 포매팅으로 직접
                    삽입하지 말 것 — Cypher 인젝션 방지를 위해 %(key)s 플레이스홀더 사용 권장)
    :return: 각 row가 파싱된 값들의 튜플인 리스트
    """
    with age_session(conn):
        with conn.cursor() as cur:
            sql = f"""
                SELECT * FROM cypher(%(graph_name)s, $$
                    {cypher_query}
                $$) AS ({return_cols});
            """
            query_params = {"graph_name": graph_name, **(params or {})}
            cur.execute(sql, query_params)
            rows = cur.fetchall()

    parsed_rows = []
    for row in rows:
        parsed_rows.append(tuple(parse_agtype(col) for col in row))
    return parsed_rows


def create_graph_if_not_exists(conn, graph_name: str = GRAPH_NAME) -> None:
    """그래프가 없으면 생성한다 (있으면 조용히 넘어감)."""
    with age_session(conn):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM ag_catalog.ag_graph WHERE name = %s;",
                (graph_name,),
            )
            (exists_count,) = cur.fetchone()
            if exists_count == 0:
                cur.execute("SELECT create_graph(%s);", (graph_name,))
        conn.commit()