from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# APPROACH
# ============================================================

class ApproachState(BaseModel):

    approach: str

    volume: int = Field(
        ge=0
    )

    carCount: int = Field(
        ge=0
    )

    motorcycleCount: int = Field(
        ge=0
    )

    busCount: int = Field(
        ge=0
    )

    truckCount: int = Field(
        ge=0
    )

    queueLengthVeh: int = Field(
        ge=0
    )

    queueLengthMEst: float = Field(
        ge=0
    )

    densityIndex: float = Field(
        ge=0
    )

    avgSpeedKmh: float | None = Field(
        default=None,
        ge=0,
    )


# ============================================================
# TRAFFIC STATE
# ============================================================

class TrafficState(BaseModel):

    intersectionId: str

    windowStart: datetime

    windowEnd: datetime

    approaches: list[ApproachState]