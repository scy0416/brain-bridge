"""
api/main.py

Open WebUI가 호출하는 OpenAI 호환 API를 흉내 내는 FastAPI 앱.

  - GET  /health              : 헬스체크
  - GET  /v1/models           : Open WebUI의 모델 선택 목록에 노출
  - POST /v1/chat/completions : agent.graph의 run_agent(비스트리밍) 또는
                                 run_agent_stream(스트리밍)으로 실제 그래프 실행

request.stream 값에 따라 분기한다:
  - stream=True  -> run_agent_stream으로 토큰을 받아 OpenAI SSE
                     chat.completion.chunk 포맷으로 실시간 전달
  - stream=False -> run_agent로 완성된 답변을 한 번에 반환 (기존 방식)

두 경우 모두 그래프 내부 구조(state 스키마, 노드 분기, 이벤트 형식)는
agent.graph의 두 함수가 전부 캡슐화하므로 이 파일은 신경 쓰지 않는다.
"""

import os
import uuid

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from agent.graph import run_agent, run_agent_stream
from api.schemas import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
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


def _format_sse(chunk: ChatCompletionChunk) -> str:
    """ChatCompletionChunk를 OpenAI SSE 규격 한 줄로 포맷팅한다."""
    return f"data: {chunk.model_dump_json()}\n\n"


async def _stream_chat_completions(messages: list[dict], model: str):
    """run_agent_stream의 이벤트를 OpenAI 호환 SSE 청크로 변환해 순차 전달.

    progress 이벤트는 delta.reasoning_content로, token 이벤트는 delta.content
    로 각각 보낸다. Open WebUI는 reasoning_content 델타를 네이티브로 인식해서
    별도의 접이식 "생각 중" UI로 렌더링하고, content와 명확히 분리해서
    보여준다 (DeepSeek R1 등 reasoning 모델과 동일한 메커니즘).

    이전에 시도했던 raw HTML(<details><summary>)이나 마크다운 인용구
    우회 방식보다 이 방식이 더 낫다 - Open WebUI가 정식으로 파싱하는
    필드라서 렌더러의 HTML escape 여부와 무관하게 항상 의도대로 접이식
    UI로 그려진다.
    """
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    def _reasoning_chunk(text: str) -> ChatCompletionChunk:
        return ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[
                ChatCompletionChunkChoice(
                    delta=ChatCompletionChunkDelta(reasoning_content=text)
                )
            ],
        )

    def _content_chunk(text: str) -> ChatCompletionChunk:
        return ChatCompletionChunk(
            id=completion_id,
            model=model,
            choices=[
                ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(content=text))
            ],
        )

    # 첫 청크: role만 포함 (OpenAI 스펙 관례 - Open WebUI도 이 형태를 기대)
    first_chunk = ChatCompletionChunk(
        id=completion_id,
        model=model,
        choices=[
            ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(role="assistant"))
        ],
    )
    yield _format_sse(first_chunk)

    async for event in run_agent_stream(messages):
        if event["type"] == "progress":
            yield _format_sse(_reasoning_chunk(f"{event['message']}\n"))

        elif event["type"] == "token":
            yield _format_sse(_content_chunk(event["content"]))

    # 종료 청크: 빈 delta + finish_reason="stop"
    final_chunk = ChatCompletionChunk(
        id=completion_id,
        model=model,
        choices=[
            ChatCompletionChunkChoice(delta=ChatCompletionChunkDelta(), finish_reason="stop")
        ],
    )
    yield _format_sse(final_chunk)
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    # Pydantic ChatMessage 리스트 -> run_agent(_stream)이 기대하는 순수
    # dict 리스트(OpenAI 포맷)로 변환. agent.graph는 이 파일의 Pydantic
    # 모델을 전혀 모르는 순수 인터페이스이므로 여기서 변환 책임을 진다.
    messages = [m.model_dump() for m in request.messages]

    if request.stream:
        return StreamingResponse(
            _stream_chat_completions(messages, request.model),
            media_type="text/event-stream",
        )

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