"""
src/graph/kg_format.py

kg_query.py의 각 함수(1-hop/2-hop/집계)가 반환하는 서로 다른 모양의 결과를,
Answer Agent가 일관되게 다룰 수 있는 하나의 포맷으로 감싼다.
(nl2sql의 format_query_result(), vector_search_tool의 결과 봉투와 같은 스타일)
"""

from typing import List


def format_kg_result(results: List[dict], query_type: str, relation: str = None) -> dict:
    """
    kg_query.py 함수들의 결과를 자연어 답변용 중간 포맷으로 변환한다.

    :param results: kg_query.py의 query_* 함수가 반환한 dict 리스트
                     (정점 결과: {"orig_id":.., "name":.., ..., "_label":..} 형태
                      집계 결과: {"name":.., "count":..} 형태)
    :param query_type: "one_hop_forward" | "one_hop_reverse" | "count_by_target"
                        | "count_by_source" | "two_hop"
    :param relation: 사용된 관계 라벨 (있으면 함께 기록, 디버깅/로깅용)
    :return: {
        "query_type": query_type,
        "relation": relation,
        "count": 결과 개수,
        "results": 결과 리스트 (그대로),
        "is_empty": 결과가 0개인지 여부,
        "note": 빈 결과일 때 Answer Agent에게 줄 안내 문구 (없으면 None)
    }
    """
    is_empty = len(results) == 0

    note = None
    if is_empty:
        note = (
            "그래프 조회는 정상적으로 실행되었으나 조건에 맞는 관계/데이터가 없습니다. "
            "이 사실을 사용자에게 명확히 안내하고, 데이터가 있다고 추측하거나 지어내지 마세요."
        )

    return {
        "query_type": query_type,
        "relation": relation,
        "count": len(results),
        "results": results,
        "is_empty": is_empty,
        "note": note,
    }