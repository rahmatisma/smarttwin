from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse

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
# KLIEN HTTP KE HUGGING FACE (DIPAKAI ULANG, BUKAN PER-REQUEST)
# ============================================================
#
# <video> browser tidak minta file sekaligus -- dia minta sepotong-
# sepotong lewat header Range setiap buffer mau habis. Sebelumnya
# tiap potongan itu bikin httpx.AsyncClient BARU (handshake TLS dari
# nol ke Hugging Face setiap kali), jadi playback kerasa "jalan-
# buffer-jalan-buffer" -- tiap kali buffer habis, ada jeda nyambung
# ulang sebelum byte berikutnya mulai mengalir.
#
# Dengan satu client yang dipakai ulang (connection pooling bawaan
# httpx), potongan-potongan berikutnya bisa lewat koneksi yang sudah
# tersambung, jauh lebih cepat responnya.
_hf_client: httpx.AsyncClient | None = None
_hf_client_lock = asyncio.Lock()


async def get_hf_client() -> httpx.AsyncClient:
    global _hf_client

    if _hf_client is None:
        async with _hf_client_lock:
            if _hf_client is None:
                _hf_client = httpx.AsyncClient(
                    headers={"Authorization": f"Bearer {settings.hf_token}"},
                    timeout=60.0,
                    follow_redirects=True,
                    limits=httpx.Limits(
                        max_keepalive_connections=20,
                        max_connections=40,
                        keepalive_expiry=60.0,
                    ),
                )

    return _hf_client


async def close_hf_client() -> None:
    global _hf_client

    if _hf_client is not None:
        await _hf_client.aclose()
        _hf_client = None


# ============================================================
# CACHE VIDEO LOKAL (opsional, lihat app/core/config.py)
# ============================================================
#
# Sekali sebuah video ditonton lengkap, disimpan di disk lokal
# supaya tontonan berikutnya (dari siapa pun, di production 1
# backend dipakai bersama) tidak perlu narik ulang dari Hugging
# Face -- lepas dari naik-turunnya koneksi internet ke luar.
#
# TIDAK ADA eviction/pembersihan otomatis di versi ini -- cache
# akan terus tumbuh selama video baru terus ditambahkan. Aman untuk
# sekarang (lihat estimasi ukuran di diskusi tim), tapi kalau nanti
# jumlah kamera/video bertambah banyak, pertimbangkan menambah
# pembersihan berkala (mis. hapus cache video yang bukan video
# terbaru per kamera).
_caching_in_progress: set[int] = set()
_caching_lock = asyncio.Lock()

# Menyimpan referensi task background yang lagi jalan -- asyncio TIDAK
# menjamin task tetap hidup kalau tidak ada yang pegang referensinya
# (bisa di-garbage-collect di tengah jalan, gagal diam-diam). Dibuang
# dari set ini otomatis lewat callback begitu task selesai.
_background_cache_tasks: set[asyncio.Task] = set()


def _spawn_cache_task(video_id: int, repository_id: str, file_path: str) -> None:
    """
    Fire-and-forget populate_video_cache() lewat asyncio.create_task()
    langsung -- SENGAJA bukan FastAPI BackgroundTasks. Kalau endpoint
    return Response (StreamingResponse/FileResponse) langsung alih-alih
    dict biasa, FastAPI TIDAK otomatis menempelkan background_tasks ke
    response itu, jadi task-nya tidak pernah benar-benar jalan. Ini
    baru ketahuan pas testing manual -- proses cache tidak pernah
    mulai walau tidak ada error yang kelihatan.
    """

    task = asyncio.create_task(
        populate_video_cache(video_id, repository_id, file_path)
    )

    _background_cache_tasks.add(task)
    task.add_done_callback(_background_cache_tasks.discard)


def _cache_path(video_id: int) -> Path:
    return Path(settings.video_cache_dir) / f"{video_id}.mp4"


