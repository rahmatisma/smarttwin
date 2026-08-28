from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.routes import digital_twin as route_module
from app.main import app


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

