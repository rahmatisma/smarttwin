from datetime import datetime, timezone

from app.schemas.traffic import (
    Approach,
    ApproachState,
    TrafficState,
)


def get_current_traffic_state() -> TrafficState:
    """
    MASIH STUB — angka di bawah ditulis literal, bukan hasil hitung.

    Sumber aslinya nanti: snapshot JSON yang ditulis
    simulation/traffic_state_builder.py dari cv/output/
    smarttwin_traffic_data.csv. Selama fungsi ini masih mengembalikan
    konstanta, endpoint /api/v1/traffic/state menyajikan data karangan
    yang bentuknya benar — jangan dipakai buat demo atau laporan.

    avgSpeedKmh sengaja None di keempat lengan: CSV CV tidak punya kolom
    kecepatan sama sekali. Jangan diganti 0.0 supaya "kelihatan lengkap"
    — 0.0 lolos validasi tanpa error dan terbaca sebagai kendaraan diam.
    """
    now = datetime.now(timezone.utc)

    return TrafficState(
        intersectionId="simpang4-pingit",
        windowStart=now,
        windowEnd=now,
        approaches=[
            ApproachState(
                approach=Approach.NORTH,
                volume=59,
                queueLengthVeh=8,
                queueLengthMEst=42.0,
                densityIndex=93.8,
                avgSpeedKmh=None,
            ),
            ApproachState(
                approach=Approach.SOUTH,
                volume=62,
                queueLengthVeh=6,
                queueLengthMEst=28.0,
                densityIndex=128.9,
                avgSpeedKmh=None,
            ),
            ApproachState(
                approach=Approach.EAST,
                volume=90,
                queueLengthVeh=8,
                queueLengthMEst=42.0,
                densityIndex=158.0,
                avgSpeedKmh=None,
            ),
            ApproachState(
                approach=Approach.WEST,
                volume=59,
                queueLengthVeh=7,
                queueLengthMEst=35.0,
                densityIndex=130.6,
                avgSpeedKmh=None,
            ),
        ],
    )