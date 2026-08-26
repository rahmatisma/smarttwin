from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.traffic import ApproachState, TrafficState  # noqa: E402
from app.services.forecast_service import ForecastService  # noqa: E402
from decision_engine.rule_based_engine import RuleBasedEngine  # noqa: E402


def test_approach_allocation_preserves_aggregate_vehicle_forecast(monkeypatch):
    service = ForecastService()
    start = datetime(2026, 8, 15, tzinfo=timezone.utc)
    aggregate = {
        "forecast": [{
            "timestamp": (start + timedelta(seconds=5)).isoformat(),
            "secondsAhead": 5,
            "vehicleCount": 40.0,
            "queueLengthVeh": 20.0,
            "queueLengthMEst": 30.0,
            "densityIndex": 0.8,
        }],
        "model": {},
        "input": {},
    }
    monkeypatch.setattr(service, "predict_records", lambda records: aggregate)
    records = []
    for index in range(12):
        records.append({
            "timestamp": (start + timedelta(seconds=5 * index)).isoformat(),
            "approaches": [
                {"approach": "west", "vehicleCount": 3, "queueLengthVeh": 2, "queueLengthMEst": 4, "densityIndex": 0.3},
                {"approach": "east", "vehicleCount": 1, "queueLengthVeh": 1, "queueLengthMEst": 2, "densityIndex": 0.1},
            ],
        })

    result = service.predict_approach_records(records)
    approaches = result["approachForecasts"][0]["approaches"]

    assert result["allocationMethod"] == "recent-approach-share"
    assert sum(item["vehicleCount"] for item in approaches) == 40.0
    assert next(item for item in approaches if item["approach"] == "west")["vehicleCount"] == 30.0


def test_forecast_can_change_rule_based_priority():
    now = datetime.now(timezone.utc)
    state = TrafficState(
        intersectionId="pingit",
        windowStart=now,
        windowEnd=now,
        approaches=[
            ApproachState(approach="west", volume=20, queueLengthVeh=10, densityIndex=0.6),
            ApproachState(approach="east", volume=5, queueLengthVeh=1, densityIndex=0.1),
        ],
    )
    forecast = {
        "approachForecasts": [{
            "timestamp": now.isoformat(),
            "secondsAhead": 60,
            "approaches": [
                {"approach": "west", "vehicleCount": 1, "queueLengthVeh": 1, "queueLengthMEst": 2, "densityIndex": 0.05},
                {"approach": "east", "vehicleCount": 40, "queueLengthVeh": 25, "queueLengthMEst": 80, "densityIndex": 1.0},
            ],
        }]
    }

    result = RuleBasedEngine().recommend(
        state,
        forecast=forecast,
        forecastWeight=0.8,
    )

    assert result.recommendedPhase == "east"
    assert result.source == "rule-based+forecast"
