import asyncio
from collections.abc import AsyncIterator, Sequence

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.models import (
    ChatMessage,
    ChatOptions,
    ChatResult,
    ProviderHealth,
    StreamChunk,
)
from app.tutor.schemas import CreateSessionRequest, TutorMessageRequest
from app.tutor.service import TutorService
from app.tutor.session_store import InMemoryTutorSessionStore


class DisconnectThenRecoverProvider(LLMProvider):
    def __init__(self) -> None:
        self.calls = 0
        self.first_chunk_sent = asyncio.Event()
        self.upstream_closed = False

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> ChatResult:
        return ChatResult(text="unused")

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> AsyncIterator[StreamChunk]:
        self.calls += 1
        if self.calls == 1:
            try:
                self.first_chunk_sent.set()
                yield StreamChunk(text="partial")
                await asyncio.Event().wait()
            finally:
                self.upstream_closed = True
        else:
            yield StreamChunk(text="recovered")
            yield StreamChunk(
                done=True,
                finish_reason="stop",
                generated_tokens=1,
            )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(status="ok", provider="fake", model="fake")

    async def close(self) -> None:
        pass


async def test_disconnect_discards_partial_and_releases_session_lock() -> None:
    provider = DisconnectThenRecoverProvider()
    settings = Settings(
        _env_file=None,
        tutor_disconnect_poll_interval_seconds=0.05,
    )
    store = InMemoryTutorSessionStore(max_history_messages=10)
    service = TutorService(provider, store, settings)
    created = await service.create_session(CreateSessionRequest())

    async def disconnected() -> bool:
        return provider.first_chunk_sent.is_set()

    first_events = [
        event
        async for event in service.stream_message(
            created.session_id,
            TutorMessageRequest(message="first"),
            disconnect_checker=disconnected,
        )
    ]
    assert first_events[0].event == "start"
    assert all(event.event in {"start", "delta"} for event in first_events)
    assert all(event.event not in {"metadata", "done", "error"} for event in first_events)
    assert provider.upstream_closed is True
    session = await service.get_session(created.session_id)
    assert [message.role.value for message in session.messages] == ["user"]

    second_events = [
        event
        async for event in service.stream_message(
            created.session_id,
            TutorMessageRequest(message="second"),
        )
    ]
    assert [event.event for event in second_events] == [
        "start",
        "delta",
        "metadata",
        "done",
    ]
    session = await service.get_session(created.session_id)
    assert session.messages[-1].content == "recovered"

    metrics = await service.metrics_snapshot()
    assert metrics.generations.cancelled == 1
    assert metrics.generations.successful == 1
    assert metrics.generations.active == 0

