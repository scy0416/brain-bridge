"""
src/tools/knowledge_graph_tool.py

질문(자연어 문자열)을 받아, 규칙 기반으로 관계 라벨/조회 유형을 판단하고
엔티티를 추출해서 적절한 그래프 템플릿을 실행하는 최종 도구 함수.
Phase 11에서 MCPServer에 그대로 등록될 인터페이스.
"""

from typing import Optional

from graph.age_client import get_connection
from graph.cypher_templates import RELATION_INFO
from graph.entity_extraction import extract_entities
from graph.kg_query import (
    query_count_by_source,
    query_count_by_target,
    query_in_progress_projects_led,
    query_one_hop_forward,
    query_one_hop_reverse,
    query_two_hop_client_projects_via_product,
)
from utils.logging_config import log_stage

# 관계 판단 키워드 — 순서가 우선순위임 (구체적인 것부터 먼저 검사)
# (questions.json 10개 실측 패턴을 근거로 확정한 닫힌 키워드 집합)
_RELATION_KEYWORDS = [
    ("LEADS", ["이끄는", "이끌", "리드"]),
    ("HEAD_IS", ["팀장", "부서장", "책임자"]),
    ("REPORTED_ISSUE", ["이슈", "제기"]),
    ("BELONGS_TO", ["소속"]),
    ("MANAGES_ACCOUNT", ["담당"]),
    ("HAS_PROJECT", ["프로젝트"]),
    ("USES", ["사용", "쓰는", "쓰고"]),
]


def _detect_relation(question: str) -> Optional[str]:
    """질문 문자열에서 키워드 매칭으로 관계 라벨을 판단한다."""
    for relation, keywords in _RELATION_KEYWORDS:
        if any(kw in question for kw in keywords):
            return relation
    return None


def _wrap(question: str, formatted_result: dict) -> dict:
    return {"question": question, "success": True, **formatted_result}


def _error(question: str, note: str) -> dict:
    return {
        "question": question,
        "success": False,
        "query_type": None,
        "relation": None,
        "count": 0,
        "results": [],
        "is_empty": True,
        "note": note,
    }


def knowledge_graph_tool(question: str, request_id: str = "unknown") -> dict:
    """
    자연어 질문을 분석해서 지식 그래프(정점 133개/관계 354개)를 조회한다.

    처리 순서:
    1. 특수 패턴: "진행 중인 프로젝트를 이끄는" — 엔티티 없이 전체 목록 조회
    2. 집계 패턴: "가장 많은"/"최다" + (이슈 | 고객+담당) — 닫힌 2개 집계 유형
    3. 2-hop 패턴: Product 엔티티 + "프로젝트"+"관련" 언급
    4. 1-hop 패턴: 키워드로 관계 판단 후, 추출된 엔티티가 출발/도착 중
       어느 쪽에 해당하는지에 따라 정방향/역방향 결정

    :param question: 사용자의 자연어 질문
    :param request_id: tool_node.py가 MCP args에 섞어 전달하는 요청 식별자.
                        Cypher 쿼리 자체는 여기서 끝나므로, 이 함수가 반환한
                        count/results 길이와 answer_agent 로그의
                        final_answer_length를 request_id로 대조하면
                        "그래프 조회는 정상인데 LLM이 문장으로 옮기며
                        누락시켰는지" 여부가 바로 확인된다.
    :return: {
        "question": 원본 질문,
        "success": 처리 성공 여부,
        "query_type": 실행된 조회 유형,
        "relation": 사용된 관계 라벨,
        "count": 결과 개수,
        "results": 결과 리스트,
        "is_empty": 결과가 0개인지,
        "note": Answer Agent에게 전달할 안내 문구 (있는 경우)
    }
    """
    conn = get_connection()
    try:
        with log_stage("kg_entity_extraction", request_id, question=question) as log_result:
            entities = extract_entities(conn, question)
            log_result["entities_found"] = {k: v for k, v in entities.items()}

        with log_stage("kg_query_execution", request_id, question=question) as log_result:
            def _finish(query_type: str, relation: Optional[str], result: dict) -> dict:
                # 이 함수가 실제로 그래프에서 몇 건을 받아왔는지를 로그에 명시적으로
                # 남긴다. answer_agent 로그의 final_answer_length/실제 나열 항목
                # 수와 이 count/results_len을 비교하면, "그래프 조회 단계에서
                # 이미 결과가 모자랐는지" vs "여기까진 정상인데 LLM 답변 생성
                # 단계(stream_chat, done_reason)에서 잘렸는지"가 바로 구분된다.
                log_result["query_type"] = query_type
                log_result["relation"] = relation
                log_result["result_count"] = result.get("count")
                log_result["results_len"] = len(result.get("results") or [])
                return _wrap(question, result)

            # 1. 특수 패턴: 진행 중 프로젝트 리드 목록 (엔티티 불필요)
            if any(kw in question for kw in ["이끄는", "이끌", "리드"]) and "진행" in question:
                result = query_in_progress_projects_led(conn)
                return _finish("in_progress_projects_led", None, result)

            # 2. 집계 패턴 (닫힌 2개 유형)
            if any(kw in question for kw in ["가장 많은", "최다", "많이"]):
                if "이슈" in question:
                    result = query_count_by_target(conn, "REPORTED_ISSUE")
                    return _finish("count_by_target", "REPORTED_ISSUE", result)
                if "고객" in question and "담당" in question:
                    result = query_count_by_source(conn, "MANAGES_ACCOUNT")
                    return _finish("count_by_source", "MANAGES_ACCOUNT", result)

            # 3. 2-hop 패턴: Product 엔티티 + "프로젝트"+"관련"
            if entities.get("Product") and "프로젝트" in question and "관련" in question:
                result = query_two_hop_client_projects_via_product(conn, entities["Product"])
                return _finish("two_hop_client_projects_via_product", None, result)

            # 4. 1-hop 패턴
            relation = _detect_relation(question)
            if relation is None:
                log_result["query_type"] = None
                log_result["relation"] = None
                log_result["result_count"] = 0
                return _error(
                    question,
                    "질문에서 어떤 관계를 조회해야 할지 판단하지 못했습니다. "
                    "다른 도구(정형 데이터 조회 또는 문서 검색)가 더 적합할 수 있습니다.",
                )

            source_label, target_label, _, _ = RELATION_INFO[relation]
            source_entity = entities.get(source_label)
            target_entity = entities.get(target_label)

            if source_entity:
                result = query_one_hop_forward(conn, relation, source_entity)
                return _finish("one_hop_forward", relation, result)
            elif target_entity:
                result = query_one_hop_reverse(conn, relation, target_entity)
                return _finish("one_hop_reverse", relation, result)
            else:
                log_result["query_type"] = None
                log_result["relation"] = relation
                log_result["result_count"] = 0
                return _error(
                    question,
                    f"'{relation}' 관계를 조회하려 했으나, 질문에서 대상 엔티티"
                    f"(예: Client-A 같은 코드, 실제 등록된 직원/부서 이름)를 찾지 못했습니다. "
                    f"질문에 언급된 이름이 데이터베이스의 실제 명칭과 다를 수 있습니다.",
                )
    finally:
        conn.close()