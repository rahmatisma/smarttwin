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

    # Kendaraan yang memotong counting line selama window ini (aliran).
    # Di CSV CV kolomnya bernama vehicle_count; "volume" adalah nama
    # level-kontrak. Lihat docs/data-contract.md.
    volume: int = Field(ge=0)

    # Antrean: jumlah kendaraan (mentah) dan turunannya dalam meter.
    queueLengthVeh: int = Field(ge=0)
    queueLengthMEst: float = Field(ge=0)

    # Proxy lane occupancy per-frame, BUKAN kendaraan/km. Belum
    # dikalibrasi ke jarak dunia nyata.
    densityIndex: float = Field(ge=0)

    # None = BELUM DIUKUR, bukan 0 km/h.
    #
    # PERHATIAN: ge=0 menerima 0.0, jadi placeholder 0.0 akan lolos
    # validasi tanpa error dan terbaca sebagai "terukur, hasilnya diam".
    # Kalau kecepatannya belum ada, isi None — jangan 0.0.
    avgSpeedKmh: float | None = Field(default=None, ge=0)


class TrafficState(BaseModel):
    intersectionId: str

    # datetime, bukan str — supaya sepadan dengan docs/data-contract.md.
    # FastAPI menserialisasikannya jadi string ISO di response, jadi
    # bentuk JSON yang dilihat frontend tidak berubah.
    windowStart: datetime
    windowEnd: datetime

    approaches: list[ApproachState]