"""
src/documents/store.py

임베딩된 문서 청크를 PostgreSQL의 document_chunks 테이블(pgvector)에 저장한다.
"""

from typing import List

import psycopg2.extras
from pgvector.psycopg2 import register_vector

from graph.age_client import get_connection  # postgres 커넥션 재사용 (graph 전용 함수 아님)


def get_connection_with_vector():
    """
    document_chunks.embedding(vector 타입)에 파이썬 list[float]를 그대로 넘길 수 있도록
    pgvector 어댑터를 등록한 커넥션을 반환한다.
    """
    conn = get_connection()
    register_vector(conn)
    return conn


def insert_chunk(conn, chunk: dict) -> None:
    """
    청크 하나를 document_chunks에 INSERT한다.
    chunk는 doc_id, chunk_index, content, embedding, type, title, title_path 키를 가져야 한다.
    """
    metadata = {
        "type": chunk["type"],
        "title": chunk.get("title", ""),
        "title_path": chunk.get("title_path", ""),
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_chunks (doc_id, chunk_index, content, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                chunk["doc_id"],
                chunk["chunk_index"],
                chunk["content"],
                chunk["embedding"],
                psycopg2.extras.Json(metadata),
            ),
        )


def insert_chunks(conn, chunks: List[dict], commit_every: int = 20) -> int:
    """
    청크 리스트 전체를 document_chunks에 순차 INSERT한다.
    commit_every개마다 커밋해서, 중간에 실패해도 그 이전까지는 반영되도록 한다.

    :return: 성공적으로 INSERT된 청크 수
    """
    inserted = 0
    for i, chunk in enumerate(chunks, start=1):
        insert_chunk(conn, chunk)
        inserted += 1
        if i % commit_every == 0:
            conn.commit()
    conn.commit()
    return inserted


def count_existing_chunks(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM document_chunks;")
        (count,) = cur.fetchone()
    return count


def clear_chunks(conn) -> None:
    """document_chunks 테이블을 비운다 (--fresh 재적재용)."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE document_chunks RESTART IDENTITY;")
    conn.commit()