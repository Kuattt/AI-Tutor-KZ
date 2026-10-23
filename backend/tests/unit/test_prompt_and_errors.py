import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import SessionNotFoundError
from app.llm.base import LLMProvider
from app.tutor.prompts import BASE_TUTOR_PROMPT
from tests.fakes import FakeLLMProvider


def test_fake_provider_implements_llm_abstraction() -> None:
    assert isinstance(FakeLLMProvider(), LLMProvider)


def test_error_serialization_is_stable() -> None:
    error = SessionNotFoundError()
    assert error.payload() == {
        "error": {
            "code": "SESSION_NOT_FOUND",
            "message": "Tutor session not found.",
        }
    }


def test_prompt_requires_calculation_verification() -> None:
    normalized = BASE_TUTOR_PROMPT.casefold()
    assert "verify every student calculation" in normalized
    assert "never praise a wrong result" in normalized


def test_prompt_requires_explicit_self_correction() -> None:
    normalized = BASE_TUTOR_PROMPT.casefold()
    assert "explicitly say that you were previously wrong" in normalized


def test_public_bind_address_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_host="0.0.0.0")


def test_private_lan_bind_requires_explicit_opt_in() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_host="192.168.1.25")

    settings = Settings(
        _env_file=None,
        app_host="192.168.1.25",
        app_allow_lan=True,
    )
    assert settings.app_host == "192.168.1.25"


def test_ollama_cannot_be_exposed_in_lan_mode() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_host="192.168.1.25",
            app_allow_lan=True,
            ollama_base_url="http://192.168.1.25:11434",
        )

