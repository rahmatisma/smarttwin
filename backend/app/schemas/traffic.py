from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Approach = Literal["north", "south", "east", "west"]


class ApproachState(BaseModel):
    approach: Approach

    volume: int = Field(ge=0)

    carCount: int = Field(ge=0)
    motorcycleCount: int = Field(ge=0)
    busCount: int = Field(ge=0)
    truckCount: int = Field(ge=0)

    queueLengthVeh: int = Field(ge=0)
    queueLengthMEst: float = Field(ge=0)

    densityIndex: float = Field(ge=0)

    avgSpeedKmh: float | None = None


class TrafficState(BaseModel):
    intersectionId: str

    windowStart: datetime
    windowEnd: datetime

    approaches: list[ApproachState]