from uuid import uuid4

from fastapi.testclient import TestClient


def parse_sse(text: str) -> list[tuple[str, dict]]:
    import json

    events: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line[7:] for line in lines if line.startswith("event: "))
        data = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
        events.append((event, data))
    return events


def create_session(client: TestClient) -> str:
    response = client.post(
        "/api/v1/tutor/sessions",
        json={"language": "mixed", "grade": 9},
    )
    assert response.status_code == 201
    return response.json()["session_id"]


def test_health_and_openapi(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ollama").json()["provider"] == "fake"
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/v1/tutor/sessions" in openapi.json()["paths"]


def test_session_create_get_delete(client: TestClient) -> None:
    session_id = create_session(client)
    retrieved = client.get(f"/api/v1/tutor/sessions/{session_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["message_count"] == 0

    deleted = client.delete(f"/api/v1/tutor/sessions/{session_id}")
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/tutor/sessions/{session_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_invalid_session_has_stable_error(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/tutor/sessions/{uuid4()}/messages",
        json={"message": "Сәлем"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_invalid_request_has_stable_error(client: TestClient) -> None:
    session_id = create_session(client)
    response = client.post(
        f"/api/v1/tutor/sessions/{session_id}/messages",
        json={"message": "   "},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_streaming_sse_and_assistant_storage(client: TestClient) -> None:
    session_id = create_session(client)
    with client.stream(
        "POST",
        f"/api/v1/tutor/sessions/{session_id}/messages",
        json={"message": "Түсіндіріп бер.", "mode": "auto"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = parse_sse("".join(response.iter_text()))

    assert [event for event, _ in events] == [
        "start",
        "delta",
        "delta",
        "metadata",
        "done",
    ]
    assert sum(event == "done" for event, _ in events) == 1
    metadata = next(data for event, data in events if event == "metadata")
    assert metadata["first_token_seconds"] is not None
    assert "".join(data["text"] for event, data in events if event == "delta") == (
        "Бірінші нақты жауап."
    )
    session = client.get(f"/api/v1/tutor/sessions/{session_id}").json()
    assert session["message_count"] == 2
    assert session["messages"][-1]["role"] == "assistant"
    assert session["messages"][-1]["content"] == "Бірінші нақты жауап."

    metrics = client.get("/api/v1/internal/metrics")
    assert metrics.status_code == 200
    body = metrics.json()
    assert body["generations"]["total"] == 1
    assert body["generations"]["successful"] == 1
    assert body["generations"]["active"] == 0
    assert body["generations"]["generated_tokens"] == 2
    assert body["sessions"] == {"created_total": 1, "active": 1}


def test_multiturn_history_reaches_provider(
    client: TestClient,
    fake_provider,
) -> None:
    session_id = create_session(client)
    for message in ("Бірінші сұрақ", "Екінші сұрақ"):
        response = client.post(
            f"/api/v1/tutor/sessions/{session_id}/messages",
            json={"message": message},
        )
        assert response.status_code == 200
    second_request = fake_provider.requests[-1]
    contents = [message.content for message in second_request]
    assert "Бірінші сұрақ" in contents
    assert "Бірінші нақты жауап." in contents
    assert "Екінші сұрақ" in contents

