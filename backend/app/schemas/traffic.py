from enum import Enum

from pydantic import BaseModel, Field


class Approach(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class ApproachState(BaseModel):
    approach: Approach

    volume: int = Field(ge=0)
    queueLengthM: float = Field(ge=0)
    densityVehPerKm: float = Field(ge=0)
    avgSpeedKmh: float = Field(ge=0)


class TrafficState(BaseModel):
    intersectionId: str

    windowStart: str
    windowEnd: str

    approaches: list[ApproachState]