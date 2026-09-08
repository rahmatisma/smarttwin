from types import SimpleNamespace

import pytest

from simulation.evaluation_demand import snapshot_population, population_hash
from app.schemas.simulation import SimulationRequest
from app.services.simulation_service import SimulationService


def state():
    return SimpleNamespace(approaches=[SimpleNamespace(approach=arm, carCount=2,
        motorcycleCount=3, truckCount=0, busCount=0, volume=100)
        for arm in ("north", "east", "south", "west")])


def test_population_uses_presence_counts_not_crossing_volume():
    population = snapshot_population(state())
    assert sum(sum(row["counts"].values()) for row in population) == 20
    assert population_hash(population) == population_hash(snapshot_population(state()))


def test_missing_approach_or_count_is_not_zero_filled():
    observation = state()
    observation.approaches.pop()
    with pytest.raises(ValueError):
        snapshot_population(observation)
    observation = state()
    observation.approaches[0].carCount = None
    with pytest.raises(ValueError):
        snapshot_population(observation)


def test_requested_snapshot_id_and_timestamp_are_preserved(monkeypatch):
    from datetime import datetime, timezone
    from app.services import traffic_snapshot
    captured = []
    observation = SimpleNamespace(trafficStateId=42, intersectionId="simpang4-pingit",
                                  windowEnd=datetime(2026, 8, 15, tzinfo=timezone.utc))
    def load(intersection, state_id):
        captured.append((intersection, state_id))
        return observation
    monkeypatch.setattr(traffic_snapshot, "load_snapshot", load)
    service = SimulationService.__new__(SimulationService)
    service.active_intersection_id = {}
    service.active_traffic_state_id = {}
    request = SimulationRequest(intersectionId="simpang4-pingit", trafficStateId=42, context="digitaltwin")
    assert service._build_traffic_state(request) is observation
    assert captured == [("simpang4-pingit", 42)]
    assert request.trafficTimestamp == observation.windowEnd.isoformat()
