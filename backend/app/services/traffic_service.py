from __future__ import annotations

from pathlib import Path

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
    get_default_csv_path,
)
from app.schemas.traffic import TrafficState


class TrafficService:
    """
    Service untuk menyediakan TrafficState kepada API.

    Alur:

        CSV asli
           ↓
        TrafficStateBuilder
           ↓
        TrafficState[]
           ↓
        TrafficService
           ↓
        API
    """

    def __init__(
        self,
        csv_path: str | Path | None = None,
        window_seconds: int = 5,
    ) -> None:

        self.csv_path = (
            Path(csv_path)
            if csv_path is not None
            else get_default_csv_path()
        )

        self.builder = TrafficStateBuilder(
            TrafficStateBuilderConfig(
                window_seconds=window_seconds
            )
        )

    # ========================================================
    # BUILD ALL STATES
    # ========================================================

    def get_all_states(self) -> list[TrafficState]:
        """
        Membaca CSV asli dan menghasilkan seluruh
        TrafficState.
        """

        return self.builder.build_from_csv(
            self.csv_path
        )

    # ========================================================
    # GET LATEST STATE
    # ========================================================

    def get_latest_state(self) -> TrafficState | None:
        """
        Mengambil TrafficState paling baru dari CSV.

        Jika CSV kosong, return None.
        """

        states = self.get_all_states()

        if not states:
            return None

        return states[-1]

    # ========================================================
    # GET STATE BY INDEX
    # ========================================================

    def get_state(
        self,
        index: int,
    ) -> TrafficState:
        """
        Mengambil satu TrafficState berdasarkan index.

        Contoh:

            index = 0
            → state pertama

            index = 10
            → state ke-11
        """

        states = self.get_all_states()

        if index < 0 or index >= len(states):
            raise IndexError(
                f"TrafficState index {index} "
                f"berada di luar range 0-{len(states) - 1}."
            )

        return states[index]

    # ========================================================
    # GET STATES BY INTERSECTION
    # ========================================================

    def get_states_by_intersection(
        self,
        intersection_id: str,
    ) -> list[TrafficState]:
        """
        Mengambil TrafficState berdasarkan intersectionId.
        """

        states = self.get_all_states()

        return [
            state
            for state in states
            if state.intersectionId
            == intersection_id
        ]