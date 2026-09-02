from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import traffic as traffic_routes
from app.services.traffic_service import TrafficServiceError


client = TestClient(app)


INTERSECTION_ID = "simpang4-pingit"


def test_health():
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"


def _traffic_state_fixture():
    return {
        "trafficState": {
            "id": 1,
            "intersectionId": 1,
            "windowStart": "2026-09-01T00:00:00+00:00",
            "windowEnd": "2026-09-01T00:00:05+00:00",
        },
        "approaches": [
            {
                "trafficStateId": 1,
                "approachId": index,
                "approach": approach,
                "volume": 1,
                "carCount": 1,
                "motorcycleCount": 0,
                "busCount": 0,
                "truckCount": 0,
                "queueLengthVeh": 0,
                "queueLengthMEst": 0.0,
                "densityIndex": 1.0,
                "avgSpeedKmh": None,
            }
            for index, approach in enumerate(
                ("north", "south", "east", "west"), start=1
            )
        ],
    }


def test_get_latest_traffic(monkeypatch):
    monkeypatch.setattr(
        traffic_routes.traffic_service,
        "get_latest_traffic",
        lambda **_kwargs: [_traffic_state_fixture()],
    )
    response = client.get(
        f"/api/traffic/{INTERSECTION_ID}",
        params={
            "limit": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["intersectionId"] == INTERSECTION_ID
    assert isinstance(data["data"], list)

    assert len(data["data"]) <= 5


def test_get_latest_traffic_contains_approaches(monkeypatch):
    monkeypatch.setattr(
        traffic_routes.traffic_service,
        "get_latest_traffic",
        lambda **_kwargs: [_traffic_state_fixture()],
    )
    response = client.get(
        f"/api/traffic/{INTERSECTION_ID}",
        params={
            "limit": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["data"]) >= 1

    first_state = data["data"][0]

    assert "trafficState" in first_state
    assert "approaches" in first_state

    approaches = first_state["approaches"]

    assert isinstance(
        approaches,
        list,
    )

    assert len(approaches) == 4


def test_get_invalid_intersection(monkeypatch):
    def not_found(**_kwargs):
        raise TrafficServiceError("Intersection tidak ditemukan.")

    monkeypatch.setattr(
        traffic_routes.traffic_service,
        "get_latest_traffic",
        not_found,
    )
    response = client.get(
        "/api/traffic/intersection-tidak-ada",
        params={
            "limit": 5,
        },
    )

    assert response.status_code == 404


def test_get_latest_traffic_returns_controlled_503_on_connection_error(monkeypatch):
    def fail_temporarily(**_kwargs):
        raise RuntimeError("temporary upstream disconnect")

    monkeypatch.setattr(
        traffic_routes.traffic_service,
        "get_latest_traffic",
        fail_temporarily,
    )

    response = client.get(
        f"/api/v1/traffic/{INTERSECTION_ID}",
        params={"limit": 12},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Data traffic sementara tidak tersedia."}
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_live_csv_returns_controlled_503_on_connection_error(monkeypatch):
    def fail_temporarily(*_args, **_kwargs):
        raise RuntimeError("temporary upstream disconnect")

    monkeypatch.setattr(
        traffic_routes.TrafficStateBuilder,
        "buildFromSupabase",
        fail_temporarily,
    )

    response = client.get(
        "/api/v1/traffic/live-csv",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Data traffic sementara tidak tersedia."}
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
