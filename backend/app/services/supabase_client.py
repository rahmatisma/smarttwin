"""
Client Supabase untuk backend.

Menggunakan service_role key (bypass RLS) karena backend adalah
lingkungan server-side yang terpercaya. JANGAN PERNAH kirim key
ini ke frontend.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import create_client, Client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY belum diset di .env"
        )

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
