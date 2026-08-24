from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# FORECAST REQUEST
# ============================================================

class ForecastRequest(BaseModel):
    intersectionId: str

    horizonMinutes: int = Field(
        default=15,
        ge=1,
        le=60,
    )


# ============================================================
# FORECAST PREDICTION
# ============================================================

class ForecastPrediction(BaseModel):
    timestamp: datetime

    predictedVehicleCount: float = Field(
        ge=0,
    )

    predictedQueueLengthVeh: float = Field(
        ge=0,
    )

    predictedQueueLengthMEst: float = Field(
        ge=0,
    )

    predictedDensityIndex: float = Field(
        ge=0,
        le=1,
    )

    predictedSpeedKmh: float | None = Field(
        default=None,
        ge=0,
    )


# ============================================================
# FORECAST RESULT
# ============================================================

class ForecastResult(BaseModel):
    intersectionId: str

    horizonMinutes: int

    model: str

    predictions: list[ForecastPrediction]