async def populate_video_cache(
    video_id: int, repository_id: str, file_path: str
) -> None:
    """
    Download PENUH (bukan sepotong Range) dari Hugging Face ke disk
    lokal, lalu pindahkan ke tempat cache final begitu selesai --
    supaya file yang setengah jadi tidak pernah terbaca sebagai
    "sudah di-cache" kalau prosesnya keburu putus/gagal.
    """

    async with _caching_lock:
        if video_id in _caching_in_progress:
            return

        _caching_in_progress.add(video_id)

    try:
        cache_dir = Path(settings.video_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        final_path = _cache_path(video_id)

        if final_path.exists():
            return

        partial_path = final_path.with_suffix(".part")

        hf_url = (
            f"https://huggingface.co/datasets/{repository_id}"
            f"/resolve/main/{file_path}"
        )

        client = await get_hf_client()

        async with client.stream("GET", hf_url) as response:
            if response.status_code != 200:
                print(
                    f"[cache] gagal download video {video_id} "
                    f"buat cache: HTTP {response.status_code}"
                )
                return

            with open(partial_path, "wb") as file:
                async for chunk in response.aiter_bytes(CHUNK_SIZE):
                    file.write(chunk)

        partial_path.replace(final_path)

        print(f"[cache] video {video_id} tersimpan di {final_path}")
    except Exception as exc:  # noqa: BLE001
        # Cache itu optimasi, bukan hal yang boleh menggagalkan
        # apapun -- kalau gagal, permintaan berikutnya cukup jatuh
        # balik ke proxy langsung seperti biasa.
        print(f"[cache] gagal cache video {video_id}: {exc}")
    finally:
        async with _caching_lock:
            _caching_in_progress.discard(video_id)


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
    except Exception as exc:  # noqa: BLE001
        # Paling sering ini error jaringan dari upload ke Hugging
        # Face (lihat RuntimeError di huggingface_hub._commit_api).
        # Sejak upload_camera_video() diurutkan ulang (HF dulu, baru
        # insert Supabase), kegagalan di sini TIDAK meninggalkan baris
        # kamera yatim di database -- jadi aman langsung dilaporkan ke
        # user sebagai error biasa, bukan 500 mentah.
        Path(temp_file.name).unlink(missing_ok=True)
        raise HTTPException(
            status_code=502,
            detail=f"Gagal mengupload video ke Hugging Face: {exc}",
        ) from exc

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
async def stream_cctv_video(video_id: int, request: Request):
    """
    Kirim video ke client. Urutan prioritas:

    1. Sudah ada di cache lokal (disk) -> langsung dari situ, lewat
       FileResponse (Range/seek ditangani otomatis oleh Starlette,
       jauh lebih cepat & stabil karena tidak lewat internet sama
       sekali).
    2. Belum ada -> proxy dari Hugging Face Hub seperti biasa (repo
       private, tidak bisa diakses langsung tanpa token) SEKALIGUS
       memicu populate_video_cache() di background supaya tontonan
       berikutnya sudah kena cache -- tanpa menghambat respons yang
       sedang berjalan ini.
    """

    if settings.video_cache_enabled:
        cached_path = _cache_path(video_id)

        if cached_path.exists():
            return FileResponse(
                cached_path,
                media_type="video/mp4",
                stat_result=cached_path.stat(),
                headers={"Accept-Ranges": "bytes"},
            )

    try:
        repository_id, file_path = get_video_hf_location(video_id)
    except CctvServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if settings.video_cache_enabled:
        _spawn_cache_task(video_id, repository_id, file_path)

    hf_url = (
        f"https://huggingface.co/datasets/{repository_id}/resolve/main/{file_path}"
    )

    request_headers: dict[str, str] = {}

    range_header = request.headers.get("range")

    if range_header:
        request_headers["Range"] = range_header

    client = await get_hf_client()

    upstream_request = client.build_request(
        "GET", hf_url, headers=request_headers
    )
    upstream_response = await client.send(upstream_request, stream=True)

    if upstream_response.status_code not in (200, 206):
        await upstream_response.aclose()
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

    response_headers = {"Accept-Ranges": "bytes"}

    # Teruskan Content-Range/Content-Length upstream apa adanya --
    # itu yang dipakai browser buat tau total durasi & posisi seek,
    # baik pada respons 200 penuh maupun 206 sebagian.
    for header_name in ("Content-Range", "Content-Length"):
        value = upstream_response.headers.get(header_name)

        if value:
            response_headers[header_name] = value

    return StreamingResponse(
        body_iterator(),
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type", "video/mp4"),
        headers=response_headers,
    )
