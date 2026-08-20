"""
api/schemas.py

Open WebUI가 호출하는 OpenAI 호환 엔드포인트(/v1/models,
/v1/chat/completions)에 필요한 최소한의 요청/응답 스키마.

전체 OpenAI 스펙을 다 구현하지 않고, Open WebUI가 실제로 참조하는
필드 위주로만 최소 구성했다 (예: logprobs, tools 등 미사용 필드는
생략). 필요해지면 그때 추가한다.
"""

import time
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------- /v1/chat/completions 요청 ----------

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    # temperature/top_p 등은 Open WebUI가 기본적으로 함께 보내지만,
    # 이 어댑터는 Ollama 호출부(call_chat)를 그대로 재사용하므로 지금
    # 단계에서는 값만 받아두고 실제로 사용하지는 않는다.
    temperature: Optional[float] = None


# ---------- /v1/chat/completions 응답 ----------

class ChatCompletionResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionResponseMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChoice]


# ---------- /v1/chat/completions 스트리밍 응답 (SSE 청크) ----------

class ChatCompletionChunkDelta(BaseModel):
    # 첫 청크는 role만, 이후 청크는 content만, 마지막 청크는 둘 다 비움
    # (OpenAI 스펙 관례 - Open WebUI도 이 형태를 그대로 기대함)
    role: Optional[Literal["assistant"]] = None
    content: Optional[str] = None


class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChunkChoice]


# ---------- /v1/models 응답 ----------

class ModelInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "brain-bridge"


class ModelsResponse(BaseModel):
    object: Literal["list"] = "list"
    data: List[ModelInfo]