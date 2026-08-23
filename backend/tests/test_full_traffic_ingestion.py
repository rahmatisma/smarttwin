from __future__ import annotations

from app.pipeline.traffic_state_builder import (
    getDefaultCsvPath,
)
from app.services.traffic_ingestion_service import (
    TrafficIngestionService,
)


def main() -> None:

    print("=" * 70)
    print("SMARTTWIN FULL TRAFFIC INGESTION TEST")
    print("=" * 70)

    csvPath = getDefaultCsvPath()

    print()
    print(f"CSV: {csvPath}")
    print()

    # ========================================================
    # SERVICE
    # ========================================================

    service = TrafficIngestionService()

    # ========================================================
    # INGEST
    # ========================================================

    print("Memproses CSV...")
    print()

    result = service.ingestCsv(
        csvPath,
        source="cv",
    )

    # ========================================================
    # RESULT
    # ========================================================

    print("=" * 70)
    print("INGESTION SELESAI")
    print("=" * 70)

    print()
    print(f"CSV              : {result.csvPath}")
    print(f"Total states     : {result.totalStates}")
    print(f"Processed states : {result.processedStates}")

    print()

    if result.totalStates != result.processedStates:
        raise RuntimeError(
            "Jumlah state yang diproses tidak sesuai "
            "dengan jumlah state hasil builder."
        )

    print("=" * 70)
    print("FULL INGESTION TEST BERHASIL")
    print("=" * 70)


if __name__ == "__main__":
    main()