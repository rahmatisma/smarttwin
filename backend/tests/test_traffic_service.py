from pathlib import Path

from app.services.traffic_service import TrafficService


def test_get_latest_state():

    project_root = (
        Path(__file__)
        .resolve()
        .parents[2]
    )

    csv_path = (
        project_root
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )

    assert csv_path.exists()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = (
        service.get_latest_state()
    )

    assert state is not None

    assert (
        state["intersectionId"]
        == "simpang4-pingit"
    )

    assert len(
        state["approaches"]
    ) == 4

    for approach in state["approaches"]:

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

        assert approach["volume"] >= 0
        assert approach["queueLengthVeh"] >= 0
        assert approach["queueLengthMEst"] >= 0
        assert approach["densityIndex"] >= 0

        # CV belum menyediakan speed.
        assert (
            approach["avgSpeedKmh"]
            is None
        )