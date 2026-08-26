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


class ForecastApproachRecord(BaseModel):
    approach: str
    vehicleCount: float = Field(default=0.0, ge=0)
    queueLengthVeh: float = Field(default=0.0, ge=0)
    queueLengthMEst: float = Field(default=0.0, ge=0)
    densityIndex: float = Field(default=0.0, ge=0, le=1)


class ForecastTrafficStateRecord(BaseModel):
    timestamp: datetime
    approaches: list[ForecastApproachRecord] = Field(..., min_length=1)


class ForecastApproachRequest(BaseModel):
    records: list[ForecastTrafficStateRecord] = Field(..., min_length=12)


# ============================================================
# FORECAST
# ============================================================

@router.post(
    "",
    summary="Traffic Forecast 60 Detik",
    description=(
        "Menjalankan model LSTM SmartTwin menggunakan "
        "12 timestep terakhir dan menghasilkan prediksi "
        "12 timestep berikutnya dengan interval 5 detik."
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


@router.post(
    "/approaches",
    summary="Traffic Forecast 60 Detik Per Pendekat",
    description=(
        "Menjalankan LSTM agregat lalu mengalokasikan prediksi ke setiap "
        "pendekat berdasarkan proporsi traffic 12 timestep terakhir."
    ),
)
def predict_approach_forecast(
    request: ForecastApproachRequest,
) -> dict[str, Any]:
    try:
        records = [record.model_dump(mode="json") for record in request.records]
        return forecast_service.predict_approach_records(records)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Forecast per pendekat gagal dijalankan: {exc}",
        ) from exc
