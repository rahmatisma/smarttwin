from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.traffic import ApproachState, TrafficState
from app.services.recommendation_service import recommendation_service
from app.services.signal_service import signal_service
from decision_engine.ppo_engine import PPOEngine


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "decision_engine/models/smarttwin_ppo.zip"


def make_state() -> TrafficState:
    now = datetime.now(timezone.utc)
    return TrafficState(
        intersectionId="simpang4-pingit",
        windowStart=now - timedelta(seconds=5),
        windowEnd=now,
        approaches=[
            ApproachState(approach="north", volume=18, queueLengthVeh=7, queueLengthMEst=49, densityIndex=12, avgSpeedKmh=20),
            ApproachState(approach="east", volume=12, queueLengthVeh=4, queueLengthMEst=28, densityIndex=8, avgSpeedKmh=25),
            ApproachState(approach="south", volume=25, queueLengthVeh=10, queueLengthMEst=70, densityIndex=16, avgSpeedKmh=15),
            ApproachState(approach="west", volume=9, queueLengthVeh=2, queueLengthMEst=14, densityIndex=6, avgSpeedKmh=30),
        ],
    )


class FakeTrafficService:
    def __init__(self, state: TrafficState):
        self.state = state

    def get_latest_traffic(self, intersection_id: str, limit: int):
        dumped = self.state.model_dump(mode="json")
        return [{"trafficState": {"windowStart": dumped["windowStart"], "windowEnd": dumped["windowEnd"]},
                 "approaches": dumped["approaches"]}]


class EmptyCache:
    def get_fresh(self, intersection_id: str):
        return None


def configure_endpoint(engine: PPOEngine) -> None:
    state = make_state()
    recommendation_service.traffic_service = FakeTrafficService(state)
    recommendation_service.cache_service = EmptyCache()
    recommendation_service.engine = engine
    # Hindari akses Supabase kedua dari SignalService; tetap gunakan hasil engine
    # yang sama untuk cycle plan empat lengan. cache_service SignalService juga
    # harus di-mock terpisah -- get_cycle_plan() konsultasi cache-nya sendiri
    # (self.cache_service), bukan cuma pakai _cycle_plan yang di-set manual di
    # bawah; kalau cache Supabase asli lagi fresh (worker scenario_worker.py
    # jalan), dia menimpa _cycle_plan ini dan assertion source jadi salah.
    signal_service.cache_service = EmptyCache()
    signal_service._cycle_plan = engine.recommend_cycle(state, currentPhase="north")


def test_real_checkpoint_reaches_recommendation_endpoint():
    assert MODEL.exists(), "Jalankan training PPO terlebih dahulu"
    engine = PPOEngine(model_path=MODEL)
    assert engine.available, engine.load_error
    configure_endpoint(engine)

    response = TestClient(app).post(
        "/recommendation", json={"intersectionId": "simpang4-pingit"}
    )

    assert response.status_code == 200
    payload = response.json()["recommendation"]
    assert payload["source"] == "ppo"
    assert payload["cyclePlan"]["source"] == "ppo"
    assert payload["recommendedPhase"] in {"north", "east", "south", "west"}
    assert 15 <= payload["recommendedGreenSeconds"] <= 60

    status = TestClient(app).get("/recommendation/engine-status")
    assert status.status_code == 200
    assert status.json()["activeEngine"] == "PPOEngine"
    assert status.json()["ppoAvailable"] is True
    assert status.json()["fallbackEnabled"] is True

    direct = TestClient(app).post(
        "/recommendation/engine-test",
        json=make_state().model_dump(mode="json"),
    )
    assert direct.status_code == 200
    assert direct.json()["recommendation"]["source"] == "ppo"
    assert direct.json()["cyclePlan"]["source"] == "ppo"


def test_missing_checkpoint_reaches_rule_based_fallback_endpoint(tmp_path):
    engine = PPOEngine(model_path=tmp_path / "missing.zip")
    assert not engine.available
    configure_endpoint(engine)

    response = TestClient(app).post(
        "/recommendation", json={"intersectionId": "simpang4-pingit"}
    )

    assert response.status_code == 200
    payload = response.json()["recommendation"]
    assert payload["source"] == "ppo-fallback-rule-based"
    assert payload["cyclePlan"]["source"] == "ppo-fallback-rule-based"
