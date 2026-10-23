from collections.abc import AsyncIterator, Sequence

from app.core.exceptions import OllamaUnavailableError
from app.llm.base import LLMProvider
from app.llm.models import (
    ChatMessage,
    ChatOptions,
    ChatResult,
    ProviderHealth,
    StreamChunk,
)


class FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        chunks: list[str] | None = None,
        *,
        fail_after_chunks: int | None = None,
    ) -> None:
        self.chunks = chunks or ["Сәлем", "!"]
        self.fail_after_chunks = fail_after_chunks
        self.requests: list[list[ChatMessage]] = []
        self.closed = False

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> ChatResult:
        self.requests.append(list(messages))
        return ChatResult(text="".join(self.chunks))

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> AsyncIterator[StreamChunk]:
        self.requests.append(list(messages))
        for index, text in enumerate(self.chunks):
            if self.fail_after_chunks is not None and index >= self.fail_after_chunks:
                raise OllamaUnavailableError("Test provider failed.")
            yield StreamChunk(text=text)
        yield StreamChunk(
            done=True,
            finish_reason="stop",
            prompt_tokens=12,
            generated_tokens=len(self.chunks),
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            status="ok",
            provider="fake",
            model="fake-model",
            version="test",
        )

    async def close(self) -> None:
        self.closed = True

