from app.services.simulation_service import SimulationService


# Smoke test -- cuma memastikan SimulationService bisa diinstansiasi
# dan method-method yang tidak butuh SUMO/TraCI beneran (belum ada
# controller aktif) berperilaku wajar. TIDAK menjalankan SUMO -- itu
# domain test_sumo_adapter.py / run_intersection.py di simulation/.


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

    assert config_file.name == "simpang4_pingit.sumocfg"
    assert config_file.exists(), (
        "Config SUMO tidak ditemukan -- jalankan dari checkout yang "
        "punya simulation/network/simpang4_pingit.sumocfg"
    )
