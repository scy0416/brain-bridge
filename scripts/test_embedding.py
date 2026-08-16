"""
scripts/test_embedding.py

src/documents/embeddings.py의 get_embedding()이 실제로 동작하는지
단일 청크로 확인하는 테스트 스크립트.

사용법:
    docker compose run --rm app python scripts/test_embedding.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from documents.embeddings import EXPECTED_DIM, get_embedding
from documents.loader import load_all_chunks


def main():
    print("==> [1/3] 청크 로드")
    chunks = load_all_chunks()
    sample = chunks[0]
    print(f"    샘플: [{sample['doc_id']}#{sample['chunk_index']}] {sample['title_path']}")
    print(f"    내용: {sample['content'][:80]}...")

    print("\n==> [2/3] 임베딩 생성 호출")
    vector = get_embedding(sample["content"])
    print(f"    벡터 차원: {len(vector)}")
    print(f"    앞 5개 값: {vector[:5]}")

    print("\n==> [3/3] 검증")
    assert len(vector) == EXPECTED_DIM, f"차원 불일치: {len(vector)} != {EXPECTED_DIM}"
    assert all(isinstance(v, float) for v in vector), "벡터 원소가 float가 아닙니다"

    # 한국어 텍스트도 별도로 확인 (인코딩 이슈 방지)
    print("\n==> [보너스] 한국어 텍스트 임베딩 확인")
    ko_vector = get_embedding("장애 발생 시 우선 로그를 확인하고 담당자에게 즉시 보고합니다")
    print(f"    한국어 텍스트 벡터 차원: {len(ko_vector)}")
    assert len(ko_vector) == EXPECTED_DIM

    print("\n✅ 임베딩 함수 테스트 통과")


if __name__ == "__main__":
    main()