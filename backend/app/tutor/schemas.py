from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.llm.models import MessageRole
from app.tutor.policies import TutorMode


class CreateSessionRequest(BaseModel):
    language: Literal["auto", "ru", "kk", "mixed"] = "auto"
    grade: int | None = Field(default=None, ge=1, le=12)


class SessionMessage(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1)
    created_at: datetime


class TutorSession(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    session_id: UUID
    created_at: datetime
    updated_at: datetime
    messages: list[SessionMessage] = Field(default_factory=list)
    mode: TutorMode = TutorMode.DIRECT_EXPLANATION
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionCreatedResponse(BaseModel):
    session_id: UUID
    created_at: datetime
    mode: TutorMode


class SessionResponse(BaseModel):
    session_id: UUID
    created_at: datetime
    updated_at: datetime
    mode: TutorMode
    message_count: int
    messages: list[SessionMessage]
    metadata: dict[str, Any]

    @classmethod
    def from_session(cls, session: TutorSession) -> "SessionResponse":
        return cls(
            session_id=session.session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            mode=session.mode,
            message_count=len(session.messages),
            messages=session.messages,
            metadata=session.metadata,
        )


class TutorMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    mode: TutorMode = TutorMode.AUTO

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned


class StreamEvent(BaseModel):
    event: Literal["start", "delta", "metadata", "done", "error"]
    data: dict[str, Any]

