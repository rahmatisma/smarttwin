"""Cache hasil Scenario Generator untuk endpoint live.

Tabel ``liveScenarioCache`` ditulis hanya oleh
``simulation/scenario_worker.py`` dan dibaca backend. Baris yang lebih tua
dari ``max_age_seconds`` dianggap tidak ada; kegagalan Supabase juga selalu
dikembalikan sebagai cache miss agar dashboard tetap memakai rule-based.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.supabase_client import get_supabase

logger = logging.getLogger("uvicorn.error")


class LiveScenarioCacheService:
    TABLE = "liveScenarioCache"

    def __init__(self, supabase=None, max_age_seconds: int = 120) -> None:
        self._supabase = supabase
        self.max_age_seconds = max_age_seconds

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase

    def get_fresh(self, intersection_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.supabase.table(self.TABLE)
                .select("*")
                .eq("intersectionId", intersection_id)
                .limit(1)
                .execute()
            )
            if not response.data:
                return None
            row = response.data[0]
            updated_at = datetime.fromisoformat(
                str(row["updatedAt"]).replace("Z", "+00:00")
            )
            age = (datetime.now(timezone.utc) - updated_at).total_seconds()
            if not 0 <= age <= self.max_age_seconds:
                return None
            if not self._is_valid_row(row, intersection_id):
                logger.warning(
                    "Cache Scenario Generator rusak untuk intersectionId=%s; "
                    "jatuh ke rule-based",
                    intersection_id,
                )
                return None
            return row
        except Exception as exc:
            logger.warning("Cache Scenario Generator tidak tersedia: %s", exc)
            return None

    @staticmethod
    def _is_valid_row(row: Any, intersection_id: str) -> bool:
        """Validasi minimum kontrak worker -> backend sebelum payload dipakai."""
        if not isinstance(row, dict) or row.get("intersectionId") != intersection_id:
            return False

        recommendation = row.get("recommendation")
        if not isinstance(recommendation, dict):
            return False

        required_recommendation = {
            "recommendedPhase": str,
            "recommendedGreenSeconds": (int, float),
            "currentGreenSeconds": (int, float),
            "currentPhase": str,
        }
        for field, expected_type in required_recommendation.items():
            value = recommendation.get(field)
            if not isinstance(value, expected_type):
                return False

        required_metrics = {
            "avgDelaySeconds": (int, float),
            "avgQueueLengthM": (int, float),
            "throughputVeh": (int, float),
        }
        for field, expected_type in required_metrics.items():
            value = row.get(field)
            if not isinstance(value, expected_type) or value < 0:
                return False

        if row.get("los") not in {"A", "B", "C", "D", "E", "F"}:
            return False
        if not isinstance(row.get("candidateId"), str) or not row["candidateId"]:
            return False

        candidates = row.get("candidates")
        # Format legacy tanpa candidates tetap valid untuk RecommendationService,
        # tetapi endpoint Digital Twin akan menandainya unavailable.
        if candidates is not None:
            if not isinstance(candidates, list):
                return False
            ids = {item.get("candidateId") for item in candidates if isinstance(item, dict)}
            if candidates and ids != {"baseline", "aggressive", "balanced"}:
                return False
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    return False
                for field in (
                    "avgDelaySeconds", "avgQueueLengthM", "queueLengthVeh",
                    "throughputVeh", "cycleLengthSeconds", "totalCycleSeconds",
                ):
                    if not isinstance(candidate.get(field), (int, float)) or candidate[field] < 0:
                        return False
                phases = candidate.get("phases")
                if not isinstance(phases, list) or len(phases) != 4:
                    return False

        cycle_plan = recommendation.get("cyclePlan")
        if cycle_plan is not None:
            if not isinstance(cycle_plan, dict):
                return False
            phases = cycle_plan.get("phases")
            if not isinstance(phases, list) or len(phases) != 4:
                return False
            for phase in phases:
                if (
                    not isinstance(phase, dict)
                    or not isinstance(phase.get("approach"), str)
                    or not isinstance(phase.get("greenSeconds"), (int, float))
                    or phase["greenSeconds"] < 0
                ):
                    return False
                for duration_field in ("yellowSeconds", "redSeconds"):
                    duration = phase.get(duration_field)
                    if duration is not None and (
                        not isinstance(duration, (int, float)) or duration < 0
                    ):
                        return False

        return True


live_scenario_cache_service = LiveScenarioCacheService()
