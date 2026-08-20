"""
src/router/ollama_client.py

Router Agent와 Answer Agent가 공유하는 Ollama /api/chat 호출 함수.
(지금까지 테스트 스크립트마다 중복됐던 호출 코드를 하나로 정리)

call_chat: 기존 동기 버전. Base/Router Agent가 계속 사용 (변경 없음).
stream_chat: Answer Agent 전용 비동기 스트리밍 버전 (신규). 토큰 조각을
             순차적으로 yield한다. requests는 동기 라이브러리라 진짜
             스트리밍에 부적합하므로, 이 함수만 httpx.AsyncClient를 쓴다.
"""

import json
import os

import httpx
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


async def stream_chat(messages: list, think: bool = False, model: str = LLM_MODEL):
    """
    Ollama /api/chat을 stream=True로 호출해서 토큰 조각을 순차적으로 yield한다.

    Answer Agent 전용 (function-calling을 쓰지 않으므로 tools 파라미터는
    없음 - Base/Router Agent는 기존 call_chat을 그대로 사용).

    Ollama의 스트리밍 응답은 NDJSON(줄바꿈으로 구분된 JSON 객체) 형식이며,
    각 줄이 {"message": {"content": "부분 토큰"}, "done": false, ...} 형태다.
    마지막 줄은 "done": true와 함께 누적 통계만 담고 content는 보통 비어있다.

    :param messages: [{"role": "system"|"user"|"assistant", "content": ...}, ...]
    :param think: thinking 모드 사용 여부
    :param model: 사용할 모델 (기본값: 환경변수 LLM_MODEL)
    :yield: 토큰 조각 문자열 (message.content의 델타)
    """
    payload = {"model": model, "think": think, "messages": messages, "stream": True}

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            async with client.stream("POST", f"{OLLAMA_HOST}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    message = chunk.get("message") or {}
                    content = message.get("content")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
    except httpx.HTTPError as e:
        raise LLMCallError(f"Ollama 스트리밍 채팅 API 호출 실패: {e}") from e