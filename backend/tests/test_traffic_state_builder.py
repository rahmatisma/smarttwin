from pathlib import Path

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
)


def test_builder_reads_csv():

    csv_path = Path(
        "../../cv/output/smarttwin_traffic_data.csv"
    )

    if not csv_path.exists():
        # Test tidak dijalankan jika CSV tidak tersedia
        # pada environment CI.
        return

    builder = TrafficStateBuilder(
        window_seconds=5,
        intersection_id="simpang4-pingit",
    )

    states = builder.build(csv_path)

    assert len(states) > 0

    first_state = states[0]

    assert (
        first_state.intersectionId
        == "simpang4-pingit"
    )

    assert len(first_state.approaches) == 4