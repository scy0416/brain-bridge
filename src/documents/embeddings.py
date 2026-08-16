"""
src/documents/embeddings.py

Ollama의 /api/embeddings 엔드포인트를 호출해 텍스트를 BGE-M3 임베딩 벡터로 변환한다.
"""

import os
from typing import List

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")
EXPECTED_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))

REQUEST_TIMEOUT = 30  # 초


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