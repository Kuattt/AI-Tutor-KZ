import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health, internal, tutor
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, app_error_handler
from app.core.logging import configure_logging
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.tutor.service import TutorService
from app.tutor.session_store import (
    InMemoryTutorSessionStore,
    TutorSessionStore,
)

logger = logging.getLogger(__name__)


async def session_cleanup_loop(
    store: TutorSessionStore,
    *,
    interval_seconds: float,
) -> None:
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            expired = await store.cleanup_expired()
            if expired:
                logger.info("sessions_expired count=%s", len(expired))
    except asyncio.CancelledError:
        logger.info("session_cleanup_stopped")
        raise


def create_app(
    *,
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    store: TutorSessionStore | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.app_log_level)
    resolved_provider = provider or OllamaProvider(resolved_settings)
    resolved_store = store or InMemoryTutorSessionStore(
        resolved_settings.tutor_max_history_messages,
        ttl_minutes=resolved_settings.tutor_session_ttl_minutes,
    )
    tutor_service = TutorService(
        resolved_provider,
        resolved_store,
        resolved_settings,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "application_starting env=%s host=%s port=%s model=%s",
            resolved_settings.app_env,
            resolved_settings.app_host,
            resolved_settings.app_port,
            resolved_settings.ollama_model,
        )
        if resolved_settings.app_allow_lan:
            logger.warning(
                "lan_development_mode_enabled host=%s port=%s ollama_remains_private=%s",
                resolved_settings.app_host,
                resolved_settings.app_port,
                resolved_settings.ollama_base_url,
            )
        try:
            health_result = await resolved_provider.health_check()
            logger.info(
                "ollama_connected provider=%s model=%s version=%s",
                health_result.provider,
                health_result.model,
                health_result.version,
            )
        except AppError as exc:
            logger.warning("ollama_startup_check_failed code=%s", exc.code)
        cleanup_task = asyncio.create_task(
            session_cleanup_loop(
                resolved_store,
                interval_seconds=(
                    resolved_settings.tutor_session_cleanup_interval_seconds
                ),
            ),
            name="tutor-session-cleanup",
        )
        try:
            yield
        finally:
            cleanup_task.cancel()
            await asyncio.gather(cleanup_task, return_exceptions=True)
            await resolved_provider.close()
            logger.info("application_stopped")

    application = FastAPI(
        title="AI Tutor KZ Backend",
        version="0.1.1",
        description=(
            "Local-first multi-turn tutoring API using Ollama and qwen3.5:9b."
        ),
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.llm_provider = resolved_provider
    application.state.session_store = resolved_store
    application.state.tutor_service = tutor_service

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.app_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    application.add_exception_handler(AppError, app_error_handler)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "The request is invalid.",
                    "details": {"validation": jsonable_encoder(exc.errors())},
                }
            },
        )

    @application.exception_handler(Exception)
    async def internal_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_application_error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred.",
                }
            },
        )

    application.include_router(health.router)
    application.include_router(tutor.router)
    application.include_router(internal.router)
    return application


app = create_app()
