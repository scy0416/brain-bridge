"""
api/main.py

Open WebUI가 호출하는 OpenAI 호환 API를 흉내 내는 FastAPI 앱.

이번 단계(골격 생성)에서는 다음만 구현한다:
  - GET  /health              : 헬스체크
  - GET  /v1/models           : Open WebUI의 모델 선택 목록에 노출
  - POST /v1/chat/completions : 스텁 응답 (아직 agent.graph와 연결 안 함)

/v1/chat/completions을 실제 LangGraph 실행(agent.graph.graph.ainvoke)에
연결하는 작업과 스트리밍(SSE) 지원은 다음 단계에서 진행한다. 지금은
Open WebUI <-> FastAPI 간 연결 자체(핸드셰이크, 모델 목록 노출, 요청/
응답 스키마)가 정상 동작하는지 독립적으로 검증하기 위한 스텁이다.

주의: 이 스텁은 요청에 포함된 마지막 user 메시지를 그대로 되돌려주는
방식으로, 실제 에이전트 로직은 전혀 타지 않는다.
"""

import os
import uuid

from fastapi import FastAPI

from api.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseMessage,
    ModelInfo,
    ModelsResponse,
)

# Open WebUI의 모델 선택 목록(/v1/models)에 노출될 모델 ID.
# docker-compose의 .env를 통해 주입되는 환경변수를 그대로 읽는다
# (기존 프로젝트 관례 - answer_node.py의 LLM_MODEL과 동일한 패턴).
API_MODEL_ID = os.environ.get("API_MODEL_ID", "brain-bridge")

app = FastAPI(title="Brain Bridge OpenAI-compatible API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/models", response_model=ModelsResponse)
def list_models() -> ModelsResponse:
    return ModelsResponse(data=[ModelInfo(id=API_MODEL_ID)])


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    # 마지막 user 메시지 추출 (아직 그래프에 연결하지 않은 스텁 단계)
    last_user_message = next(
        (m.content for m in reversed(request.messages) if m.role == "user"),
        "",
    )

    stub_content = (
        "[스텁 응답 - 아직 에이전트에 연결되지 않았습니다]\n"
        f"수신한 질문: {last_user_message}"
    )

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        model=request.model,
        choices=[
            ChatCompletionChoice(
                message=ChatCompletionResponseMessage(content=stub_content)
            )
        ],
    )