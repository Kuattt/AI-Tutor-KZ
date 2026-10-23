import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_tutor_service
from app.tutor.schemas import (
    CreateSessionRequest,
    SessionCreatedResponse,
    SessionResponse,
    StreamEvent,
    TutorMessageRequest,
)
from app.tutor.service import TutorService

router = APIRouter(prefix="/api/v1/tutor", tags=["tutor"])


def encode_sse(event: StreamEvent) -> str:
    data = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.event}\ndata: {data}\n\n"


@router.post(
    "/sessions",
    response_model=SessionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request: CreateSessionRequest,
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> SessionCreatedResponse:
    return await service.create_session(request)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> SessionResponse:
    session = await service.get_session(session_id)
    return SessionResponse.from_session(session)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session(
    session_id: UUID,
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> Response:
    await service.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: UUID,
    request: TutorMessageRequest,
    http_request: Request,
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> StreamingResponse:
    # Validate before response headers start so missing sessions return normal JSON.
    await service.get_session(session_id)

    async def event_stream() -> AsyncIterator[str]:
        async for event in service.stream_message(
            session_id,
            request,
            disconnect_checker=http_request.is_disconnected,
        ):
            yield encode_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

