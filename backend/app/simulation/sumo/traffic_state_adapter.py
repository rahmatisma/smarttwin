from __future__ import annotations

from typing import Any

from app.pipeline.traffic_state_builder import (
    BuiltTrafficState,
)


class SumoTrafficStateAdapter:
    """
    Adapter:

        BuiltTrafficState
                ↓
        SUMO demand
                ↓
        SumoController.inject_demand()

    Adapter TIDAK menjalankan SUMO.

    Adapter hanya bertugas mengubah format data.
    """

    # ============================================================
    # VALID APPROACHES
    # ============================================================

    VALID_APPROACHES = {
        "north",
        "south",
        "east",
        "west",
    }

    # ============================================================
    # INIT
    # ============================================================

    def __init__(
        self,
        approach_to_edge: dict[str, str],
    ) -> None:

        self.approach_to_edge = {
            str(key)
            .lower()
            .strip(): str(value)
            for key, value in (
                approach_to_edge.items()
            )
        }

    # ============================================================
    # TO DEMAND
    # ============================================================

    def to_demand(
        self,
        state: BuiltTrafficState,
    ) -> list[dict[str, Any]]:
        """
        Mengubah BuiltTrafficState menjadi
        demand kendaraan untuk SUMO.

        Output:

        [
            {
                "approach": "north",
                "edge_id": "484349908#2",
                "volume": 10,
                "motorcycleCount": 6,
                "carCount": 3,
                "busCount": 1,
                "truckCount": 0
            }
        ]
        """

        demand: list[
            dict[str, Any]
        ] = []

        # ========================================================
        # APPROACH
        # ========================================================

        for approach_state in (
            state.approaches
        ):

            approach_name = str(
                approach_state.approach
            ).lower().strip()

            # ----------------------------------------------------
            # VALIDATE APPROACH
            # ----------------------------------------------------

            if (
                approach_name
                not in self.VALID_APPROACHES
            ):
                continue

            # ----------------------------------------------------
            # GET EDGE
            # ----------------------------------------------------

            edge_id = (
                self.approach_to_edge.get(
                    approach_name
                )
            )

            if edge_id is None:
                continue

            # ----------------------------------------------------
            # READ COUNTS
            # ----------------------------------------------------

            motorcycle_count = max(
                0,
                int(
                    approach_state.motorcycleCount
                    or 0
                ),
            )

            car_count = max(
                0,
                int(
                    approach_state.carCount
                    or 0
                ),
            )

            bus_count = max(
                0,
                int(
                    approach_state.busCount
                    or 0
                ),
            )

            truck_count = max(
                0,
                int(
                    approach_state.truckCount
                    or 0
                ),
            )

            volume = max(
                0,
                int(
                    approach_state.volume
                    or 0
                ),
            )

            # ----------------------------------------------------
            # BUILD DEMAND
            # ----------------------------------------------------

            demand.append(
                {
                    "approach": (
                        approach_name
                    ),
                    "edge_id": edge_id,
                    "volume": volume,
                    "motorcycleCount": (
                        motorcycle_count
                    ),
                    "carCount": car_count,
                    "busCount": bus_count,
                    "truckCount": (
                        truck_count
                    ),
                }
            )

        return demand

    # ============================================================
    # EMPTY CHECK
    # ============================================================

    @staticmethod
    def has_demand(
        demand: list[dict[str, Any]],
    ) -> bool:

        for item in demand:

            total = (
                int(
                    item.get(
                        "motorcycleCount",
                        0,
                    )
                    or 0
                )
                + int(
                    item.get(
                        "carCount",
                        0,
                    )
                    or 0
                )
                + int(
                    item.get(
                        "busCount",
                        0,
                    )
                    or 0
                )
                + int(
                    item.get(
                        "truckCount",
                        0,
                    )
                    or 0
                )
            )

            if total > 0:
                return True

        return False