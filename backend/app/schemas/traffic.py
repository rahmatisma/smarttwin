from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# APPROACH ENUM
# ============================================================

class Approach(str, Enum):
    """Empat lengan simpang yang dipakai lintas modul backend."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


# ============================================================
# APPROACH STATE
# ============================================================

class ApproachState(BaseModel):
    """
    Kondisi traffic pada satu approach dalam satu traffic window.

    Contract:
        CV -> Traffic State Builder -> Backend -> Frontend
    """

    model_config = ConfigDict(populate_by_name=True)

    approach: str

    volume: int = Field(ge=0)

    carCount: int = Field(default=0, alias="carCount", ge=0)
    motorcycleCount: int = Field(
        default=0,
        alias="motorcycleCount",
        ge=0,
    )
    busCount: int = Field(default=0, alias="busCount", ge=0)
    truckCount: int = Field(default=0, alias="truckCount", ge=0)

    queueLengthVeh: int = Field(
        default=0,
        alias="queueLengthVeh",
        ge=0,
    )

    queueLengthMEst: float = Field(
        default=0.0,
        alias="queueLengthMEst",
        ge=0.0,
    )

    densityIndex: float = Field(
        default=0.0,
        alias="densityIndex",
        ge=0.0,
    )

    avgSpeedKmh: float | None = Field(
        default=None,
        alias="avgSpeedKmh",
        ge=0.0,
    )


# ============================================================
# TRAFFIC STATE
# ============================================================

class TrafficState(BaseModel):
    """
    Snapshot kondisi lalu lintas pada satu intersection
    dalam satu time window.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )

    intersectionId: str = Field(alias="intersectionId")

    windowStart: datetime = Field(alias="windowStart")
    windowEnd: datetime = Field(alias="windowEnd")

    approaches: list[ApproachState]


# ============================================================
# CREATE TRAFFIC STATE REQUEST
# ============================================================

class TrafficStateCreateRequest(TrafficState):
    """
    Request body untuk:

        POST /api/traffic/state

    source:
        Sumber traffic state, misalnya:
        - cv
        - uploaded_video
        - camera
        - simulation
    """

    source: str = "cv"

    processing_job_id: int | None = Field(
        default=None,
        alias="processingJobId",
    )


# ============================================================
# RESPONSE
# ============================================================

class TrafficStateResponse(TrafficState):
    """
    Response setelah TrafficState berhasil disimpan.
    """

    traffic_state_id: int = Field(alias="trafficStateId")

    source: str

    created_at: datetime = Field(alias="createdAt")