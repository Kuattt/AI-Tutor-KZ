from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    code = "INTERNAL_ERROR"
    status_code = 500
    default_message = "An internal error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.details = details

    def payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"error": error}


class InvalidRequestError(AppError):
    code = "INVALID_REQUEST"
    status_code = 422
    default_message = "The request is invalid."


class SessionNotFoundError(AppError):
    code = "SESSION_NOT_FOUND"
    status_code = 404
    default_message = "Tutor session not found."


class OllamaUnavailableError(AppError):
    code = "OLLAMA_UNAVAILABLE"
    status_code = 503
    default_message = "The local Ollama service is unavailable."


class ModelNotAvailableError(AppError):
    code = "MODEL_NOT_AVAILABLE"
    status_code = 503
    default_message = "The configured language model is not available."


class LLMTimeoutError(AppError):
    code = "LLM_TIMEOUT"
    status_code = 504
    default_message = "The language model request timed out."


class LLMResponseError(AppError):
    code = "LLM_RESPONSE_ERROR"
    status_code = 502
    default_message = "The language model returned an invalid response."


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.payload())

