import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.exceptions import SessionNotFoundError
from app.llm.models import MessageRole
from app.tutor.policies import TutorMode
from app.tutor.schemas import SessionMessage, TutorSession

Clock = Callable[[], datetime]


class TutorSessionStore(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        language: str = "auto",
        grade: int | None = None,
    ) -> TutorSession:
        """Create and store a tutor session."""

    @abstractmethod
    async def get(self, session_id: UUID) -> TutorSession:
        """Return a non-expired session or raise SessionNotFoundError."""

    @abstractmethod
    async def delete(self, session_id: UUID) -> None:
        """Delete a session or raise SessionNotFoundError."""

    @abstractmethod
    async def add_message(
        self,
        session_id: UUID,
        role: MessageRole,
        content: str,
    ) -> TutorSession:
        """Append a message and enforce the configured history limit."""

    @abstractmethod
    async def update_policy(
        self,
        session_id: UUID,
        *,
        mode: TutorMode,
        guided_steps: int,
    ) -> TutorSession:
        """Persist policy state for a session."""

    @abstractmethod
    async def begin_generation(self, session_id: UUID) -> TutorSession:
        """Atomically protect a session from expiry cleanup."""

    @abstractmethod
    async def end_generation(self, session_id: UUID) -> None:
        """Release a session's generation protection."""

    @abstractmethod
    async def cleanup_expired(self) -> list[UUID]:
        """Remove inactive expired sessions and return their IDs."""

    @abstractmethod
    async def count(self) -> int:
        """Return the number of non-expired sessions."""


class InMemoryTutorSessionStore(TutorSessionStore):
    def __init__(
        self,
        max_history_messages: int,
        *,
        ttl_minutes: float = 60.0,
        clock: Clock | None = None,
    ) -> None:
        self._max_history_messages = max_history_messages
        self._ttl = timedelta(minutes=ttl_minutes)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sessions: dict[UUID, TutorSession] = {}
        self._active_generations: set[UUID] = set()
        self._lock = asyncio.Lock()

    @staticmethod
    def _copy(session: TutorSession) -> TutorSession:
        return session.model_copy(deep=True)

    def _is_expired(self, session: TutorSession, now: datetime) -> bool:
        return now - session.updated_at >= self._ttl

    def _get_live_locked(
        self,
        session_id: UUID,
        now: datetime,
    ) -> TutorSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError()
        if (
            session_id not in self._active_generations
            and self._is_expired(session, now)
        ):
            del self._sessions[session_id]
            raise SessionNotFoundError()
        return session

    async def create(
        self,
        *,
        language: str = "auto",
        grade: int | None = None,
    ) -> TutorSession:
        now = self._clock()
        session = TutorSession(
            session_id=uuid4(),
            created_at=now,
            updated_at=now,
            mode=TutorMode.DIRECT_EXPLANATION,
            metadata={"language": language, "grade": grade, "guided_steps": 0},
        )
        async with self._lock:
            self._sessions[session.session_id] = session
        return self._copy(session)

    async def get(self, session_id: UUID) -> TutorSession:
        async with self._lock:
            return self._copy(self._get_live_locked(session_id, self._clock()))

    async def delete(self, session_id: UUID) -> None:
        async with self._lock:
            self._get_live_locked(session_id, self._clock())
            del self._sessions[session_id]
            self._active_generations.discard(session_id)

    async def add_message(
        self,
        session_id: UUID,
        role: MessageRole,
        content: str,
    ) -> TutorSession:
        async with self._lock:
            now = self._clock()
            session = self._get_live_locked(session_id, now)
            session.messages.append(
                SessionMessage(role=role, content=content, created_at=now)
            )
            if len(session.messages) > self._max_history_messages:
                session.messages = session.messages[-self._max_history_messages :]
            session.updated_at = now
            return self._copy(session)

    async def update_policy(
        self,
        session_id: UUID,
        *,
        mode: TutorMode,
        guided_steps: int,
    ) -> TutorSession:
        async with self._lock:
            now = self._clock()
            session = self._get_live_locked(session_id, now)
            session.mode = mode
            session.metadata["guided_steps"] = guided_steps
            session.updated_at = now
            return self._copy(session)

    async def begin_generation(self, session_id: UUID) -> TutorSession:
        async with self._lock:
            session = self._get_live_locked(session_id, self._clock())
            self._active_generations.add(session_id)
            return self._copy(session)

    async def end_generation(self, session_id: UUID) -> None:
        async with self._lock:
            self._active_generations.discard(session_id)

    async def cleanup_expired(self) -> list[UUID]:
        async with self._lock:
            now = self._clock()
            expired = [
                session_id
                for session_id, session in self._sessions.items()
                if session_id not in self._active_generations
                and self._is_expired(session, now)
            ]
            for session_id in expired:
                del self._sessions[session_id]
            return expired

    async def count(self) -> int:
        await self.cleanup_expired()
        async with self._lock:
            return len(self._sessions)
