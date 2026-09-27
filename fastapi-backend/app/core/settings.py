"""
Civic Task Navigator backend settings loaded from environment variables.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me"

    supabase_url: str = ""
    supabase_key: str = ""

    groq_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GROQ_API_KEY", "LLM_API_KEY"),
    )
    groq_model: str = "llama-3.3-70b-versatile"

    geocoding_api_key: str = ""
    geocoding_provider: str = "nominatim"

    nlp_service_url: str = "http://localhost:8001"
    nlp_service_timeout: int = 30

    stt_provider: str = "google"
    stt_api_key: str = ""
    tts_provider: str = "google"
    tts_api_key: str = ""
    audexum_api_key: str = ""

    frontend_url: str = "http://localhost:3000"
    extra_allowed_origins: str = ""

    @property
    def allowed_origins(self) -> List[str]:
        """All CORS-allowed origins, merged from primary and extra settings."""
        origins = [self.frontend_url]
        if self.extra_allowed_origins:
            extras = [origin.strip() for origin in self.extra_allowed_origins.split(",") if origin.strip()]
            origins.extend(extras)
        if self.app_env == "development":
            dev_origins = [
                "http://localhost:3000",
                "http://localhost:5173",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:5173",
            ]
            for origin in dev_origins:
                if origin not in origins:
                    origins.append(origin)
        return origins

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()