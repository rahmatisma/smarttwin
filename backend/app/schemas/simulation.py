from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    intersectionId: str
    trafficStateId: int | None = Field(default=None, ge=1)
    durationSeconds: int = Field(default=300, ge=1, le=3600)
    seed: int | None = None


class SimulationMetrics(BaseModel):
    averageDelaySeconds: float = Field(ge=0)
    averageQueueLength: float = Field(ge=0)
    throughputVehicles: int = Field(ge=0)
    averageWaitingTimeSeconds: float = Field(ge=0)


class SimulationResult(BaseModel):
    intersectionId: str
    trafficStateId: int | None = None
    simulatedAt: datetime
    durationSeconds: int = Field(ge=1)
    metrics: SimulationMetrics
