"""
scripts/load_documents.py

전체 파이프라인: data/documents/DOC-001~040.md 청킹 → BGE-M3 임베딩 → document_chunks 적재

사용법:
    docker compose run --rm app python scripts/load_documents.py
    docker compose run --rm app python scripts/load_documents.py --fresh   # 전체 삭제 후 재적재
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from documents.embeddings import EXPECTED_DIM, embed_chunks
from documents.loader import load_all_chunks
from documents.store import clear_chunks, count_existing_chunks, get_connection_with_vector, insert_chunks


def main():
    fresh = "--fresh" in sys.argv

    print("==> [1/4] 문서 청킹")
    chunks = load_all_chunks()
    expected_total = len(chunks)
    print(f"    총 {expected_total}개 청크 (40개 문서)")

    conn = get_connection_with_vector()

    if fresh:
        print("\n==> 기존 document_chunks 전체 삭제 (--fresh)")
        clear_chunks(conn)
    else:
        existing = count_existing_chunks(conn)
        if existing == expected_total:
            print(f"\n==> 이미 {existing}개 청크가 적재되어 있습니다 — 건너뜁니다. (강제 재적재: --fresh)")
            conn.close()
            print("\n✅ 문서 데이터가 이미 최신 상태입니다.")
            return
        elif existing > 0:
            print(f"\n⚠️  기존에 {existing}개 청크가 있지만 기대값({expected_total})과 다릅니다.")
            print("    부분 적재 상태로 보입니다. --fresh로 초기화 후 재실행을 권장합니다.")
            conn.close()
            sys.exit(1)

    print("\n==> [2/4] 임베딩 생성 (Ollama BGE-M3, 순차 처리)")
    embedded = embed_chunks(chunks, progress_interval=20)

    if len(embedded) != expected_total:
        print(f"\n⚠️  일부 청크 임베딩 실패: {len(embedded)}/{expected_total}개만 성공")
        print("    실패한 청크가 있는 상태로는 적재를 진행하지 않습니다.")
        conn.close()
        sys.exit(1)

    print("\n==> [3/4] document_chunks 테이블 적재")
    inserted = insert_chunks(conn, embedded, commit_every=20)
    print(f"    INSERT 완료: {inserted}개")

    print("\n==> [4/4] 검증")
    final_count = count_existing_chunks(conn)
    print(f"    document_chunks 전체 행 수: {final_count}")
    assert final_count == expected_total, f"최종 행 수 불일치: {final_count} != {expected_total}"

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM document_chunks WHERE embedding IS NULL;"
        )
        (null_count,) = cur.fetchone()
    assert null_count == 0, f"embedding이 NULL인 행이 {null_count}개 있습니다"

    conn.close()
    print(f"\n✅ 전체 파이프라인 완료 — 청킹 {expected_total}개 → 임베딩 → 적재까지 전부 성공")


if __name__ == "__main__":
    main()