from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import traffic as traffic_routes


client = TestClient(app)


INTERSECTION_ID = "simpang4-pingit"


def test_health():
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"


def test_get_latest_traffic():
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


def test_get_latest_traffic_contains_approaches():
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


def test_get_invalid_intersection():
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
