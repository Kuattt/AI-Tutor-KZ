from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence

from app.llm.models import (
    ChatMessage,
    ChatOptions,
    ChatResult,
    ProviderHealth,
    StreamChunk,
)


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> ChatResult:
        """Generate one complete assistant response."""

    @abstractmethod
    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> AsyncIterator[StreamChunk]:
        """Yield progressive generation chunks."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Check provider reachability and configured model availability."""

    @abstractmethod
    async def close(self) -> None:
        """Release provider resources."""

