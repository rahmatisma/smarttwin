from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ============================================================
    # APPLICATION
    # ============================================================

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
    # ============================================================

    # URL project Supabase
    supabase_url: str

    # Service role key.
    # SERVER-ONLY — jangan pernah dikirim ke frontend.
    supabase_service_role_key: str

    # ============================================================
    # HUGGING FACE
    # ============================================================

    # Token Hugging Face
    hf_token: str

    # Repository tempat video CCTV disimpan
    # Contoh:
    # rahmatisma/smarttwin-cctv
    hf_repo_id: str

    # ============================================================
    # ENVIRONMENT CONFIG
    # ============================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """
        Mengubah:

            http://localhost:3000,http://127.0.0.1:3000

        menjadi:

            [
                "http://localhost:3000",
                "http://127.0.0.1:3000"
            ]
        """
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()