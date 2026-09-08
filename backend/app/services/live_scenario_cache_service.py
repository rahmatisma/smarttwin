"""Cache hasil Scenario Generator untuk endpoint live.

Tabel ``liveScenarioCache`` ditulis hanya oleh
``simulation/scenario_worker.py`` dan dibaca backend. Baris yang lebih tua
dari ``max_age_seconds`` dianggap tidak ada; kegagalan Supabase juga selalu
dikembalikan sebagai cache miss agar dashboard tetap memakai rule-based.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from app.services.supabase_client import get_scenario_cache_supabase

logger = logging.getLogger("uvicorn.error")


class LiveScenarioCacheService:
    TABLE = "liveScenarioCache"

    def __init__(self, supabase=None, max_age_seconds: int = 120) -> None:
        self._supabase = supabase
        self.max_age_seconds = max_age_seconds
        self._refresh_lock = threading.Lock()
        self._recent: OrderedDict[str, tuple[float, dict[str, Any] | None]] = OrderedDict()

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_scenario_cache_supabase()
        return self._supabase

    def get_fresh(self, intersection_id: str) -> dict[str, Any] | None:
        # Coalesce polling from dashboard, recommendation, and other tabs.
        # A slow database query must never create a queue of waiting threads.
        if not self._refresh_lock.acquire(blocking=False):
            return None
        try:
            cached = self._recent.get(intersection_id)
            if cached and time.monotonic() < cached[0]:
                return cached[1] if cached[1] is not None and self._is_fresh(cached[1]) else None
            row = self._load_fresh(intersection_id)
            self._recent[intersection_id] = (time.monotonic() + (5 if row is not None else 15), row)
            self._recent.move_to_end(intersection_id)
            while len(self._recent) > 16:
                self._recent.popitem(last=False)
            return row
        finally:
            self._refresh_lock.release()

    def _is_fresh(self, row: dict[str, Any]) -> bool:
        updated_at = datetime.fromisoformat(str(row["updatedAt"]).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - updated_at).total_seconds()
        return 0 <= age <= self.max_age_seconds

    def _load_fresh(self, intersection_id: str) -> dict[str, Any] | None:
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
            if not self._is_fresh(row):
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
