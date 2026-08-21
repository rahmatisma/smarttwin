from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.schemas.traffic import TrafficState
from app.services.traffic_service import TrafficService
from app.services.ws_manager import traffic_ws_manager


router = APIRouter(
    prefix="/api/v1/traffic",
    tags=["Traffic"],
)


# ============================================================
# CSV LOCATION
# ============================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[4]
)

CSV_PATH = (
    PROJECT_ROOT
    / "cv"
    / "output"
    / "smarttwin_traffic_data.csv"
)


# ============================================================
# SERVICE
# ============================================================

traffic_service = TrafficService(
    csv_path=CSV_PATH,
    window_seconds=5,
)


# ============================================================
# GET LATEST TRAFFIC STATE
# ============================================================

@router.get(
    "/state",
    response_model=TrafficState,
)
def get_traffic_state() -> TrafficState:
    """
    Mengambil TrafficState terbaru.

    Flow:

        CV CSV
          ↓
        TrafficStateBuilder
          ↓
        TrafficService
          ↓
        API
          ↓
        Frontend
    """

    try:

        state = (
            traffic_service
            .get_latest_state()
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal membangun traffic state: "
                f"{exc}"
            ),
        ) from exc

    if state is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Traffic state belum tersedia."
            ),
        )

    return state


# ============================================================
# REALTIME PUSH (pengganti Supabase Realtime yang tidak jalan)
# ============================================================
#
# Bukan polling: cv/process_uploaded_video.py memanggil /notify
# PERSIS setelah satu window traffic berhasil ditulis ke Supabase,
# lalu di sini langsung di-broadcast ke seluruh dashboard yang
# terhubung. Dashboard cukup subscribe /ws sekali dan menunggu --
# tidak ada interval yang menanyakan "ada perubahan belum?".

@router.websocket("/ws")
async def traffic_ws(websocket: WebSocket) -> None:
    await traffic_ws_manager.connect(websocket)

    try:
        while True:
            # Dashboard tidak pernah mengirim apa pun ke sini --
            # cuma menahan koneksi tetap terbuka supaya broadcast()
            # bisa mendorong pesan kapan saja. recv() dipakai semata
            # untuk mendeteksi kapan browser menutup koneksinya.
            await websocket.receive_text()
    except WebSocketDisconnect:
        traffic_ws_manager.disconnect(websocket)


@router.post("/notify")
async def notify_traffic_update(payload: dict[str, Any]) -> dict[str, str]:
    """
    Dipanggil oleh cv/process_uploaded_video.py setiap satu window
    (5 detik) berhasil di-upsert ke Supabase. Body-nya diteruskan
    apa adanya ke seluruh client WebSocket yang terhubung.
    """

    await traffic_ws_manager.broadcast(payload)

    return {"status": "broadcast"}