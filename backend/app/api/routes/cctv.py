from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.services.cctv_service import CctvServiceError, get_video_hf_location, upload_camera_video
from app.services.cv_trigger_service import trigger_cv_processing

router = APIRouter(
    prefix="/api/v1/cctv",
    tags=["CCTV"],
)

# Ukuran chunk saat menulis upload ke disk. Nilai kecil-sedang supaya
# tidak pernah menahan lebih dari ini di RAM sekaligus, walau file-nya
# berukuran GB-an.
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


# ============================================================
# UPLOAD VIDEO
# ============================================================

@router.post("/upload")
async def upload_cctv_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    approach: str = Form(...),
    intersection_id: str = Form("simpang4-pingit"),
):
    """
    Upload video CCTV.

    File di-stream langsung ke disk (bukan ditahan penuh di RAM --
    penting untuk video berukuran GB-an) baru kemudian:

    File asli -> Hugging Face Hub (dataset repo, private)
    Metadata  -> Supabase (cameras, cameraVideos)

    TODO: file sementara di disk belum dihapus otomatis setelah CV
    processing selesai (lihat cv_trigger_service.py) -- pembersihan
    berkala belum diimplementasikan.
    """

    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="File yang diupload harus berupa video.",
        )

    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    file_size = 0

    try:
        while chunk := await file.read(CHUNK_SIZE):
            temp_file.write(chunk)
            file_size += len(chunk)
    finally:
        temp_file.close()

    if file_size == 0:
        Path(temp_file.name).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File video kosong.")

    try:
        result = await run_in_threadpool(
            upload_camera_video,
            intersection_id=intersection_id,
            approach=approach,
            name=name,
            filename=file.filename or "video.mp4",
            file_path=temp_file.name,
            file_size=file_size,
        )
    except CctvServiceError as exc:
        Path(temp_file.name).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(
        trigger_cv_processing,
        file_path=temp_file.name,
        approach=approach,
        camera_id=result.camera_id,
        video_id=result.video_id,
        intersection_id=intersection_id,
    )

    return {
        "cameraId": result.camera_id,
        "videoId": result.video_id,
        "streamUrl": result.stream_path,
    }


# ============================================================
# STREAM VIDEO
# ============================================================

@router.get("/videos/{video_id}/stream")
async def stream_cctv_video(video_id: int):
    """
    Relay video dari Hugging Face Hub (private dataset repo) ke
    client. Diperlukan karena repo private tidak bisa diakses
    langsung lewat resolve/main URL tanpa token.
    """

    try:
        repository_id, file_path = get_video_hf_location(video_id)
    except CctvServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    hf_url = (
        f"https://huggingface.co/datasets/{repository_id}/resolve/main/{file_path}"
    )

    client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {settings.hf_token}"},
        timeout=60.0,
        follow_redirects=True,
    )

    upstream_request = client.build_request("GET", hf_url)
    upstream_response = await client.send(upstream_request, stream=True)

    if upstream_response.status_code != 200:
        await upstream_response.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail="Gagal mengambil video dari Hugging Face.",
        )

    async def body_iterator():
        try:
            async for chunk in upstream_response.aiter_bytes():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(
        body_iterator(),
        media_type=upstream_response.headers.get("content-type", "video/mp4"),
    )
