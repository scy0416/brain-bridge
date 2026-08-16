"""
scripts/test_vector_search.py

src/documents/search.py의 search_similar_chunks()를 questions.json의
vector_search 타입 질문 몇 개로 실제 검색해서 확인한다.

사용법:
    docker compose run --rm app python scripts/test_vector_search.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from documents.embeddings import get_embedding
from documents.search import search_similar_chunks
from documents.store import get_connection_with_vector

# data/questions.json의 vector_search 타입 질문 중 일부
TEST_QUESTIONS = [
    "Product-C1 설치 방법이 궁금해",
    "최근 서버 장애 사례와 원인을 알려줘",
    "백업 정책은 어떻게 되어 있어?",
    "API 인증 방식은 뭐야?",
]


def main():
    conn = get_connection_with_vector()

    for question in TEST_QUESTIONS:
        print(f"\n{'=' * 70}")
        print(f"질문: {question}")
        print("=" * 70)

        query_vec = get_embedding(question)
        results = search_similar_chunks(conn, query_vec, k=3)

        for rank, r in enumerate(results, start=1):
            title_path = r["metadata"].get("title_path", "")
            preview = r["content"][:70].replace("\n", " ")
            print(f"  [{rank}] distance={r['distance']:.4f}  "
                  f"{r['doc_id']}#{r['chunk_index']} ({r['metadata'].get('type')})")
            print(f"      {title_path}")
            print(f"      {preview}...")

    conn.close()
    print("\n✅ 벡터 검색 테스트 완료")


if __name__ == "__main__":
    main()