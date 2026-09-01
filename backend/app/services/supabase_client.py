from __future__ import annotations

import base64
import json
from functools import lru_cache

from postgrest.utils import SyncClient as PostgrestSyncClient
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

    client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )

    _force_http1(client)

    return client


def _force_http1(client: Client) -> None:
    """
    postgrest-py hardcode `http2=True` saat bikin sesi httpx-nya
    (postgrest/_sync/client.py -- tidak ada opsi resmi untuk
    mematikannya lewat ClientOptions). Client ini di-@lru_cache jadi
    DIBAGI oleh seluruh backend -- banyak endpoint polling paralel
    (traffic state, signal status, dst, semuanya tiap ~0,5-1 detik)
    plus panggilan simulasi semuanya lewat satu koneksi HTTP/2 yang
    sama.

    Diverifikasi lewat reproduksi manual (4 thread x 4 request
    paralel ke Supabase yang sama): dengan http2=True, 14/16 request
    gagal `httpx.RemoteProtocolError: Server disconnected`. Setelah
    dipaksa http2=False (HTTP/1.1, banyak koneksi independen alih-alih
    satu koneksi termultiplex), 0/16 gagal. Ini bug konkurensi di
    kombinasi httpx+h2 di bawah beban banyak thread, bukan masalah
    jaringan -- lihat riwayat commit untuk detail investigasi.

    Postgrest-py tidak expose cara resmi mengganti ini, jadi sesi
    httpx-nya diganti langsung di sini. `postgrest.utils.SyncClient`
    cuma `httpx.Client` biasa (+ alias `aclose()`), jadi aman
    dikonstruksi ulang dengan konfigurasi yang sama persis kecuali
    `http2`.
    """

    old_session = client.postgrest.session

    client.postgrest.session = PostgrestSyncClient(
        base_url=old_session.base_url,
        headers=old_session.headers,
        timeout=old_session.timeout,
        follow_redirects=True,
        http2=False,
    )