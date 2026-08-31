from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# PATH
# ============================================================

# backend/app/core/config.py
# parents[0] = core
# parents[1] = app
# parents[2] = backend
# parents[3] = root repo

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = PROJECT_ROOT / ".env"


# ============================================================
# SETTINGS
# ============================================================

class Settings(BaseSettings):

    # ========================================================
    # APPLICATION
    # ========================================================

    app_name: str = "SmartTwin Backend"

    app_version: str = "0.1.0"

    debug: bool = True

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        """Toleransi DEBUG=release/production dari environment Windows/runner."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "develop", "dev"}:
                return True
        return value

    cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )

    # ========================================================
    # DATABASE
    # ========================================================

    database_url: str = Field(
        default="",
        description="PostgreSQL connection string",
    )

    # ========================================================
    # SUPABASE
    # ========================================================

    supabase_url: str

    supabase_service_role_key: str

    # ========================================================
    # HUGGING FACE
    # ========================================================

    hf_token: str

    hf_repo_id: str

    # ========================================================
    # VIDEO CACHE
    # ========================================================

    video_cache_enabled: bool = Field(
        default=True,
        description=(
            "Simpan salinan video CCTV "
            "di disk lokal."
        ),
    )

    video_cache_dir: str = Field(
        default="cache/videos",
        description=(
            "Folder cache video."
        ),
    )

    # ========================================================
    # PYDANTIC SETTINGS CONFIG
    # ========================================================

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================================
    # CORS
    # ========================================================

    @property
    def cors_origins_list(self) -> list[str]:

        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


# ============================================================
# SINGLETON
# ============================================================

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
