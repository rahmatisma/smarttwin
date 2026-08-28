from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DigitalTwinPhase(BaseModel):
    approach: Literal["north", "east", "south", "west"]
    greenSeconds: int = Field(ge=1, le=60)
    yellowSeconds: int = Field(default=4, ge=1)
    redSeconds: int = Field(default=0, ge=0)
    demandScore: float = Field(default=0.0, ge=0.0, le=1.0)


class DigitalTwinCandidate(BaseModel):
    candidateId: Literal["baseline", "aggressive", "balanced"]
    phases: list[DigitalTwinPhase] = Field(min_length=4, max_length=4)
    cycleLengthSeconds: int = Field(ge=1)
    totalCycleSeconds: int = Field(ge=1)
    busiestApproach: str | None = None
    avgDelaySeconds: float = Field(ge=0)
    avgQueueLengthM: float = Field(ge=0)
    queueLengthVeh: int = Field(ge=0)
    throughputVeh: int = Field(ge=0)
    los: Literal["A", "B", "C", "D", "E", "F"]
    isWinner: bool = False


class DigitalTwinScenarioResponse(BaseModel):
    intersectionId: str
    status: Literal["completed", "unavailable"]
    updatedAt: datetime | None = None
    winnerId: Literal["baseline", "aggressive", "balanced"] | None = None
    candidates: list[DigitalTwinCandidate] = Field(default_factory=list)
    message: str | None = None

