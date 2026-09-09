from types import SimpleNamespace
import pytest

from app.schemas.simulation import SimulationRequest
from app.services.simulation_service import SimulationService
from app.simulation.sumo.sumo_controller import SumoController


class FakeRoute:
    def add(self, _route_id, _edges):
        return None


class FakeVehicle:
    def __init__(self):
        self.active = set()
        self.colors = {}

    def add(self, *, vehID, **_kwargs):
        self.active.add(vehID)

    def remove(self, vehicle_id):
        self.active.discard(vehicle_id)

    def setColor(self, vehicle_id, color):
        self.colors[vehicle_id] = color


def demand(*, stale, count, timestamp):
    return [{
        "approach": "east",
        "targetVehicleCount": count,
        "motorcycleCount": 0,
        "carCount": count,
        "busCount": 0,
        "truckCount": 0,
        "stale": stale,
        "dataTimestamp": timestamp,
    }]


def make_controller():
    controller = SumoController(scenario="Traffic Realtime")
    vehicle = FakeVehicle()
    controller.traci = SimpleNamespace(
        route=FakeRoute(), vehicle=vehicle, TraCIException=RuntimeError,
    )
    return controller, vehicle


def test_history_transition_adds_white_cohort_without_recoloring_live_cars():
    controller, traci_vehicle = make_controller()
    controller.sync_demand(
        demand(stale=False, count=2, timestamp=None),
        traffic_timestamp="2026-09-10T10:00:00+07:00",
    )
    live_ids = set(controller._vehicle_sources)

    controller.sync_demand(
        demand(stale=True, count=3, timestamp="2026-08-15T16:30:00+07:00"),
        traffic_timestamp="2026-09-10T10:00:03+07:00",
    )
    replay_ids = set(controller._vehicle_sources) - live_ids

    assert len(live_ids) == 2
    assert len(replay_ids) == 3
    assert all(controller._vehicle_sources[key]["dataSource"] == "live" for key in live_ids)
    assert all(controller._vehicle_sources[key]["dataSource"] == "replay" for key in replay_ids)
    assert all(controller._vehicle_sources[key]["dataTimestamp"] == "2026-08-15T16:30:00+07:00" for key in replay_ids)

    for key in live_ids | replay_ids:
        controller._color_vehicle_by_next_tls(key)
    assert all(traci_vehicle.colors[key] == (255, 255, 0, 255) for key in live_ids)
    assert all(traci_vehicle.colors[key] == (255, 255, 255, 255) for key in replay_ids)


def test_recovery_keeps_history_white_and_reconciles_live_separately():
    controller, traci_vehicle = make_controller()
    controller.sync_demand(demand(stale=False, count=1, timestamp=None))
    controller.sync_demand(
        demand(stale=True, count=2, timestamp="2026-08-15T16:30:00+07:00")
    )
    replay_ids = {
        key for key, source in controller._vehicle_sources.items()
        if source["dataSource"] == "replay"
    }

    controller.sync_demand(demand(stale=False, count=2, timestamp=None))
    live_ids = {
        key for key, source in controller._vehicle_sources.items()
        if source["dataSource"] == "live"
    }

    assert len(live_ids) == 2
    assert len(replay_ids) == 2
    assert replay_ids <= set(controller._vehicle_sources)
    for key in live_ids | replay_ids:
        controller._color_vehicle_by_next_tls(key)
    assert all(traci_vehicle.colors[key] == (255, 255, 0, 255) for key in live_ids)
    assert all(traci_vehicle.colors[key] == (255, 255, 255, 255) for key in replay_ids)


def test_replenishment_counts_only_current_source_cohort():
    controller, _ = make_controller()
    controller.sync_demand(demand(stale=False, count=2, timestamp=None))
    controller.sync_demand(
        demand(stale=True, count=3, timestamp="2026-08-15T16:30:00+07:00")
    )
    replay_id = next(
        key for key, source in controller._vehicle_sources.items()
        if source["dataSource"] == "replay"
    )
    controller._vehicle_approach.pop(replay_id)
    controller._vehicle_type.pop(replay_id)
    controller._vehicle_sources.pop(replay_id)

    assert controller._replenish_current_demand() == 1
    assert sum(
        source["dataSource"] == "replay"
        for source in controller._vehicle_sources.values()
    ) == 3


def test_run_request_carries_offline_arm_with_its_demand():
    request = SimulationRequest(
        intersectionId="simpang4-pingit",
        approaches=[],
        offlineApproaches=["west"],
    )
    assert request.offlineApproaches == ["west"]


def test_repeated_offline_updates_preserve_failure_start_time():
    service = SimulationService()
    service._update_offline_approaches("dashboard", ["west"])
    started = service.offline_since["dashboard"]["west"]
    service._update_offline_approaches("dashboard", ["WEST"])
    assert service.offline_since["dashboard"]["west"] == started

    service._update_offline_approaches("dashboard", [])
    assert service.offline_approaches["dashboard"] == set()
    assert service.offline_since["dashboard"] == {}


@pytest.mark.parametrize("arm", ["north", "east", "south", "west"])
@pytest.mark.parametrize("cutoff", [300, 900])
def test_replay_loops_only_prefix_before_failure(monkeypatch, arm, cutoff):
    now = [1000.0]
    monkeypatch.setattr("app.services.simulation_service.time.time", lambda: now[0])
    service = SimulationService()
    service._offline_replay_history = SimpleNamespace(
        start=10000.0, end=12700.0, rows={arm: [1]},
        sample=lambda approach, timestamp: {"approach": approach, "time": timestamp},
    )
    service._update_offline_approaches("dashboard", [arm], cutoff)
    assert service._sample_offline_replay(arm, "dashboard")["time"] == 10000
    now[0] += cutoff - 1
    assert service._sample_offline_replay(arm, "dashboard")["time"] == 10000 + cutoff - 1
    service._update_offline_approaches("dashboard", [arm], 1800)
    now[0] += 2
    assert service._sample_offline_replay(arm, "dashboard")["time"] == 10001
    assert service.offline_cutoffs["dashboard"][arm] == cutoff
    now[0] += cutoff * 4
    assert service._sample_offline_replay(arm, "dashboard")["time"] == 10001


def test_each_arm_freezes_its_own_cutoff_and_recovery_resets_it():
    service = SimulationService()
    service._update_offline_approaches("dashboard", ["east"], 300)
    service._update_offline_approaches("dashboard", ["east", "west"], 900)
    assert service.offline_cutoffs["dashboard"] == {"east": 300, "west": 900}
    service._update_offline_approaches("dashboard", ["west"], 1000)
    service._update_offline_approaches("dashboard", ["east", "west"], 1200)
    assert service.offline_cutoffs["dashboard"] == {"east": 1200, "west": 900}
