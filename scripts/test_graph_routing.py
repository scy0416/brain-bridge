"""
scripts/test_graph_routing.py

Phase 12 최종 검증: StateGraph 조건부 분기(base_agent -> router_agent/
answer_agent)가 실제로 의도대로 타는지 확인한다.

질문 소스: 대회 검증용 질문 세트(hint_classifier baseline 검증에 쓰인
것과 동일한 30건 — nl2sql/vector_search/knowledge_graph 각 10건)를
외부 파일 참조 없이 이 스크립트 안에 직접 내장했다. 여기에 이 세트에는
없는 도구 불필요(잡담/시스템 질문) 4건을 보강해서 총 34건을 테스트한다.

이 스크립트가 검증하는 것 (3단계):
  1. branch_ok   — Base Agent의 needs_tools 판단이 기대와 맞는가
  2. wiring_ok   — needs_tools 값과 실제로 router_agent/tool_exec를
                   탔는지가 논리적으로 일치하는가 (그래프 배선 자체 검증)
  3. tool_ok     — (도구 필요 케이스만) Router Agent가 고른 도구가
                   정답 도구와 일치하는가
                   * 참고용 지표: Router Agent 자체는 이미 별도로
                   100% 정확도 검증이 끝난 상태이므로, 여기서 어긋나면
                   Router 문제라기보다 그래프 연결 과정에서 무언가
                   달라졌는지를 의심해봐야 한다.

실행 방법 (docker compose 환경 기준):
  docker compose run --rm app python scripts/test_graph_routing.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import asyncio

from agent.graph import graph

# questions.json에는 도구 불필요(잡담/시스템 질문) 케이스가 없어서 보강
CHITCHAT_CASES = [
    {"category": "잡담", "question": "안녕하세요!", "expected_needs_tools": False, "expected_tool": None},
    {"category": "잡담", "question": "오늘 하루 어땠어?", "expected_needs_tools": False, "expected_tool": None},
    {"category": "시스템 질문", "question": "너는 뭘 할 수 있어?", "expected_needs_tools": False, "expected_tool": None},
    {"category": "감사 표현", "question": "고마워, 도움이 많이 됐어", "expected_needs_tools": False, "expected_tool": None},
]

# 대회 검증용 질문 30건 (nl2sql 10 / vector_search 10 / knowledge_graph 10)
# hint 필드는 정답 도구가 어떤 조회 로직을 타야 하는지에 대한 참고용
# 메모이며, 이 테스트에서 직접 사용하지는 않는다 (필요 시 실패 케이스
# 디버깅용으로 참고).
TOOL_QUESTIONS = [
    {"q": "서울 지역 매출 상위 5개 고객사를 알려줘", "tool": "nl2sql",
     "hint": "sales + clients 조인, region='서울', GROUP BY, ORDER BY DESC LIMIT 5"},
    {"q": "2025년 3분기 총 매출액은 얼마야?", "tool": "nl2sql",
     "hint": "sales WHERE quarter='2025-Q3', SUM(amount)"},
    {"q": "보안 솔루션 카테고리 제품들의 월 평균 매출은?", "tool": "nl2sql",
     "hint": "sales WHERE category='security', AVG(amount)"},
    {"q": "현재 활성 상태인 계약 수는 몇 개야?", "tool": "nl2sql",
     "hint": "contracts WHERE status='active', COUNT(*)"},
    {"q": "기술지원팀 직원 목록과 연봉을 알려줘", "tool": "nl2sql",
     "hint": "employees JOIN departments WHERE name='기술지원팀'"},
    {"q": "가장 많은 프로젝트를 진행 중인 고객사는?", "tool": "nl2sql",
     "hint": "projects JOIN clients, GROUP BY client_id, ORDER BY COUNT DESC LIMIT 1"},
    {"q": "Critical 우선순위 티켓 중 아직 해결되지 않은 건은?", "tool": "nl2sql",
     "hint": "support_tickets WHERE priority='critical' AND status IN ('open','in_progress')"},
    {"q": "제품별 총 계약 금액을 큰 순서로 보여줘", "tool": "nl2sql",
     "hint": "contracts JOIN products, GROUP BY product_id, SUM(amount) ORDER BY DESC"},
    {"q": "2024년에 등록된 고객사는 몇 개야?", "tool": "nl2sql",
     "hint": "clients WHERE registered_at BETWEEN '2024-01-01' AND '2024-12-31'"},
    {"q": "평균 연봉이 가장 높은 부서는 어디야?", "tool": "nl2sql",
     "hint": "employees JOIN departments, GROUP BY dept_id, AVG(salary) ORDER BY DESC LIMIT 1"},

    {"q": "최근 서버 장애 사례와 원인을 알려줘", "tool": "vector_search",
     "hint": "장애 보고서 문서 검색, incident_report 타입"},
    {"q": "Product-C1 설치 방법이 궁금해", "tool": "vector_search",
     "hint": "기술 문서에서 설치 가이드 검색"},
    {"q": "Kubernetes 관련 장애 대응 방법은?", "tool": "vector_search",
     "hint": "K8s, Pod, 컨테이너 관련 장애 보고서 검색"},
    {"q": "성능 최적화를 위한 DB 튜닝 방법 알려줘", "tool": "vector_search",
     "hint": "성능 튜닝 가이드 문서 검색"},
    {"q": "보안 취약점 점검 관련 내용이 있어?", "tool": "vector_search",
     "hint": "회의록 또는 장애보고서에서 보안 관련 검색"},
    {"q": "백업 정책은 어떻게 되어 있어?", "tool": "vector_search",
     "hint": "운영 매뉴얼에서 백업 관련 검색"},
    {"q": "API 인증 방식은 뭐야?", "tool": "vector_search",
     "hint": "API 레퍼런스 문서 검색"},
    {"q": "고객사 미팅에서 논의된 일정 지연 이슈는?", "tool": "vector_search",
     "hint": "회의록에서 일정 지연 관련 검색"},
    {"q": "클라우드 마이그레이션 제안서 내용 보여줘", "tool": "vector_search",
     "hint": "제안서 문서에서 마이그레이션 관련 검색"},
    {"q": "SSL 인증서 관련 장애가 있었어?", "tool": "vector_search",
     "hint": "장애 보고서에서 SSL 관련 검색"},

    {"q": "Client-A가 사용 중인 제품 목록은?", "tool": "knowledge_graph",
     "hint": "client_1 -[USES]→ product_* 탐색"},
    {"q": "Product-C1을 사용하는 고객사는 어디야?", "tool": "knowledge_graph",
     "hint": "product_1 ←[USES]- client_* 역방향 탐색"},
    {"q": "클라우드사업부 소속 직원들은 누구야?", "tool": "knowledge_graph",
     "hint": "dept_2 ←[BELONGS_TO]- employee_* 탐색"},
    {"q": "서울물산 담당 엔지니어는 누구야?", "tool": "knowledge_graph",
     "hint": "client_2 ←[MANAGES_ACCOUNT]- employee_* 탐색"},
    {"q": "Product-D1 제품과 관련된 프로젝트는?", "tool": "knowledge_graph",
     "hint": "product_5 ←[USES]- client_* -[HAS_PROJECT]→ project_* 2홉 탐색"},
    {"q": "기술 지원 이슈가 가장 많은 제품은?", "tool": "knowledge_graph",
     "hint": "REPORTED_ISSUE 관계 카운트로 집계"},
    {"q": "경영지원팀 팀장은 누구야?", "tool": "knowledge_graph",
     "hint": "dept_1 -[HEAD_IS]→ employee_* 탐색"},
    {"q": "진행 중인 프로젝트를 이끄는 직원 목록", "tool": "knowledge_graph",
     "hint": "project(status=in_progress) ←[LEADS]- employee_* 탐색"},
    {"q": "Product-S1 관련 고객 이슈 현황은?", "tool": "knowledge_graph",
     "hint": "product_3 ←[REPORTED_ISSUE]- client_* 탐색 + 속성 확인"},
    {"q": "가장 많은 고객을 담당하는 직원은?", "tool": "knowledge_graph",
     "hint": "MANAGES_ACCOUNT 관계 카운트로 집계"},
]

# TOOL_QUESTIONS의 tool 필드 값 -> 실제 MCP 도구 이름 매핑
TOOL_NAME_MAP = {
    "nl2sql": "nl2sql_tool",
    "vector_search": "vector_search_tool",
    "knowledge_graph": "knowledge_graph_tool",
}


def build_tool_cases() -> list[dict]:
    cases = []
    for item in TOOL_QUESTIONS:
        expected_tool = TOOL_NAME_MAP.get(item["tool"], item["tool"])
        cases.append(
            {
                "category": item["tool"],
                "question": item["q"],
                "expected_needs_tools": True,
                "expected_tool": expected_tool,
                "hint": item.get("hint", ""),
            }
        )
    return cases


async def run_case(case: dict) -> dict:
    result_state = await graph.ainvoke({"question": case["question"]})

    observed_needs_tools = result_state.get("needs_tools")
    router_tools = result_state.get("router_tools") or []
    tool_results = result_state.get("tool_results") or []
    final_answer = result_state.get("final_answer") or ""

    branch_ok = observed_needs_tools == case["expected_needs_tools"]

    if observed_needs_tools is True:
        wiring_ok = len(router_tools) > 0
    else:
        wiring_ok = len(router_tools) == 0 and len(tool_results) == 0

    selected_tool_names = [t.get("name") for t in router_tools]
    if case["expected_tool"] is None:
        tool_ok = True  # 도구 불필요 케이스는 해당 없음
    else:
        tool_ok = case["expected_tool"] in selected_tool_names

    return {
        **case,
        "observed_needs_tools": observed_needs_tools,
        "branch_ok": branch_ok,
        "wiring_ok": wiring_ok,
        "tool_ok": tool_ok,
        "selected_tool_names": selected_tool_names,
        "final_answer_preview": final_answer[:80],
    }


async def main() -> None:
    tool_cases = build_tool_cases()
    all_cases = CHITCHAT_CASES + tool_cases

    print(f"총 {len(all_cases)}건 테스트 (도구 불필요 {len(CHITCHAT_CASES)}건 + 도구 필요 {len(tool_cases)}건)")
    print(f"{'분류':16} {'판단':4} {'배선':4} {'도구':4}  질문")
    print("-" * 100)

    results = []
    for case in all_cases:
        try:
            r = await run_case(case)
        except Exception as exc:  # noqa: BLE001 - 한 건 실패해도 나머지는 계속 진행
            print(f"{case['category']:16} {'FAIL':4} {'FAIL':4} {'FAIL':4}  {case['question']}  -> {exc!r}")
            results.append({**case, "branch_ok": False, "wiring_ok": False, "tool_ok": False})
            continue

        results.append(r)
        judge_mark = "OK" if r["branch_ok"] else "FAIL"
        wiring_mark = "OK" if r["wiring_ok"] else "FAIL"
        tool_mark = "OK" if r["tool_ok"] else "FAIL"
        print(
            f"{case['category']:16} "
            f"{judge_mark:4} "
            f"{wiring_mark:4} "
            f"{tool_mark:4}  "
            f"{case['question']}"
        )
        if case["expected_tool"] is not None:
            print(f"                 정답 도구: {case['expected_tool']}  |  선택된 도구: {r['selected_tool_names']}")
        if not r["branch_ok"] or not r["wiring_ok"] or not r["tool_ok"]:
            print(f"                 답변 미리보기: {r['final_answer_preview']}...")

    print("-" * 100)
    total = len(results)
    branch_pass = sum(1 for r in results if r["branch_ok"])
    wiring_pass = sum(1 for r in results if r["wiring_ok"])
    tool_pass = sum(1 for r in results if r["expected_tool"] is not None and r["tool_ok"])
    tool_total = sum(1 for c in all_cases if c["expected_tool"] is not None)

    print(f"Base Agent 판단 정확도: {branch_pass}/{total}")
    print(f"그래프 배선(분기 일관성) 정확도: {wiring_pass}/{total}")
    print(f"Router 도구 선택 정확도(도구 필요 케이스만): {tool_pass}/{tool_total}")

    if wiring_pass < total:
        print(
            "\n[경고] 배선 일관성이 깨진 케이스가 있습니다. "
            "needs_tools 값과 실제 router_agent/tool_exec 통과 여부가 "
            "불일치합니다 — graph.py의 add_conditional_edges 설정을 확인하세요."
        )
    if tool_pass < tool_total:
        print(
            "\n[참고] 정답 도구와 다른 도구가 선택된 케이스가 있습니다. "
            "Router Agent 자체는 별도 검증에서 100% 정확도가 확인된 바 있으므로, "
            "hint와 실제 시딩 데이터 상태(스키마 컬럼명, 그래프 정점/간선 "
            "존재 여부 등)가 달라졌는지부터 의심해보세요."
        )


if __name__ == "__main__":
    asyncio.run(main())