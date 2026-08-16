from datetime import datetime, timezone

from app.schemas.traffic import (
    Approach,
    ApproachState,
    TrafficState,
)


def get_current_traffic_state() -> TrafficState:
    now = datetime.now(timezone.utc)

    return TrafficState(
        intersectionId="simpang4-pingit",
        windowStart=now.isoformat(),
        windowEnd=now.isoformat(),
        approaches=[
            ApproachState(
                approach=Approach.NORTH,
                volume=59,
                queueLengthM=42,
                densityVehPerKm=93.8,
                avgSpeedKmh=52.9,
            ),
            ApproachState(
                approach=Approach.SOUTH,
                volume=62,
                queueLengthM=28,
                densityVehPerKm=128.9,
                avgSpeedKmh=49.8,
            ),
            ApproachState(
                approach=Approach.EAST,
                volume=90,
                queueLengthM=42,
                densityVehPerKm=158.0,
                avgSpeedKmh=15.9,
            ),
            ApproachState(
                approach=Approach.WEST,
                volume=59,
                queueLengthM=35,
                densityVehPerKm=130.6,
                avgSpeedKmh=16.5,
            ),
        ],
    )