from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SmartTwin Backend"
    app_version: str = "0.1.0"
    debug: bool = True

    cors_origins: str = "http://localhost:3000"

    # Supabase (service_role — server-only, bypass RLS)
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Hugging Face Hub (storage video CCTV, lihat docs/database.md #13)
    hf_token: str = ""
    hf_repo_id: str = "rahmatisma/smarttwin-cctv"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()