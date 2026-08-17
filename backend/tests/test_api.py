from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_traffic_latest():
    response = client.get("/api/traffic/latest")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["data"]["intersection_id"] == "intersection_01"


def test_signal_status():
    response = client.get("/api/signal/status")

    assert response.status_code == 200

    data = response.json()

    assert data["intersection_id"] == "intersection_01"


def test_forecast():
    response = client.post(
        "/api/forecast",
        json={
            "intersection_id": "intersection_01",
            "horizon_minutes": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert len(data["predictions"]) == 5


def test_recommendation():
    response = client.post(
        "/api/recommendation",
        json={
            "intersection_id": "intersection_01",
            "simulation_horizon_minutes": 15,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert "recommendation" in data