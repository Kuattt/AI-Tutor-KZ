from fastapi import Request

from app.llm.base import LLMProvider
from app.tutor.service import TutorService


def get_tutor_service(request: Request) -> TutorService:
    return request.app.state.tutor_service


def get_llm_provider(request: Request) -> LLMProvider:
    return request.app.state.llm_provider

