from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import traffic as traffic_routes


client = TestClient(app)


def test_get_traffic_state(monkeypatch):

    payload = {
        "intersectionId": "simpang4-pingit",
        "windowStart": "2026-09-01T00:00:00+00:00",
        "windowEnd": "2026-09-01T00:00:05+00:00",
        "approaches": [
            {
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
            for approach in ("north", "south", "east", "west")
        ],
    }
    latest_state = SimpleNamespace(
        windowEnd=datetime(2026, 9, 1, 0, 0, 5, tzinfo=timezone.utc),
        model_dump=lambda **_kwargs: payload,
    )

    monkeypatch.setattr(
        traffic_routes.TrafficStateBuilder,
        "buildFromSupabase",
        lambda *_args, **_kwargs: [latest_state],
    )

    response = client.get(
        "/api/v1/traffic/live-csv"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True

    data = body["data"]

    assert data is not None, (
        "Belum ada traffic state di Supabase "
        "-- jalankan ingest dulu sebelum test ini."
    )

    # ========================================================
    # TRAFFIC STATE
    # ========================================================

    assert (
        data["intersectionId"]
        == "simpang4-pingit"
    )

    assert "windowStart" in data
    assert "windowEnd" in data
    assert "approaches" in data

    # Simpang 4
    assert len(
        data["approaches"]
    ) == 4

    # ========================================================
    # APPROACH CONTRACT
    # ========================================================

    for approach in data["approaches"]:

        assert "approach" in approach
        assert "volume" in approach
        assert "carCount" in approach
        assert "motorcycleCount" in approach
        assert "busCount" in approach
        assert "truckCount" in approach
        assert "queueLengthVeh" in approach
        assert "queueLengthMEst" in approach
        assert "densityIndex" in approach
        assert "avgSpeedKmh" in approach

        # Speed memang belum tersedia.
        assert (
            approach["avgSpeedKmh"]
            is None
        )
