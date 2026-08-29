from datetime import datetime, timedelta, timezone

import app.services.recommendation_service as recommendation_module
from app.schemas.recommendation import RecommendationRequest
from app.services.live_scenario_cache_service import LiveScenarioCacheService
from app.services.recommendation_service import RecommendationService
from decision_engine.rule_based_engine import ApproachPhase, CyclePlan


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, data):
        self.data = data

    def select(self, *_args): return self
    def eq(self, *_args): return self
    def limit(self, *_args): return self
    def execute(self): return _Response(self.data)


class _Supabase:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    def table(self, _name):
        if self.error:
            raise self.error
        return _Query(self.data)


class _TrafficService:
    def get_latest_traffic(self, **_kwargs):
        approaches = [
            {
                "approach": approach,
                "volume": 5,
                "queueLengthVeh": 2,
                "queueLengthMEst": 14,
                "densityIndex": 2,
                "avgSpeedKmh": 20,
            }
            for approach in ("west", "south", "east", "north")
        ]
        return [{
            "trafficState": {
                "windowStart": "2026-08-27T00:00:00+00:00",
                "windowEnd": "2026-08-27T00:00:05+00:00",
            },
            "approaches": approaches,
        }]


class _SignalService:
    def get_cycle_plan(self):
        phases = [
            ApproachPhase(approach=name, greenSeconds=20, demandScore=0.2)
            for name in ("west", "south", "east", "north")
        ]
        return CyclePlan(
            phases=phases,
            cycleLengthSeconds=80,
            currentPhase="north",
            source="rule-based",
        )


def _valid_row(updated_at=None):
    return {
        "intersectionId": "simpang4-pingit",
        "updatedAt": updated_at or datetime.now(timezone.utc).isoformat(),
        "recommendation": {
            "recommendedPhase": "south",
            "recommendedGreenSeconds": 22,
            "currentGreenSeconds": 15,
            "currentPhase": "south",
            "confidence": 0.8,
            "expectedDelayReductionPercent": 3.0,
            "reason": "hasil SUMO",
        },
        "avgDelaySeconds": 13.37,
        "avgQueueLengthM": 35.0,
        "throughputVeh": 9,
        "los": "B",
        "candidateId": "balanced",
    }


def _request(monkeypatch, supabase):
    # Test kontrak fallback harus deterministik dan tidak mengikuti feature
    # flag developer di backend/.env (misalnya mesin lokal sedang mencoba PPO).
    monkeypatch.setenv("SMARTTWIN_DECISION_ENGINE", "rule-based")
    monkeypatch.setattr(recommendation_module, "signal_service", _SignalService())
    monkeypatch.setattr(
        recommendation_module.per_approach_forecast_service,
        "predict_records",
        lambda _records: None,
    )
    service = RecommendationService(
        traffic_service=_TrafficService(),
        cache_service=LiveScenarioCacheService(supabase, max_age_seconds=120),
    )
    return service.get_recommendation(
        RecommendationRequest(intersectionId="simpang4-pingit")
    ).recommendation


def test_fresh_cache_flows_end_to_end_to_recommendation(monkeypatch):
    result = _request(monkeypatch, _Supabase([_valid_row()]))
    assert result.source == "scenario-generator"
    assert result.candidateId == "balanced"
    assert result.avgDelaySeconds == 13.37


def test_stale_cache_falls_back_end_to_end(monkeypatch):
    stale = datetime.now(timezone.utc) - timedelta(minutes=3)
    result = _request(monkeypatch, _Supabase([_valid_row(stale.isoformat())]))
    assert result.source == "rule-based"
    assert result.candidateId is None


def test_corrupt_cache_falls_back_end_to_end(monkeypatch):
    row = _valid_row()
    row["recommendation"] = {"recommendedPhase": "south"}
    result = _request(monkeypatch, _Supabase([row]))
    assert result.source == "rule-based"
    assert result.avgDelaySeconds is None


def test_unavailable_cache_falls_back_end_to_end(monkeypatch):
    result = _request(monkeypatch, _Supabase(error=RuntimeError("offline")))
    assert result.source == "rule-based"
    assert result.candidateId is None
