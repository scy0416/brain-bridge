"""
api/main.py

Open WebUI가 호출하는 OpenAI 호환 API를 흉내 내는 FastAPI 앱.

  - GET  /health              : 헬스체크
  - GET  /v1/models           : Open WebUI의 모델 선택 목록에 노출
  - POST /v1/chat/completions : agent.graph.run_agent로 실제 그래프 실행

/v1/chat/completions은 agent.graph.run_agent(messages) -> str 하나만
호출한다. 그래프 내부 구조(state 스키마, 노드 분기 등)는 run_agent가
전부 캡슐화하므로 이 파일은 신경 쓰지 않는다.

주의: 아직 스트리밍(SSE)은 지원하지 않는다 — Open WebUI가 stream=True로
요청해도 지금은 완성된 답변을 한 번에 반환한다. 스트리밍 지원은 이후
단계에서 추가한다.
"""

import os
import uuid

from fastapi import FastAPI

from agent.graph import run_agent
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
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    # Pydantic ChatMessage 리스트 -> run_agent가 기대하는 순수 dict 리스트
    # (OpenAI 포맷) 로 변환. run_agent는 agent.graph 내부 구조를 전혀
    # 모르는 순수 인터페이스이므로 여기서 변환 책임을 진다.
    messages = [m.model_dump() for m in request.messages]

    answer = await run_agent(messages)

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        model=request.model,
        choices=[
            ChatCompletionChoice(
                message=ChatCompletionResponseMessage(content=answer)
            )
        ],
    )