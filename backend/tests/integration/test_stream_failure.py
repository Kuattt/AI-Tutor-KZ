from fastapi.testclient import TestClient

from app.core.exceptions import LLMTimeoutError
from app.main import create_app
from tests.fakes import FakeLLMProvider


class TimeoutProvider(FakeLLMProvider):
    async def stream_chat(self, messages, options):
        raise LLMTimeoutError()
        yield  # pragma: no cover - makes this an async generator


def test_failed_stream_does_not_store_partial_assistant(test_settings) -> None:
    provider = FakeLLMProvider(["partial", "never"], fail_after_chunks=1)
    application = create_app(settings=test_settings, provider=provider)

    with TestClient(application) as client:
        session_id = client.post(
            "/api/v1/tutor/sessions",
            json={},
        ).json()["session_id"]
        response = client.post(
            f"/api/v1/tutor/sessions/{session_id}/messages",
            json={"message": "Trigger failure"},
        )
        assert "event: delta" in response.text
        assert "event: error" in response.text
        assert "OLLAMA_UNAVAILABLE" in response.text
        assert "event: done" not in response.text

        session = client.get(
            f"/api/v1/tutor/sessions/{session_id}"
        ).json()
        assert session["message_count"] == 1
        assert session["messages"][0]["role"] == "user"
        metrics = client.get("/api/v1/internal/metrics").json()
        assert metrics["generations"]["failed"] == 1
        assert metrics["generations"]["successful"] == 0
        assert metrics["generations"]["active"] == 0


def test_timeout_emits_error_without_done(test_settings) -> None:
    application = create_app(
        settings=test_settings,
        provider=TimeoutProvider(),
    )
    with TestClient(application) as client:
        session_id = client.post(
            "/api/v1/tutor/sessions",
            json={},
        ).json()["session_id"]
        response = client.post(
            f"/api/v1/tutor/sessions/{session_id}/messages",
            json={"message": "Trigger timeout"},
        )
        assert response.status_code == 200
        assert "event: error" in response.text
        assert "LLM_TIMEOUT" in response.text
        assert "event: done" not in response.text
        session = client.get(
            f"/api/v1/tutor/sessions/{session_id}"
        ).json()
        assert [message["role"] for message in session["messages"]] == ["user"]

