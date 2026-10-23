from app.core.exceptions import SessionNotFoundError
from app.llm.models import MessageRole
from app.tutor.session_store import InMemoryTutorSessionStore


async def test_session_creation_retrieval_and_deletion() -> None:
    store = InMemoryTutorSessionStore(max_history_messages=4)
    created = await store.create(language="kk", grade=9)

    retrieved = await store.get(created.session_id)
    assert retrieved.session_id == created.session_id
    assert retrieved.metadata["language"] == "kk"
    assert retrieved.metadata["grade"] == 9

    await store.delete(created.session_id)
    try:
        await store.get(created.session_id)
    except SessionNotFoundError:
        pass
    else:
        raise AssertionError("Deleted session was still retrievable")


async def test_history_is_preserved_and_trimmed_to_limit() -> None:
    store = InMemoryTutorSessionStore(max_history_messages=3)
    session = await store.create()

    for index in range(5):
        await store.add_message(
            session.session_id,
            MessageRole.USER if index % 2 == 0 else MessageRole.ASSISTANT,
            f"message-{index}",
        )

    stored = await store.get(session.session_id)
    assert [message.content for message in stored.messages] == [
        "message-2",
        "message-3",
        "message-4",
    ]


async def test_returned_session_is_a_defensive_copy() -> None:
    store = InMemoryTutorSessionStore(max_history_messages=3)
    created = await store.create()
    created.metadata["language"] = "changed-outside-store"

    stored = await store.get(created.session_id)
    assert stored.metadata["language"] == "auto"

