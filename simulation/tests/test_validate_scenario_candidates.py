import sys
from pathlib import Path


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
if str(SIMULATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMULATION_ROOT))

from validate_scenario_candidates import aggregate_results, select_representative_records


def _record(state_id, pressure):
    return {
        "trafficState": {
            "id": state_id,
            "windowStart": "2026-08-27T00:00:00+00:00",
            "windowEnd": "2026-08-27T00:00:05+00:00",
        },
        "approaches": [
            {"approach": name, "volume": pressure, "queueLengthVeh": 0}
            for name in ("west", "south", "east", "north")
        ],
    }


def test_select_representative_records_returns_low_middle_high():
    selected = select_representative_records(
        [_record(index, index) for index in range(1, 6)], count=3
    )
    assert [row["trafficState"]["id"] for row in selected] == [1, 3, 5]


def test_aggregate_results_reports_mean_and_sample_stdev():
    rows = [
        {"candidateId": "baseline", "avgDelaySeconds": 10, "avgQueueLengthM": 20, "throughputVeh": 5},
        {"candidateId": "baseline", "avgDelaySeconds": 12, "avgQueueLengthM": 24, "throughputVeh": 7},
    ]
    result = aggregate_results(rows)["baseline"]
    assert result["runs"] == 2
    assert result["meanDelaySeconds"] == 11
    assert result["meanQueueLengthM"] == 22
    assert result["meanThroughputVeh"] == 6
    assert result["stdevDelaySeconds"] > 0
