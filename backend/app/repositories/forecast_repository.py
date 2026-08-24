from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.supabase_client import get_supabase


class ForecastRepository:

    def __init__(self) -> None:

        self.supabase = get_supabase()

    # ========================================================
    # GET RECENT TRAFFIC APPROACH STATES
    # ========================================================

    def get_recent_traffic(
        self,
        intersection_id: str,
        minutes: int = 60,
    ) -> list[dict[str, Any]]:

        since = (
            datetime.now(timezone.utc)
            - timedelta(minutes=minutes)
        ).isoformat()

        response = (
            self.supabase
            .table("trafficApproachStates")
            .select(
                """
                approach,
                volume,
                carCount,
                motorcycleCount,
                busCount,
                truckCount,
                queueLengthVeh,
                queueLengthMEst,
                densityIndex,
                avgSpeedKmh,
                trafficStateId
                """
            )
            .eq(
                "intersectionId",
                intersection_id,
            )
            .gte(
                "windowStart",
                since,
            )
            .order(
                "windowStart",
                desc=False,
            )
            .execute()
        )

        return response.data or []