import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import AppError, LLMResponseError
from app.core.metrics import MetricsSnapshot, OperationalMetrics
from app.llm.base import LLMProvider
from app.llm.models import ChatMessage, ChatOptions, MessageRole, StreamChunk
from app.tutor.policies import GuidedSolvingPolicy
from app.tutor.prompts import build_system_prompt
from app.tutor.schemas import (
    CreateSessionRequest,
    SessionCreatedResponse,
    StreamEvent,
    TutorMessageRequest,
    TutorSession,
)
from app.tutor.session_store import TutorSessionStore

logger = logging.getLogger(__name__)
DisconnectChecker = Callable[[], Awaitable[bool]]


class ClientDisconnected(Exception):
    """Internal control flow for a client-abandoned generation."""


class TutorService:
    def __init__(
        self,
        provider: LLMProvider,
        store: TutorSessionStore,
        settings: Settings,
        policy: GuidedSolvingPolicy | None = None,
        metrics: OperationalMetrics | None = None,
    ) -> None:
        self._provider = provider
        self._store = store
        self._settings = settings
        self._policy = policy or GuidedSolvingPolicy()
        self._metrics = metrics or OperationalMetrics()
        self._session_locks: dict[UUID, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _session_lock(self, session_id: UUID) -> asyncio.Lock:
        async with self._locks_guard:
            return self._session_locks.setdefault(session_id, asyncio.Lock())

    async def create_session(
        self, request: CreateSessionRequest
    ) -> SessionCreatedResponse:
        session = await self._store.create(
            language=request.language,
            grade=request.grade,
        )
        await self._metrics.session_created()
        logger.info(
            "session_created session_id=%s language=%s grade=%s",
            session.session_id,
            request.language,
            request.grade,
        )
        return SessionCreatedResponse(
            session_id=session.session_id,
            created_at=session.created_at,
            mode=session.mode,
        )

    async def get_session(self, session_id: UUID) -> TutorSession:
        return await self._store.get(session_id)

    async def delete_session(self, session_id: UUID) -> None:
        await self._store.delete(session_id)
        async with self._locks_guard:
            self._session_locks.pop(session_id, None)
        logger.info("session_deleted session_id=%s", session_id)

    async def metrics_snapshot(self) -> MetricsSnapshot:
        return await self._metrics.snapshot(
            active_sessions=await self._store.count()
        )

    async def _monitor_disconnect(
        self,
        checker: DisconnectChecker,
        disconnected: asyncio.Event,
        stopped: asyncio.Event,
    ) -> None:
        while not stopped.is_set():
            if await checker():
                disconnected.set()
                return
            try:
                await asyncio.wait_for(
                    stopped.wait(),
                    timeout=self._settings.tutor_disconnect_poll_interval_seconds,
                )
            except TimeoutError:
                continue

    async def _provider_chunks(
        self,
        messages: list[ChatMessage],
        options: ChatOptions,
        disconnect_checker: DisconnectChecker | None,
    ) -> AsyncIterator[StreamChunk]:
        upstream = self._provider.stream_chat(messages, options).__aiter__()
        if disconnect_checker is None:
            try:
                async for chunk in upstream:
                    yield chunk
            finally:
                await upstream.aclose()
            return

        disconnected = asyncio.Event()
        stopped = asyncio.Event()
        monitor = asyncio.create_task(
            self._monitor_disconnect(
                disconnect_checker,
                disconnected,
                stopped,
            ),
            name="tutor-client-disconnect-monitor",
        )
        try:
            while True:
                next_chunk = asyncio.create_task(anext(upstream))
                disconnect_wait = asyncio.create_task(disconnected.wait())
                done, pending = await asyncio.wait(
                    {next_chunk, disconnect_wait},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if disconnect_wait in done and disconnected.is_set():
                    next_chunk.cancel()
                    await asyncio.gather(next_chunk, return_exceptions=True)
                    raise ClientDisconnected()
                disconnect_wait.cancel()
                await asyncio.gather(disconnect_wait, return_exceptions=True)
                try:
                    yield next_chunk.result()
                except StopAsyncIteration:
                    break
                finally:
                    for task in pending:
                        task.cancel()
        finally:
            stopped.set()
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
            await upstream.aclose()

    async def stream_message(
        self,
        session_id: UUID,
        request: TutorMessageRequest,
        *,
        disconnect_checker: DisconnectChecker | None = None,
    ) -> AsyncIterator[StreamEvent]:
        lock = await self._session_lock(session_id)
        async with lock:
            await self._store.begin_generation(session_id)
            tracker = await self._metrics.generation_started()
            outcome_recorded = False
            try:
                session = await self._store.get(session_id)
                decision = self._policy.decide(
                    request.message,
                    request.mode,
                    session.mode,
                    session.metadata,
                )
                await self._store.update_policy(
                    session_id,
                    mode=decision.mode,
                    guided_steps=decision.guided_steps,
                )
                session = await self._store.add_message(
                    session_id,
                    MessageRole.USER,
                    request.message,
                )

                messages = [
                    ChatMessage(
                        role=MessageRole.SYSTEM,
                        content=build_system_prompt(decision.mode.value),
                    ),
                    *[
                        ChatMessage(role=message.role, content=message.content)
                        for message in session.messages
                    ],
                ]
                options = ChatOptions(
                    max_tokens=self._settings.tutor_max_generation_tokens,
                    temperature=self._settings.tutor_temperature,
                )
                logger.info(
                    "generation_started session_id=%s mode=%s message_length=%s history_messages=%s",
                    session_id,
                    decision.mode.value,
                    len(request.message),
                    len(session.messages),
                )
                yield StreamEvent(
                    event="start",
                    data={
                        "session_id": str(session_id),
                        "mode": decision.mode.value,
                    },
                )

                fragments: list[str] = []
                finish_reason = "stop"
                prompt_tokens: int | None = None
                generated_tokens: int | None = None
                async for chunk in self._provider_chunks(
                    messages,
                    options,
                    disconnect_checker,
                ):
                    if chunk.text:
                        await self._metrics.first_token(tracker)
                        fragments.append(chunk.text)
                        yield StreamEvent(event="delta", data={"text": chunk.text})
                    if chunk.done:
                        finish_reason = chunk.finish_reason or "stop"
                        prompt_tokens = chunk.prompt_tokens
                        generated_tokens = chunk.generated_tokens

                assistant_text = "".join(fragments).strip()
                if not assistant_text:
                    raise LLMResponseError("The model completed without response text.")
                await self._store.add_message(
                    session_id,
                    MessageRole.ASSISTANT,
                    assistant_text,
                )
                duration, first_token = await self._metrics.generation_succeeded(
                    tracker,
                    generated_tokens=generated_tokens,
                    generated_characters=len(assistant_text),
                )
                outcome_recorded = True
                yield StreamEvent(
                    event="metadata",
                    data={
                        "mode": decision.mode.value,
                        "policy_reason": decision.reason,
                        "duration_seconds": round(duration, 3),
                        "first_token_seconds": (
                            round(first_token, 3)
                            if first_token is not None
                            else None
                        ),
                        "prompt_tokens": prompt_tokens,
                        "generated_tokens": generated_tokens,
                    },
                )
                yield StreamEvent(
                    event="done",
                    data={"finish_reason": finish_reason},
                )
                logger.info(
                    "generation_completed session_id=%s mode=%s duration_seconds=%.3f first_token_seconds=%s response_length=%s generated_tokens=%s",
                    session_id,
                    decision.mode.value,
                    duration,
                    f"{first_token:.3f}" if first_token is not None else "none",
                    len(assistant_text),
                    generated_tokens,
                )
            except ClientDisconnected:
                duration, first_token = await self._metrics.generation_cancelled(
                    tracker
                )
                outcome_recorded = True
                logger.info(
                    "generation_cancelled session_id=%s duration_seconds=%.3f first_token_seconds=%s",
                    session_id,
                    duration,
                    f"{first_token:.3f}" if first_token is not None else "none",
                )
                return
            except AppError as exc:
                duration, first_token = await self._metrics.generation_failed(
                    tracker
                )
                outcome_recorded = True
                logger.exception(
                    "generation_failed session_id=%s code=%s duration_seconds=%.3f first_token_seconds=%s",
                    session_id,
                    exc.code,
                    duration,
                    f"{first_token:.3f}" if first_token is not None else "none",
                )
                yield StreamEvent(event="error", data=exc.payload()["error"])
            except asyncio.CancelledError:
                if not outcome_recorded:
                    await self._metrics.generation_cancelled(tracker)
                    outcome_recorded = True
                logger.info(
                    "generation_cancelled session_id=%s reason=task_cancelled",
                    session_id,
                )
                raise
            except Exception:
                duration, first_token = await self._metrics.generation_failed(
                    tracker
                )
                outcome_recorded = True
                logger.exception(
                    "generation_failed session_id=%s code=INTERNAL_ERROR duration_seconds=%.3f first_token_seconds=%s",
                    session_id,
                    duration,
                    f"{first_token:.3f}" if first_token is not None else "none",
                )
                yield StreamEvent(
                    event="error",
                    data={
                        "code": "INTERNAL_ERROR",
                        "message": "Generation failed unexpectedly.",
                    },
                )
            finally:
                if not outcome_recorded:
                    await self._metrics.generation_cancelled(tracker)
                    logger.info(
                        "generation_cancelled session_id=%s reason=stream_closed",
                        session_id,
                    )
                await self._store.end_generation(session_id)
