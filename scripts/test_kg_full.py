"""
scripts/test_kg_full.py

data/questions.json의 knowledge_graph 타입 질문 10개를, 관계 라벨을 질문
문자열에서 규칙 기반으로 추측 + entity_extraction으로 엔티티를 뽑아
kg_query.py의 적절한 함수로 실행해본다.

이 스크립트는 아직 knowledge_graph_tool()로 캡슐화하기 전, 각 조각(엔티티
추출/템플릿/실행/포맷)이 실제 10개 질문에 대해 맞물려 동작하는지 확인하는
수동 연결 테스트다. 질문→관계 자동 판단 로직 자체는 다음 캡슐화 단계에서
좀 더 정교하게 다듬을 예정이라, 여기서는 질문마다 어떤 함수를 호출해야
하는지 수동으로 매핑해서 각 조각의 동작만 검증한다.

사용법:
    docker compose run --rm app python scripts/test_kg_full.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from graph.age_client import get_connection
from graph.entity_extraction import extract_entities
from graph.kg_query import (
    query_count_by_source,
    query_count_by_target,
    query_one_hop_forward,
    query_one_hop_reverse,
    query_two_hop_client_projects_via_product,
)

QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        all_questions = json.load(f)

    kg_questions = [q for q in all_questions if q["tool"] == "knowledge_graph"]
    print(f"==> knowledge_graph 타입 질문 {len(kg_questions)}개 테스트\n")

    conn = get_connection()

    for i, q in enumerate(kg_questions, start=1):
        question = q["q"]
        hint = q["hint"]
        print(f"[{i}/{len(kg_questions)}] 질문: {question}")
        print(f"       힌트: {hint}")

        entities = extract_entities(conn, question)
        found = {k: v for k, v in entities.items() if v}
        print(f"       추출된 엔티티: {found}")

        # 질문별로 어떤 kg_query 함수/관계를 써야 하는지는 힌트를 참고해 수동 매핑
        # (실제 자동 판단 로직은 다음 캡슐화 단계에서 구현)
        result = None
        if i == 1:  # Client-A가 사용 중인 제품 목록은?
            result = query_one_hop_forward(conn, "USES", entities["Client"])
        elif i == 2:  # Product-C1을 사용하는 고객사는 어디야?
            result = query_one_hop_reverse(conn, "USES", entities["Product"])
        elif i == 3:  # 클라우드사업부 소속 직원들은 누구야?
            result = query_one_hop_reverse(conn, "BELONGS_TO", entities["Department"])
        elif i == 4:  # 서울물산 담당 엔지니어는 누구야?
            # 참고: 실제 데이터의 고객사명은 "Client-A" 형식 코드뿐이라
            # "서울물산"처럼 서사적 이름은 정규식으로 매칭되지 않는 게 정상.
            # 이런 케이스는 순수 정규식/룩업만으로는 한계가 있다는 걸 보여주는 예시.
            if not entities.get("Client"):
                print("       ⚠️  '서울물산'은 실제 고객사 코드(Client-X)와 매칭되지 않음 "
                      "(정규식 기반 추출의 한계 사례)\n")
                continue
            result = query_one_hop_reverse(conn, "MANAGES_ACCOUNT", entities["Client"])
        elif i == 5:  # Product-D1 제품과 관련된 프로젝트는? (2-hop)
            result = query_two_hop_client_projects_via_product(conn, entities["Product"])
        elif i == 6:  # 기술 지원 이슈가 가장 많은 제품은?
            result = query_count_by_target(conn, "REPORTED_ISSUE", limit=5)
        elif i == 7:  # 경영지원팀 팀장은 누구야?
            result = query_one_hop_forward(conn, "HEAD_IS", entities["Department"])
        elif i == 8:  # 진행 중인 프로젝트를 이끄는 직원 목록 (별도 처리 필요, 여기선 스킵)
            print("       (LEADS 전체 목록 — 별도 쿼리 필요, 이번 검증에서는 스킵)\n")
            continue
        elif i == 9:  # Product-S1 관련 고객 이슈 현황은?
            result = query_one_hop_reverse(conn, "REPORTED_ISSUE", entities["Product"])
        elif i == 10:  # 가장 많은 고객을 담당하는 직원은?
            result = query_count_by_source(conn, "MANAGES_ACCOUNT", limit=5)

        if result is not None:
            print(f"       결과 (count={result['count']}): {result['results'][:3]}")
            if result["is_empty"]:
                print(f"       ⚠️  빈 결과: {result['note']}")
        print()

    conn.close()
    print("✅ KG 10개 질문 수동 연결 테스트 완료")


if __name__ == "__main__":
    main()