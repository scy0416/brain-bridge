"""
src/agent/state.py

LangGraph 그래프의 노드들이 공유하는 상태(state) 스키마.
Base/Router/Tool/Answer 노드가 이 상태를 읽고 갱신하며 그래프를 진행한다.
"""

from typing import List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    # Open WebUI가 보낸 전체 대화 히스토리 (OpenAI 포맷: role/content dict 리스트)
    # Answer Agent만 사용 — 자연스러운 대화 연속성 + tool_results 근거 답변용.
    # Base/Router Agent는 이 필드를 참조하지 않는다 (question만 사용).
    messages: List[dict]

    question: str  # 사용자 원본 질문 (messages의 최신 user 발화). Base/Router Agent가 사용

    # Base Agent가 채우는 값. add_conditional_edges의 분기 기준으로 쓰인다.
    #   True  -> 라우팅 에이전트로 진행 (도구 실행 필요)
    #   False -> Tool 실행 없이 곧장 답변 생성 에이전트로 진행
    needs_tools: bool

    router_tools: List[dict]  # Router Agent가 선택한 도구 목록 [{"name":..., "args":...}, ...]
    tool_results: List[dict]  # Tool 실행 노드가 채운 각 도구의 실행 결과
    final_answer: Optional[str]  # Answer Agent가 생성한 최종 답변