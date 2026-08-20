from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_traffic_state():

    response = client.get(
        "/api/v1/traffic/state"
    )

    assert response.status_code == 200

    data = response.json()

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