from __future__ import annotations

from pathlib import Path

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
)

from app.schemas.simulation import (
    SimulationRequest,
    SimulationResult,
)

from app.simulation.sumo.sumo_controller import (
    SumoController,
)

from app.simulation.sumo.traffic_state_adapter import (
    SumoTrafficStateAdapter,
)


class SimulationServiceError(Exception):
    pass


class SimulationService:

    def __init__(self) -> None:
        self.builder = TrafficStateBuilder()

    def run(
        self,
        request: SimulationRequest,
    ) -> SimulationResult:

        # ====================================================
        # 1. BUILD TRAFFIC STATE
        # ====================================================

        try:

            if request.trafficStateId is not None:
                raise NotImplementedError(
                    "trafficStateId spesifik "
                    "belum diimplementasikan."
                )

            traffic_state = (
                self.builder
                .build_latest_state_for_intersection(
                    intersection_id=(
                        request.intersectionId
                    ),
                    save=True,
                )
            )

        except Exception as exc:

            raise SimulationServiceError(
                "Gagal membangun TrafficState "
                f"dari Supabase: {exc}"
            ) from exc

        if traffic_state is None:

            raise SimulationServiceError(
                "Tidak ditemukan TrafficState "
                "dengan trafficLaneMetrics "
                "untuk intersection "
                f"'{request.intersectionId}'."
            )

        # ====================================================
        # 2. SUMO CONFIG
        # ====================================================

        config_file = (
            SumoController.DEFAULT_CONFIG_FILE
        )

        if not config_file.exists():

            raise SimulationServiceError(
                "SUMO config file tidak ditemukan: "
                f"{config_file}"
            )

        # ====================================================
        # 3. ADAPTER
        # ====================================================

        approach_to_edge = {
            "north": "484349908#0",
            "south": "134603786#0",
            "east": "153857851#2",
            "west": "590064461#0",
        }

        adapter = SumoTrafficStateAdapter(
            approach_to_edge=approach_to_edge
        )

        demand = adapter.to_demand(
            traffic_state
        )

        if not demand:

            raise SimulationServiceError(
                "TrafficState berhasil dibangun, "
                "tetapi tidak ada demand SUMO "
                "yang dapat dibuat."
            )

        # ====================================================
        # 4. START SUMO
        # ====================================================

        controller = SumoController(
            config_file=config_file,
            seed=request.seed,
        )

        try:

            controller.start(
                gui=request.gui,
                gui_delay_ms=request.guiDelayMs,
            )

            controller.create_vehicle_types()

            # =================================================
            # 5. RUN SIMULATION
            # =================================================

            result = controller.run(
                demand=demand,
                duration_seconds=(
                    request.durationSeconds
                ),
            )

        except Exception as exc:

            raise SimulationServiceError(
                f"SUMO simulation gagal: {exc}"
            ) from exc

        finally:

            controller.close()

        # ====================================================
        # 6. ADD IDENTIFIERS
        # ====================================================

        result["trafficStateId"] = (
            traffic_state.trafficStateId
        )

        result["intersectionId"] = (
            traffic_state.intersectionId
        )

        # ====================================================
        # 7. RETURN API RESULT
        # ====================================================

        return SimulationResult(
            **result
        )


simulation_service = SimulationService()