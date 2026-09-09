from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.replay_demo_service import ReplayDemoController
from app.simulation.sumo.sumo_controller import SumoController


@pytest.fixture
def controller(monkeypatch):
    colors = {}
    controller = ReplayDemoController()
    controller.traci = SimpleNamespace(
        vehicle=SimpleNamespace(setColor=lambda key, value: colors.update({key: value})),
        TraCIException=RuntimeError,
    )

    def insert(self, vehicle_type, approach):
        key = f"smart_{vehicle_type}_{approach}_{self._vehicle_counter}"
        self._vehicle_counter += 1
        self._vehicle_approach[key] = approach
        self._vehicle_type[key] = vehicle_type
        return True

    monkeypatch.setattr(SumoController, "add_vehicle", insert)
    start = datetime.now(timezone.utc).timestamp()
    def row(timestamp, count):
        return {"time": timestamp, "timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(), "counts": {"car": count}}
    controller.history = SimpleNamespace(start=start - 300, end=start + 3000, playback_start=start,
        sample=lambda arm, timestamp: row(timestamp, 8),
        history_window=lambda arm, cutoff, age: [row(cutoff - age, 12)])
    controller.set_sources([], 300)
    return controller, colors


def test_two_offline_arms_only_new_historical_vehicles_turn_white(controller):
    sim, colors = controller
    original_ids = set(sim.vehicle_sources)
    sim.set_sources(["east", "south"], 86400)
    new_ids = set(sim.vehicle_sources) - original_ids
    assert len(new_ids) == 24
    assert {sim.vehicle_sources[key]["approach"] for key in new_ids} == {"east", "south"}
    for key in original_ids:
        sim._color_vehicle_by_next_tls(key)
        assert colors[key] == (255, 255, 0, 255)
        assert sim.vehicle_sources[key]["dataSource"] == "live"
    for key in new_ids:
        assert colors[key] == (255, 255, 255, 255)
        source = sim.vehicle_sources[key]
        assert source["dataSource"] == "replay"
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(source["dataTimestamp"])).total_seconds()
        assert 86399 < age < 86410


def test_recovery_preserves_white_vehicles_but_new_insertions_are_live(controller):
    sim, colors = controller
    sim.set_sources(["east"], 300)
    historical = {key: value.copy() for key, value in sim.vehicle_sources.items() if value["dataSource"] == "replay"}
    sim.set_sources([], 300)
    for key, source in historical.items():
        sim._color_vehicle_by_next_tls(key)
        assert sim.vehicle_sources[key] == source
        assert colors[key] == (255, 255, 255, 255)
    assert sim.add_vehicle("car", "east")
    last_id = f"smart_car_east_{sim._vehicle_counter - 1}"
    assert sim.vehicle_sources[last_id]["dataSource"] == "live"
    assert colors[last_id] == (255, 255, 0, 255)


def test_replenishment_keeps_history_running_and_cleans_arrivals(controller):
    sim, _ = controller
    sim.set_sources(["east", "west"], 900)
    previous = set(sim.vehicle_sources)
    sim._vehicle_approach.clear()
    sim._vehicle_type.clear()
    sim._replenish_current_demand()
    assert previous.isdisjoint(sim.vehicle_sources)
    assert len(sim.vehicle_sources) == 40
    assert all(value["dataSource"] == ("replay" if value["approach"] in ("east", "west") else "live") for value in sim.vehicle_sources.values())


def test_changing_history_time_does_not_rewrite_existing_provenance(controller):
    sim, _ = controller
    sim.set_sources(["east"], 86400)
    previous = {key: value.copy() for key, value in sim.vehicle_sources.items()}
    sim.set_sources(["east"], 300)
    assert sim.vehicle_sources == previous
    sim.add_vehicle("car", "east")
    new = sim.vehicle_sources[f"smart_car_east_{sim._vehicle_counter - 1}"]
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(new["dataTimestamp"])).total_seconds()
    assert 299 < age < 310


def test_explicit_trigger_adds_history_even_if_arm_already_offline(controller):
    sim, colors = controller
    sim.set_sources(["east"], 300)
    before = set(sim.vehicle_sources)
    sim.set_sources(["east"], 300, trigger=True)
    added = set(sim.vehicle_sources) - before
    assert added and sim.triggered_count == len(added)
    assert all(colors[key] == (255, 255, 255, 255) for key in added)


def test_no_history_does_not_fabricate_white_vehicles(controller):
    sim, _ = controller
    sim.history.history_window = lambda *args: []
    before = set(sim.vehicle_sources)
    sim.set_sources(["east"], 300, trigger=True)
    assert set(sim.vehicle_sources) == before
    assert sim.sources["east"]["dataTimestamp"] is None
    assert sim.current_demand["east"] == {}
    assert sim.triggered_count == 0


def test_recording_window_never_reads_future_or_yesterday(tmp_path):
    from app.services.replay_demo_history import RecordedHistory
    path = tmp_path / "snapshots.csv"
    lines = ["timestamp,lengan,mobil_di_zona,motor_di_zona,truk_di_zona,bus_di_zona"]
    for minute in range(3):
        for arm in ["timur", "selatan", "barat", "simpang_tengah"]:
            lines.append(f"2026-08-15 16:0{minute}:00,{arm},2,0,0,0")
    path.write_text("\n".join(lines))
    history = RecordedHistory(path)
    cutoff = history.start + 60
    window = history.history_window("east", cutoff, 300)
    assert len(window) == 1
    assert window[0]["time"] == history.start
    assert history.history_window("east", history.start, 300) == []
    assert window[0]["timestamp"].endswith("+07:00")
