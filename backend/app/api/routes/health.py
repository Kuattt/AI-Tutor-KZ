from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_llm_provider
from app.llm.base import LLMProvider
from app.llm.models import ProviderHealth

router = APIRouter(tags=["health"])


@router.get("/health")
async def application_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ollama", response_model=ProviderHealth)
async def ollama_health(
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> ProviderHealth:
    return await provider.health_check()

