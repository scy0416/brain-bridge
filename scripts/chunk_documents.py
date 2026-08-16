"""
scripts/chunk_documents.py

data/documents/DOC-001~040.md 전체를 청킹하고, 결과를 요약/샘플 출력하며
기본적인 무결성(빈 청크 없음, 타입 값 유효성)을 검증한다.

사용법:
    docker compose run --rm app python scripts/chunk_documents.py
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from documents.loader import load_all_chunks

VALID_TYPES = {"incident_report", "technical_doc", "meeting_note", "proposal"}


def main():
    chunks = load_all_chunks()
    print(f"==> 총 {len(chunks)}개 청크 생성 (40개 문서 대상)")

    per_doc = Counter(c["doc_id"] for c in chunks)
    print(f"    문서 수: {len(per_doc)}")
    print(f"    문서당 청크 수 — 평균: {sum(per_doc.values()) / len(per_doc):.1f}, "
          f"최소: {min(per_doc.values())}, 최대: {max(per_doc.values())}")

    per_type = Counter(c["type"] for c in chunks)
    print(f"    타입별 청크 수: {dict(per_type)}")

    content_lengths = [len(c["content"]) for c in chunks]
    print(f"    청크 길이(자) — 평균: {sum(content_lengths) / len(content_lengths):.0f}, "
          f"최소: {min(content_lengths)}, 최대: {max(content_lengths)}")

    print("\n==> 샘플 청크 (앞 8개, 수작업 검토용)")
    for c in chunks[:8]:
        preview = c["content"][:60].replace("\n", " ")
        print(f"    [{c['doc_id']}#{c['chunk_index']}] ({c['type']}) {c['title_path']}")
        print(f"        {preview}...")

    print("\n==> 무결성 검증")
    assert len(chunks) > 0, "청크가 하나도 생성되지 않았습니다"
    assert len(per_doc) == 40, f"문서 수가 40개가 아닙니다: {len(per_doc)}"
    for c in chunks:
        assert c["content"].strip(), f"빈 청크 발견: {c['doc_id']}#{c['chunk_index']}"
        assert c["type"] in VALID_TYPES, f"알 수 없는 타입: {c['type']} ({c['doc_id']})"
        assert c["title_path"], f"title_path가 비어있는 청크: {c['doc_id']}#{c['chunk_index']}"

    print("✅ 청킹 완료 및 무결성 검증 통과 — 40개 문서, 에러 없음")


if __name__ == "__main__":
    main()