from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.traffic import TrafficState
from app.services.traffic_service import TrafficService


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