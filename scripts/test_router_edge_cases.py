"""
scripts/test_router_edge_cases.py

Router Agent 도구 선택 튜닝 전용 테스트.

test_graph_routing.py(회귀 검증, 34건)와는 목적이 다르다 — 이 스크립트는
이미 드러난 두 가지 취약 지점을 집중적으로 다룬다:

  1. 경계 질문(aggregation_boundary): "가장 많은 X는?" 같은 집계/최댓값
     질문. nl2sql(GROUP BY + ORDER BY DESC LIMIT 1)로도, knowledge_graph
     (관계 카운트 집계)로도 풀리는 문제라 Router가 혼동하는 것으로
     test_graph_routing.py 34건 검증에서 2건 확인됨.

  2. 복합 질문(compound): 여러 성격이 섞여서 2개 이상의 도구가 동시에
     필요한 질문. 단일 도구 라우팅은 100% 검증됐지만 복수 도구 동시
     선택은 HANDOFF.md에 "확률적으로 불안정" 하다고 기록된 기존 한계.

채점 기준:
  - aggregation_boundary: 정답 도구 1개와 정확히 일치해야 pass
  - compound: 기대하는 도구 집합이 "모두" 선택된 도구 목록에 포함되면
    pass (선택된 도구가 기대보다 많아도, 즉 여분의 도구를 더 골라도
    이 테스트에서는 감점하지 않는다 — 과소 선택보다 과다 선택이
    상대적으로 덜 치명적이라는 판단)

실행 방법:
  docker compose run --rm app python scripts/test_router_edge_cases.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import asyncio

from agent.graph import graph

TOOL_NAME_MAP = {
    "nl2sql": "nl2sql_tool",
    "vector_search": "vector_search_tool",
    "knowledge_graph": "knowledge_graph_tool",
}

# --- 1. 경계 질문: 집계/최댓값 질문 (nl2sql vs knowledge_graph 혼동 지점) ---
AGGREGATION_BOUNDARY_CASES = [
    # 기존 회귀 테스트에서 실패했던 2건 - 회귀 확인용으로 유지
    {"question": "가장 많은 프로젝트를 진행 중인 고객사는?", "expected_tool": "nl2sql",
     "note": "projects JOIN clients GROUP BY, 정형 데이터 집계"},
    {"question": "가장 많은 고객을 담당하는 직원은?", "expected_tool": "knowledge_graph",
     "note": "MANAGES_ACCOUNT 관계 카운트 집계"},

    # 같은 패턴의 신규 케이스
    {"question": "부서별 직원 수가 가장 많은 부서는?", "expected_tool": "nl2sql",
     "note": "employees JOIN departments GROUP BY, 정형 데이터 집계"},
    {"question": "매출이 가장 높은 제품은 뭐야?", "expected_tool": "nl2sql",
     "note": "sales JOIN products GROUP BY, 정형 데이터 집계"},
    {"question": "이슈를 가장 많이 제기한 고객사는 어디야?", "expected_tool": "knowledge_graph",
     "note": "REPORTED_ISSUE 관계 카운트 집계"},
    {"question": "가장 많은 프로젝트를 이끄는 직원은 누구야?", "expected_tool": "knowledge_graph",
     "note": "LEADS 관계 카운트 집계"},
    {"question": "계약 금액이 가장 큰 고객사는 어디야?", "expected_tool": "nl2sql",
     "note": "contracts JOIN clients GROUP BY, 정형 데이터 집계"},
    {"question": "가장 많은 제품을 사용 중인 고객사는?", "expected_tool": "knowledge_graph",
     "note": "USES 관계 카운트 집계"},
]

# --- 2. 복합 질문: 2개 이상 도구가 동시에 필요한 질문 ---
COMPOUND_CASES = [
    {
        "question": "인사팀 조직 구조랑 최근 채용 관련 규정 문서를 같이 알려줘",
        "expected_tools": ["knowledge_graph", "vector_search"],
        "note": "조직도(그래프) + 규정 문서(벡터 검색)",
    },
    {
        "question": "Client-A가 사용 중인 제품 목록이랑 관련 장애 보고서를 같이 보여줘",
        "expected_tools": ["knowledge_graph", "vector_search"],
        "note": "사용 제품(그래프 USES) + 장애 보고서(벡터 검색)",
    },
    {
        "question": "이번 분기 매출 상위 고객사랑 그 고객사 담당 엔지니어를 알려줘",
        "expected_tools": ["nl2sql", "knowledge_graph"],
        "note": "매출 집계(SQL) + 담당자(그래프 MANAGES_ACCOUNT)",
    },
    {
        "question": "기술 지원 이슈가 가장 많은 제품이 뭔지랑, 그 제품 관련 기술 문서를 같이 알려줘",
        "expected_tools": ["knowledge_graph", "vector_search"],
        "note": "이슈 집계(그래프) + 기술 문서(벡터 검색)",
    },
    {
        "question": "활성 계약 수랑 최근 서버 장애 사례를 같이 알려줘",
        "expected_tools": ["nl2sql", "vector_search"],
        "note": "계약 수(SQL COUNT) + 장애 보고서(벡터 검색), 서로 무관한 두 질문이 한 문장에 섞인 경우",
    },
]


async def run_aggregation_case(case: dict) -> dict:
    result_state = await graph.ainvoke({"question": case["question"]})
    router_tools = result_state.get("router_tools") or []
    selected_names = [t.get("name") for t in router_tools]

    expected_tool_name = TOOL_NAME_MAP[case["expected_tool"]]
    tool_ok = selected_names == [expected_tool_name]

    return {
        **case,
        "selected_names": selected_names,
        "tool_ok": tool_ok,
        "final_answer_preview": (result_state.get("final_answer") or "")[:80],
    }


async def run_compound_case(case: dict) -> dict:
    result_state = await graph.ainvoke({"question": case["question"]})
    router_tools = result_state.get("router_tools") or []
    selected_names = [t.get("name") for t in router_tools]

    expected_tool_names = {TOOL_NAME_MAP[t] for t in case["expected_tools"]}
    selected_set = set(selected_names)
    tool_ok = expected_tool_names.issubset(selected_set)

    return {
        **case,
        "selected_names": selected_names,
        "tool_ok": tool_ok,
        "final_answer_preview": (result_state.get("final_answer") or "")[:80],
    }


async def main() -> None:
    print("=" * 100)
    print("[1] 경계 질문 (집계/최댓값 - nl2sql vs knowledge_graph 혼동 지점)")
    print("=" * 100)

    agg_results = []
    for case in AGGREGATION_BOUNDARY_CASES:
        r = await run_aggregation_case(case)
        agg_results.append(r)
        mark = "OK" if r["tool_ok"] else "FAIL"
        expected_name = TOOL_NAME_MAP[case["expected_tool"]]
        print(f"[{mark}] {case['question']}")
        print(f"      정답: {expected_name}  |  선택: {r['selected_names']}  |  ({case['note']})")
        if not r["tool_ok"]:
            print(f"      답변 미리보기: {r['final_answer_preview']}...")

    agg_pass = sum(1 for r in agg_results if r["tool_ok"])
    print(f"\n경계 질문 정확도: {agg_pass}/{len(agg_results)}")

    print()
    print("=" * 100)
    print("[2] 복합 질문 (2개 이상 도구 동시 필요)")
    print("=" * 100)

    compound_results = []
    for case in COMPOUND_CASES:
        r = await run_compound_case(case)
        compound_results.append(r)
        mark = "OK" if r["tool_ok"] else "FAIL"
        expected_names = [TOOL_NAME_MAP[t] for t in case["expected_tools"]]
        print(f"[{mark}] {case['question']}")
        print(f"      정답(모두 포함되어야 함): {expected_names}  |  선택: {r['selected_names']}  |  ({case['note']})")
        if not r["tool_ok"]:
            print(f"      답변 미리보기: {r['final_answer_preview']}...")

    compound_pass = sum(1 for r in compound_results if r["tool_ok"])
    print(f"\n복합 질문 정확도: {compound_pass}/{len(compound_results)}")

    print()
    print("=" * 100)
    print(f"전체 요약 - 경계 질문: {agg_pass}/{len(agg_results)}  |  복합 질문: {compound_pass}/{len(compound_results)}")


if __name__ == "__main__":
    asyncio.run(main())