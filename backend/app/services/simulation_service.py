from __future__ import annotations

import inspect
import threading
from pathlib import Path
from typing import Any

from app.pipeline.traffic_state_builder import TrafficStateBuilder
from app.schemas.simulation import (
    SimulationRequest,
    SimulationResult,
)
from app.simulation.sumo.sumo_controller import SumoController
from app.simulation.sumo.traffic_state_adapter import (
    SumoTrafficStateAdapter,
)


# ================================================================
# DEBUG IMPORT
# ================================================================

print("=" * 70)
print("SUMO CONTROLLER IMPORT CHECK")
print("=" * 70)

print(
    "Loaded from:",
    inspect.getfile(SumoController),
)

print(
    "Has start():",
    hasattr(SumoController, "start"),
)

print(
    "Has close():",
    hasattr(SumoController, "close"),
)

print(
    "Has inject_demand():",
    hasattr(SumoController, "inject_demand"),
)

print(
    "Has is_running():",
    hasattr(SumoController, "is_running"),
)

print(
    "Has get_metrics():",
    hasattr(SumoController, "get_metrics"),
)

print("=" * 70)


# ================================================================
# EXCEPTION
# ================================================================

class SimulationServiceError(Exception):
    """
    Exception khusus untuk error pada simulation service.
    """

    pass


# ================================================================
# SIMULATION SERVICE
# ================================================================

