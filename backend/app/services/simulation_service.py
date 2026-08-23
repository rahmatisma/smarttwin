from __future__ import annotations

import threading
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


# ================================================================
# DEBUG IMPORT
# ================================================================

# Ini membantu memastikan Uvicorn benar-benar menggunakan
# SumoController yang kita maksud.
import inspect

print("=" * 70)
print("SUMO CONTROLLER IMPORT CHECK")
print("=" * 70)
print(
    "Loaded from:",
    inspect.getfile(SumoController),
)
print(
    "Has close():",
    hasattr(SumoController, "close"),
)
print("=" * 70)


# ================================================================
# EXCEPTION
# ================================================================

class SimulationServiceError(Exception):
    pass


# ================================================================
# SIMULATION SERVICE
# ================================================================

class SimulationService:
    """
    Service untuk mengelola satu instance SUMO
    yang berjalan terus-menerus.

    Alur:

        POST /simulation/run
                ↓
        Ambil TrafficState terbaru
                ↓
        Start SUMO jika belum hidup
                ↓
        Convert TrafficState → SUMO demand
                ↓
        Inject vehicle ke SUMO
                ↓
        Background thread menjalankan simulationStep()
                ↓
        Ambil metrics SUMO
                ↓
        Return SimulationResult

    SUMO TIDAK dijalankan ulang setiap request.

    Jika SUMO sudah hidup:
        → instance yang sama digunakan kembali.

    Jika SUMO belum hidup:
        → satu instance SUMO dibuat.

    TrafficState diambil dari TrafficStateBuilder.
    """

    # ============================================================
    # INIT
    # ============================================================

    def __init__(self) -> None:
        self.builder = TrafficStateBuilder()

        # --------------------------------------------------------
        # SUMO CONTROLLER
        # --------------------------------------------------------

        # Hanya SATU instance SUMO.
        self.controller: SumoController | None = None

        # --------------------------------------------------------
        # LOCK
        # --------------------------------------------------------

        # Melindungi operasi:
        #
        # - start SUMO
        # - inject demand
        # - stop SUMO
        #
        self._lock = threading.RLock()

        # --------------------------------------------------------
        # ACTIVE STATE
        # --------------------------------------------------------

        self.active_intersection_id: str | None = None
        self.active_traffic_state_id: str | None = None

    # ============================================================
    # SUMO CONFIG
    # ============================================================

    @staticmethod
    def _get_config_file() -> Path:
        """
        File:
            backend/app/services/simulation_service.py

        Project root:
            smarttwin/

        SUMO config:
            simulation/network/simpang4_pingit.sumocfg
        """

        project_root = (
            Path(__file__)
            .resolve()
            .parents[3]
        )

        config_file = (
            project_root
            / "simulation"
            / "network"
            / "simpang4_pingit.sumocfg"
        )

        return config_file

    # ============================================================
    # ADAPTER
    # ============================================================

    @staticmethod
    def _create_adapter() -> SumoTrafficStateAdapter:
        """
        Mapping approach TrafficState ke edge masuk SUMO.
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
    ):
        """
        Mengambil TrafficState terbaru dari Supabase.

        Untuk sekarang trafficStateId spesifik belum
        digunakan.

        Sistem mengambil TrafficState terbaru
        berdasarkan intersectionId.
        """

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
                f"dari Supabase: {exc}"
            ) from exc

        if traffic_state is None:
            raise SimulationServiceError(
                "Tidak ditemukan TrafficState "
                "dengan trafficLaneMetrics "
                "untuk intersection "
                f"'{request.intersectionId}'."
            )

        # --------------------------------------------------------
        # SIMPAN STATE AKTIF
        # --------------------------------------------------------

        self.active_intersection_id = (
            traffic_state.intersectionId
        )

        self.active_traffic_state_id = (
            traffic_state.trafficStateId
        )

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
            # SUMO SUDAH HIDUP
            # ====================================================

            if (
                self.controller is not None
                and self.controller.is_running()
            ):

                # ------------------------------------------------
                # Pastikan intersection sama
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

                return self.controller

            # ====================================================
            # CONFIG
            # ====================================================

            config_file = self._get_config_file()

            print()
            print("=" * 70)
            print("CHECKING SUMO CONFIG")
            print("=" * 70)
            print(
                f"Config file: {config_file}"
            )

            if not config_file.exists():
                raise SimulationServiceError(
                    "SUMO config file tidak ditemukan: "
                    f"{config_file}"
                )

            print("SUMO config ditemukan.")
            print("=" * 70)

            # ====================================================
            # CREATE CONTROLLER
            # ====================================================

            controller = SumoController(
                config_file=config_file,
                seed=request.seed,
            )

            # ====================================================
            # START SUMO
            # ====================================================

            try:

                print()
                print("=" * 70)
                print("STARTING SUMO CONTROLLER")
                print("=" * 70)

                controller.start(
                    gui=request.gui,
                    gui_delay_ms=0,
                )

                print(
                    "SUMO controller berhasil dijalankan."
                )

            except Exception as exc:

                # ------------------------------------------------
                # PENTING
                #
                # Jangan biarkan error cleanup menutupi
                # error asli dari controller.start().
                # ------------------------------------------------

                print()
                print("=" * 70)
                print("SUMO START FAILED")
                print("=" * 70)
                print(
                    f"Original error type: "
                    f"{type(exc).__name__}"
                )
                print(
                    f"Original error: {exc}"
                )
                print("=" * 70)

                try:

                    controller.close()

                except Exception as close_exc:

                    print()
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
            # 1. BUILD LATEST TRAFFIC STATE
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
                "GUI:",
                request.gui,
            )

            print(
                "Seed:",
                request.seed,
            )

            traffic_state = (
                self._build_traffic_state(
                    request
                )
            )

            print(
                "TrafficState:",
                traffic_state.trafficStateId,
            )

            # ====================================================
            # 2. START / REUSE SUMO
            # ====================================================

            controller = (
                self._ensure_sumo(
                    request
                )
            )

            # ====================================================
            # 3. ADAPTER
            # ====================================================

            adapter = (
                self._create_adapter()
            )

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

            # ====================================================
            # 5. INJECT NEW TRAFFIC
            # ====================================================

            if demand:

                try:

                    injected = (
                        controller
                        .inject_demand(
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

            # ====================================================
            # 7. GET CURRENT SUMO METRICS
            # ====================================================

            try:

                result = (
                    controller.get_metrics()
                )

            except Exception as exc:

                raise SimulationServiceError(
                    "Gagal mengambil metrics SUMO: "
                    f"{exc}"
                ) from exc

            # ====================================================
            # 8. IDENTIFIERS
            # ====================================================

            result["trafficStateId"] = (
                traffic_state.trafficStateId
            )

            result["intersectionId"] = (
                traffic_state.intersectionId
            )

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
            # BELUM ADA CONTROLLER
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
            # AMBIL METRICS
            # ----------------------------------------------------

            try:

                metrics = (
                    self.controller
                    .get_metrics()
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
            # RETURN STATUS
            # ----------------------------------------------------

            return {
                "running": (
                    self.controller
                    .is_running()
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
    # STOP
    # ============================================================

    def stop(self) -> dict:

        with self._lock:

            # ----------------------------------------------------
            # BELUM ADA CONTROLLER
            # ----------------------------------------------------

            if self.controller is None:

                return {
                    "running": False,
                    "message": (
                        "SUMO tidak sedang berjalan."
                    ),
                }

            # ----------------------------------------------------
            # CLOSE CONTROLLER
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

                self.active_intersection_id = (
                    None
                )

                self.active_traffic_state_id = (
                    None
                )

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