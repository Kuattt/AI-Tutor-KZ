import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.fakes import FakeLLMProvider


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_log_level="WARNING",
        tutor_max_history_messages=6,
    )


@pytest.fixture
def fake_provider() -> FakeLLMProvider:
    return FakeLLMProvider(["Бірінші ", "нақты жауап."])


@pytest.fixture
def client(
    test_settings: Settings,
    fake_provider: FakeLLMProvider,
) -> TestClient:
    application = create_app(
        settings=test_settings,
        provider=fake_provider,
    )
    with TestClient(application) as test_client:
        yield test_client

