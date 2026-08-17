"""
src/graph/kg_query.py

cypher_templates.py의 템플릿을 실제로 실행하고, agtype 결과(run_cypher가 이미
파싱해준 것)에서 필요한 정보만 깔끔한 파이썬 dict/list로 뽑아내는 실행 wrapper.
age_client.run_cypher()(Phase 5에서 만든 헬퍼)를 그대로 재사용한다.
"""

from typing import List

from graph.age_client import run_cypher
from graph.cypher_templates import (
    one_hop_forward,
    one_hop_reverse,
    relation_count_by_source,
    relation_count_by_target,
    two_hop_client_projects_via_product,
)
from graph.kg_format import format_kg_result


def _vertex_to_dict(vertex: dict) -> dict:
    """run_cypher가 반환한 파싱된 정점(dict: id/label/properties)에서 properties만 꺼낸다."""
    props = dict(vertex.get("properties", {}))
    props["_label"] = vertex.get("label")
    return props


def query_one_hop_forward(conn, relation: str, source_orig_id: str) -> dict:
    """정방향 1-hop 실행: 특정 출발 정점과 연결된 도착 정점 목록을 반환한다."""
    cypher = one_hop_forward(relation, source_orig_id)
    rows = run_cypher(conn, cypher, return_cols="b agtype")
    results = [_vertex_to_dict(row[0]) for row in rows]
    return format_kg_result(results, "one_hop_forward", relation=relation)


def query_one_hop_reverse(conn, relation: str, target_orig_id: str) -> dict:
    """역방향 1-hop 실행: 특정 도착 정점과 연결된 출발 정점 목록을 반환한다."""
    cypher = one_hop_reverse(relation, target_orig_id)
    rows = run_cypher(conn, cypher, return_cols="a agtype")
    results = [_vertex_to_dict(row[0]) for row in rows]
    return format_kg_result(results, "one_hop_reverse", relation=relation)


def query_count_by_target(conn, relation: str, limit: int = 5) -> dict:
    """관계 카운트 집계(도착 정점 기준): [{"name": ..., "count": ...}, ...] 반환."""
    cypher = relation_count_by_target(relation, limit=limit)
    rows = run_cypher(conn, cypher, return_cols="name agtype, cnt agtype")
    results = [{"name": name, "count": count} for name, count in rows]
    return format_kg_result(results, "count_by_target", relation=relation)


def query_count_by_source(conn, relation: str, limit: int = 5) -> dict:
    """관계 카운트 집계(출발 정점 기준): [{"name": ..., "count": ...}, ...] 반환."""
    cypher = relation_count_by_source(relation, limit=limit)
    rows = run_cypher(conn, cypher, return_cols="name agtype, cnt agtype")
    results = [{"name": name, "count": count} for name, count in rows]
    return format_kg_result(results, "count_by_source", relation=relation)


def query_two_hop_client_projects_via_product(conn, product_orig_id: str) -> dict:
    """2-hop 실행: 특정 제품을 사용하는 고객사들의 프로젝트 목록을 반환한다."""
    cypher = two_hop_client_projects_via_product(product_orig_id)
    rows = run_cypher(conn, cypher, return_cols="client_name agtype, project_name agtype")
    results = [{"client_name": c, "project_name": p} for c, p in rows]
    return format_kg_result(results, "two_hop", relation="USES+HAS_PROJECT")