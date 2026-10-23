from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import SessionNotFoundError
from app.tutor.session_store import InMemoryTutorSessionStore


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


async def test_session_remains_before_ttl_and_expires_after_ttl() -> None:
    clock = FakeClock()
    store = InMemoryTutorSessionStore(
        max_history_messages=4,
        ttl_minutes=60,
        clock=clock,
    )
    session = await store.create()

    clock.advance(minutes=59)
    assert (await store.get(session.session_id)).session_id == session.session_id

    clock.advance(minutes=1)
    with pytest.raises(SessionNotFoundError):
        await store.get(session.session_id)


async def test_active_generation_is_not_removed_by_cleanup() -> None:
    clock = FakeClock()
    store = InMemoryTutorSessionStore(
        max_history_messages=4,
        ttl_minutes=1,
        clock=clock,
    )
    session = await store.create()
    await store.begin_generation(session.session_id)

    clock.advance(minutes=2)
    assert await store.cleanup_expired() == []
    assert (await store.get(session.session_id)).session_id == session.session_id

    await store.end_generation(session.session_id)
    assert await store.cleanup_expired() == [session.session_id]
    with pytest.raises(SessionNotFoundError):
        await store.get(session.session_id)


async def test_cleanup_handles_multiple_sessions_independently() -> None:
    clock = FakeClock()
    store = InMemoryTutorSessionStore(
        max_history_messages=4,
        ttl_minutes=60,
        clock=clock,
    )
    old_session = await store.create()
    clock.advance(minutes=30)
    fresh_session = await store.create()
    clock.advance(minutes=31)

    assert await store.cleanup_expired() == [old_session.session_id]
    with pytest.raises(SessionNotFoundError):
        await store.delete(old_session.session_id)
    assert (await store.get(fresh_session.session_id)).session_id == (
        fresh_session.session_id
    )
    assert await store.count() == 1

