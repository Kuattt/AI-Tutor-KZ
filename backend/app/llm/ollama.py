import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import (
    LLMResponseError,
    LLMTimeoutError,
    ModelNotAvailableError,
    OllamaUnavailableError,
)
from app.llm.base import LLMProvider
from app.llm.models import (
    ChatMessage,
    ChatOptions,
    ChatResult,
    ProviderHealth,
    StreamChunk,
)


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        timeout = httpx.Timeout(
            connect=settings.ollama_connect_timeout_seconds,
            read=settings.ollama_read_timeout_seconds,
            write=30.0,
            pool=settings.ollama_connect_timeout_seconds,
        )
        self._client = client or httpx.AsyncClient(
            base_url=settings.ollama_base_url.rstrip("/"),
            timeout=timeout,
        )

    def _payload(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": self._settings.ollama_model,
            "messages": [message.model_dump(mode="json") for message in messages],
            "stream": stream,
            "think": False,
            "keep_alive": "10m",
            "options": {
                "temperature": options.temperature,
                "num_predict": options.max_tokens,
            },
        }

    @staticmethod
    def _translate_http_error(exc: httpx.HTTPError) -> Exception:
        if isinstance(exc, httpx.TimeoutException):
            return LLMTimeoutError()
        if isinstance(exc, httpx.ConnectError):
            return OllamaUnavailableError()
        return OllamaUnavailableError(f"Ollama request failed: {type(exc).__name__}.")

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> ChatResult:
        try:
            response = await self._client.post(
                "/api/chat",
                json=self._payload(messages, options, stream=False),
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ModelNotAvailableError() from exc
            raise OllamaUnavailableError(
                f"Ollama returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise self._translate_http_error(exc) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMResponseError("Ollama returned malformed JSON.") from exc

        text = str(data.get("message", {}).get("content", ""))
        if not text:
            raise LLMResponseError("Ollama returned an empty assistant message.")
        return ChatResult(
            text=text,
            finish_reason=str(data.get("done_reason") or "stop"),
            prompt_tokens=data.get("prompt_eval_count"),
            generated_tokens=data.get("eval_count"),
            metadata={"total_duration_ns": data.get("total_duration")},
        )

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        options: ChatOptions,
    ) -> AsyncIterator[StreamChunk]:
        saw_done = False
        try:
            async with self._client.stream(
                "POST",
                "/api/chat",
                json=self._payload(messages, options, stream=True),
            ) as response:
                if response.status_code == 404:
                    raise ModelNotAvailableError()
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise LLMResponseError(
                            "Ollama returned malformed streaming JSON."
                        ) from exc
                    if data.get("error"):
                        message = str(data["error"])
                        if "not found" in message.casefold():
                            raise ModelNotAvailableError(message)
                        raise LLMResponseError(message)
                    text = str(data.get("message", {}).get("content", ""))
                    done = bool(data.get("done", False))
                    if text or done:
                        yield StreamChunk(
                            text=text,
                            done=done,
                            finish_reason=(
                                str(data.get("done_reason") or "stop")
                                if done
                                else None
                            ),
                            prompt_tokens=data.get("prompt_eval_count"),
                            generated_tokens=data.get("eval_count"),
                            metadata={
                                "total_duration_ns": data.get("total_duration")
                            }
                            if done
                            else {},
                        )
                    saw_done = saw_done or done
        except (ModelNotAvailableError, LLMResponseError):
            raise
        except httpx.HTTPStatusError as exc:
            raise OllamaUnavailableError(
                f"Ollama returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise self._translate_http_error(exc) from exc
        except ValidationError as exc:
            raise LLMResponseError("Invalid Ollama stream payload.") from exc

        if not saw_done:
            raise LLMResponseError("Ollama stream ended without a completion event.")

    async def health_check(self) -> ProviderHealth:
        try:
            version_response = await self._client.get("/api/version")
            version_response.raise_for_status()
            tags_response = await self._client.get("/api/tags")
            tags_response.raise_for_status()
            version = version_response.json().get("version")
            models = tags_response.json().get("models", [])
        except httpx.HTTPError as exc:
            raise self._translate_http_error(exc) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMResponseError("Ollama health response was malformed.") from exc

        installed = {
            str(item.get("name") or item.get("model"))
            for item in models
            if isinstance(item, dict)
        }
        if self._settings.ollama_model not in installed:
            raise ModelNotAvailableError(
                f"Configured model '{self._settings.ollama_model}' is not installed."
            )
        return ProviderHealth(
            status="ok",
            provider="ollama",
            model=self._settings.ollama_model,
            version=str(version) if version else None,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
