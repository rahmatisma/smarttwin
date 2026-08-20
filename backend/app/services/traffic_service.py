from __future__ import annotations

from pathlib import Path
from typing import Any

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)


class TrafficService:
    """
    Service untuk menyediakan TrafficState
    kepada layer API.

    Service tidak melakukan perhitungan traffic sendiri.

    Semua agregasi dilakukan oleh:

        TrafficStateBuilder
    """

    def __init__(
        self,
        csv_path: str | Path,
        window_seconds: int = 5,
    ) -> None:

        self.csv_path = Path(csv_path)

        self.builder = TrafficStateBuilder(
            TrafficStateBuilderConfig(
                window_seconds=window_seconds
            )
        )

    # ========================================================
    # BUILD ALL STATES
    # ========================================================

    def get_all_states(
        self,
    ) -> list[dict[str, Any]]:
        """
        Mengambil seluruh TrafficState
        yang dihasilkan dari CSV.
        """

        return self.builder.build_from_csv(
            self.csv_path
        )

    # ========================================================
    # LATEST STATE
    # ========================================================

    def get_latest_state(
        self,
    ) -> dict[str, Any] | None:
        """
        Mengambil TrafficState paling terbaru.

        Karena builder menghasilkan data
        dalam urutan timestamp, state terakhir
        adalah state terbaru.
        """

        states = self.get_all_states()

        if not states:
            return None

        return states[-1]

    # ========================================================
    # STATE BY INTERSECTION
    # ========================================================

    def get_latest_state_by_intersection(
        self,
        intersection_id: str,
    ) -> dict[str, Any] | None:
        """
        Mengambil state terbaru dari intersection tertentu.
        """

        states = self.get_all_states()

        matching_states = [
            state
            for state in states
            if state["intersectionId"]
            == intersection_id
        ]

        if not matching_states:
            return None

        return matching_states[-1]