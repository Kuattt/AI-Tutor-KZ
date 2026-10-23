import asyncio
import time
from dataclasses import dataclass

from pydantic import BaseModel


class GenerationMetrics(BaseModel):
    total: int
    successful: int
    failed: int
    cancelled: int
    active: int
    avg_duration_ms: float | None
    avg_first_token_ms: float | None
    recent_duration_ms: float | None
    generated_tokens: int
    generated_characters: int


class SessionMetrics(BaseModel):
    created_total: int
    active: int


class MetricsSnapshot(BaseModel):
    generations: GenerationMetrics
    sessions: SessionMetrics


@dataclass
class GenerationTracker:
    started_at: float
    first_token_at: float | None = None
    finished: bool = False


class OperationalMetrics:
    """Concurrency-safe, process-local operational counters."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._generation_total = 0
        self._generation_successful = 0
        self._generation_failed = 0
        self._generation_cancelled = 0
        self._generation_active = 0
        self._duration_total = 0.0
        self._duration_count = 0
        self._first_token_total = 0.0
        self._first_token_count = 0
        self._recent_duration: float | None = None
        self._generated_tokens = 0
        self._generated_characters = 0
        self._sessions_created = 0

    async def generation_started(self) -> GenerationTracker:
        tracker = GenerationTracker(started_at=time.perf_counter())
        async with self._lock:
            self._generation_total += 1
            self._generation_active += 1
        return tracker

    async def first_token(self, tracker: GenerationTracker) -> None:
        if tracker.first_token_at is not None:
            return
        now = time.perf_counter()
        async with self._lock:
            if tracker.first_token_at is None:
                tracker.first_token_at = now
                self._first_token_total += now - tracker.started_at
                self._first_token_count += 1

    async def generation_succeeded(
        self,
        tracker: GenerationTracker,
        *,
        generated_tokens: int | None,
        generated_characters: int,
    ) -> tuple[float, float | None]:
        duration, first_token = await self._finish(tracker)
        async with self._lock:
            self._generation_successful += 1
            self._generated_tokens += generated_tokens or 0
            self._generated_characters += generated_characters
        return duration, first_token

    async def generation_failed(
        self, tracker: GenerationTracker
    ) -> tuple[float, float | None]:
        duration, first_token = await self._finish(tracker)
        async with self._lock:
            self._generation_failed += 1
        return duration, first_token

    async def generation_cancelled(
        self, tracker: GenerationTracker
    ) -> tuple[float, float | None]:
        duration, first_token = await self._finish(tracker)
        async with self._lock:
            self._generation_cancelled += 1
        return duration, first_token

    async def _finish(
        self, tracker: GenerationTracker
    ) -> tuple[float, float | None]:
        now = time.perf_counter()
        duration = now - tracker.started_at
        first_token = (
            tracker.first_token_at - tracker.started_at
            if tracker.first_token_at is not None
            else None
        )
        async with self._lock:
            if tracker.finished:
                return duration, first_token
            tracker.finished = True
            self._generation_active = max(0, self._generation_active - 1)
            self._duration_total += duration
            self._duration_count += 1
            self._recent_duration = duration
        return duration, first_token

    async def session_created(self) -> None:
        async with self._lock:
            self._sessions_created += 1

    async def snapshot(self, *, active_sessions: int) -> MetricsSnapshot:
        async with self._lock:
            return MetricsSnapshot(
                generations=GenerationMetrics(
                    total=self._generation_total,
                    successful=self._generation_successful,
                    failed=self._generation_failed,
                    cancelled=self._generation_cancelled,
                    active=self._generation_active,
                    avg_duration_ms=(
                        round(
                            self._duration_total / self._duration_count * 1000,
                            3,
                        )
                        if self._duration_count
                        else None
                    ),
                    avg_first_token_ms=(
                        round(
                            self._first_token_total
                            / self._first_token_count
                            * 1000,
                            3,
                        )
                        if self._first_token_count
                        else None
                    ),
                    recent_duration_ms=(
                        round(self._recent_duration * 1000, 3)
                        if self._recent_duration is not None
                        else None
                    ),
                    generated_tokens=self._generated_tokens,
                    generated_characters=self._generated_characters,
                ),
                sessions=SessionMetrics(
                    created_total=self._sessions_created,
                    active=active_sessions,
                ),
            )
