import asyncio
import os
import time
from pathlib import Path
from fastapi import Request

async def stream_simulation(
    request: Request,
    fps: int = 10,
    max_lifetime_seconds: int = 30,
    context: str = "default",
):
    """
    Generator yang membaca screenshot simulasi SUMO secara kontinu
    dan menghasilkan MJPEG stream.
    """
    frame_path = (
        Path(__file__).resolve().parents[3]
        / "cache" / "simulation" / f"frame_{context}.jpg"
    )
    wait_time = 1.0 / fps
    
    last_mtime = 0
    started_at = time.monotonic()

    # Fallback/placeholder frame (jika diperlukan)
    # Kita cukup menunggu sampai file ada.
    
    while True:
        if await request.is_disconnected():
            break
        # Endpoint lama MJPEG dipertahankan untuk kompatibilitas, tetapi dibuat
        # finite agar tidak menahan graceful shutdown/reload Uvicorn selamanya.
        # Frontend aktif memakai endpoint frame finite, bukan stream ini.
        if time.monotonic() - started_at >= max_lifetime_seconds:
            break
        try:
            if frame_path.exists():
                current_mtime = os.path.getmtime(frame_path)
                # Jika ada frame baru, kita kirim. Jika tidak, kirim yang lama saja
                # agar stream tidak putus.
                
                with open(frame_path, "rb") as f:
                    frame_data = f.read()
                    
                if frame_data:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n")
                    last_mtime = current_mtime
                    
        except Exception:
            # Abaikan jika file sedang ditulis (lock) atau tidak bisa dibaca
            pass
            
        try:
            await asyncio.sleep(wait_time)
        except asyncio.CancelledError:
            break
