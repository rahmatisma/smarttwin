import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Query

from app.schemas.digital_twin import (
    DigitalTwinCandidate,
    DigitalTwinScenarioResponse,
)
from app.services.live_scenario_cache_service import live_scenario_cache_service

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/v1/digital-twin", tags=["Digital Twin"])


@router.get("/scenarios/latest", response_model=DigitalTwinScenarioResponse)
def get_latest_scenarios(
    intersectionId: str = Query(default="simpang4-pingit"),
) -> DigitalTwinScenarioResponse:
    """Kontrak tunggal frontend untuk tiga hasil Scenario Generator terbaru."""
    row = live_scenario_cache_service.get_fresh(intersectionId)
    if row is None:
        try:
            from app.services.traffic_service import TrafficService
            from app.schemas.traffic import TrafficState, ApproachState
            from decision_engine.rule_based_engine import RuleBasedEngine
            from simulation.scenario_generator import generate_cycle_candidate_plans
            
            traffic_service = TrafficService()
            latest = traffic_service.get_latest_traffic(intersection_id=intersectionId, limit=1)
            
            if not latest:
                return DigitalTwinScenarioResponse(
                    intersectionId=intersectionId,
                    status="unavailable",
                    message="Cache scenario kosong dan data traffic juga tidak tersedia.",
                )
                
            data = latest[0]
            ts_data = data["trafficState"]
            approaches_data = data["approaches"]
            
            traffic_state = TrafficState(
                intersectionId=intersectionId,
                windowStart=ts_data["windowStart"],
                windowEnd=ts_data["windowEnd"],
                approaches=[ApproachState(**app) for app in approaches_data]
            )
            
            engine = RuleBasedEngine()
            baseline_cycle = engine.recommend_cycle(traffic_state)
            raw_candidates = generate_cycle_candidate_plans(baseline_cycle)
            
            candidates = [
                DigitalTwinCandidate(**candidate, isWinner=candidate["candidateId"] == "baseline")
                for candidate in raw_candidates
            ]
            
            return DigitalTwinScenarioResponse(
                intersectionId=intersectionId,
                status="completed",
                updatedAt=datetime.now(timezone.utc),
                winnerId="baseline",
                candidates=candidates,
                message="Dihasilkan secara dinamis karena cache tidak tersedia."
            )
            
        except Exception as e:
            logger.error(f"Gagal generate scenario dinamis: {e}")
            return DigitalTwinScenarioResponse(
                intersectionId=intersectionId,
                status="unavailable",
                message=f"Hasil Scenario Generator belum tersedia atau sudah basi. Error fallback: {e}",
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
