from __future__ import annotations

import inspect
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.pipeline.traffic_state_builder import TrafficStateBuilder
from app.services.supabase_client import get_supabase
from app.services.replay_demo_history import RecordedHistory
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

        # Berubah setiap proses backend dimulai ulang. Frontend memakai ID ini
        # untuk membedakan sesi kamera lama dari sesi backend yang baru.
        self.instance_id = uuid.uuid4().hex

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
        self.active_scenario: dict[str, str | None] = {}
        self.active_seed: dict[str, int | None] = {}
        self.started_at: dict[str, str | None] = {}

        # Lengan (approach) yang lagi ditandai "CCTV mati" di dashboard --
        # dikirim lewat /sync-clock (lihat sync_clock() di bawah). Disimpan
        # per context supaya sandbox /digitaltwin tidak ikut kepengaruh
        # simulasi mati kamera dashboard. Dipakai run() (lihat "3.5 LENGAN
        # OFFLINE" di bawah) buat mengganti demand lengan itu dengan data
        # historis yang diputar ulang, bukan data live.
        self.offline_approaches: dict[str, set[str]] = {}

        # Kapan (time.time(), wall-clock) tiap lengan MULAI offline, per
        # context -- dipakai buat menghitung posisi putar-ulang data historis
        # yang terus maju & melingkar (modulo) selama lengan itu masih
        # offline. Lihat sync_clock() (yang mengisi ini) dan
        # _sample_offline_replay() (yang memakainya).
        self.offline_since: dict[str, dict[str, float]] = {}

        # Riwayat CSV YOLO (cv/output/snapshot_zona.csv) dipakai sebagai
        # sumber "data lama" untuk lengan yang offline -- SAMA PERSIS file
        # yang dipakai replay_demo_history.py punya sistem demo terpisah
        # (replay-demo, port 8001), supaya tidak perlu duplikasi data. Lazy-
        # load sekali (bisa mahal baca CSV-nya) lewat _get_offline_replay_history().
        # None kalau file belum pernah berhasil dimuat -- lihat method itu
        # soal fallback-nya.
        self._offline_replay_history: RecordedHistory | None = None
        self._offline_replay_history_failed = False

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

        from app.services.traffic_snapshot import load_snapshot
        try:
            traffic_state = load_snapshot(request.intersectionId, request.trafficStateId)
        except Exception as exc:
            raise SimulationServiceError(f"TrafficState tidak tersedia: {exc}") from exc
        self.active_intersection_id[request.context] = traffic_state.intersectionId
        self.active_traffic_state_id[request.context] = traffic_state.trafficStateId
        request.trafficTimestamp = traffic_state.windowEnd.isoformat()
        return traffic_state
    # ============================================================

    def _ensure_sumo(
        self,
        request: SimulationRequest,
    ) -> SumoController:

        context = request.context

        with self._lock:

            controller = self.controllers.get(context)
            if context == "digitaltwin" and controller is not None:
                controller.close()
                self.controllers[context] = None
                controller = None

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
            self.active_scenario[context] = request.scenario
            self.active_seed[context] = request.seed
            self.started_at[context] = datetime.now(timezone.utc).isoformat()

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
                        for item in generate_cycle_candidate_plans(
                            baseline_cycle, traffic_state=traffic_state
                        )
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
                    controller.close()
                    self.controllers[request.context] = None
                    raise SimulationServiceError(f"Gagal menerapkan skenario: {exc}") from exc

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

            # ====================================================
            # 3.5 LENGAN "CCTV MATI" -> PUTAR DATA HISTORIS (Step 6+)
            # ====================================================
            # Approach yang ditandai offline lewat /sync-clock (lihat
            # sync_clock() + self.offline_approaches) demand-nya DIGANTI
            # data historis dari cv/output/snapshot_zona.csv, BUKAN
            # dikosongkan ke 0 -- supaya lengan itu tetap kelihatan ada lalu
            # lintas (data lama diputar ulang terus, melingkar), bukan
            # langsung sepi. Item ditandai "stale"+"dataTimestamp" -- itu
            # kontrak yang sudah dibaca sync_demand() (lihat sumo_controller.py):
            # kendaraannya otomatis diwarnai putih, dan karena targetnya
            # tetap ada isinya (bukan 0), sync_demand() tetap menambah/
            # mengurangi kendaraan mengikuti angka historis itu setiap
            # polling -- bukan sekadar membekukan yang sudah ada.
            # Kalau CSV riwayatnya kebetulan tidak tersedia (mis. belum
            # pernah ada run CV di mesin ini), jatuh balik ke dikosongkan
            # ke 0 seperti sebelumnya -- approach lain di list yang sama
            # tetap apa adanya.
            offline_approaches = self.offline_approaches.get(request.context, set())
            if offline_approaches and demand:
                for item in demand:
                    approach = str(item.get("approach", "")).lower().strip()
                    if approach not in offline_approaches:
                        continue

                    row = self._sample_offline_replay(approach, request.context)
                    if row is not None:
                        counts = row["counts"]
                        item["motorcycleCount"] = counts.get("motorcycle", 0)
                        item["carCount"] = counts.get("car", 0)
                        item["busCount"] = counts.get("bus", 0)
                        item["truckCount"] = counts.get("truck", 0)
                        item["targetVehicleCount"] = sum(counts.values())
                        item["volume"] = item["targetVehicleCount"]
                        item["stale"] = True
                        item["dataTimestamp"] = row["timestamp"]
                    else:
                        for field in (
                            "targetVehicleCount",
                            "motorcycleCount",
                            "carCount",
                            "busCount",
                            "truckCount",
                            "volume",
                        ):
                            if field in item:
                                item[field] = 0

            print()
            print("=" * 70)
            print("SUMO DEMAND")
            print("=" * 70)

            if offline_approaches:
                print(f"Lengan offline (dikosongkan): {sorted(offline_approaches)}")

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
                # PENTING: "volume" dari adapter.to_demand() itu hasil
                # hitung CROSSING (kendaraan yang melintasi garis, dari
                # crossing_simpang.csv) -- BUKAN jumlah kendaraan yang
                # sedang ada di lengan itu sekarang. Sering bernilai 0
                # walau lenganNya jelas ada kendaraan, karena crossing
                # dan kehadiran-di-zona itu dua pengukuran yang beda
                # (lihat cv_csv_bridge.py). Kalau "volume" dipakai
                # sebagai target, sync_demand() menghapus SEMUA
                # kendaraan yang ada tiap kali baris data terbaru
                # kebetulan volume=0 -- persis bug "ganti skenario,
                # kendaraan hilang total" yang ditemukan 6 September.
                # targetVehicleCount yang benar adalah jumlah kendaraan
                # per JENIS (motorcycleCount+carCount+busCount+truckCount),
                # dari snapshot_zona.csv -- itu yang mengukur "berapa
                # kendaraan ada di lengan sekarang", bukan arus lintasan.
                try:

                    sync_ready_demand = [
                        {
                            **item,
                            "targetVehicleCount": (
                                int(item.get("motorcycleCount", 0) or 0)
                                + int(item.get("carCount", 0) or 0)
                                + int(item.get("busCount", 0) or 0)
                                + int(item.get("truckCount", 0) or 0)
                            ),
                        }
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
                    "scenario": self.active_scenario.get(context),
                    "seed": self.active_seed.get(context),
                    "startedAt": self.started_at.get(context),
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
                "scenario": self.active_scenario.get(context),
                "seed": self.active_seed.get(context),
                "startedAt": self.started_at.get(context),
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
        _stale: dict[str, Any] = dict(getattr(controller, "stale_approaches", {}) or {})
        if controller is None or not controller.is_running():
            return {
                "backendInstanceId": self.instance_id,
                "running": False,
                "lastError": getattr(controller, "last_error", None),
                "paused": False,
                "vehicles": [],
                "signals": [],
                "simulationTimeSeconds": 0,
                "scenario": self.active_scenario.get(context),
                "seed": self.active_seed.get(context),
                "startedAt": self.started_at.get(context),
            }
        return {
            "backendInstanceId": self.instance_id,
            "running": True,
            "lastError": getattr(controller, "last_error", None),
            "paused": controller.paused,
            "vehicles": list(controller.active_vehicles_data),
            "visibleVehicleCount": controller.live_visible_vehicle_count,
            "lastSyncFailedInsertions": controller.live_last_sync_failed_insertions,
            "lastSyncFailedByApproach": controller.live_last_sync_failed_by_approach,
            "signals": list(controller.active_signals_data),
            "simulationTimeSeconds": controller.get_display_time(),
            "detectedVehicles": controller.detected_vehicle_count,
            "trafficTimestamp": controller.traffic_timestamp,
            "trafficStateId": self.active_traffic_state_id.get(context),
            # Lengan yang CCTV-nya mati -> demand-nya data lama yang diputar
            # ulang. {approach: isoTimestamp|null}. Frontend memakai ini untuk
            # menandai lengan tsb (banner + badge + kendaraan biru di SUMO).
            "staleApproaches": dict(_stale),
            "replayApproaches": sorted(_stale.keys()),
            "replaySince": next((ts for ts in _stale.values() if ts), None),
            "dataMode": (
                "replay"
                if _stale
                else "timestamped-observation"
                if controller.traffic_timestamp
                else "unknown"
            ),
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
            # Rincian per lengan -- lihat
            # catatan-pribadi/temuan-data-tersembunyi-per-lengan.md. Rata-
            # rata simpang di atas bisa menyembunyikan satu lengan yang
            # sebenarnya masih buruk.
            "delayByApproachSeconds": controller.live_delay_by_approach_seconds,
            "losByApproach": controller.live_los_by_approach,
            "queueLengthVehByApproach": controller.live_queue_length_veh_by_approach,
            "throughputVehPerMinByApproach": (
                controller.live_throughput_veh_per_min_by_approach
            ),
            "scenario": self.active_scenario.get(context),
            "seed": self.active_seed.get(context),
            "startedAt": self.started_at.get(context),
        }

    def set_stream_view(self, mode: str, context: str = "default") -> dict[str, Any]:
        """Ubah crop renderer tanpa me-restart atau mengganggu waktu simulasi."""
        if mode not in {"compact", "wide"}:
            raise SimulationServiceError("Mode tampilan harus 'compact' atau 'wide'.")

        controller = self.controllers.get(context)
        if controller is None or not controller.is_running():
            raise SimulationServiceError("Simulasi SUMO belum berjalan.")

        try:
            controller.set_stream_view(wide=mode == "wide")
        except Exception as exc:
            raise SimulationServiceError(str(exc)) from exc

        return {"context": context, "mode": mode}

    def set_stale_approaches(
        self,
        approaches: dict[str, str | None],
        context: str = "default",
    ) -> dict[str, Any]:
        """Tandai lengan yang CCTV-nya mati (demand diisi data lama).

        Dipakai oleh logic deteksi CCTV: begitu satu kamera tidak mengirim
        data lagi, lengan itu ditandai di sini supaya SUMO-GUI mewarnai
        kendaraannya biru dan dashboard menampilkan penanda. Kirim dict
        kosong untuk mengembalikan semua lengan ke status live.
        """
        controller = self.controllers.get(context)
        if controller is None or not controller.is_running():
            raise SimulationServiceError("Simulasi SUMO belum berjalan.")
        try:
            controller.set_stale_approaches(approaches)
        except Exception as exc:
            raise SimulationServiceError(str(exc)) from exc
        return {
            "context": context,
            "staleApproaches": dict(controller.stale_approaches),
        }

    def _get_offline_replay_history(self) -> RecordedHistory | None:
        """Muat cv/output/snapshot_zona.csv sekali (lazy) sebagai sumber
        data historis untuk lengan yang offline. None kalau gagal (mis. file
        belum ada) -- caller (run()) jatuh balik ke kosongkan demand apa
        adanya, bukan crash.
        """
        if self._offline_replay_history is not None:
            return self._offline_replay_history
        if self._offline_replay_history_failed:
            return None
        csv_path = (
            Path(__file__).resolve().parents[3]
            / "cv"
            / "output"
            / "snapshot_zona.csv"
        )
        try:
            self._offline_replay_history = RecordedHistory(csv_path)
        except Exception as exc:  # noqa: BLE001
            print(f"[offline-replay] Gagal memuat {csv_path}: {exc}")
            self._offline_replay_history_failed = True
            return None
        return self._offline_replay_history

    def _sample_offline_replay(
        self, approach: str, context: str
    ) -> dict[str, Any] | None:
        """Ambil satu baris data historis untuk `approach`, terus maju &
        melingkar (modulo total durasi rekaman) sejak lengan itu MULAI
        offline -- efeknya "muter data lama terus" selama masih offline,
        bukan cuma sekali ambil snapshot lalu diam. None kalau riwayat
        tidak tersedia/lengan ini tidak ada di CSV.
        """
        history = self._get_offline_replay_history()
        if history is None or approach not in history.rows:
            return None

        started_at = self.offline_since.get(context, {}).get(approach)
        if started_at is None:
            started_at = time.time()
            self.offline_since.setdefault(context, {})[approach] = started_at

        duration = max(1.0, history.end - history.start)
        elapsed = time.time() - started_at
        virtual_timestamp = history.start + (elapsed % duration)

        return history.sample(approach, virtual_timestamp)

    def sync_clock(
        self,
        video_time_seconds: float,
        video_duration_seconds: float | None = None,
        context: str = "default",
        offline_approaches: list[str] | None = None,
    ) -> dict[str, Any]:
        """Camera Feed adalah clock utama untuk fase lampu realtime.

        offline_approaches: lengan yang lagi ditandai "CCTV mati" di
        dashboard (simulasi manual). Disimpan TERLEPAS dari status SUMO
        (bisa saja SUMO belum jalan waktu dashboard mengirim status ini) --
        supaya begitu SUMO dimulai/direstart, status offline yang sudah
        ada tidak hilang begitu saja.
        """
        if offline_approaches is not None:
            new_offline = {
                approach.lower().strip() for approach in offline_approaches
            }
            if new_offline != self.offline_approaches.get(context, set()):
                print(
                    f"[sync_clock] context={context!r} "
                    f"offlineApproaches={sorted(new_offline) or '(kosong)'}"
                )
            self.offline_approaches[context] = new_offline

            # Catat/hapus "sejak kapan" per lengan -- dipakai
            # _sample_offline_replay() buat memutar data lama terus maju,
            # bukan diam di satu titik. setdefault: JANGAN reset waktu mulai
            # kalau lengan itu memang sudah offline dari sebelumnya (video
            # terus dikirim tiap detik lewat heartbeat, bukan cuma sekali
            # saat toggle).
            since_map = self.offline_since.setdefault(context, {})
            now = time.time()
            for approach in new_offline:
                since_map.setdefault(approach, now)
            for approach in list(since_map.keys()):
                if approach not in new_offline:
                    since_map.pop(approach, None)

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
            return controller.sync_signal_clock(video_time_seconds, video_duration_seconds)
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
        self.active_scenario[context] = scenario
        return {
            "applied": True,
            "scenario": scenario,
            "paused": controller.paused,
            "simulationTimeSeconds": controller.get_display_time(),
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

                self.active_scenario[context] = None

                self.active_seed[context] = None

                self.started_at[context] = None

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
