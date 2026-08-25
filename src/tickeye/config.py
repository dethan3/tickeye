"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the local-first application."""

    app_name: str = "TickEye"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    market_data_max_attempts: int = 3
    market_data_retry_delay_seconds: float = 0.5
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'tickeye.db'}"
    frontend_dist_dir: Path = PROJECT_ROOT / "frontend" / "dist"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="TICKEYE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
