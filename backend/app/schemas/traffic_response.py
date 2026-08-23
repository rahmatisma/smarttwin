from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class TrafficStateRowResponse(BaseModel):
    """Row trafficStates yang dikembalikan dari Supabase."""

    model_config = ConfigDict(extra="ignore")

    id: int
    intersectionId: int
    windowStart: datetime
    windowEnd: datetime

    source: str | None = None
    processingJobId: int | None = None
    createdAt: datetime | None = None


class TrafficApproachStateResponse(BaseModel):
    """Row trafficApproachStates yang dikembalikan dari Supabase."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    trafficStateId: int
    approachId: int
    approach: str
    volume: int
    carCount: int
    motorcycleCount: int
    busCount: int
    truckCount: int
    queueLengthVeh: int
    queueLengthMEst: float
    densityIndex: float
    avgSpeedKmh: float | None = None


class TrafficStateWithApproachesResponse(BaseModel):
    """Satu traffic state beserta seluruh approach state-nya."""

    trafficState: TrafficStateRowResponse
    approaches: list[TrafficApproachStateResponse]


class TrafficListResponse(BaseModel):
    """Response endpoint daftar traffic state terbaru."""

    success: bool
    intersectionId: str
    count: int = Field(ge=0)
    data: list[TrafficStateWithApproachesResponse]


class TrafficDetailResponse(BaseModel):
    """Response endpoint satu traffic state lengkap."""

    success: bool
    intersectionId: str
    data: TrafficStateWithApproachesResponse
