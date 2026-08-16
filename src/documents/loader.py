"""
src/documents/loader.py

data/documents/index.json을 기준으로 DOC-001~040.md 전체를 읽어
chunker.chunk_markdown()으로 청킹하고, 각 청크에 문서 메타데이터
(doc_id, type)를 붙여서 반환한다.
"""

import json
import os
from typing import List, TypedDict

from documents.chunker import chunk_markdown

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "documents")
INDEX_PATH = os.path.join(DOCS_DIR, "index.json")


class DocumentChunk(TypedDict):
    doc_id: str
    chunk_index: int
    type: str
    title: str
    title_path: str
    content: str


def load_all_chunks() -> List[DocumentChunk]:
    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)

    all_chunks: List[DocumentChunk] = []
    for doc in index:
        doc_id = doc["id"]
        doc_type = doc["type"]
        title = doc["title"]
        filename = doc["filename"]
        path = os.path.join(DOCS_DIR, filename)

        with open(path, encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_markdown(text)
        for i, c in enumerate(chunks):
            all_chunks.append(
                {
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "type": doc_type,
                    "title": title,
                    "title_path": c.title_path,
                    "content": c.content,
                }
            )

    return all_chunks