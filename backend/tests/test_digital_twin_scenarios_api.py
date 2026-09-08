from datetime import datetime, timezone
from datetime import timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fastapi.testclient import TestClient

from app.api.routes import digital_twin as route_module
from app.main import app
from app.core.auth import require_operator


def candidate(candidate_id: str, delay: float) -> dict:
    greens = {"north": 30, "east": 25, "south": 40, "west": 20}
    if candidate_id == "aggressive":
        greens["south"] = 41
    elif candidate_id == "balanced":
        greens = {name: round((value + 15) / 2) for name, value in greens.items()}
    green_cycle = sum(greens.values())
    total_cycle = green_cycle + 16
    return {
        "candidateId": candidate_id,
        "phases": [
            {
                "approach": approach,
                "greenSeconds": green,
                "yellowSeconds": 4,
                "redSeconds": total_cycle - green - 4,
                "demandScore": 0.5,
            }
            for approach, green in greens.items()
        ],
        "cycleLengthSeconds": green_cycle,
        "totalCycleSeconds": total_cycle,
        "busiestApproach": "south",
        "avgDelaySeconds": delay,
        "avgQueueLengthM": 35.0,
        "queueLengthVeh": 5,
        "throughputVeh": 12,
        "los": "B",
    }


class FakeCache:
    def __init__(self, row):
        self.row = row

    def get_fresh(self, _intersection_id):
        return self.row


def test_latest_scenarios_returns_stable_three_candidate_contract(monkeypatch):
    row = {
        "intersectionId": "simpang4-pingit",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "candidateId": "balanced",
        "candidates": [
            candidate("baseline", 16.0),
            candidate("aggressive", 15.0),
            candidate("balanced", 14.0),
        ],
    }
    monkeypatch.setattr(route_module, "live_scenario_cache_service", FakeCache(row))

    response = TestClient(app).get(
        "/api/v1/digital-twin/scenarios/latest?intersectionId=simpang4-pingit"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["winnerId"] == "balanced"
    assert [item["candidateId"] for item in payload["candidates"]] == [
        "baseline", "aggressive", "balanced"
    ]
    assert [item["isWinner"] for item in payload["candidates"]] == [False, False, True]
    assert all(len(item["phases"]) == 4 for item in payload["candidates"])


def test_latest_scenarios_handles_missing_or_legacy_cache(monkeypatch):
    monkeypatch.setattr(route_module, "live_scenario_cache_service", FakeCache(None))
    missing = TestClient(app).get("/api/v1/digital-twin/scenarios/latest")
    assert missing.status_code == 200
    assert missing.json()["status"] == "unavailable"
    assert missing.json()["candidates"] == []

    legacy = {
        "intersectionId": "simpang4-pingit",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "candidateId": "baseline",
    }
    monkeypatch.setattr(route_module, "live_scenario_cache_service", FakeCache(legacy))
    response = TestClient(app).get("/api/v1/digital-twin/scenarios/latest")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert "format lama" in response.json()["message"]


def forecast_payload(state_id=42):
    now = datetime.now(timezone.utc)
    candidates = [candidate(name, 10) for name in ("baseline", "aggressive", "balanced")]
    for item in candidates:
        item.update(
            evaluation={"trafficStateId": state_id, "durationSeconds": 60, "completedSteps": 60,
                        "demandSource": "traffic-state-snapshot", "demandHash": "same-demand", "seed": 42},
            finalQueueLengthVehByApproach={arm: 2 for arm in ("north", "east", "south", "west")},
            finalSpeedKmhByApproach={arm: None for arm in ("north", "east", "south", "west")},
        )
    return {"intersectionId": "simpang4-pingit", "status": "completed", "trafficStateId": state_id,
            "inputTimestamp": now.isoformat(), "predictionTimestamp": (now + timedelta(seconds=60)).isoformat(),
            "horizonSeconds": 60, "assumptions": [], "candidates": candidates}


@pytest.fixture
def forecast_client(monkeypatch):
    monkeypatch.setattr(route_module, "forecast_cache", route_module.OrderedDict())
    app.dependency_overrides[require_operator] = lambda: None
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_operator, None)


def test_forecast_endpoint_reuses_all_candidates_without_evaluation_history(monkeypatch, forecast_client):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert Path(command[1]).name == "forecast_snapshot.py"
        state_id = int(command[command.index("--state-id") + 1])
        Path(command[command.index("--output") + 1]).write_text(json.dumps(forecast_payload(state_id)), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(route_module.subprocess, "run", run)
    first = forecast_client.post("/api/v1/digital-twin/forecast", json={"trafficStateId": 42})
    assert first.status_code == 200
    assert first.json()["winnerId"] is None
    assert first.json()["candidates"][0]["finalQueueLengthVehByApproach"]["north"] == 2
    assert forecast_client.post("/api/v1/digital-twin/forecast", json={"trafficStateId": 42}).json() == first.json()
    assert len(calls) == 1
    assert forecast_client.post("/api/v1/digital-twin/forecast", json={"trafficStateId": 43}).status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize("invalid", ["duration", "incomplete", "missing-arm", "different-demand", "wrong-state"])
def test_invalid_projection_is_rejected_and_not_cached(monkeypatch, forecast_client, invalid):
    def run(command, **kwargs):
        payload = forecast_payload(43 if invalid == "wrong-state" else 42)
        item = payload["candidates"][0]
        if invalid == "duration":
            item["evaluation"]["durationSeconds"] = 120
        elif invalid == "incomplete":
            item["evaluation"]["completedSteps"] = 59
        elif invalid == "missing-arm":
            del item["finalQueueLengthVehByApproach"]["north"]
        elif invalid == "different-demand":
            item["evaluation"]["demandHash"] = "different"
        Path(command[command.index("--output") + 1]).write_text(json.dumps(payload), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(route_module.subprocess, "run", run)
    assert forecast_client.post("/api/v1/digital-twin/forecast", json={"trafficStateId": 42}).status_code == 503
    assert not route_module.forecast_cache
    assert not route_module.evaluation_lock.locked()


def test_busy_forecast_is_retryable(forecast_client):
    route_module.evaluation_lock.acquire()
    try:
        assert forecast_client.post("/api/v1/digital-twin/forecast", json={"trafficStateId": 42}).status_code == 409
    finally:
        route_module.evaluation_lock.release()
