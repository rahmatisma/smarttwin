from fastapi import APIRouter

from app.schemas.forecast import ForecastPoint
from app.services.forecast_service import get_forecast


router = APIRouter(
    prefix="/api/v1/forecast",
    tags=["Forecast"],
)


@router.get(
    "",
    response_model=list[ForecastPoint],
)
def get_forecast_endpoint() -> list[ForecastPoint]:
    return get_forecast()