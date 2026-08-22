from __future__ import annotations

import json

from app.pipeline.traffic_state_builder import (
    getDefaultCsvPath,
)
from app.services.traffic_ingestion_service import (
    TrafficIngestionService,
)
from app.services.traffic_repository import (
    TrafficRepository,
)


def main() -> None:

    print("=" * 70)
    print("SMARTTWIN BULK TRAFFIC REPOSITORY TEST")
    print("=" * 70)

    csv_path = getDefaultCsvPath()

    print(f"CSV: {csv_path}")
    print()

    # ========================================================
    # BUILD
    # ========================================================

    print("Memproses CSV...")

    ingestionService = TrafficIngestionService()

    states = ingestionService.buildStates(
        csv_path
    )

    print(
        f"Jumlah TrafficState: {len(states)}"
    )

    print()

    if not states:
        raise RuntimeError(
            "Tidak ada TrafficState."
        )

    # ========================================================
    # LIMIT TEST
    # ========================================================

    test_states = states[:10]

    print(
        f"Jumlah state yang diuji: "
        f"{len(test_states)}"
    )

    print()

    # ========================================================
    # BULK UPSERT
    # ========================================================

    repository = TrafficRepository()

    print(
        "Menjalankan BULK UPSERT ke Supabase..."
    )

    result = repository.bulk_upsert_traffic_states(
        test_states,
        source="cv",
    )

    print()
    print("=" * 70)
    print("BULK UPSERT BERHASIL")
    print("=" * 70)

    print(
        f"Traffic states : "
        f"{result['traffic_state_count']}"
    )

    print(
        f"Approach states: "
        f"{result['approach_state_count']}"
    )

    print()

    # ========================================================
    # FIRST STATE
    # ========================================================

    print("FIRST TRAFFIC STATE")
    print("-" * 70)

    print(
        json.dumps(
            result["traffic_states"][0],
            indent=2,
            default=str,
        )
    )

    print()

    # ========================================================
    # FIRST APPROACH
    # ========================================================

    print("FIRST APPROACH STATE")
    print("-" * 70)

    print(
        json.dumps(
            result["approaches"][0],
            indent=2,
            default=str,
        )
    )

    print()

    print("=" * 70)
    print("BULK REPOSITORY TEST BERHASIL")
    print("=" * 70)


if __name__ == "__main__":
    main()