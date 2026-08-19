"""
src/nl2sql/generate.py

Ollama(Gemma 4 E4B)를 호출해 자연어 질문을 SQL로 변환한다.
"""

import os

import requests

from nl2sql.prompt import SYSTEM_PROMPT, build_user_message

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:e4b")
REQUEST_TIMEOUT = 300  # 초 (웜업을 해도 예외적으로 콜드 스타트가 발생할 가능성까지 감안한 여유값)


class SQLGenerationError(Exception):
    """SQL 생성 실패 시 발생하는 예외."""


def _call_llm(messages: list, model: str = LLM_MODEL) -> str:
    """Ollama /api/chat을 호출해서 응답 텍스트를 반환하는 공용 헬퍼."""
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={"model": model, "think": False, "messages": messages, "stream": False},
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


def generate_sql(question: str, model: str = LLM_MODEL) -> str:
    """
    자연어 질문을 SQL 쿼리 텍스트로 변환한다. (실행/검증은 하지 않음 — 다음 단계에서 처리)

    :param question: 사용자의 자연어 질문
    :param model: 사용할 Ollama LLM 모델
    :return: LLM이 생성한 원시 텍스트 (SQL 또는 "NO_QUERY")
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(question)},
    ]
    return _call_llm(messages, model=model)


def regenerate_sql_after_error(
    question: str, previous_sql: str, error_message: str, model: str = LLM_MODEL
) -> str:
    """
    실행에 실패한 이전 SQL과 실제 DB 에러 메시지를 모델에게 보여주고,
    수정된 SQL을 다시 생성하게 한다. (도구 내부 제한적 자기 수정 루프 —
    ReAct처럼 여러 도구를 오가는 게 아니라, NL2SQL 도구 하나 안에서만
    "생성→실행 실패→에러 피드백→재생성"을 반복하는 좁은 범위의 재시도)

    :param question: 원본 질문
    :param previous_sql: 실행에 실패했던 SQL
    :param error_message: DB가 반환한 실제 에러 메시지
    :param model: 사용할 Ollama LLM 모델
    :return: LLM이 생성한 원시 텍스트 (수정된 SQL 또는 "NO_QUERY")
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(question)},
        {"role": "assistant", "content": previous_sql},
        {
            "role": "user",
            "content": (
                f"위 SQL을 PostgreSQL에서 실행했더니 다음 오류가 발생했습니다:\n"
                f"{error_message}\n\n"
                f"이 오류의 원인을 분석해서, 문제를 수정한 올바른 PostgreSQL SELECT "
                f"쿼리 하나만 다시 출력하세요. (설명 없이 SQL만)"
            ),
        },
    ]
    return _call_llm(messages, model=model)