"""
src/agent/state.py

LangGraph 그래프의 노드들이 공유하는 상태(state) 스키마.
Base/Router/Tool/Answer 노드가 이 상태를 읽고 갱신하며 그래프를 진행한다.
"""

from typing import Any, List, Optional, TypedDict


class GraphState(TypedDict, total=False):
    question: str  # 사용자 원본 질문
    router_tools: List[dict]  # Router Agent가 선택한 도구 목록 [{"name":..., "args":...}, ...]
    tool_results: List[dict]  # Tool 실행 노드가 채운 각 도구의 실행 결과
    final_answer: Optional[str]  # Answer Agent가 생성한 최종 답변