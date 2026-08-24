import asyncio
import os
from pathlib import Path

async def stream_simulation(fps: int = 10):
    """
    Generator yang membaca screenshot simulasi SUMO secara kontinu
    dan menghasilkan MJPEG stream.
    """
    frame_path = Path("cache/simulation/frame.jpg")
    wait_time = 1.0 / fps
    
    last_mtime = 0

    # Fallback/placeholder frame (jika diperlukan)
    # Kita cukup menunggu sampai file ada.
    
    while True:
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
            
        await asyncio.sleep(wait_time)
