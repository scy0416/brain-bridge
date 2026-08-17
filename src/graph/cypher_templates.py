"""
src/graph/cypher_templates.py

지식 그래프 7개 관계 라벨에 대한 파라미터화된 Cypher 쿼리 템플릿.
자연어→Cypher를 LLM에게 매번 생성시키는 대신, 검증된 템플릿에
엔티티 값만 채워 넣는 방식(템플릿 기반)을 사용한다.
(결정 근거: AGE 고유의 Cypher 문법 제약을 LLM이 매번 재현하기 어렵고,
 questions.json 분석 결과 패턴이 유한하고 예측 가능했기 때문)
"""

from typing import Optional

from graph.age_client import to_cypher_literal

# 관계 라벨별 (출발 정점 레이블, 도착 정점 레이블, 정방향 설명, 역방향 설명)
# schema.md / edges.json 실측 분포 기준
RELATION_INFO = {
    "USES": ("Client", "Product", "고객사가 사용하는 제품", "제품을 사용하는 고객사"),
    "MANAGES_ACCOUNT": ("Employee", "Client", "직원이 담당하는 고객사", "고객사를 담당하는 직원"),
    "BELONGS_TO": ("Employee", "Department", "직원의 소속 부서", "부서 소속 직원"),
    "HAS_PROJECT": ("Client", "Project", "고객사의 프로젝트", "프로젝트를 보유한 고객사"),
    "LEADS": ("Employee", "Project", "직원이 이끄는 프로젝트", "프로젝트를 이끄는 직원"),
    "REPORTED_ISSUE": ("Client", "Product", "고객사가 제기한 이슈 대상 제품", "이슈가 제기된 제품을 보고한 고객사"),
    "HEAD_IS": ("Department", "Employee", "부서의 부서장", "부서장을 맡은 부서"),
}


def one_hop_forward(relation: str, source_orig_id: str) -> str:
    """
    정방향 1-hop: 특정 출발 정점 → 관계 → 도착 정점들을 조회한다.
    예: USES + client_1 → "client_1이 사용하는 제품 목록"
    """
    source_label, target_label, _, _ = RELATION_INFO[relation]
    return (
        f"MATCH (a:{source_label} {{orig_id: {to_cypher_literal(source_orig_id)}}})"
        f"-[:{relation}]->(b:{target_label}) "
        f"RETURN b"
    )


def one_hop_reverse(relation: str, target_orig_id: str) -> str:
    """
    역방향 1-hop: 특정 도착 정점 ← 관계 ← 출발 정점들을 조회한다.
    예: USES + product_1 → "product_1을 사용하는 고객사 목록"
    """
    source_label, target_label, _, _ = RELATION_INFO[relation]
    return (
        f"MATCH (a:{source_label})-[:{relation}]->"
        f"(b:{target_label} {{orig_id: {to_cypher_literal(target_orig_id)}}}) "
        f"RETURN a"
    )


def relation_count_by_target(relation: str, limit: int = 5) -> str:
    """
    관계 카운트 집계 (도착 정점 기준). 예: "이슈가 가장 많은 제품 상위 5개"
    (REPORTED_ISSUE에서 도착=Product 기준으로 건수를 세는 패턴)
    """
    source_label, target_label, _, _ = RELATION_INFO[relation]
    return (
        f"MATCH (a:{source_label})-[:{relation}]->(b:{target_label}) "
        f"WITH b.orig_id AS orig_id, b.name AS name, count(*) AS cnt "
        f"RETURN name, cnt "
        f"ORDER BY cnt DESC "
        f"LIMIT {int(limit)}"
    )


def relation_count_by_source(relation: str, limit: int = 5) -> str:
    """
    관계 카운트 집계 (출발 정점 기준). 예: "가장 많은 고객을 담당하는 직원 상위 5명"
    (MANAGES_ACCOUNT에서 출발=Employee 기준으로 건수를 세는 패턴)
    """
    source_label, target_label, _, _ = RELATION_INFO[relation]
    return (
        f"MATCH (a:{source_label})-[:{relation}]->(b:{target_label}) "
        f"WITH a.orig_id AS orig_id, a.name AS name, count(*) AS cnt "
        f"RETURN name, cnt "
        f"ORDER BY cnt DESC "
        f"LIMIT {int(limit)}"
    )


def two_hop_client_projects_via_product(product_orig_id: str) -> str:
    """
    2-hop: 특정 제품을 사용하는 고객사들의 프로젝트 목록.
    (questions.json 실측 패턴: "Product-D1 사용 고객의 프로젝트")
    Product <-[:USES]- Client -[:HAS_PROJECT]-> Project
    """
    return (
        f"MATCH (c:Client)-[:USES]->(p:Product {{orig_id: {to_cypher_literal(product_orig_id)}}}), "
        f"(c)-[:HAS_PROJECT]->(proj:Project) "
        f"RETURN c.name AS client_name, proj.name AS project_name"
    )


def two_hop_generic(
    relation_1: str,
    relation_1_direction: str,
    anchor_orig_id: str,
    relation_2: str,
    relation_2_direction: str,
) -> Optional[str]:
    """
    범용 2-hop 헬퍼: anchor 정점에서 relation_1을 타고 중간 정점을 찾고,
    그 중간 정점에서 relation_2를 타고 최종 정점까지 조회한다.
    two_hop_client_projects_via_product처럼 자주 쓰이는 조합이 아닌
    새로운 2-hop 질문이 나왔을 때 대응하기 위한 폴백.

    :param relation_1_direction: "forward" | "reverse" — anchor 기준 relation_1의 방향
    :param relation_2_direction: "forward" | "reverse" — 중간 정점 기준 relation_2의 방향
    :return: Cypher 쿼리 문자열, 조합이 라벨 불일치 등으로 성립 불가능하면 None
    """
    src1, tgt1, _, _ = RELATION_INFO[relation_1]
    src2, tgt2, _, _ = RELATION_INFO[relation_2]

    if relation_1_direction == "forward":
        anchor_label, mid_label_1 = src1, tgt1
        hop1 = f"(a:{anchor_label} {{orig_id: {to_cypher_literal(anchor_orig_id)}}})-[:{relation_1}]->(m)"
    else:
        anchor_label, mid_label_1 = tgt1, src1
        hop1 = f"(m)-[:{relation_1}]->(a:{anchor_label} {{orig_id: {to_cypher_literal(anchor_orig_id)}}})"

    if relation_2_direction == "forward":
        mid_label_2, final_label = src2, tgt2
        hop2 = f"(m)-[:{relation_2}]->(b:{final_label})"
    else:
        mid_label_2, final_label = tgt2, src2
        hop2 = f"(b:{final_label})-[:{relation_2}]->(m)"

    if mid_label_1 != mid_label_2:
        return None  # 중간 정점 레이블이 안 맞으면 이 조합은 성립하지 않음

    return f"MATCH {hop1}, {hop2} RETURN a, b"