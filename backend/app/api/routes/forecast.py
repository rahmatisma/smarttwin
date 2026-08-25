from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.forecast_service import forecast_service


router = APIRouter(
    prefix="/api/forecast",
    tags=["Forecast"],
)


# ============================================================
# REQUEST SCHEMA
# ============================================================

class ForecastRecord(BaseModel):
    timestamp: datetime = Field(
        ...,
        description="Timestamp data traffic",
        examples=["2026-08-15T17:19:15"],
    )

    vehicleCount: float = Field(
        ...,
        ge=0,
        description="Jumlah kendaraan",
        examples=[10],
    )

    queueLengthVeh: float = Field(
        ...,
        ge=0,
        description="Panjang antrean dalam kendaraan",
        examples=[0],
    )

    queueLengthMEst: float = Field(
        ...,
        ge=0,
        description="Estimasi panjang antrean dalam meter",
        examples=[0],
    )

    densityIndex: float = Field(
        ...,
        ge=0,
        le=1,
        description="Indeks kepadatan 0 sampai 1",
        examples=[0.171212],
    )


class ForecastRequest(BaseModel):
    records: list[ForecastRecord] = Field(
        ...,
        min_length=12,
        description="Minimal 12 timestep data traffic",
    )


# ============================================================
# FORECAST
# ============================================================

@router.post(
    "",
    summary="Traffic Forecast 15 Detik",
    description=(
        "Menjalankan model LSTM SmartTwin menggunakan "
        "12 timestep terakhir dan menghasilkan prediksi "
        "3 timestep berikutnya dengan interval 5 detik."
    ),
)
def predict_forecast(
    request: ForecastRequest,
) -> dict[str, Any]:

    try:
        records = [
            record.model_dump(mode="json")
            for record in request.records
        ]

        result = forecast_service.predict_records(
            records
        )

        return result

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Forecast gagal dijalankan: {exc}",
        ) from exc


# ============================================================
# HEALTH
# ============================================================

@router.get(
    "/health",
    summary="Forecast Service Health",
)
def forecast_health() -> dict[str, Any]:

    try:
        return forecast_service.health()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Forecast health check gagal: {exc}",
        ) from exc