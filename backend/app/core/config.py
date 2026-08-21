from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration.

    Semua konfigurasi dibaca dari environment variable
    atau file .env.
    """

    # ========================================================
    # APPLICATION
    # ========================================================

    app_name: str = "SmartTwin Backend"

    app_version: str = "0.1.0"

    debug: bool = True

    cors_origins: str = "http://localhost:3000"

    # ========================================================
    # DATABASE
    # ========================================================

    database_url: str = Field(
        ...,
        description="PostgreSQL connection string",
    )

    # ========================================================
    # SUPABASE
    # ========================================================

    supabase_url: str = ""

    supabase_service_role_key: str = ""

    # ========================================================
    # HUGGING FACE
    # ========================================================

    hf_token: str = ""

    hf_repo_id: str = ""

    # ========================================================
    # PYDANTIC SETTINGS
    # ========================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()