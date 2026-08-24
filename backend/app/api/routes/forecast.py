from __future__ import annotations

from fastapi import APIRouter

from app.services.forecast_service import forecast_service
from app.schemas.traffic import TrafficState


router = APIRouter(
    prefix="/forecast",
    tags=["Forecast"],
)


@router.post("/predict")
def predict(
    state: TrafficState,
):
    """
    Menerima TrafficState terbaru,
    memasukkannya ke history LSTM,
    lalu menjalankan forecast jika
    sequence sudah mencukupi.
    """

    result = forecast_service.add_traffic_state(state)

    if result is None:
        return {
            "status": "warming_up",
            "message": (
                "History traffic belum cukup "
                "untuk menjalankan LSTM."
            ),
            "requiredTimesteps": (
                forecast_service
                .forecaster
                .sequence_length
            ),
        }

    return result