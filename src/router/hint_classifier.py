"""
src/router/hint_classifier.py

질문 텍스트를 키워드 매칭만으로 빠르게 분류해서, 어떤 MCP 도구가 적합할지
"참고용 힌트"를 생성한다. 이 결과는 Router Agent(LLM function-calling)의
프롬프트에 참고 정보로만 제공되며, 최종 도구 선택을 강제하지 않는다.
(하이브리드 라우팅 설계: 규칙 기반 힌트 + 에이전트 자율 판단)
"""

from typing import Dict, List

# 도구별 키워드 사전. 겹치는 키워드가 있어도 괜찮다 — 여러 도구가 동시에
# 제안될 수 있고, 최종 판단은 Router Agent가 한다.
TOOL_KEYWORDS: Dict[str, List[str]] = {
    "nl2sql_tool": [
        # 집계/통계 표현
        "총", "합계", "평균", "몇 개", "몇개", "개수", "상위", "순위",
        "가장 많은", "가장 높은", "최대", "최소", "큰 순서", "작은 순서",
        # 정형 테이블에 대응되는 필드/값 표현
        "지역", "분기", "카테고리", "우선순위", "상태", "연봉", "매출",
        "계약", "가격", "등록", "활성", "예산",
    ],
    "vector_search_tool": [
        "방법", "내용이 있어", "정책", "가이드", "사례", "대응",
        "논의된", "제안서", "매뉴얼", "절차", "설정", "인증 방식",
        "이슈가 있", "장애",
    ],
    "knowledge_graph_tool": [
        "사용", "쓰는", "쓰고", "담당", "소속", "이끄는", "이끌", "리드",
        "팀장", "부서장", "책임자", "제기", "관련된 프로젝트", "이슈", "관련",
    ],
}

MIN_KEYWORD_LEN_FOR_WORD_BOUNDARY = 3  # 이보다 짧은 키워드는 부분 문자열 매칭이 오탐 위험 높음


def _find_matches(question: str, keywords: List[str]) -> List[str]:
    """질문 문자열에 포함된 키워드들을 찾아 리스트로 반환한다."""
    return [kw for kw in keywords if kw in question]


def classify(question: str) -> dict:
    """
    질문을 키워드 매칭으로 분류해서 참고용 힌트를 생성한다.

    :param question: 사용자의 자연어 질문
    :return: {
        "suggested_tools": 매칭된 키워드 수 기준 내림차순으로 정렬된 도구 이름 리스트
                            (매칭이 하나도 없으면 빈 리스트),
        "confidence": "high" | "medium" | "low"
                       - high: 1위 도구가 2개 이상의 키워드로 매칭되고, 다른 도구와 동률이 아님
                       - medium: 1위 도구가 1개 키워드로만 매칭되었거나, 여러 도구가 동률
                       - low: 매칭된 키워드가 하나도 없음
        "matched_keywords": {도구 이름: [매칭된 키워드, ...], ...} (매칭 없는 도구는 제외)
    }
    """
    matched_keywords = {}
    match_counts = {}

    for tool, keywords in TOOL_KEYWORDS.items():
        matches = _find_matches(question, keywords)
        if matches:
            matched_keywords[tool] = matches
            match_counts[tool] = len(matches)

    if not match_counts:
        return {"suggested_tools": [], "confidence": "low", "matched_keywords": {}}

    suggested_tools = sorted(match_counts, key=lambda t: match_counts[t], reverse=True)

    top_count = match_counts[suggested_tools[0]]
    tied_at_top = sum(1 for c in match_counts.values() if c == top_count)

    if top_count >= 2 and tied_at_top == 1:
        confidence = "high"
    else:
        confidence = "medium"

    return {
        "suggested_tools": suggested_tools,
        "confidence": confidence,
        "matched_keywords": matched_keywords,
    }