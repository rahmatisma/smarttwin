from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.forecast_service import (
    FEATURES,
    INPUT_TIMESTEPS,
    OUTPUT_TIMESTEPS,
    STEP_SECONDS,
    forecast_service,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/forecast",
    tags=["Forecast"],
)


# ============================================================
# REQUEST SCHEMAS
# ============================================================


class ForecastRecord(BaseModel):
    """
    Satu timestep traffic.

    Contoh:

    {
        "timestamp": "2026-08-15T17:19:05",
        "vehicleCount": 12,
        "queueLengthVeh": 0,
        "queueLengthMEst": 0,
        "densityIndex": 0.21
    }
    """

    timestamp: Any

    vehicleCount: float = Field(
        ...,
        ge=0,
    )

    queueLengthVeh: float = Field(
        ...,
        ge=0,
    )

    queueLengthMEst: float = Field(
        ...,
        ge=0,
    )

    densityIndex: float = Field(
        ...,
        ge=0,
        le=1,
    )


class ForecastRequest(BaseModel):
    """
    Request forecasting.

    Minimal:
        12 timestep.

    Lebih dari 12 timestep juga boleh.
    Service akan mengambil 12 timestep terakhir.
    """

    records: list[ForecastRecord] = Field(
        ...,
        min_length=INPUT_TIMESTEPS,
    )


# ============================================================
# RESPONSE SCHEMAS
# ============================================================


class ForecastOutput(BaseModel):

    timestamp: str

    vehicleCount: float

    queueLengthVeh: float

    queueLengthMEst: float

    densityIndex: float

    secondsAhead: int


class ForecastResponse(BaseModel):

    model: dict[str, Any]

    input: dict[str, Any]

    forecast: list[ForecastOutput]


# ============================================================
# HEALTH
# ============================================================


@router.get(
    "/health",
    summary="Check LSTM forecasting service",
)
async def forecast_health():
    """
    Mengecek apakah file model dan scaler tersedia.
    """

    try:

        return forecast_service.health()

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================
# MODEL INFO
# ============================================================


@router.get(
    "/info",
    summary="Get LSTM model information",
)
async def forecast_info():
    """
    Informasi kontrak model.
    """

    try:

        health = forecast_service.health()

        return {
            "service": "SmartTwin Traffic Forecast",
            "modelType": "LSTM",

            "features": FEATURES,

            "input": {
                "timesteps": INPUT_TIMESTEPS,
                "seconds": (
                    INPUT_TIMESTEPS
                    * STEP_SECONDS
                ),
                "features": len(FEATURES),
            },

            "output": {
                "timesteps": OUTPUT_TIMESTEPS,
                "seconds": (
                    OUTPUT_TIMESTEPS
                    * STEP_SECONDS
                ),
                "features": len(FEATURES),
            },

            "device": health["device"],

            "modelLoaded": health["loaded"],
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# ============================================================
# FORECAST
# ============================================================


@router.post(
    "",
    response_model=ForecastResponse,
    summary="Generate traffic forecast",
)
async def generate_forecast(
    request: ForecastRequest,
):
    """
    Jalankan LSTM forecasting.

    Frontend mengirim minimal 12 timestep terakhir.

    LSTM kemudian menghasilkan:

        +5 detik
        +10 detik
        +15 detik
    """

    try:

        records = [
            record.model_dump()
            for record in request.records
        ]

        result = (
            forecast_service
            .predict_records(
                records
            )
        )

        return result

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
            detail=(
                "Model forecasting belum tersedia: "
                f"{exc}"
            ),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Terjadi error saat menjalankan "
                f"forecast LSTM: {exc}"
            ),
        ) from exc


# ============================================================
# FORECAST FROM LATEST TRAFFIC
# ============================================================


@router.post(
    "/predict",
    response_model=ForecastResponse,
    summary="Predict from latest traffic records",
)
async def predict_forecast(
    request: ForecastRequest,
):
    """
    Alias endpoint untuk prediction.

    Bisa dipakai frontend sebagai:

        POST /api/forecast/predict
    """

    try:

        records = [
            record.model_dump()
            for record in request.records
        ]

        return forecast_service.predict_records(
            records
        )

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
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
            detail=str(exc),
        ) from exc


# ============================================================
# SIMPLE TEST ENDPOINT
# ============================================================


@router.get(
    "/test",
    summary="Test forecasting model with dummy sequence",
)
async def test_forecast():
    """
    Endpoint testing lokal.

    Endpoint ini membuat 12 timestep dummy
    lalu menjalankan model.

    Tujuannya untuk memastikan:

        FastAPI
            ↓
        ForecastService
            ↓
        traffic_lstm.pt
            ↓
        scaler.json
            ↓
        prediction

    bekerja dengan benar.
    """

    try:

        records = []

        base_timestamp = (
            "2026-08-15T17:18:20"
        )

        import pandas as pd

        base_time = pd.Timestamp(
            base_timestamp
        )

        for index in range(
            INPUT_TIMESTEPS
        ):

            timestamp = (
                base_time
                + pd.Timedelta(
                    seconds=STEP_SECONDS * index
                )
            )

            records.append(
                {
                    "timestamp": timestamp.isoformat(),

                    "vehicleCount": float(
                        8 + (index % 5)
                    ),

                    "queueLengthVeh": 0.0,

                    "queueLengthMEst": 0.0,

                    "densityIndex": 0.15,
                }
            )

        result = (
            forecast_service
            .predict_records(
                records
            )
        )

        return {
            "status": "success",
            "message": (
                "LSTM forecasting berhasil "
                "dijalankan."
            ),
            "result": result,
        }

    except FileNotFoundError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc