from pathlib import Path

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)


def test_build_traffic_state_from_csv():
    csv_path = Path(
        "cv/output/smarttwin_traffic_data.csv"
    )

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            window_seconds=5
        )
    )

    states = builder.build_from_csv(csv_path)

    assert len(states) > 0

    state = states[0]

    assert "intersectionId" in state
    assert "windowStart" in state
    assert "windowEnd" in state
    assert "approaches" in state

    assert len(state["approaches"]) == 4

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

        # Speed memang belum tersedia.
        assert approach["avgSpeedKmh"] is None