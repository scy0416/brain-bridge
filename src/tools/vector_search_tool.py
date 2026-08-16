"""
src/tools/vector_search_tool.py

질문(자연어 문자열)을 받아 관련 문서 청크를 벡터 검색으로 찾아 반환하는
최종 도구 함수. Phase 11에서 MCPServer에 그대로 등록될 인터페이스.
"""

from typing import Optional

from documents.embeddings import get_embedding
from documents.search import search_similar_chunks
from documents.store import get_connection_with_vector

DEFAULT_K = 5


def vector_search_tool(question: str, k: int = DEFAULT_K, doc_type: Optional[str] = None) -> dict:
    """
    자연어 질문을 임베딩해서 관련 문서 청크를 벡터 유사도 검색으로 찾는다.

    :param question: 사용자의 자연어 질문
    :param k: 반환할 결과 개수 (기본 5)
    :param doc_type: 문서 타입으로 필터링하고 싶을 때 지정
                      (incident_report/technical_doc/meeting_note/proposal)
    :return: {
        "question": 원본 질문,
        "results": [{"doc_id", "chunk_index", "content", "title_path", "type", "distance"}, ...]
    }
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
        }
        for r in raw_results
    ]

    return {"question": question, "results": results}