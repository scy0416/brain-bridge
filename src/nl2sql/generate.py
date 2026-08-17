"""
src/nl2sql/generate.py

Ollama(Gemma 4 E4B)를 호출해 자연어 질문을 SQL로 변환한다.
"""

import os

import requests

from nl2sql.prompt import SYSTEM_PROMPT, build_user_message

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:e4b")
REQUEST_TIMEOUT = 60


class SQLGenerationError(Exception):
    """SQL 생성 실패 시 발생하는 예외."""


def generate_sql(question: str, model: str = LLM_MODEL) -> str:
    """
    자연어 질문을 SQL 쿼리 텍스트로 변환한다. (실행/검증은 하지 않음 — 다음 단계에서 처리)

    :param question: 사용자의 자연어 질문
    :param model: 사용할 Ollama LLM 모델
    :return: LLM이 생성한 원시 텍스트 (SQL 또는 "NO_QUERY")
    """
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "think": False,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_message(question)},
                ],
                "stream": False,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise SQLGenerationError(f"Ollama 호출 실패: {e}") from e

    data = response.json()
    content = data.get("message", {}).get("content", "")
    if not content:
        raise SQLGenerationError(f"응답에 content가 없습니다: {data}")

    return content.strip()