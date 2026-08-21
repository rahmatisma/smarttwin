"""
Memicu deteksi kendaraan (cv/process_uploaded_video.py) setelah video
CCTV selesai diupload.

cv/ punya venv dan dependency (ultralytics, torch, opencv) sendiri,
terpisah dari venv backend ini — makanya dijalankan sebagai subprocess
lewat interpreter python di cv/.venv, bukan diimpor langsung.

Alur:
    upload_cctv_video() (route) sukses
        -> trigger_cv_processing() (BackgroundTasks, tidak diblokir)
            -> pakai file_path yang sudah ditulis route ke disk saat
               streaming upload (tidak menulis ulang/duplikasi)
            -> insert baris cvProcessingJobs (status=running)
            -> spawn subprocess cv/process_uploaded_video.py
               (subprocess sendiri yang mengisi Supabase per window
               dan menutup job-nya di akhir, lihat cv/supabase_writer.py)

Catatan: file_path TIDAK dihapus di sini karena subprocess CV masih
membacanya secara async setelah fungsi ini selesai. Pembersihan
file sementara belum diimplementasikan (sama seperti versi
sebelumnya) -- lihat TODO di app/api/routes/cctv.py.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.services.supabase_client import get_supabase

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CV_DIR = PROJECT_ROOT / "cv"
CV_SCRIPT = CV_DIR / "process_uploaded_video.py"
CV_VENV_PYTHON = CV_DIR / ".venv" / "Scripts" / "python.exe"

MODEL_NAME = "YOLO26s-ByteTrack"
MODEL_VERSION = "ultralytics-track"

# URL backend ini sendiri, diteruskan ke subprocess CV supaya dia bisa
# POST /api/v1/traffic/notify tiap window selesai -- lihat
# app/services/ws_manager.py soal kenapa ini menggantikan Supabase
# Realtime (terbukti tidak mem-broadcast event di project ini).
BACKEND_SELF_URL = "http://127.0.0.1:8001"


def _create_processing_job(video_id: int) -> int:
    supabase = get_supabase()

    inserted = (
        supabase.table("cvProcessingJobs")
        .insert(
            {
                "videoId": video_id,
                "modelName": MODEL_NAME,
                "modelVersion": MODEL_VERSION,
                "status": "running",
                "startedAt": datetime.now(timezone.utc).isoformat(),
            }
        )
        .execute()
    )

    return inserted.data[0]["id"]


def _get_intersection_row_id(intersection_id: str) -> int:
    supabase = get_supabase()

    result = (
        supabase.table("intersections")
        .select("id")
        .eq("intersectionId", intersection_id)
        .maybe_single()
        .execute()
    )

    # .maybe_single() balikin None (bukan objek dengan .data=None) kalau
    # tidak ada baris yang cocok -- bukan cuma .data yang None.
    if result is None or not result.data:
        raise RuntimeError(f"Intersection '{intersection_id}' tidak ditemukan.")

    return result.data["id"]


def trigger_cv_processing(
    *,
    file_path: str,
    approach: str,
    camera_id: int,
    video_id: int,
    intersection_id: str,
) -> None:
    """
    Dipanggil lewat BackgroundTasks setelah upload sukses. Tidak
    melempar exception ke caller-nya (route sudah selesai merespons
    saat ini jalan) — kegagalan cukup di-print supaya kelihatan di
    log uvicorn, tidak sampai mematikan proses backend.
    """

    try:
        if not CV_VENV_PYTHON.exists():
            print(
                f"[cv_trigger] Lewati: {CV_VENV_PYTHON} tidak ada. "
                "Jalankan `cd cv && python -m venv .venv && "
                "pip install -r requirements.txt` dulu."
            )
            return

        intersection_row_id = _get_intersection_row_id(intersection_id)
        job_id = _create_processing_job(video_id)

        subprocess.Popen(
            [
                str(CV_VENV_PYTHON),
                str(CV_SCRIPT),
                "--video", file_path,
                "--approach", approach,
                "--camera-id", str(camera_id),
                "--video-id", str(video_id),
                "--intersection-id", str(intersection_row_id),
                "--intersection-slug", intersection_id,
                "--job-id", str(job_id),
            ],
            cwd=str(CV_DIR),
            env={
                "SUPABASE_URL": settings.supabase_url,
                "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
                "HF_TOKEN": settings.hf_token,
                "HF_REPO_ID": settings.hf_repo_id,
                "BACKEND_URL": BACKEND_SELF_URL,
                # PATH dkk tetap diwariskan lewat env=None secara default;
                # di sini env DIGANTI total jadi harus disalin manual.
                **_inherit_essential_env(),
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print(
            f"[cv_trigger] Memulai deteksi untuk videoId={video_id} "
            f"approach={approach} (jobId={job_id})"
        )

    except Exception as exc:  # noqa: BLE001
        print(f"[cv_trigger] Gagal memicu deteksi CV: {exc}")


def _inherit_essential_env() -> dict[str, str]:
    """
    subprocess.Popen(env=...) MENGGANTI seluruh environment kalau
    diisi, bukan menambah. Salin variabel penting dari proses backend
    supaya python/ultralytics di subprocess tetap bisa jalan normal
    (PATH untuk cari DLL, dsb).
    """

    import os

    keys = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA")

    return {key: os.environ[key] for key in keys if key in os.environ}
