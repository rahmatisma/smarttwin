from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulation.forecast_client import (  # noqa: E402
    APPROACHES,
    ForecastClient,
    ForecastClientConfig,
    ForecastClientError,
)


def make_history(count: int = 12, *, gap_at: int | None = None):
    start = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)
    records = []
    offset = 0
    for index in range(count):
        if gap_at is not None and index == gap_at:
            offset += 5
        timestamp = start + timedelta(seconds=(index * 5) + offset)
        records.append(
            {
                "trafficState": {
                    "windowStart": (timestamp - timedelta(seconds=5)).isoformat(),
                    "windowEnd": timestamp.isoformat(),
                },
                "approaches": [
                    {
                        "approach": approach,
                        "volume": index + approach_index + 1,
                        "queueLengthVeh": index,
                        "queueLengthMEst": index * 2.5,
                        "densityIndex": index / 20,
                    }
                    for approach_index, approach in enumerate(APPROACHES)
                ],
            }
        )
    # Endpoint Supabase mengembalikan terbaru lebih dulu.
    return list(reversed(records))


def make_forecast(*, source: str = "lstm-per-approach", fallback=False):
    start = datetime(2026, 8, 26, 8, 1, 0, tzinfo=timezone.utc)
    return {
        "forecastSource": source,
        "fallbackUsed": fallback,
        "approachForecasts": [
            {
                "timestamp": (start + timedelta(seconds=step * 5)).isoformat(),
                "secondsAhead": step * 5,
                "approaches": [
                    {
                        "approach": approach,
                        "vehicleCount": 10.0,
                        "queueLengthVeh": 3.0,
                        "queueLengthMEst": 12.0,
                        "densityIndex": 0.4,
                    }
                    for approach in APPROACHES
                ],
            }
            for step in range(1, 13)
        ],
    }


def test_build_records_sorts_history_and_maps_volume_to_vehicle_count():
    records = ForecastClient.build_forecast_records(make_history())

    assert len(records) == 12
    assert records[0]["timestamp"] < records[-1]["timestamp"]
    assert records[0]["approaches"][0]["approach"] == "west"
    assert records[0]["approaches"][0]["vehicleCount"] == 1
    assert records[-1]["approaches"][0]["densityIndex"] == pytest.approx(
        (11 / 20) / 33.0
    )


def test_build_records_rejects_history_with_gap():
    with pytest.raises(ForecastClientError, match="interval tepat lima detik"):
        ForecastClient.build_forecast_records(make_history(gap_at=6))


def test_build_records_rejects_incomplete_approach():
    history = make_history()
    history[0]["approaches"] = history[0]["approaches"][:-1]

    with pytest.raises(ForecastClientError, match="Dibutuhkan 12 TrafficState"):
        ForecastClient.build_forecast_records(history)


def test_live_forecast_calls_traffic_then_forecast_endpoint():
    calls = []
    history = make_history()
    expected = make_forecast()

    def transport(method, url, payload, timeout):
        calls.append((method, url, payload, timeout))
        if method == "GET":
            return {"success": True, "data": history}
        return expected

    client = ForecastClient(
        ForecastClientConfig(backend_url="http://backend.test", timeout_seconds=3),
        transport=transport,
    )
    result = client.get_live_forecast()

    assert result is expected
    assert client.last_error is None
    assert calls[0][0] == "GET"
    assert "/api/v1/traffic/simpang4-pingit?limit=24" in calls[0][1]
    assert calls[1][0] == "POST"
    assert calls[1][1].endswith("/api/forecast/approaches")
    assert len(calls[1][2]["records"]) == 12


def test_aggregate_fallback_response_is_still_accepted():
    fallback = make_forecast(
        source="aggregate-recent-share-fallback",
        fallback=True,
    )

    def transport(method, _url, _payload, _timeout):
        if method == "GET":
            return {"success": True, "data": make_history()}
        return fallback

    result = ForecastClient(transport=transport).get_live_forecast()

    assert result is not None
    assert result["fallbackUsed"] is True
    assert result["forecastSource"] == "aggregate-recent-share-fallback"


def test_network_failure_returns_none_for_safe_sumo_fallback():
    def transport(_method, _url, _payload, _timeout):
        raise ForecastClientError("backend mati")

    client = ForecastClient(transport=transport)

    assert client.get_live_forecast() is None
    assert client.last_error == "backend mati"


def test_invalid_forecast_returns_none_for_safe_sumo_fallback():
    def transport(method, _url, _payload, _timeout):
        if method == "GET":
            return {"success": True, "data": make_history()}
        return {"approachForecasts": []}

    client = ForecastClient(transport=transport)

    assert client.get_live_forecast() is None
    assert "tepat 12 horizon" in client.last_error


def test_runner_passes_forecast_and_weight_to_scenario_engine(monkeypatch):
    simulation_root = PROJECT_ROOT / "simulation"
    if str(simulation_root) not in sys.path:
        sys.path.insert(0, str(simulation_root))

    import run_tls_simulation as runner

    captured = {}
    recommendation = SimpleNamespace(
        recommendedPhase="west",
        recommendedGreenSeconds=30,
        currentGreenSeconds=15,
        confidence=0.8,
        expectedDelayReductionPercent=10.0,
        source="rule-based+forecast",
        reason="forecast integration test",
        id=None,
    )

    class ScenarioEngineStub:
        def __init__(self, **kwargs):
            captured["constructor"] = kwargs
            self.last_cycle_plan = None

        def recommend_full_cycle(self, **kwargs):
            captured["recommend_full_cycle"] = kwargs
            return recommendation

    monkeypatch.setattr(runner, "ScenarioEngine", ScenarioEngineStub)
    forecast = make_forecast()
    traffic_state = object()

    result, phase_plan = runner.createDecision(
        traffic_state,
        forecast=forecast,
        forecastWeight=0.3,
    )

    assert result is recommendation
    assert captured["recommend_full_cycle"]["state"] is traffic_state
    assert captured["recommend_full_cycle"]["forecast"] is forecast
    assert captured["recommend_full_cycle"]["forecastWeight"] == 0.3
    assert phase_plan["source"] == "rule-based+forecast"
    assert phase_plan["forecastApplied"] is True
    assert phase_plan["forecastWeight"] == 0.3
    assert phase_plan["forecastSource"] == "lstm-per-approach"
