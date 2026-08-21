from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL belum dikonfigurasi.")

    if not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY belum dikonfigurasi."
        )

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )