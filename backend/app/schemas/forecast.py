from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


# ============================================================
# MODEL CONTRACT
# ============================================================

FEATURES = [
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
]


# ============================================================
# APPROACH STATE
# ============================================================

class ForecastApproachState(BaseModel):
    approach: str

    vehicleCount: float = Field(default=0.0, ge=0.0)

    queueLengthVeh: float = Field(default=0.0, ge=0.0)

    queueLengthMEst: float = Field(default=0.0, ge=0.0)

    densityIndex: float = Field(default=0.0, ge=0.0)


# ============================================================
# TRAFFIC STATE INPUT
# ============================================================

class TrafficStateInput(BaseModel):
    intersectionId: str

    timestamp: datetime

    approaches: List[ForecastApproachState]


# ============================================================
# AGGREGATED FORECAST INPUT
# ============================================================

class ForecastInput(BaseModel):
    intersectionId: str

    timestamp: datetime

    vehicleCount: float = Field(default=0.0, ge=0.0)

    queueLengthVeh: float = Field(default=0.0, ge=0.0)

    queueLengthMEst: float = Field(default=0.0, ge=0.0)

    densityIndex: float = Field(default=0.0, ge=0.0)


# ============================================================
# SINGLE FORECAST
# ============================================================

class ForecastPrediction(BaseModel):
    timestamp: datetime

    vehicleCount: float

    queueLengthVeh: float

    queueLengthMEst: float

    densityIndex: float


# ============================================================
# FORECAST RESPONSE
# ============================================================

class ForecastResponse(BaseModel):
    intersectionId: str

    generatedAt: datetime

    historyTimestep: int

    timestepSeconds: int

    forecastHorizonSeconds: int

    predictions: List[ForecastPrediction]


# ============================================================
# STATUS
# ============================================================

class ForecastStatusResponse(BaseModel):
    status: str

    modelLoaded: bool

    device: str

    inputTimestep: int

    outputTimestep: int

    featureCount: int

    features: List[str]