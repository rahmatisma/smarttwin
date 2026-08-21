from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# APPROACH ENUM
# ============================================================

class Approach(str, Enum):
    """
    Empat lengan/approach pada simpang.

    Enum ini dipertahankan karena beberapa bagian backend,
    termasuk SUMO adapter dan test lama, masih menggunakannya.
    """

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


# ============================================================
# APPROACH STATE
# ============================================================

class ApproachState(BaseModel):
    """
    Kondisi lalu lintas pada satu approach/lengan simpang
    dalam satu time window.

    Satu approach dapat memiliki beberapa lane.

    Contoh:

        south
        ├── lane_1
        ├── lane_2
        └── lane_3

    Traffic State Builder akan menggabungkan data dari
    beberapa lane menjadi satu ApproachState.
    """

    # --------------------------------------------------------
    # APPROACH
    # --------------------------------------------------------

    approach: str

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    volume: int = Field(
        default=0,
        ge=0,
    )

    # --------------------------------------------------------
    # VEHICLE CLASSIFICATION
    # --------------------------------------------------------

    # Default = 0 supaya ApproachState juga dapat dibuat
    # oleh modul lain seperti SUMO tanpa harus mengetahui
    # klasifikasi kendaraan dari Computer Vision.

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

    # --------------------------------------------------------
    # QUEUE
    # --------------------------------------------------------

    queueLengthVeh: int = Field(
        default=0,
        ge=0,
    )

    queueLengthMEst: float = Field(
        default=0.0,
        ge=0,
    )

    # --------------------------------------------------------
    # DENSITY
    # --------------------------------------------------------

    densityIndex: float = Field(
        default=0.0,
        ge=0,
    )

    # --------------------------------------------------------
    # SPEED
    # --------------------------------------------------------

    avgSpeedKmh: float | None = Field(
        default=None,
        ge=0,
    )


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

# Beberapa file lama masih menggunakan:
#
#     from app.schemas.traffic import Approach
#
# Approach sekarang berupa Enum di atas.
#
# Contract tetap menggunakan:
#
#     approach: "north"
#     approach: "south"
#     approach: "east"
#     approach: "west"


# ============================================================
# TRAFFIC STATE
# ============================================================

class TrafficState(BaseModel):
    """
    Snapshot kondisi lalu lintas satu simpang
    pada satu time window.
    """

    intersectionId: str

    windowStart: datetime

    windowEnd: datetime

    approaches: list[ApproachState]