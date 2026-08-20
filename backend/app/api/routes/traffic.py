from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.traffic import TrafficState
from app.services.traffic_service import TrafficService


router = APIRouter(
    prefix="/api/v1/traffic",
    tags=["Traffic"],
)


# =========================================================
# CSV LOCATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[4]

CSV_PATH = (
    PROJECT_ROOT
    / "cv"
    / "output"
    / "smarttwin_traffic_data.csv"
)


traffic_service = TrafficService(
    csv_path=CSV_PATH,
    window_seconds=5,
)


# =========================================================
# GET LATEST TRAFFIC STATE
# =========================================================

@router.get(
    "/state",
    response_model=TrafficState,
)
def get_traffic_state() -> TrafficState:
    """
    Mengambil TrafficState terbaru hasil
    Traffic State Builder.
    """

    try:
        return traffic_service.get_latest_state()

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal membangun traffic state: "
                f"{exc}"
            ),
        ) from exc