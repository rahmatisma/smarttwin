from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# FORECAST PREDICTION
# ============================================================

class ForecastPrediction(BaseModel):

    predictionTime: datetime

    horizonSeconds: int

    totalDiZona: float = Field(
        default=0.0,
        ge=0,
    )

    motorDiZona: float = Field(
        default=0.0,
        ge=0,
    )

    mobilDiZona: float = Field(
        default=0.0,
        ge=0,
    )

    trukDiZona: float = Field(
        default=0.0,
        ge=0,
    )

    busDiZona: float = Field(
        default=0.0,
        ge=0,
    )


# ============================================================
# FORECAST RESULT
# ============================================================

class ForecastResult(BaseModel):

    intersectionId: str

    generatedAt: datetime

    sourceWindowStart: datetime

    sourceWindowEnd: datetime

    modelName: str

    modelVersion: str

    predictions: list[ForecastPrediction]