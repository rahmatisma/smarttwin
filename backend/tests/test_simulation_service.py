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

    def __init__(self, *, config_file, seed, scenario):
        self.scenario = scenario
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

    def is_running(self):
        return not self.closed

    def close(self):
        self.closed = True


def test_instantiation_has_no_active_controller():
    service = SimulationService()

    assert service.controller is None
    assert service.active_intersection_id is None
    assert service.active_traffic_state_id is None


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


def test_stop_without_running_sumo_is_a_noop():
    service = SimulationService()

    result = service.stop()

    assert result["running"] is False
    assert service.controller is None


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


def test_ensure_sumo_restarts_controller_when_scenario_changes(monkeypatch):
    # Regresi buat bug: ganti skenario (Baseline -> Balanced) sambil
    # simulasi jalan dulu tidak memicu restart sama sekali -- controller
    # lama dipakai ulang apa adanya dan request.scenario yang baru tidak
    # pernah sampai ke SumoController manapun.
    monkeypatch.setattr(
        simulation_service_module, "SumoController", _FakeSumoController
    )

    service = SimulationService()
    old_controller = _FakeRunningController(is_gui=True, scenario="Baseline")
    service.controller = old_controller
    service.active_intersection_id = "simpang4-pingit"

    request = SimulationRequest(
        intersectionId="simpang4-pingit",
        scenario="Balanced",
        gui=True,
    )

    new_controller = service._ensure_sumo(request)

    assert old_controller.closed is True, (
        "Controller lama harus di-close begitu skenario berubah"
    )
    assert new_controller is not old_controller
    assert new_controller.scenario == "Balanced"


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
    service.controller = old_controller
    service.active_intersection_id = "simpang4-pingit"

    request = SimulationRequest(
        intersectionId="simpang4-pingit",
        scenario="Balanced",
        gui=True,
    )

    result = service._ensure_sumo(request)

    assert old_controller.closed is False
    assert result is old_controller
