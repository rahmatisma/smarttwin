"""
Helper Supabase untuk process_uploaded_video.py.

Dipisah dari process_uploaded_video.py supaya query Supabase tidak
bercampur dengan loop deteksi YOLO.

Autentikasi lewat service_role (bypass RLS) — SUPABASE_URL dan
SUPABASE_SERVICE_ROLE_KEY dibaca dari environment variable yang
di-inject backend saat men-spawn subprocess ini (lihat
backend/app/services/cv_trigger_service.py), bukan dari file .env
di folder cv/.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from supabase import Client, create_client


@lru_cache
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY tidak ada di "
            "environment. Script ini harus di-spawn oleh backend "
            "(cv_trigger_service.py), bukan dijalankan berdiri sendiri."
        )

    return create_client(url, key)


# ============================================================
# LOOKUP
# ============================================================

def get_approach_row_id(intersection_row_id: int, approach: str) -> int:
    """
    Mirror dari backend/app/services/cctv_service.py::_get_approach_row_id.
    Duplikasi kecil ini disengaja — cv/ dan backend/ punya venv terpisah,
    tidak saling impor.
    """

    supabase = get_client()

    result = (
        supabase.table("approaches")
        .select("id")
        .eq("intersectionId", intersection_row_id)
        .eq("approach", approach)
        .maybe_single()
        .execute()
    )

    if result is None or not result.data:
        raise RuntimeError(f"Approach '{approach}' tidak ditemukan.")

    return result.data["id"]


# ============================================================
# TRAFFIC STATE UPSERT
# ============================================================

def upsert_traffic_window(
    *,
    intersection_row_id: int,
    window_start: datetime,
    window_end: datetime,
    processing_job_id: int,
    approach: str,
    approach_id: int,
    metrics: dict[str, Any],
) -> None:
    """
    Find-or-create baris trafficStates untuk window ini, lalu upsert
    baris trafficApproachStates untuk approach yang diproses.

    metrics wajib berisi: volume, carCount, motorcycleCount, busCount,
    truckCount, queueLengthVeh, queueLengthMEst, densityIndex.
    """

    supabase = get_client()

    existing = (
        supabase.table("trafficStates")
        .select("id")
        .eq("intersectionId", intersection_row_id)
        .eq("windowStart", window_start.isoformat())
        .eq("windowEnd", window_end.isoformat())
        .maybe_single()
        .execute()
    )

    # .maybe_single() balikin None (bukan objek dengan .data=None) kalau
    # tidak ada baris yang cocok -- bukan cuma .data yang None.
    if existing is not None and existing.data:
        traffic_state_id = existing.data["id"]
    else:
        inserted = (
            supabase.table("trafficStates")
            .insert(
                {
                    "intersectionId": intersection_row_id,
                    "windowStart": window_start.isoformat(),
                    "windowEnd": window_end.isoformat(),
                    "source": "cv",
                    "processingJobId": processing_job_id,
                }
            )
            .execute()
        )

        traffic_state_id = inserted.data[0]["id"]

    supabase.table("trafficApproachStates").upsert(
        {
            "trafficStateId": traffic_state_id,
            "approachId": approach_id,
            "approach": approach,
            **metrics,
        },
        on_conflict="trafficStateId,approachId",
    ).execute()


# ============================================================
# PROCESSING JOB STATUS
# ============================================================
#
# Baris cvProcessingJobs dibuat oleh backend (cv_trigger_service.py)
# SEBELUM subprocess ini di-spawn, supaya job_id sudah ada untuk
# dilewatkan lewat --job-id. Di sini cuma update status di akhir.

def update_job_status(
    job_id: int,
    status: str,
    error_message: str | None = None,
) -> None:
    supabase = get_client()

    payload: dict[str, Any] = {
        "status": status,
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }

    if error_message is not None:
        payload["errorMessage"] = error_message

    supabase.table("cvProcessingJobs").update(payload).eq("id", job_id).execute()


def mark_video_processed(video_id: int) -> None:
    supabase = get_client()

    supabase.table("cameraVideos").update(
        {"status": "processed"}
    ).eq("id", video_id).execute()


# ============================================================
# VIDEO ANOTASI (kotak deteksi dibakar ke frame)
# ============================================================
#
# Disimpan sebagai baris cameraVideos BARU (bukan menimpa video
# aslinya), dengan uploadedAt lebih baru -> frontend (yang selalu
# ambil baris cameraVideos terbaru per kamera, lihat
# fetchCameras() di supabaseData.ts) otomatis memutar video
# anotasi ini begitu tersedia, tanpa perlu ubah frontend sama
# sekali.

def insert_annotated_video(
    *,
    camera_id: int,
    video_name: str,
    repository_id: str,
    file_path: str,
    file_size_bytes: int,
) -> int:
    supabase = get_client()

    inserted = (
        supabase.table("cameraVideos")
        .insert(
            {
                "cameraId": camera_id,
                "videoName": video_name,
                "videoFormat": "mp4",
                "storageProvider": "huggingface",
                "repositoryId": repository_id,
                "filePath": file_path,
                "fileUrl": None,
                "fileSizeBytes": file_size_bytes,
                "status": "processed",
            }
        )
        .execute()
    )

    return inserted.data[0]["id"]


def set_video_file_url(video_id: int, file_url: str) -> None:
    supabase = get_client()

    supabase.table("cameraVideos").update(
        {"fileUrl": file_url}
    ).eq("id", video_id).execute()
