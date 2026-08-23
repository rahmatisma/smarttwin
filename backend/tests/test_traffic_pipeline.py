from datetime import datetime, timedelta, timezone

from app.services.traffic_metrics_writer import (
    TrafficMetricsWriter,
)


def main() -> None:

    writer = TrafficMetricsWriter()

    now = datetime.now(
        timezone.utc
    )

    window_start = (
        now - timedelta(seconds=5)
    )

    window_end = now

    metrics = [
        {
            "laneId": "lane_1",
            "timestamp": now,
            "vehicleCount": 10,
            "carCount": 4,
            "motorcycleCount": 5,
            "busCount": 0,
            "truckCount": 1,
            "queueLengthVeh": 3,
            "queueLengthMEst": 18.5,
            "densityIndex": 0.45,
        },
        {
            "laneId": "lane_2",
            "timestamp": now,
            "vehicleCount": 7,
            "carCount": 3,
            "motorcycleCount": 4,
            "busCount": 0,
            "truckCount": 0,
            "queueLengthVeh": 2,
            "queueLengthMEst": 11.0,
            "densityIndex": 0.32,
        },
        {
            "laneId": "lane_1",
            "timestamp": now,
            "vehicleCount": 8,
            "carCount": 2,
            "motorcycleCount": 5,
            "busCount": 1,
            "truckCount": 0,
            "queueLengthVeh": 4,
            "queueLengthMEst": 21.0,
            "densityIndex": 0.51,
        },
    ]

    result = writer.write_cv_window(
        intersection_id="simpang4-pingit",
        window_start=window_start,
        window_end=window_end,
        metrics=metrics,
        source="cv_test",
    )

    print()
    print("=" * 70)
    print("CV -> SUPABASE TEST")
    print("=" * 70)
    print(result)
    print("=" * 70)


if __name__ == "__main__":
    main()