"""
src/graph/entity_extraction.py

질문 텍스트에서 그래프 엔티티(Client/Product/Employee/Department)를 찾아
orig_id로 변환한다.

방식: 정규식 매칭 + DB 역조회 (NER 모델 없이)
- Client/Product: "Client-A", "Product-C1"처럼 구조화된 코드 패턴이라 정규식으로
  후보를 뽑고, DB에서 name으로 정확히 조회해 orig_id를 얻는다.
- Employee/Department: 이름이 자유 형식 한글이라 정규식으로 못 잡으므로,
  DB에 있는 전체 이름 목록을 가져와 질문 문자열에 부분 문자열로 포함되는지
  대조하는 룩업 방식을 쓴다 (별도 NER 모델 없이 로컬 환경에 가볍게 동작).
"""

import re
from typing import Dict, Optional

from graph.age_client import run_cypher

# \b(단어 경계)는 "Client-A가"처럼 영문자 바로 뒤에 한글 조사가 붙으면
# 유니코드 경계 인식이 불안정해 매칭에 실패할 수 있어, 뒤에 영문자/숫자가
# 이어지지 않는지만 확인하는 부정형 전방탐색으로 대체한다.
CLIENT_PATTERN = re.compile(r"Client-[A-Z]{1,2}(?![A-Za-z0-9])")
PRODUCT_PATTERN = re.compile(r"Product-[A-Z]\d(?![A-Za-z0-9])")


def _lookup_orig_id_by_exact_name(conn, label: str, name: str) -> Optional[str]:
    """레이블+정확한 name으로 그래프에서 orig_id를 조회한다."""
    result = run_cypher(
        conn,
        f'MATCH (n:{label} {{name: "{name}"}}) RETURN n.orig_id',
        return_cols="orig_id agtype",
    )
    if not result:
        return None
    return result[0][0]


def _get_all_names(conn, label: str) -> Dict[str, str]:
    """레이블에 속한 모든 정점의 {name: orig_id} 딕셔너리를 가져온다."""
    result = run_cypher(
        conn,
        f"MATCH (n:{label}) RETURN n.name, n.orig_id",
        return_cols="name agtype, orig_id agtype",
    )
    return {name: orig_id for name, orig_id in result}


def extract_entities(conn, question: str) -> Dict[str, Optional[str]]:
    """
    질문 텍스트에서 Client/Product/Employee/Department 엔티티를 찾아
    각각의 orig_id를 반환한다. 못 찾은 타입은 값이 None이다.

    :param conn: age_client.get_connection() 등으로 얻은 커넥션
    :param question: 사용자의 자연어 질문
    :return: {"Client": orig_id 또는 None, "Product": ..., "Employee": ..., "Department": ...}
    """
    entities: Dict[str, Optional[str]] = {
        "Client": None,
        "Product": None,
        "Employee": None,
        "Department": None,
    }

    # 1. Client / Product — 정규식으로 후보 추출 후 DB 역조회
    client_match = CLIENT_PATTERN.search(question)
    if client_match:
        entities["Client"] = _lookup_orig_id_by_exact_name(conn, "Client", client_match.group())

    product_match = PRODUCT_PATTERN.search(question)
    if product_match:
        entities["Product"] = _lookup_orig_id_by_exact_name(conn, "Product", product_match.group())

    # 2. Employee / Department — DB의 전체 이름 목록과 부분 문자열 대조
    #    (긴 이름부터 먼저 검사해서, 짧은 이름이 긴 이름의 부분 문자열인 경우의 오탐을 줄임)
    dept_names = _get_all_names(conn, "Department")
    for name in sorted(dept_names, key=len, reverse=True):
        if name in question:
            entities["Department"] = dept_names[name]
            break

    employee_names = _get_all_names(conn, "Employee")
    for name in sorted(employee_names, key=len, reverse=True):
        if name in question:
            entities["Employee"] = employee_names[name]
            break

    return entities