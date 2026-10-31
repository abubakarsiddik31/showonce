"""Runtime settings, read from environment variables or a local ``.env`` file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. The API key is the only required value for live calls."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SHOWONCE_",
        extra="ignore",
        populate_by_name=True,
    )

    api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("MODEL_API_KEY", "SHOWONCE_API_KEY"),
        description="Meta Model API key.",
    )
    api_base_url: str = "https://api.meta.ai/v1"
    sam_model: str = "sam-3.1"
    plan_model: str = "muse-spark-1.3"
    request_timeout_s: float = 120.0
    cache_dir: Path = Path(".cache/showonce")
    runs_dir: Path = Path("runs")
    samples_dir: Path = Path("samples")
    web_dist: Path = Path("web/dist")
    log_level: str = "INFO"

    def require_api_key(self) -> str:
        """Return the API key or raise a clear error if it is not configured."""
        if self.api_key is None or not self.api_key.get_secret_value():
            raise RuntimeError(
                "MODEL_API_KEY is not set. Copy .env.example to .env and add your Meta key."
            )
        return self.api_key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
