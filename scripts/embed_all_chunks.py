"""
scripts/embed_all_chunks.py

data/documents/의 40개 문서에서 나온 전체 청크(약 200개)를 순차적으로 임베딩한다.
(DB INSERT는 다음 단계에서 별도 스크립트로 처리 — 이 단계는 임베딩 생성까지만 검증)

사용법:
    docker compose run --rm app python scripts/embed_all_chunks.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from documents.embeddings import EXPECTED_DIM, embed_chunks
from documents.loader import load_all_chunks


def main():
    print("==> [1/2] 청크 로드")
    chunks = load_all_chunks()
    print(f"    총 {len(chunks)}개 청크")

    print("\n==> [2/2] 순차 임베딩 생성 (Ollama BGE-M3)")
    embedded = embed_chunks(chunks, progress_interval=20)

    print("\n==> 검증")
    assert len(embedded) > 0, "임베딩된 청크가 없습니다"
    dims = {len(c["embedding"]) for c in embedded}
    assert dims == {EXPECTED_DIM}, f"차원이 일관되지 않습니다: {dims}"

    success_rate = len(embedded) / len(chunks) * 100
    print(f"    성공률: {len(embedded)}/{len(chunks)} ({success_rate:.1f}%)")
    print(f"    모든 임베딩 차원 일치: {EXPECTED_DIM}")

    if len(embedded) == len(chunks):
        print("\n✅ 전체 청크 임베딩 완료 — 실패 없음")
    else:
        print(f"\n⚠️  일부 청크 임베딩 실패 ({len(chunks) - len(embedded)}건) — 위 로그 확인")


if __name__ == "__main__":
    main()