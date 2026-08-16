"""
src/documents/search.py

document_chunks에 대한 벡터 유사도 검색(조회) 로직.
적재(store.py)와 책임을 분리 — 이 파일은 오직 "읽기"만 담당한다.

Phase 10의 vector_search_tool이 이 모듈을 그대로 사용하게 된다.
"""

from typing import List, Optional


def search_similar_chunks(
    conn,
    query_embedding: List[float],
    k: int = 5,
    doc_type: Optional[str] = None,
) -> List[dict]:
    """
    쿼리 임베딩과 코사인 거리가 가장 가까운 청크 k개를 반환한다.

    pgvector의 <=> 연산자는 "코사인 거리"(1 - 코사인 유사도)를 계산하므로
    값이 작을수록 더 유사하다 (0에 가까울수록 유사, 오름차순 정렬 = 가장 유사한 것부터).

    :param conn: get_connection_with_vector()로 얻은 커넥션 (vector 어댑터 등록 필요)
    :param query_embedding: 검색할 쿼리의 임베딩 벡터 (BGE-M3, 1024차원)
    :param k: 반환할 상위 결과 개수
    :param doc_type: 지정하면 해당 문서 타입(incident_report/technical_doc/meeting_note/proposal)
                      으로만 필터링 (하이브리드 검색용, 다음 단계에서 본격 사용)
    :return: [{"doc_id", "chunk_index", "content", "metadata", "distance"}, ...] (거리 오름차순)
    """
    where_clause = ""
    params = [query_embedding]
    if doc_type:
        where_clause = "WHERE metadata->>'type' = %s"
        params.append(doc_type)
    params.append(query_embedding)
    params.append(k)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT doc_id, chunk_index, content, metadata, embedding <=> %s::vector AS distance
            FROM document_chunks
            {where_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()

    return [
        {
            "doc_id": doc_id,
            "chunk_index": chunk_index,
            "content": content,
            "metadata": metadata,
            "distance": float(distance),
        }
        for doc_id, chunk_index, content, metadata, distance in rows
    ]