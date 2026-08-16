"""
src/tools/vector_search_tool.py

질문(자연어 문자열)을 받아 관련 문서 청크를 벡터 검색으로 찾아 반환하는
최종 도구 함수. Phase 11에서 MCPServer에 그대로 등록될 인터페이스.
"""

from typing import Optional

from documents.embeddings import get_embedding
from documents.search import search_similar_chunks
from documents.store import get_connection_with_vector

DEFAULT_K = 3
LOW_CONFIDENCE_THRESHOLD = 0.5  # 이 값을 넘는 distance는 관련성이 낮다고 판단 (관측 기반: 정답 0.30~0.47, 무관 0.55+)


def vector_search_tool(question: str, k: int = DEFAULT_K, doc_type: Optional[str] = None) -> dict:
    """
    자연어 질문을 임베딩해서 관련 문서 청크를 벡터 유사도 검색으로 찾는다.

    :param question: 사용자의 자연어 질문
    :param k: 반환할 결과 개수 (기본 3 — K값 튜닝 결과 반영: 재현율과 노이즈의 균형점)
    :param doc_type: 문서 타입으로 필터링하고 싶을 때 지정
                      (incident_report/technical_doc/meeting_note/proposal)
    :return: {
        "question": 원본 질문,
        "results": [{"doc_id", "chunk_index", "content", "title_path", "type",
                      "distance", "low_confidence"}, ...],
        "has_confident_result": 결과 중 신뢰도 높은 것이 하나라도 있는지 여부
    }

    유사도 임계값(LOW_CONFIDENCE_THRESHOLD): 결과를 하드 컷오프로 제외하지 않고,
    각 결과에 low_confidence 플래그를 붙인다. Answer Agent가 "관련 문서 없음"과
    "약하게만 관련된 결과 있음"을 구분해서 답변할 수 있도록 하기 위함이다.
    """
    conn = get_connection_with_vector()
    try:
        query_embedding = get_embedding(question)
        raw_results = search_similar_chunks(conn, query_embedding, k=k, doc_type=doc_type)
    finally:
        conn.close()

    results = [
        {
            "doc_id": r["doc_id"],
            "chunk_index": r["chunk_index"],
            "content": r["content"],
            "title_path": r["metadata"].get("title_path", ""),
            "type": r["metadata"].get("type", ""),
            "distance": r["distance"],
            "low_confidence": r["distance"] > LOW_CONFIDENCE_THRESHOLD,
        }
        for r in raw_results
    ]

    has_confident_result = any(not r["low_confidence"] for r in results)

    return {"question": question, "results": results, "has_confident_result": has_confident_result}