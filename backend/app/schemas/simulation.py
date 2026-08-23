from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    intersectionId: str
    trafficStateId: int | None = Field(default=None, ge=1)
    durationSeconds: int = Field(default=300, ge=1, le=3600)
    seed: int | None = None
    gui: bool = False
    guiDelayMs: int = Field(default=0, ge=0)


class SimulationResult(BaseModel):
    trafficStateId: int | None = None
    intersectionId: str
    durationSeconds: int = Field(ge=1)
    generatedVehicles: int = Field(ge=0)
    departedVehicles: int = Field(ge=0)
    arrivedVehicles: int = Field(ge=0)
    maxQueueVehicles: int = Field(ge=0)
    totalWaitingSeconds: float = Field(ge=0)
    simulationRuntimeSeconds: float = Field(ge=0)
    status: str
    simulatedAt: datetime
