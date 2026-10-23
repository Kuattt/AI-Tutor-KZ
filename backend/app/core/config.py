from functools import lru_cache
from ipaddress import ip_address
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_allow_lan: bool = False
    app_port: int = 8000
    app_log_level: str = "INFO"
    app_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ]
    )

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_connect_timeout_seconds: float = 10.0
    ollama_read_timeout_seconds: float = 180.0

    tutor_max_history_messages: int = Field(default=30, ge=2, le=200)
    tutor_max_generation_tokens: int = Field(default=450, ge=32, le=4096)
    tutor_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    tutor_session_ttl_minutes: float = Field(default=60.0, gt=0)
    tutor_session_cleanup_interval_seconds: float = Field(default=300.0, gt=0)
    tutor_disconnect_poll_interval_seconds: float = Field(
        default=0.25, ge=0.05, le=5.0
    )

    @field_validator("ollama_base_url")
    @classmethod
    def ollama_must_remain_local(cls, value: str) -> str:
        hostname = urlparse(value).hostname
        if hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("OLLAMA_BASE_URL must use a loopback address")
        return value

    @model_validator(mode="after")
    def validate_backend_bind(self) -> "Settings":
        if self.app_host in {"127.0.0.1", "localhost", "::1"}:
            return self
        if not self.app_allow_lan:
            raise ValueError("Non-loopback APP_HOST requires APP_ALLOW_LAN=true")
        try:
            address = ip_address(self.app_host)
        except ValueError as exc:
            raise ValueError("APP_HOST must be a literal private LAN address") from exc
        if not address.is_private or address.is_unspecified or address.is_loopback:
            raise ValueError("APP_HOST must be a specific private LAN address")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


