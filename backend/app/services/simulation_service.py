from __future__ import annotations

import inspect
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from app.pipeline.traffic_state_builder import TrafficStateBuilder
from app.services.supabase_client import get_supabase
from app.schemas.simulation import (
    SimulationRequest,
    SimulationResult,
)
from app.simulation.sumo.sumo_controller import SumoController
from app.simulation.sumo.traffic_state_adapter import (
    SumoTrafficStateAdapter,
)
from decision_engine.rule_based_engine import RuleBasedEngine, FIXED_CYCLE_ORDER
from simulation.scenario_generator import (
    calculate_los,
    generate_cycle_candidate_plans,
    METERS_PER_QUEUED_VEHICLE,
)

# Konstanta State String SUMO diambil dari spesifikasi scenario_generator
_GREEN_STATE_BY_APPROACH = {
    "south": "GGGggrrrrrrrrrrrrrrr",
    "east": "rrrrrGGGggrrrrrrrrrr",
    "north": "rrrrrrrrrrGGGggrrrrr",
    "west": "rrrrrrrrrrrrrrrGGGgg",
}
_YELLOW_STATE_BY_APPROACH = {
    "south": "yyyyyrrrrrrrrrrrrrrr",
    "east": "rrrrryyyyyrrrrrrrrrr",
    "north": "rrrrrrrrrryyyyyrrrrr",
    "west": "rrrrrrrrrrrrrrryyyyy",
}
YELLOW_SECONDS = 4


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
        # SUMO CONTROLLERS -- SATU PER "context"
        # --------------------------------------------------------
        # Dashboard (live realtime, auto-start) dan halaman /digitaltwin
        # (sandbox skenario, manual start/pause/stop) berjalan sebagai
        # instance SUMO TERPISAH sepenuhnya -- masing-masing dikunci
        # oleh string context (mis. "dashboard"/"digitaltwin"), supaya
        # pause/stop di satu context tidak menyentuh context lain sama
        # sekali. Tidak ada context bawaan yang "lebih benar"; "default"
        # cuma nama slot untuk pemanggil yang tidak mengirim context.

        self.controllers: dict[str, SumoController | None] = {}

        # --------------------------------------------------------
        # LOCK
        # --------------------------------------------------------
        # Satu lock untuk semua context -- operasi start/stop antar
        # context jadi serial (bukan paralel), tapi ini murah (cuma
        # beberapa detik saat start SUMO) dan jauh lebih aman daripada
        # lock per-context yang berisiko deadlock kalau nanti ada
        # operasi yang menyentuh 2 context sekaligus.

        self._lock = threading.RLock()

        # --------------------------------------------------------
        # ACTIVE STATE -- PER CONTEXT
        # --------------------------------------------------------

        self.active_intersection_id: dict[str, str | None] = {}
        self.active_traffic_state_id: dict[str, str | None] = {}

    # ============================================================
    # CONTROLLER LOOKUP
    # ============================================================

    def _get_controller(self, context: str) -> SumoController | None:
        return self.controllers.get(context)

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
            / "simpang4_pingit_live.sumocfg"
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

        except httpx.TransportError:

            # get_supabase() di-@lru_cache -- satu koneksi (pool httpx)
            # dipakai seumur proses backend. Kalau backend idle cukup
            # lama, PostgREST/Supabase bisa menutup keep-alive di sisi
            # server duluan tanpa client tahu, dan request berikutnya
            # gagal dengan "Server disconnected". Refresh client + coba
            # sekali lagi sebelum benar-benar menyerah -- ini transient,
            # bukan masalah data.
            #
            # Jeda singkat SEBELUM retry: kalau penyebabnya kontensi
            # CPU/IO sesaat (mis. proses SUMO-GUI lain baru saja start
            # bersamaan), retry tanpa jeda sama sekali bisa masih kena
            # jendela gangguan yang persis sama dan gagal lagi juga.
            time.sleep(0.5)

            get_supabase.cache_clear()
            self.builder.supabase = get_supabase()

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

            self.active_intersection_id[request.context] = request.intersectionId
            self.active_traffic_state_id[request.context] = None

            return None

        # --------------------------------------------------------
        # SAVE ACTIVE STATE
        # --------------------------------------------------------

        self.active_intersection_id[request.context] = (
            traffic_state.intersectionId
        )

        self.active_traffic_state_id[request.context] = (
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

        context = request.context

        with self._lock:

            controller = self.controllers.get(context)

            # Perubahan renderer (GUI/headless) perlu process baru. Perubahan
            # skenario tidak: program TLS dapat diganti lewat TraCI pada
            # controller yang sama supaya kendaraan dan simulationTime lanjut.
            if (
                controller is not None
                and controller.is_running()
                and controller.is_gui != request.gui
            ):
                controller.close()
                controller = None
                self.controllers[context] = None

            # ====================================================
            # SUMO SUDAH RUNNING (di context ini)
            # ====================================================

            if (
                controller is not None
                and controller.is_running()
            ):

                print()
                print("=" * 70)
                print("SUMO CONTROLLER ALREADY RUNNING")
                print("Context:", context)
                print("=" * 70)

                print(
                    "Active intersection:",
                    self.active_intersection_id.get(context),
                )

                print(
                    "Requested intersection:",
                    request.intersectionId,
                )

                # ------------------------------------------------
                # CHECK INTERSECTION
                # ------------------------------------------------

                if (
                    self.active_intersection_id.get(context)
                    != request.intersectionId
                ):

                    raise SimulationServiceError(
                        "SUMO sedang menjalankan "
                        f"intersection "
                        f"'{self.active_intersection_id.get(context)}'. "
                        "Stop simulation terlebih dahulu "
                        "sebelum mengganti intersection."
                    )

                print(
                    "Menggunakan instance SUMO yang sama."
                )

                controller.scenario = request.scenario

                print("=" * 70)

                return controller

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
            print("Context:", context)
            print("=" * 70)

            controller = SumoController(
                config_file=config_file,
                seed=request.seed,
                scenario=request.scenario,
                context=context,
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

            self.controllers[context] = controller

            print(
                "SUMO controller berhasil disimpan "
                f"sebagai active controller (context={context})."
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

            if request.approaches is not None:
                traffic_state = None
                self.active_intersection_id[request.context] = request.intersectionId
                self.active_traffic_state_id[request.context] = (
                    str(request.trafficStateId) if request.trafficStateId is not None else None
                )
            else:
                traffic_state = self._build_traffic_state(request)

            # ====================================================
            # 2. START / REUSE SUMO
            # ====================================================

            controller = (
                self._ensure_sumo(request)
            )

            # ====================================================
            # 2.5 APPLY SCENARIO LOGIC TO TRAFFIC LIGHT
            # ====================================================

            if request.scenario != "Traffic Realtime" and traffic_state is not None:
                try:
                    engine = RuleBasedEngine()
                    # Scenario Generator adalah SATU-SATUNYA sumber rumus
                    # Baseline/Aggressive/Balanced. Jangan hitung ulang di sini.
                    baseline_cycle = engine.recommend_cycle(traffic_state)
                    candidates = {
                        item["candidateId"]: item
                        for item in generate_cycle_candidate_plans(baseline_cycle)
                    }
                    selected_candidate = candidates[request.scenario.lower()]
                    phase_by_approach = {
                        phase["approach"]: phase
                        for phase in selected_candidate["phases"]
                    }
                    
                    import traci
                    tls_phases = []
                    
                    for approach in FIXED_CYCLE_ORDER:
                        phase = phase_by_approach[approach]
                        green = int(phase["greenSeconds"])
                            
                        tls_phases.append(
                            traci.trafficlight.Phase(
                                green, _GREEN_STATE_BY_APPROACH[approach]
                            )
                        )
                        tls_phases.append(
                            traci.trafficlight.Phase(
                                YELLOW_SECONDS, _YELLOW_STATE_BY_APPROACH[approach]
                            )
                        )

                    controller.apply_scenario_logic(
                        logic_phases=tls_phases,
                        scenario_id=selected_candidate["candidateId"],
                    )

                    # apply_scenario_logic() cuma menyuntik TraCI, tidak
                    # mencatat active_cycle_plan (beda dari apply_cycle_plan()
                    # yang dipakai jalur dashboard) -- tanpa ini,
                    # get_simulation_state() akan expose cyclePlan basi/None
                    # untuk skenario sandbox. Dicatat di sini supaya kartu
                    # "Durasi Sinyal" di frontend selalu akurat untuk kedua
                    # jalur.
                    controller.active_cycle_plan = selected_candidate

                except Exception as exc:
                    print(f"Gagal apply scenario logic: {exc}")

            # ====================================================
            # 3. CREATE ADAPTER
            # 3. MAPPING KE SUMO DEMAND
            # ====================================================

            adapter = self._create_adapter()
            demand = None

            if request.approaches is not None:
                demand = [item.model_dump() for item in request.approaches]
            elif traffic_state is not None:
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

            if request.cyclePlan is not None:
                try:
                    controller.apply_cycle_plan(request.cyclePlan.model_dump())
                except Exception as exc:
                    raise SimulationServiceError(
                        f"Gagal memasang CyclePlan ke TLS SUMO: {exc}"
                    ) from exc

            if demand and request.approaches is not None:
                try:
                    injected = controller.sync_demand(
                        demand,
                        traffic_timestamp=request.trafficTimestamp,
                    )
                except Exception as exc:
                    raise SimulationServiceError(
                        f"Gagal menyinkronkan demand dashboard ke SUMO: {exc}"
                    ) from exc
            elif demand:

                # Rekonsiliasi (sync_demand), BUKAN inject_demand. Controller
                # di sini bisa saja instance yang SUDAH JALAN dan dipakai
                # berkali-kali -- direuse _ensure_sumo() tiap kali skenario
                # diterapkan ulang, atau dipakai bersama dashboard lewat
                # context "dashboard" untuk skenario "Traffic Realtime".
                # inject_demand() SELALU MENAMBAH kendaraan di atas yang
                # sudah ada tanpa mengecek berapa yang sudah aktif --
                # dipanggil berulang di controller yang sama membuat
                # kendaraan menumpuk terus, kelihatan seperti simulasi
                # "restart/ngulang" walau prosesnya sendiri tidak pernah
                # mati. sync_demand() rekonsiliasi ke target (hapus
                # kelebihan, tambah kekurangan) -- aman dipanggil berkali-
                # kali di controller yang sama, termasuk yang baru dibuat
                # (tidak ada kelebihan untuk dihapus).
                #
                # adapter.to_demand() menulis total per lengan sebagai
                # "volume", sync_demand() mengharapkan "targetVehicleCount"
                # (nama field yang sama dipakai skema approaches dashboard)
                # -- dipetakan di sini, bukan mengubah adapter yang juga
                # dipakai jalur lain.
                try:

                    sync_ready_demand = [
                        {**item, "targetVehicleCount": item.get("volume", 0)}
                        for item in demand
                    ]

                    injected = (
                        controller.sync_demand(
                            sync_ready_demand,
                            traffic_timestamp=request.trafficTimestamp,
                        )
                    )

                except Exception as exc:

                    raise SimulationServiceError(
                        "Gagal menyinkronkan "
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

    def status(self, context: str = "default") -> dict:

        with self._lock:

            controller = self.controllers.get(context)

            # ----------------------------------------------------
            # NO CONTROLLER
            # ----------------------------------------------------

            if controller is None:

                return {
                    "running": False,
                    "intersectionId": (
                        self.active_intersection_id.get(context)
                    ),
                    "trafficStateId": (
                        self.active_traffic_state_id.get(context)
                    ),
                }

            # ----------------------------------------------------
            # METRICS
            # ----------------------------------------------------

            try:

                metrics = (
                    controller.get_metrics()
                )

            except Exception as exc:

                return {
                    "running": False,
                    "intersectionId": (
                        self.active_intersection_id.get(context)
                    ),
                    "trafficStateId": (
                        self.active_traffic_state_id.get(context)
                    ),
                    "error": str(exc),
                }

            # ----------------------------------------------------
            # RESULT
            # ----------------------------------------------------

            return {
                "running": (
                    controller.is_running()
                ),
                "paused": (
                    controller.paused
                ),
                "intersectionId": (
                    self.active_intersection_id.get(context)
                ),
                "trafficStateId": (
                    self.active_traffic_state_id.get(context)
                ),
                **metrics,
            }

    # ============================================================
    # SIMULATION STATE (VEHICLES + SIGNALS)
    # ============================================================

    def get_simulation_state(self, context: str = "default") -> dict[str, Any]:
        # Jangan ikut menunggu lock run/update. Semua field di bawah merupakan
        # snapshot cache Python yang ditulis loop SUMO secara atomik; endpoint
        # state tidak melakukan panggilan TraCI. Sebelumnya satu screenshot atau
        # sync_demand lambat dapat menahan polling dashboard >10 detik.
        controller = self.controllers.get(context)
        if controller is None or not controller.is_running():
            return {
                "running": False,
                "paused": False,
                "vehicles": [],
                "signals": [],
                "simulationTimeSeconds": 0
            }
        return {
            "running": True,
            "paused": controller.paused,
            "vehicles": list(controller.active_vehicles_data),
            "visibleVehicleCount": controller.live_visible_vehicle_count,
            "lastSyncFailedInsertions": controller.live_last_sync_failed_insertions,
            "lastSyncFailedByApproach": controller.live_last_sync_failed_by_approach,
            "signals": list(controller.active_signals_data),
            "simulationTimeSeconds": controller.last_simulation_time,
            "detectedVehicles": controller.detected_vehicle_count,
            "trafficTimestamp": controller.traffic_timestamp,
            "cyclePlan": controller.active_cycle_plan,
            "queueLengthVeh": controller.live_queue_length_veh,
            "queueBusiestApproach": controller.live_queue_busiest_approach,
            "throughputVehPerMin": round(
                controller.live_throughput_veh_per_min, 1
            ),
            # Metrik simpang keseluruhan (4 lengan digabung) untuk panel
            # "Hasil Simulasi" -- dihitung LANGSUNG dari SUMO yang sedang
            # jalan di halaman ini, BUKAN dari liveScenarioCache produksi
            # (itu decision engine, sengaja dipisah dari sandbox skenario).
            "avgDelaySeconds": round(controller.live_avg_delay_seconds, 1),
            "avgQueueLengthVeh": controller.live_total_queue_length_veh,
            "avgQueueLengthM": round(
                controller.live_total_queue_length_veh
                * METERS_PER_QUEUED_VEHICLE,
                1,
            ),
            "los": calculate_los(controller.live_avg_delay_seconds),
        }

    def sync_clock(
        self, video_time_seconds: float, context: str = "default"
    ) -> dict[str, Any]:
        """Camera Feed adalah clock utama untuk fase lampu realtime."""
        controller = self.controllers.get(context)
        if controller is None or not controller.is_running():
            return {
                "synced": False,
                "reason": "SUMO belum berjalan.",
                "videoTimeSeconds": video_time_seconds,
            }
        if controller.active_cycle_plan is None:
            return {
                "synced": False,
                "reason": "CyclePlan SUMO belum aktif.",
                "videoTimeSeconds": video_time_seconds,
            }
        try:
            return controller.sync_signal_clock(video_time_seconds)
        except RuntimeError as exc:
            return {
                "synced": False,
                "reason": str(exc),
                "videoTimeSeconds": video_time_seconds,
            }

    def apply_scenario(
        self,
        scenario: str,
        cycle_plan: dict[str, Any],
        context: str = "default",
    ) -> dict[str, Any]:
        """Terapkan skenario ke controller aktif tanpa operasi database."""
        # Jangan mengambil service._lock: request /run yang sedang menunggu
        # database memegang lock itu. Controller memiliki _traci_lock sendiri
        # untuk menjamin pergantian program TLS tetap thread-safe.
        controller = self.controllers.get(context)
        if controller is None or not controller.is_running():
            raise SimulationServiceError("SUMO belum berjalan. Tekan Start Simulation dahulu.")
        try:
            controller.apply_cycle_plan(cycle_plan)
        except Exception as exc:
            raise SimulationServiceError(f"Gagal menerapkan skenario: {exc}") from exc
        controller.scenario = scenario
        return {
            "applied": True,
            "scenario": scenario,
            "paused": controller.paused,
            "simulationTimeSeconds": controller.last_simulation_time,
        }

    # ============================================================
    # PAUSE / RESUME
    # ============================================================

    def pause(self, context: str = "default") -> dict:
        controller = self.controllers.get(context)
        if controller is not None and controller.is_running():
            controller.pause()
            return {"status": "paused", "applied": True}
        return {"status": "idle", "applied": False}

    def resume(self, context: str = "default") -> dict:
        controller = self.controllers.get(context)
        if controller is not None and controller.is_running():
            controller.resume()
            return {"status": "running", "applied": True}
        return {"status": "idle", "applied": False}

    # ============================================================
    # STOP
    # ============================================================

    def stop(self, context: str = "default") -> dict:

        with self._lock:

            controller = self.controllers.get(context)

            # ----------------------------------------------------
            # NO CONTROLLER
            # ----------------------------------------------------

            if controller is None:

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

                controller.close()

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

                self.controllers[context] = None

                self.active_intersection_id[context] = None

                self.active_traffic_state_id[context] = None

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

    def stop_all(self) -> None:
        """Tutup SEMUA context (dashboard, digitaltwin, dst) -- dipanggil
        saat backend shutdown supaya tidak ada proses SUMO yang tertinggal
        (bukan cuma context "default")."""
        for context in list(self.controllers.keys()):
            try:
                self.stop(context)
            except SimulationServiceError:
                pass


# ================================================================
# SINGLETON SERVICE
# ================================================================

simulation_service = SimulationService()
