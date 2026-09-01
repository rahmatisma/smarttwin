import app.services.simulation_service as simulation_service_module
from app.schemas.simulation import SimulationRequest
from app.services.simulation_service import SimulationService


# Smoke test -- cuma memastikan SimulationService bisa diinstansiasi
# dan method-method yang tidak butuh SUMO/TraCI beneran (belum ada
# controller aktif) berperilaku wajar. TIDAK menjalankan SUMO -- itu
# domain test_sumo_adapter.py / run_intersection.py di simulation/.


class _FakeSumoController:
    """Pengganti SumoController asli -- tidak pernah menyentuh SUMO/TraCI
    sungguhan. Dipakai buat menguji logika restart di _ensure_sumo()
    tanpa perlu proses SUMO beneran."""

    def __init__(self, *, config_file, seed, scenario, context="default"):
        self.scenario = scenario
        self.context = context
        self.is_gui = False
        self.closed = False
        self._running = True

    def is_running(self):
        return self._running

    def start(self, *, gui, gui_delay_ms):
        self.is_gui = gui

    def close(self):
        self.closed = True
        self._running = False


class _FakeRunningController:
    """Controller yang SUDAH berjalan sebelum _ensure_sumo() dipanggil --
    simulasi kondisi "SUMO sedang running dengan skenario/mode GUI
    tertentu", persis situasi nyata sebelum user ganti dropdown skenario."""

    def __init__(self, *, is_gui, scenario):
        self.is_gui = is_gui
        self.scenario = scenario
        self.closed = False
        self.paused = False

    def is_running(self):
        return not self.closed

    def close(self):
        self.closed = True

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def get_metrics(self):
        return {}


def test_instantiation_has_no_active_controller():
    service = SimulationService()

    assert service._get_controller("default") is None
    assert service.active_intersection_id.get("default") is None
    assert service.active_traffic_state_id.get("default") is None


def test_status_without_running_sumo():
    service = SimulationService()

    status = service.status()

    assert status["running"] is False
    assert status["intersectionId"] is None
    assert status["trafficStateId"] is None


def test_get_simulation_state_without_running_sumo():
    service = SimulationService()

    state = service.get_simulation_state()

    assert state["running"] is False
    assert state["paused"] is False
    assert state["vehicles"] == []
    assert state["signals"] == []
    assert state["simulationTimeSeconds"] == 0


class _FakeControllerWithLiveMetrics:
    """Controller yang sedang berjalan, dipakai buat menguji field kartu
    statistik Digital Twin (queueLengthVeh/throughputVehPerMin) benar-benar
    ikut ter-expose lewat get_simulation_state(), bukan diam-diam basi lagi
    kalau nanti ada yang refactor SumoController."""

    def __init__(self):
        self.paused = False
        self.active_vehicles_data = []
        self.active_signals_data = []
        self.last_simulation_time = 42.0
        self.detected_vehicle_count = 0
        self.traffic_timestamp = None
        self.active_cycle_plan = None
        self.live_queue_length_veh = 5
        self.live_queue_busiest_approach = "north"
        self.live_total_queue_length_veh = 11
        self.live_avg_delay_seconds = 8.7
        self.live_throughput_veh_per_min = 12.345
        self.live_visible_vehicle_count = 3
        self.live_last_sync_failed_insertions = 2
        self.live_last_sync_failed_by_approach = {"south": 2}

    def is_running(self):
        return True


def test_get_simulation_state_exposes_live_traffic_metrics():
    service = SimulationService()
    service.controllers["default"] = _FakeControllerWithLiveMetrics()

    state = service.get_simulation_state()

    assert state["running"] is True
    assert state["queueLengthVeh"] == 5
    assert state["queueBusiestApproach"] == "north"
    assert state["throughputVehPerMin"] == 12.3
    assert state["avgDelaySeconds"] == 8.7
    assert state["avgQueueLengthVeh"] == 11
    assert state["avgQueueLengthM"] == 77.0  # 11 * METERS_PER_QUEUED_VEHICLE (7.0)
    assert state["los"] == "A"  # calculate_los(8.7) -- di bawah ambang LOS A HCM
    assert state["visibleVehicleCount"] == 3
    assert state["lastSyncFailedInsertions"] == 2
    assert state["lastSyncFailedByApproach"] == {"south": 2}


