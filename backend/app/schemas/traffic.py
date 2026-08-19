from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Approach(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class ApproachState(BaseModel):
    approach: Approach

    # Total kendaraan yang melewati counting line selama window.
    volume: int = Field(ge=0)

    # Jumlah kendaraan berdasarkan kelas.
    carCount: int = Field(ge=0)
    motorcycleCount: int = Field(ge=0)
    busCount: int = Field(ge=0)
    truckCount: int = Field(ge=0)

    # Antrean.
    queueLengthVeh: int = Field(ge=0)
    queueLengthMEst: float = Field(ge=0)

    # Proxy lane occupancy / kepadatan.
    # Bukan vehicles/km.
    densityIndex: float = Field(ge=0)

    # Belum tersedia dari CSV CV.
    # None berarti data belum diukur.
    avgSpeedKmh: float | None = Field(default=None, ge=0)


class TrafficState(BaseModel):
    intersectionId: str
    windowStart: datetime
    windowEnd: datetime
    approaches: list[ApproachState]