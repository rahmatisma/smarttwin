
from pathlib import Path

from app.services.traffic_ingestion_service import (
    TrafficIngestionService,
)


def main() -> None:
    """
    Test sederhana:

        CSV
        ↓
        TrafficStateBuilder
        ↓
        TrafficState[]
    """

    csv_path = (
        Path(__file__).resolve().parents[2]
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )

    print("=" * 70)
    print("SMARTTWIN TRAFFIC INGESTION TEST")
    print("=" * 70)

    print(f"CSV: {csv_path}")
    print()

    service = TrafficIngestionService(
        window_seconds=5
    )

    states = service.build_states_from_csv(
        csv_path
    )

    print(f"Jumlah TrafficState: {len(states)}")
    print()

    if not states:
        print("Tidak ada TrafficState.")
        return

    first_state = states[0]

    print("FIRST TRAFFIC STATE")
    print("-" * 70)

    print(
        first_state.model_dump(
            mode="json"
        )
    )

    print()
    print("APPROACH")
    print("-" * 70)

    for approach in first_state.approaches:
        print(
            f"{approach.approach}: "
            f"volume={approach.volume}, "
            f"car={approach.carCount}, "
            f"motorcycle={approach.motorcycleCount}, "
            f"bus={approach.busCount}, "
            f"truck={approach.truckCount}, "
            f"queueVeh={approach.queueLengthVeh}, "
            f"queueM={approach.queueLengthMEst}, "
            f"density={approach.densityIndex}, "
            f"speed={approach.avgSpeedKmh}"
        )

    print()
    print("=" * 70)
    print("BUILD TEST BERHASIL")
    print("=" * 70)


if __name__ == "__main__":
    main()

