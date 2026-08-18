"""
src/router/ollama_client.py

Router Agent와 Answer Agent가 공유하는 Ollama /api/chat 호출 함수.
(지금까지 테스트 스크립트마다 중복됐던 호출 코드를 하나로 정리)
"""

import os

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:e4b")
REQUEST_TIMEOUT = 300  # 초 (콜드 스타트 대비 여유값, generate.py와 동일 기준)


class LLMCallError(Exception):
    """Ollama 채팅 API 호출 실패 시 발생하는 예외."""


def call_chat(messages: list, tools: list = None, think: bool = False, model: str = LLM_MODEL) -> dict:
    """
    Ollama /api/chat을 호출하고 message 딕셔너리를 반환한다.

    :param messages: [{"role": "system"|"user"|"assistant", "content": ...}, ...]
    :param tools: function-calling에 사용할 도구 스키마 리스트 (없으면 생략)
    :param think: thinking 모드 사용 여부
    :param model: 사용할 모델 (기본값: 환경변수 LLM_MODEL)
    :return: 응답의 "message" 필드 (role/content/tool_calls 포함)
    """
    payload = {"model": model, "think": think, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = tools

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat", json=payload, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise LLMCallError(f"Ollama 채팅 API 호출 실패: {e}") from e

    data = response.json()
    message = data.get("message")
    if message is None:
        raise LLMCallError(f"응답에 message 필드가 없습니다: {data}")

    return message