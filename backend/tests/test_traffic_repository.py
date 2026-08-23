from __future__ import annotations

import json
from pathlib import Path

from app.services.traffic_repository import (
    TrafficRepository,
)
from app.services.traffic_ingestion_service import (
    TrafficIngestionService,
)


def main() -> None:
    print("=" * 70)
    print("SMARTTWIN TRAFFIC REPOSITORY TEST")
    print("=" * 70)

    csvPath = (
        Path(__file__).resolve().parents[2]
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )

    print(f"CSV: {csvPath}")
    print()

    # ============================================================
    # BUILD TRAFFIC STATES
    # ============================================================

    ingestionService = TrafficIngestionService(
        window_seconds=5
    )

    states = ingestionService.build_states_from_csv(
        csvPath
    )

    print(f"Jumlah TrafficState: {len(states)}")

    if not states:
        raise RuntimeError(
            "Tidak ada TrafficState yang berhasil dibuat."
        )

    # ============================================================
    # AMBIL SATU STATE SAJA
    # ============================================================

    state = states[0]

    print()
    print("STATE YANG AKAN DISIMPAN")
    print("-" * 70)

    print(
        json.dumps(
            state.model_dump(
                mode="json"
            ),
            indent=2,
        )
    )

    # ============================================================
    # SAVE KE SUPABASE
    # ============================================================

    repository = TrafficRepository()

    print()
    print("Menyimpan TrafficState ke Supabase...")
    print()

    result = repository.save_traffic_state(
        state,
        source="cv",
    )

    # ============================================================
    # RESULT
    # ============================================================

    print("=" * 70)
    print("SUPABASE INSERT BERHASIL")
    print("=" * 70)

    print()
    print("TRAFFIC STATE")
    print("-" * 70)

    print(
        json.dumps(
            result["traffic_state"],
            indent=2,
            default=str,
        )
    )

    print()
    print("APPROACH STATES")
    print("-" * 70)

    for approach in result["approaches"]:
        print(
            json.dumps(
                approach,
                indent=2,
                default=str,
            )
        )

    print()
    print("=" * 70)
    print("REPOSITORY TEST BERHASIL")
    print("=" * 70)


if __name__ == "__main__":
    main()