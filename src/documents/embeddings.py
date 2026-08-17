"""
src/documents/embeddings.py

Ollama의 /api/embeddings 엔드포인트를 호출해 텍스트를 BGE-M3 임베딩 벡터로 변환한다.
"""

import os
import time
from typing import List

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")
EXPECTED_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))

REQUEST_TIMEOUT = 120  # 초 (웜업을 해도 예외적으로 콜드 스타트가 발생할 가능성까지 감안한 여유값)


class EmbeddingError(Exception):
    """임베딩 생성 실패 시 발생하는 예외."""


def get_embedding(text: str, model: str = EMBEDDING_MODEL) -> List[float]:
    """
    단일 텍스트를 임베딩 벡터로 변환한다.

    :param text: 임베딩할 텍스트
    :param model: 사용할 Ollama 임베딩 모델 (기본값: 환경변수 EMBEDDING_MODEL, 없으면 bge-m3)
    :return: 실수(float) 리스트 형태의 임베딩 벡터
    :raises EmbeddingError: API 호출 실패, 응답 형식 이상, 차원 불일치 시
    """
    if not text or not text.strip():
        raise EmbeddingError("빈 텍스트는 임베딩할 수 없습니다")

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise EmbeddingError(f"Ollama 임베딩 API 호출 실패: {e}") from e

    data = response.json()
    embedding = data.get("embedding")

    if not embedding:
        raise EmbeddingError(f"응답에 embedding 필드가 없습니다: {data}")

    if len(embedding) != EXPECTED_DIM:
        raise EmbeddingError(
            f"임베딩 차원 불일치: 기대={EXPECTED_DIM}, 실제={len(embedding)} "
            f"(모델={model} — 스키마의 document_chunks.embedding vector({EXPECTED_DIM})와 다릅니다)"
        )

    return embedding


def get_embeddings_batch(texts: List[str], model: str = EMBEDDING_MODEL) -> List[List[float]]:
    """
    여러 텍스트를 순차적으로 임베딩한다.
    (Ollama의 /api/embeddings는 프롬프트 1개씩만 받으므로 배치는 순차 호출로 구현)

    :param texts: 임베딩할 텍스트 리스트
    :param model: 사용할 Ollama 임베딩 모델
    :return: 각 텍스트에 대응하는 임베딩 벡터 리스트
    """
    return [get_embedding(text, model=model) for text in texts]


def embed_chunks(
    chunks: List[dict],
    model: str = EMBEDDING_MODEL,
    progress_interval: int = 20,
    max_retries: int = 2,
) -> List[dict]:
    """
    문서 청크 리스트(load_all_chunks() 결과) 전체를 순차적으로 임베딩하고,
    각 청크 dict에 "embedding" 필드를 추가해서 반환한다.

    처리 방식: 순차(sequential) 호출.
    - Ollama /api/embeddings가 프롬프트 1개씩만 처리하는 API라 진짜 배치가 불가능함
    - 데이터 규모(수백 개)가 작아 순차 처리로도 충분히 짧은 시간에 끝남
    - 실패 시 어느 청크에서 멈췄는지 추적하기 쉬움 (배치 병렬 처리 대비 디버깅 용이)

    :param chunks: load_all_chunks()가 반환한 청크 dict 리스트
    :param model: 사용할 임베딩 모델
    :param progress_interval: 몇 개마다 진행 상황을 출력할지
    :param max_retries: 개별 청크 임베딩 실패 시 재시도 횟수
    :return: 각 청크에 "embedding" 키가 추가된 리스트
    """
    total = len(chunks)
    result = []
    failed = []
    start = time.time()

    for i, chunk in enumerate(chunks, start=1):
        # 검색 정확도 개선: title_path(섹션 맥락)를 본문 앞에 붙여서 임베딩한다.
        # DB에 저장되는 원문 content 자체는 바꾸지 않고, 임베딩 생성용 텍스트만 조합한다.
        title_path = chunk.get("title_path", "")
        embed_text = f"{title_path}\n{chunk['content']}" if title_path else chunk["content"]

        attempt = 0
        while True:
            try:
                embedding = get_embedding(embed_text, model=model)
                result.append({**chunk, "embedding": embedding})
                break
            except EmbeddingError as e:
                attempt += 1
                if attempt > max_retries:
                    print(f"    ⚠️  실패 (재시도 {max_retries}회 초과): "
                          f"[{chunk['doc_id']}#{chunk['chunk_index']}] {e}")
                    failed.append(chunk)
                    break
                print(f"    재시도 {attempt}/{max_retries}: "
                      f"[{chunk['doc_id']}#{chunk['chunk_index']}] {e}")

        if i % progress_interval == 0 or i == total:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            print(f"    진행: {i}/{total} ({elapsed:.1f}초 경과, {rate:.1f}개/초)")

    elapsed_total = time.time() - start
    print(f"    완료: 성공 {len(result)}개, 실패 {len(failed)}개, 총 {elapsed_total:.1f}초 소요")

    if failed:
        print("    실패한 청크 목록:")
        for c in failed:
            print(f"      - [{c['doc_id']}#{c['chunk_index']}] {c['title_path']}")

    return result