class SimulationService:
    """
    Service untuk mengelola SATU instance SUMO yang berjalan
    secara terus-menerus.

    Arsitektur:

        TrafficStateBuilder
                |
                v
        TrafficState terbaru
                |
                v
        SimulationService
                |
                v
        SumoTrafficStateAdapter
                |
                v
        SUMO / TraCI
                |
                v
        Background simulation loop
                |
                v
        Metrics


    IMPORTANT:

    SUMO TIDAK restart setiap request.

    Request pertama:
        -> build TrafficState
        -> start SUMO
        -> inject demand

    Request berikutnya:
        -> build TrafficState terbaru
        -> gunakan SUMO instance yang sama
        -> inject demand terbaru

    SUMO terus berjalan di background thread.
    """

    # ============================================================
    # INIT
    # ============================================================

    def __init__(self) -> None:

        # --------------------------------------------------------
        # TRAFFIC STATE BUILDER
        # --------------------------------------------------------

        self.builder = TrafficStateBuilder()

        # --------------------------------------------------------
        # SUMO CONTROLLER
        # --------------------------------------------------------

        self.controller: SumoController | None = None

        # --------------------------------------------------------
        # LOCK
        # --------------------------------------------------------

        self._lock = threading.RLock()

        # --------------------------------------------------------
        # ACTIVE STATE
        # --------------------------------------------------------

        self.active_intersection_id: str | None = None
        self.active_traffic_state_id: str | None = None

    # ============================================================
    # SUMO CONFIG PATH
    # ============================================================

    @staticmethod
    def _get_config_file() -> Path:
        """
        Struktur:

            smarttwin/
            ├── backend/
            │   └── app/
            │       └── services/
            │           └── simulation_service.py
            │
            └── simulation/
                └── network/
                    └── simpang4_pingit.sumocfg
        """

        current_file = Path(__file__).resolve()

        project_root = current_file.parents[3]

        config_file = (
            project_root
            / "simulation"
            / "network"
            / "simpang4_pingit.sumocfg"
        )

        print()
        print("=" * 70)
        print("SUMO CONFIG PATH DEBUG")
        print("=" * 70)

        print(
            "Current file :",
            current_file,
        )

        print(
            "Project root :",
            project_root,
        )

        print(
            "Config file  :",
            config_file,
        )

        print(
            "Exists       :",
            config_file.exists(),
        )

        print("=" * 70)

        return config_file

    # ============================================================
    # ADAPTER
    # ============================================================

    @staticmethod
    def _create_adapter() -> SumoTrafficStateAdapter:
        """
        Mapping TrafficState approach -> SUMO incoming edge.
        """

        approach_to_edge = {
            "north": "484349908#2",
            "south": "134603786#2",
            "east": "153857851#4",
            "west": "590064461#2",
        }

        return SumoTrafficStateAdapter(
            approach_to_edge=approach_to_edge
        )

    # ============================================================
    # BUILD TRAFFIC STATE
    # ============================================================

    def _build_traffic_state(
        self,
        request: SimulationRequest,
    ) -> Any:

        print()
        print("=" * 70)
        print("BUILDING TRAFFIC STATE")
        print("=" * 70)

        print(
            "Intersection:",
            request.intersectionId,
        )

        print(
            "Requested TrafficState ID:",
            request.trafficStateId,
        )

        # --------------------------------------------------------
        # BUILD LATEST STATE
        # --------------------------------------------------------

        try:

            traffic_state = (
                self.builder
                .build_latest_state_for_intersection(
                    intersection_id=request.intersectionId,
                    save=True,
                )
            )

        except Exception as exc:

            raise SimulationServiceError(
                "Gagal membangun TrafficState "
                f"dari database: {exc}"
            ) from exc

        # --------------------------------------------------------
        # STATE NOT FOUND
        # --------------------------------------------------------

        if traffic_state is None:

            print()
            print("=" * 70)
            print("TRAFFIC STATE WARNING")
            print("=" * 70)
            print(
                "Tidak ditemukan TrafficState dengan "
                "trafficLaneMetrics untuk intersection "
                f"'{request.intersectionId}'."
            )
            print("Simulation akan berjalan TANPA demand kendaraan.")
            print("=" * 70)

            self.active_intersection_id = request.intersectionId
            self.active_traffic_state_id = None

            return None

        # --------------------------------------------------------
        # SAVE ACTIVE STATE
        # --------------------------------------------------------

        self.active_intersection_id = (
            traffic_state.intersectionId
        )

        self.active_traffic_state_id = (
            traffic_state.trafficStateId
        )

        print(
            "TrafficState berhasil dibangun:"
        )

        print(
            "  trafficStateId:",
            traffic_state.trafficStateId,
        )

        print(
            "  intersectionId:",
            traffic_state.intersectionId,
        )

        print("=" * 70)

        return traffic_state

    # ============================================================
    # ENSURE SUMO
    # ============================================================

    def _ensure_sumo(
        self,
        request: SimulationRequest,
    ) -> SumoController:

        with self._lock:

            # ====================================================
            # SUMO SUDAH RUNNING
            # ====================================================

            if (
                self.controller is not None
                and self.controller.is_running()
            ):

                print()
                print("=" * 70)
                print("SUMO CONTROLLER ALREADY RUNNING")
                print("=" * 70)

                print(
                    "Active intersection:",
                    self.active_intersection_id,
                )

                print(
                    "Requested intersection:",
                    request.intersectionId,
                )

                # ------------------------------------------------
                # CHECK INTERSECTION
                # ------------------------------------------------

                if (
                    self.active_intersection_id
                    != request.intersectionId
                ):

                    raise SimulationServiceError(
                        "SUMO sedang menjalankan "
                        f"intersection "
                        f"'{self.active_intersection_id}'. "
                        "Stop simulation terlebih dahulu "
                        "sebelum mengganti intersection."
                    )

                print(
                    "Menggunakan instance SUMO yang sama."
                )

                print("=" * 70)

                return self.controller

            # ====================================================
            # CONFIG
            # ====================================================

            config_file = self._get_config_file()

            if not config_file.exists():

                raise SimulationServiceError(
                    "SUMO config file tidak ditemukan: "
                    f"{config_file}"
                )

            # ====================================================
            # CREATE CONTROLLER
            # ====================================================

            print()
            print("=" * 70)
            print("CREATING SUMO CONTROLLER")
            print("=" * 70)

            controller = SumoController(
                config_file=config_file,
                seed=request.seed,
            )

            print(
                "Controller created:",
                controller,
            )

            print("=" * 70)

            # ====================================================
            # START SUMO
            # ====================================================

            try:

                print()
                print("=" * 70)
                print("STARTING SUMO CONTROLLER")
                print("=" * 70)

                print(
                    "GUI:",
                    request.gui,
                )

                print(
                    "GUI Delay:",
                    request.guiDelayMs,
                )

                print(
                    "Seed:",
                    request.seed,
                )

                controller.start(
                    gui=request.gui,
                    gui_delay_ms=request.guiDelayMs,
                )

                print(
                    "SUMO controller berhasil dijalankan."
                )

                print(
                    "SUMO running:",
                    controller.is_running(),
                )

                print("=" * 70)

            except Exception as exc:

                print()
                print("=" * 70)
                print("SUMO START FAILED")
                print("=" * 70)

                print(
                    "Original error type:",
                    type(exc).__name__,
                )

                print(
                    "Original error:",
                    exc,
                )

                print("=" * 70)

                try:
                    controller.close()
                except Exception as close_exc:

                    print(
                        "[SUMO] Cleanup setelah "
                        "start gagal juga gagal:"
                    )

                    print(
                        f"{type(close_exc).__name__}: "
                        f"{close_exc}"
                    )

                raise SimulationServiceError(
                    "Gagal menjalankan SUMO: "
                    f"{exc}"
                ) from exc

            # ====================================================
            # SAVE CONTROLLER
            # ====================================================

            self.controller = controller

            print(
                "SUMO controller berhasil disimpan "
                "sebagai active controller."
            )

            return controller

    # ============================================================
    # RUN / UPDATE REALTIME
    # ============================================================

    def run(
        self,
        request: SimulationRequest,
    ) -> SimulationResult:

        with self._lock:

            # ====================================================
            # REQUEST DEBUG
            # ====================================================

            print()
            print("=" * 70)
            print("SIMULATION REQUEST")
            print("=" * 70)

            print(
                "Intersection:",
                request.intersectionId,
            )

            print(
                "TrafficState ID:",
                request.trafficStateId,
            )

            print(
                "Duration:",
                request.durationSeconds,
            )

            print(
                "GUI:",
                request.gui,
            )

            print(
                "GUI Delay:",
                request.guiDelayMs,
            )

            print(
                "Seed:",
                request.seed,
            )

            print("=" * 70)

            # ====================================================
            # 1. BUILD TRAFFIC STATE
            # ====================================================

            traffic_state = (
                self._build_traffic_state(request)
            )

            # ====================================================
            # 2. START / REUSE SUMO
            # ====================================================

            controller = (
                self._ensure_sumo(request)
            )

            # ====================================================
            # 3. CREATE ADAPTER
            # 3. MAPPING KE SUMO DEMAND
            # ====================================================

            adapter = self._create_adapter()
            demand = None

            if traffic_state is not None:
                try:

                    demand = (
                        adapter.to_demand(
                            traffic_state
                        )
                    )

                except Exception as exc:

                    raise SimulationServiceError(
                        "Gagal mengubah TrafficState "
                        "menjadi demand SUMO: "
                        f"{exc}"
                    ) from exc

            # ====================================================
            # 4. DEBUG DEMAND
            # ====================================================

            print()
            print("=" * 70)
            print("SUMO DEMAND")
            print("=" * 70)

            print(demand)

            print("=" * 70)

            # ====================================================
            # 5. INJECT DEMAND
            # ====================================================

            if demand:

                try:

                    injected = (
                        controller.inject_demand(
                            demand
                        )
                    )

                except Exception as exc:

                    raise SimulationServiceError(
                        "Gagal memasukkan "
                        "TrafficState terbaru "
                        "ke SUMO: "
                        f"{exc}"
                    ) from exc

            else:

                injected = {
                    "motorcycle": 0,
                    "car": 0,
                    "bus": 0,
                    "truck": 0,
                    "total": 0,
                }

            # ====================================================
            # 6. DEBUG INJECTION
            # ====================================================

            print()
            print("=" * 70)
            print("VEHICLES INJECTED")
            print("=" * 70)

            print(injected)

            print("=" * 70)

            # ====================================================
            # 7. GET CURRENT METRICS
            # ====================================================

            try:

                result = controller.get_metrics()

            except Exception as exc:

                raise SimulationServiceError(
                    "Gagal mengambil metrics SUMO: "
                    f"{exc}"
                ) from exc

            # ====================================================
            # 8. IDENTIFIERS
            # ====================================================

            if traffic_state is not None:
                result["trafficStateId"] = (
                    traffic_state.trafficStateId
                )

                result["intersectionId"] = (
                    traffic_state.intersectionId
                )
            else:
                result["trafficStateId"] = None
                result["intersectionId"] = request.intersectionId

            result["injectedVehicles"] = injected

            # ====================================================
            # 9. RETURN
            # ====================================================

            print()
            print("=" * 70)
            print("SUMO SIMULATION RESULT")
            print("=" * 70)

            print(result)

            print("=" * 70)

            return SimulationResult(
                **result
            )

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> dict:

        with self._lock:

            # ----------------------------------------------------
            # NO CONTROLLER
            # ----------------------------------------------------

            if self.controller is None:

                return {
                    "running": False,
                    "intersectionId": (
                        self.active_intersection_id
                    ),
                    "trafficStateId": (
                        self.active_traffic_state_id
                    ),
                }

            # ----------------------------------------------------
            # METRICS
            # ----------------------------------------------------

            try:

                metrics = (
                    self.controller.get_metrics()
                )

            except Exception as exc:

                return {
                    "running": False,
                    "intersectionId": (
                        self.active_intersection_id
                    ),
                    "trafficStateId": (
                        self.active_traffic_state_id
                    ),
                    "error": str(exc),
                }

            # ----------------------------------------------------
            # RESULT
            # ----------------------------------------------------

            return {
                "running": (
                    self.controller.is_running()
                ),
                "paused": (
                    self.controller.paused
                ),
                "intersectionId": (
                    self.active_intersection_id
                ),
                "trafficStateId": (
                    self.active_traffic_state_id
                ),
                **metrics,
            }

    # ============================================================
    # SIMULATION STATE (VEHICLES + SIGNALS)
    # ============================================================

    def get_simulation_state(self) -> dict[str, Any]:
        with self._lock:
            if self.controller is None or not self.controller.is_running():
                return {
                    "running": False,
                    "paused": False,
                    "vehicles": [],
                    "signals": [],
                    "simulationTimeSeconds": 0
                }
            return {
                "running": True,
                "paused": self.controller.paused,
                "vehicles": self.controller.active_vehicles_data,
                "signals": self.controller.active_signals_data,
                "simulationTimeSeconds": self.controller.last_simulation_time
            }

    # ============================================================
    # PAUSE / RESUME
    # ============================================================

    def pause(self) -> dict:
        with self._lock:
            if self.controller is not None and self.controller.is_running():
                self.controller.pause()
            return {"status": "paused"}

    def resume(self) -> dict:
        with self._lock:
            if self.controller is not None and self.controller.is_running():
                self.controller.resume()
            return {"status": "running"}

    # ============================================================
    # STOP
    # ============================================================

    def stop(self) -> dict:

        with self._lock:

            # ----------------------------------------------------
            # NO CONTROLLER
            # ----------------------------------------------------

            if self.controller is None:

                return {
                    "running": False,
                    "message": (
                        "SUMO tidak sedang berjalan."
                    ),
                }

            # ----------------------------------------------------
            # CLOSE
            # ----------------------------------------------------

            try:

                self.controller.close()

            except Exception as exc:

                print()
                print("=" * 70)
                print("SUMO STOP ERROR")
                print("=" * 70)

                print(
                    f"{type(exc).__name__}: {exc}"
                )

                print("=" * 70)

                raise SimulationServiceError(
                    "Gagal menghentikan SUMO: "
                    f"{exc}"
                ) from exc

            finally:

                self.controller = None

                self.active_intersection_id = None

                self.active_traffic_state_id = None

            # ----------------------------------------------------
            # RETURN
            # ----------------------------------------------------

            return {
                "running": False,
                "message": (
                    "SUMO realtime simulation "
                    "berhasil dihentikan."
                ),
            }


# ================================================================
# SINGLETON SERVICE
# ================================================================

simulation_service = SimulationService()