import json

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import LLMResponseError, LLMTimeoutError
from app.llm.models import ChatMessage, ChatOptions, MessageRole
from app.llm.ollama import OllamaProvider


def make_settings() -> Settings:
    return Settings(_env_file=None, ollama_model="qwen3.5:9b")


async def test_ollama_health_checks_configured_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.1"})
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen3.5:9b"}]},
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    provider = OllamaProvider(make_settings(), client=client)
    result = await provider.health_check()
    assert result.status == "ok"
    assert result.model == "qwen3.5:9b"
    await client.aclose()


async def test_ollama_stream_parses_progressive_ndjson() -> None:
    body = "\n".join(
        [
            json.dumps({"message": {"content": "Сәлем"}, "done": False}),
            json.dumps(
                {
                    "message": {"content": "!"},
                    "done": True,
                    "done_reason": "stop",
                    "eval_count": 2,
                }
            ),
        ]
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    provider = OllamaProvider(make_settings(), client=client)
    chunks = [
        chunk
        async for chunk in provider.stream_chat(
            [ChatMessage(role=MessageRole.USER, content="Hi")],
            ChatOptions(),
        )
    ]
    assert [chunk.text for chunk in chunks] == ["Сәлем", "!"]
    assert chunks[-1].done is True
    await client.aclose()


async def test_ollama_stream_rejects_malformed_json() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="{not-json}\n")

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    provider = OllamaProvider(make_settings(), client=client)
    with pytest.raises(LLMResponseError):
        _ = [
            chunk
            async for chunk in provider.stream_chat(
                [ChatMessage(role=MessageRole.USER, content="Hi")],
                ChatOptions(),
            )
        ]
    await client.aclose()


async def test_ollama_stream_translates_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    )
    provider = OllamaProvider(make_settings(), client=client)
    with pytest.raises(LLMTimeoutError):
        _ = [
            chunk
            async for chunk in provider.stream_chat(
                [ChatMessage(role=MessageRole.USER, content="Hi")],
                ChatOptions(),
            )
        ]
    await client.aclose()

