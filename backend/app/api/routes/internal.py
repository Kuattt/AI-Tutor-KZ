from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_tutor_service
from app.core.metrics import MetricsSnapshot
from app.tutor.service import TutorService

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


@router.get("/metrics", response_model=MetricsSnapshot)
async def metrics(
    service: Annotated[TutorService, Depends(get_tutor_service)],
) -> MetricsSnapshot:
    return await service.metrics_snapshot()

