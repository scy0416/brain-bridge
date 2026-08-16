"""
scripts/verify_document_store.py

src/documents/store.py의 INSERT 로직이 실제로 동작하는지,
소량의 더미 청크로 먼저 검증한다. (전체 200개 적재는 다음 단계)

사용법:
    docker compose run --rm app python scripts/verify_document_store.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from documents.embeddings import get_embedding
from documents.store import (
    clear_chunks,
    count_existing_chunks,
    get_connection_with_vector,
    insert_chunk,
    insert_chunks,
)

DUMMY_CHUNKS = [
    {
        "doc_id": "TEST-001",
        "chunk_index": 0,
        "type": "incident_report",
        "title": "테스트 문서",
        "title_path": "테스트 문서 > 기본 정보",
        "content": "이것은 INSERT 로직 검증용 더미 청크입니다.",
    },
    {
        "doc_id": "TEST-001",
        "chunk_index": 1,
        "type": "incident_report",
        "title": "테스트 문서",
        "title_path": "테스트 문서 > 조치 사항",
        "content": "두 번째 더미 청크로 배치 INSERT를 확인합니다.",
    },
]


def main():
    conn = get_connection_with_vector()

    print("==> [0/4] 기존 상태 정리 (TEST-* 접두 데이터가 남아있으면 삭제)")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM document_chunks WHERE doc_id LIKE 'TEST-%';")
    conn.commit()

    before_count = count_existing_chunks(conn)
    print(f"    적재 전 전체 행 수: {before_count}")

    print("\n==> [1/4] 임베딩 생성 (더미 청크 2개)")
    for chunk in DUMMY_CHUNKS:
        chunk["embedding"] = get_embedding(chunk["content"])
    print(f"    임베딩 차원: {len(DUMMY_CHUNKS[0]['embedding'])}")

    print("\n==> [2/4] 배치 INSERT 실행")
    inserted = insert_chunks(conn, DUMMY_CHUNKS, commit_every=1)
    print(f"    INSERT된 청크 수: {inserted}")

    print("\n==> [3/4] DB 재조회로 검증")
    after_count = count_existing_chunks(conn)
    print(f"    적재 후 전체 행 수: {after_count}")
    assert after_count == before_count + len(DUMMY_CHUNKS), "행 수가 기대와 다릅니다"

    with conn.cursor() as cur:
        cur.execute(
            "SELECT doc_id, chunk_index, content, metadata, embedding "
            "FROM document_chunks WHERE doc_id = 'TEST-001' ORDER BY chunk_index;"
        )
        rows = cur.fetchall()

    assert len(rows) == 2, f"TEST-001 청크가 2개가 아닙니다: {len(rows)}"
    for doc_id, chunk_index, content, metadata, embedding in rows:
        print(f"    [{doc_id}#{chunk_index}] content={content[:30]}... "
              f"metadata={metadata} embedding_dim={len(embedding)}")
        assert metadata["type"] == "incident_report"
        assert len(embedding) == 1024

    print("\n==> [4/4] 정리 (테스트 데이터 삭제)")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM document_chunks WHERE doc_id LIKE 'TEST-%';")
    conn.commit()
    final_count = count_existing_chunks(conn)
    assert final_count == before_count, "정리 후 행 수가 원래대로 돌아오지 않았습니다"
    print(f"    정리 후 전체 행 수: {final_count} (원래대로 복원됨)")

    conn.close()
    print("\n✅ document_chunks INSERT 로직 검증 완료")


if __name__ == "__main__":
    main()