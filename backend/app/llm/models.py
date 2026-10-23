from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)


class ChatOptions(BaseModel):
    max_tokens: int = 450
    temperature: float = 0.1


class ChatResult(BaseModel):
    text: str
    finish_reason: str = "stop"
    prompt_tokens: int | None = None
    generated_tokens: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamChunk(BaseModel):
    text: str = ""
    done: bool = False
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    generated_tokens: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderHealth(BaseModel):
    status: str
    provider: str
    model: str
    version: str | None = None

