from fastapi import APIRouter, Query

from app.schemas.digital_twin import (
    DigitalTwinCandidate,
    DigitalTwinScenarioResponse,
)
from app.services.live_scenario_cache_service import live_scenario_cache_service


router = APIRouter(prefix="/api/v1/digital-twin", tags=["Digital Twin"])


@router.get("/scenarios/latest", response_model=DigitalTwinScenarioResponse)
def get_latest_scenarios(
    intersectionId: str = Query(default="simpang4-pingit"),
) -> DigitalTwinScenarioResponse:
    """Kontrak tunggal frontend untuk tiga hasil Scenario Generator terbaru."""
    row = live_scenario_cache_service.get_fresh(intersectionId)
    if row is None:
        return DigitalTwinScenarioResponse(
            intersectionId=intersectionId,
            status="unavailable",
            message="Hasil Scenario Generator belum tersedia atau sudah basi.",
        )

    winner_id = str(row["candidateId"]).lower()
    raw_candidates = row.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        return DigitalTwinScenarioResponse(
            intersectionId=intersectionId,
            status="unavailable",
            updatedAt=row.get("updatedAt"),
            winnerId=winner_id,
            message=(
                "Cache format lama hanya menyimpan pemenang. Jalankan migrasi "
                "live_scenario_cache.sql lalu restart scenario_worker.py "
                "(full-cycle sudah menjadi default)."
            ),
        )

    candidates = [
        DigitalTwinCandidate(**candidate, isWinner=candidate["candidateId"] == winner_id)
        for candidate in raw_candidates
    ]
    return DigitalTwinScenarioResponse(
        intersectionId=intersectionId,
        status="completed",
        updatedAt=row["updatedAt"],
        winnerId=winner_id,
        candidates=candidates,
    )
