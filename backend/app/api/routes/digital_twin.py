import logging
from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel, Field
from app.core.auth import require_operator
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from app.schemas.digital_twin import (
    DigitalTwinCandidate,
    DigitalTwinScenarioResponse,
)
from app.services.live_scenario_cache_service import live_scenario_cache_service

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/v1/digital-twin", tags=["Digital Twin"])
evaluation_lock = threading.Lock()


class EvaluationRequest(BaseModel):
    trafficStateId: int = Field(gt=0)


@router.post("/evaluate", response_model=DigitalTwinScenarioResponse, dependencies=[Depends(require_operator)])
def evaluate_snapshot(request: EvaluationRequest):
    if not evaluation_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Evaluasi lain masih berjalan.")
    try:
        root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory(prefix="smarttwin-evaluation-") as directory:
            output = Path(directory) / "result.json"
            process = subprocess.run(
                [sys.executable, str(root / "simulation" / "evaluate_snapshot.py"),
                 "--state-id", str(request.trafficStateId), "--output", str(output)],
                cwd=root, capture_output=True, text=True, timeout=180,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if process.returncode or not output.exists():
                logger.error("Evaluasi snapshot gagal: %s", process.stderr[-4000:])
                raise HTTPException(status_code=503, detail="Evaluasi SUMO gagal; periksa log backend.")
            row = json.loads(output.read_text(encoding="utf-8"))
            return DigitalTwinScenarioResponse(
                intersectionId=row["intersectionId"], status="completed", updatedAt=row["updatedAt"],
                winnerId=row["candidateId"], candidates=[DigitalTwinCandidate(**candidate,
                    isWinner=candidate["candidateId"] == row["candidateId"]) for candidate in row["candidates"]],
            )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Evaluasi melewati batas waktu.") from exc
    finally:
        evaluation_lock.release()


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
            message="Evaluasi Scenario Generator belum tersedia atau kedaluwarsa. Hasil sesi SUMO aktif tersedia melalui endpoint simulation/state.",
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