def test_sync_clock_before_sumo_is_ready_is_a_noop():
    service = SimulationService()

    result = service.sync_clock(12.5)

    assert result == {
        "synced": False,
        "reason": "SUMO belum berjalan.",
        "videoTimeSeconds": 12.5,
    }


def test_stop_without_running_sumo_is_a_noop():
    service = SimulationService()

    result = service.stop()

    assert result["running"] is False
    assert service._get_controller("default") is None


def test_create_adapter_maps_all_four_approaches():
    adapter = SimulationService._create_adapter()

    for approach in ("north", "south", "east", "west"):
        assert approach in adapter.approach_to_edge


def test_get_config_file_points_to_simpang4_pingit():
    config_file = SimulationService._get_config_file()

    assert config_file.name == "simpang4_pingit_live.sumocfg"
    assert config_file.exists(), (
        "Config SUMO tidak ditemukan -- jalankan dari checkout yang "
        "punya simulation/network/simpang4_pingit_live.sumocfg"
    )


def test_ensure_sumo_reuses_controller_when_scenario_changes(monkeypatch):
    # Program TLS bisa diganti lewat TraCI; jangan membuang kendaraan dan
    # simulationTime hanya karena dropdown skenario berubah.
    monkeypatch.setattr(
        simulation_service_module, "SumoController", _FakeSumoController
    )

    service = SimulationService()
    old_controller = _FakeRunningController(is_gui=True, scenario="Baseline")
    service.controllers["default"] = old_controller
    service.active_intersection_id["default"] = "simpang4-pingit"

    request = SimulationRequest(
        intersectionId="simpang4-pingit",
        scenario="Balanced",
        gui=True,
    )

    result = service._ensure_sumo(request)

    assert old_controller.closed is False
    assert result is old_controller
    assert result.scenario == "Balanced"


def test_ensure_sumo_reuses_controller_when_scenario_unchanged(monkeypatch):
    # Kebalikannya -- kalau skenario SAMA dengan yang sedang jalan, jangan
    # restart tanpa perlu (SUMO restart makan waktu ~1-2 detik dan bikin
    # GUI kedip; regresi paling gampang kalau fix di atas ditulis
    # ceroboh jadi "selalu restart").
    monkeypatch.setattr(
        simulation_service_module, "SumoController", _FakeSumoController
    )

    service = SimulationService()
    old_controller = _FakeRunningController(is_gui=True, scenario="Balanced")
    service.controllers["default"] = old_controller
    service.active_intersection_id["default"] = "simpang4-pingit"

    request = SimulationRequest(
        intersectionId="simpang4-pingit",
        scenario="Balanced",
        gui=True,
    )

    result = service._ensure_sumo(request)

    assert old_controller.closed is False
    assert result is old_controller


def test_contexts_are_fully_isolated():
    # Dashboard (live realtime) dan /digitaltwin (sandbox skenario) HARUS
    # jadi 2 instance independen -- pause/stop di satu context tidak boleh
    # menyentuh context lain sama sekali. Ini bug yang dilaporkan user:
    # sebelum diperbaiki, keduanya berbagi SATU controller global.
    service = SimulationService()

    dashboard_controller = _FakeRunningController(is_gui=True, scenario="Traffic Realtime")
    digitaltwin_controller = _FakeRunningController(is_gui=True, scenario="Baseline")

    service.controllers["dashboard"] = dashboard_controller
    service.controllers["digitaltwin"] = digitaltwin_controller

    # Pause di "digitaltwin" TIDAK BOLEH memause "dashboard".
    result = service.pause("digitaltwin")

    assert result == {"status": "paused", "applied": True}
    assert digitaltwin_controller.paused is True
    assert dashboard_controller.paused is False

    # Stop di "digitaltwin" TIDAK BOLEH mematikan "dashboard".
    service.stop("digitaltwin")

    assert digitaltwin_controller.closed is True
    assert dashboard_controller.closed is False
    assert service._get_controller("dashboard") is dashboard_controller
    assert service._get_controller("digitaltwin") is None

    # status()/get_simulation_state() juga tidak boleh saling bocor.
    dashboard_status = service.status("dashboard")
    digitaltwin_status = service.status("digitaltwin")

    assert dashboard_status["running"] is True
    assert digitaltwin_status["running"] is False
