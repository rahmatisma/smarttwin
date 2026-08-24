from fastapi import APIRouter, HTTPException

from app.schemas.forecast import (
    ForecastRequest,
    ForecastResult,
)

from app.services.realtime_forecast_service import (
    RealtimeForecastService,
)


router = APIRouter(
    prefix="/api",
    tags=["Forecast"],
)


@router.post(
    "/forecast",
    response_model=ForecastResult,
)
def forecast(
    request: ForecastRequest,
):

    try:

        service = RealtimeForecastService()

        return service.forecast(
            intersection_id=request.intersectionId,
            horizon_minutes=request.horizonMinutes,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Gagal menjalankan realtime forecast: "
                f"{exc}"
            ),
        )