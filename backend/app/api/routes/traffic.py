from fastapi import APIRouter

from app.schemas.traffic import TrafficState
from app.services.traffic_service import get_current_traffic_state


router = APIRouter(
    prefix="/api/v1/traffic",
    tags=["Traffic"],
)


@router.get(
    "/state",
    response_model=TrafficState,
)
def get_traffic_state() -> TrafficState:
    return get_current_traffic_state()