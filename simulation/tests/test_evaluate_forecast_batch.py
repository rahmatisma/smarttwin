from datetime import datetime, timedelta, timezone

from simulation.evaluate_forecast_batch import (
    _summary,
    contiguous_histories,
    evenly_spaced,
)


def _record(index):
    end = datetime(2026, 8, 29, tzinfo=timezone.utc) + timedelta(seconds=index * 5)
    return {
        "trafficState": {"windowStart": (end - timedelta(seconds=5)).isoformat(), "windowEnd": end.isoformat()},
        "approaches": [],
    }


def test_contiguous_histories_reject_gap_and_keep_valid_windows():
    records = [_record(index) for index in range(13)]
    assert len(contiguous_histories(records)) == 2
    records.pop(6)
    assert contiguous_histories(records) == []


def test_evenly_spaced_keeps_requested_coverage():
    assert evenly_spaced(list(range(20)), 3) == [0, 10, 19]


def test_summary_does_not_hide_throughput_regression():
    rows = [
        {"delta": {"avgDelaySeconds": -1.0, "avgQueueLengthM": -2.0, "throughputVeh": -1}},
        {"delta": {"avgDelaySeconds": 1.0, "avgQueueLengthM": -1.0, "throughputVeh": 2}},
    ]
    result = _summary(rows)
    assert result["delayImproved"] == 1
    assert result["queueImproved"] == 2
    assert result["throughputImproved"] == 1
    assert result["allThreeImproved"] == 0
