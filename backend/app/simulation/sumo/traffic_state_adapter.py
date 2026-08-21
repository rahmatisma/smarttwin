from __future__ import annotations

from typing import Any

from app.schemas.traffic import TrafficState


class SumoTrafficStateAdapter:
    """
    Adapter yang mengubah TrafficState dari backend menjadi
    format demand sederhana yang dapat digunakan oleh SUMO.

    TrafficState
        ↓
    SumoTrafficStateAdapter
        ↓
    SUMO demand
    """

    def __init__(
        self,
        approach_to_edge: dict[str, str],
    ) -> None:
        """
        Mapping antara nama approach dengan edge SUMO.

        Contoh:

            {
                "north": "north_in",
                "south": "south_in",
                "east": "east_in",
                "west": "west_in",
            }
        """

        self.approach_to_edge = {
            str(key).lower(): str(value)
            for key, value in approach_to_edge.items()
        }

    # ========================================================
    # TRAFFIC STATE -> SUMO DEMAND
    # ========================================================

    def to_demand(
        self,
        state: TrafficState,
    ) -> list[dict[str, Any]]:
        """
        Mengubah satu TrafficState menjadi daftar demand SUMO.

        Output:

            [
                {
                    "approach": "south",
                    "edge_id": "south_in",
                    "volume": 10,
                }
            ]

        Catatan:
        Adapter ini BELUM menjalankan SUMO.

        Tugasnya hanya menerjemahkan data backend
        ke format yang dapat digunakan simulation layer.
        """

        demand: list[dict[str, Any]] = []

        for approach_state in state.approaches:

            # ------------------------------------------------
            # Normalisasi nama approach
            # ------------------------------------------------

            approach_name = str(
                approach_state.approach
            ).lower()

            # ------------------------------------------------
            # Cari edge SUMO
            # ------------------------------------------------

            edge_id = self.approach_to_edge.get(
                approach_name
            )

            # ------------------------------------------------
            # Kalau approach belum memiliki mapping,
            # jangan membuat edge SUMO palsu.
            #
            # Approach tersebut dilewati.
            # ------------------------------------------------

            if edge_id is None:
                continue

            # ------------------------------------------------
            # Buat demand
            # ------------------------------------------------

            demand.append(
                {
                    "approach": approach_name,
                    "edge_id": edge_id,
                    "volume": int(
                        approach_state.volume
                    ),
                }
            )

        return demand