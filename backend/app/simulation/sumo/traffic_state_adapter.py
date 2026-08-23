from __future__ import annotations

from typing import Any

from app.pipeline.traffic_state_builder import BuiltTrafficState


class SumoTrafficStateAdapter:
    """
    Adapter yang mengubah BuiltTrafficState backend
    menjadi traffic demand yang dapat digunakan oleh SUMO.

    Alur:

        Traffic State Builder
                ↓
        BuiltTrafficState
                ↓
        SumoTrafficStateAdapter
                ↓
        SUMO demand
    """

    # ========================================================
    # VALID APPROACHES
    # ========================================================

    VALID_APPROACHES = {
        "north",
        "south",
        "east",
        "west",
    }

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        approach_to_edge: dict[str, str],
    ) -> None:
        """
        Parameters
        ----------
        approach_to_edge:
            Mapping approach backend ke edge SUMO.

        Contoh:

            {
                "north": "484349908#2",
                "south": "134603786#2",
                "east": "153857851#4",
                "west": "590064461#2",
            }
        """

        self.approach_to_edge = {
            str(key).lower().strip(): str(value)
            for key, value in approach_to_edge.items()
        }

    # ========================================================
    # TO DEMAND
    # ========================================================

    def to_demand(
        self,
        state: BuiltTrafficState,
    ) -> list[dict[str, Any]]:
        """
        Mengubah BuiltTrafficState menjadi SUMO demand.

        Input:

            BuiltTrafficState
                ↓
            approaches
                ↓
            ApproachState

        Output:

            [
                {
                    "approach": "north",
                    "edge_id": "484349908#2",
                    "volume": 10,
                    "motorcycleCount": 6,
                    "carCount": 3,
                    "busCount": 1,
                    "truckCount": 0,
                }
            ]
        """

        demand: list[dict[str, Any]] = []

        for approach_state in state.approaches:

            approach_name = str(
                approach_state.approach
            ).lower().strip()

            # ------------------------------------------------
            # VALIDATE APPROACH
            # ------------------------------------------------

            if (
                approach_name
                not in self.VALID_APPROACHES
            ):
                continue

            # ------------------------------------------------
            # GET SUMO EDGE
            # ------------------------------------------------

            edge_id = (
                self.approach_to_edge.get(
                    approach_name
                )
            )

            if edge_id is None:
                continue

            # ------------------------------------------------
            # BUILD DEMAND
            # ------------------------------------------------

            demand.append(
                {
                    "approach": approach_name,

                    "edge_id": edge_id,

                    "volume": max(
                        0,
                        int(
                            approach_state.volume
                        ),
                    ),

                    "motorcycleCount": max(
                        0,
                        int(
                            approach_state.motorcycleCount
                        ),
                    ),

                    "carCount": max(
                        0,
                        int(
                            approach_state.carCount
                        ),
                    ),

                    "busCount": max(
                        0,
                        int(
                            approach_state.busCount
                        ),
                    ),

                    "truckCount": max(
                        0,
                        int(
                            approach_state.truckCount
                        ),
                    ),
                }
            )

        return demand