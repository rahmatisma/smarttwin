from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.forecast import ForecastResult
from app.services.forecast_service import (
    forecast_service,
)


router = APIRouter(
    prefix="/api/forecast",
    tags=["Forecast"],
)


@router.get(
    "/latest/{intersection_id}",
    response_model=ForecastResult,
)
async def get_latest_forecast(
    intersection_id: str,
):

    result = (
        forecast_service
        .get_latest(
            intersection_id
        )
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Forecast belum tersedia."
            ),
        )

    return result