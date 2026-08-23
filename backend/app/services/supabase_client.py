from __future__ import annotations

import base64
import json
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


def _validate_service_role_key(key: str) -> None:
    """Pastikan key server bukan anon/publishable key."""

    parts = key.split(".")
    if len(parts) != 3:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY bukan JWT yang valid."
        )

    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        role = json.loads(
            base64.urlsafe_b64decode(payload)
        ).get("role")
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY bukan JWT yang valid."
        ) from None

    if role != "service_role":
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY harus menggunakan role service_role."
        )


@lru_cache
def get_supabase() -> Client:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL belum dikonfigurasi.")

    if not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY belum dikonfigurasi."
        )

    _validate_service_role_key(
        settings.supabase_service_role_key
    )

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )