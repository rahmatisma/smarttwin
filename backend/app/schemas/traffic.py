from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# APPROACH
# ============================================================

class Approach(str, Enum):
    north = "north"
    south = "south"
    east = "east"
    west = "west"


# ============================================================
# APPROACH STATE
# ============================================================

class ApproachState(BaseModel):
    approach: Approach

    volume: int = Field(
        default=0,
        ge=0,
    )

    carCount: int = Field(
        default=0,
        ge=0,
    )

    motorcycleCount: int = Field(
        default=0,
        ge=0,
    )

    busCount: int = Field(
        default=0,
        ge=0,
    )

    truckCount: int = Field(
        default=0,
        ge=0,
    )

    queueLengthVeh: int = Field(
        default=0,
        ge=0,
    )

    queueLengthMEst: float = Field(
        default=0.0,
        ge=0,
    )

    densityIndex: float = Field(
        default=0.0,
        ge=0,
        le=1,
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