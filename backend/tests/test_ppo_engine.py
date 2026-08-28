from __future__ import annotations

from app.schemas.traffic import ApproachState, TrafficState
from decision_engine.engine_factory import create_decision_engine
from decision_engine.ppo_engine import PPOEngine
from decision_engine.rule_based_engine import FIXED_CYCLE_ORDER, RuleBasedEngine


class FakeModel:
    def __init__(self, action):
        self.action = action
        self.last_observation = None

    def predict(self, observation, deterministic=True):
        self.last_observation = observation
        assert deterministic is True
        return self.action, None


def make_state() -> TrafficState:
    return TrafficState(
        intersectionId="simpang4-pingit",
        windowStart="2026-08-15T16:30:00+00:00",
        windowEnd="2026-08-15T16:30:05+00:00",
        approaches=[
            ApproachState(
                approach=approach,
                volume=10 + index,
                carCount=10 + index,
                queueLengthVeh=4 + index,
                queueLengthMEst=20 + index,
                densityIndex=5 + index,
                avgSpeedKmh=25,
            )
            for index, approach in enumerate(FIXED_CYCLE_ORDER)
        ],
    )


def test_observation_has_stable_25_features():
    engine = PPOEngine(model=FakeModel([0, 0, 0, 0, 0]))

    observation = engine.build_observation(
        make_state(), current_phase="east", current_green_seconds=30
    )

    assert len(observation) == 25
    assert observation[20:24] == [0.0, 1.0, 0.0, 0.0]
    assert observation[24] == 0.5
    assert all(0.0 <= value <= 1.0 for value in observation)


def test_ppo_recommends_phase_and_four_green_times():
    # east dipilih; durasi N/E/S/W = 15/20/25/30 detik.
    model = FakeModel([1, 0, 1, 2, 3])
    engine = PPOEngine(model=model)

    recommendation = engine.recommend(make_state())
    cycle = engine.recommend_cycle(make_state())

    assert recommendation.source == "ppo"
    assert recommendation.recommendedPhase == "east"
    assert recommendation.recommendedGreenSeconds == 20
    assert cycle.source == "ppo"
    assert [phase.approach for phase in cycle.phases] == FIXED_CYCLE_ORDER
    assert [phase.greenSeconds for phase in cycle.phases] == [15, 20, 25, 30]
    assert cycle.totalCycleSeconds == 106


def test_invalid_ppo_action_falls_back_to_rule_based():
    engine = PPOEngine(model=FakeModel([99]))

    recommendation = engine.recommend(make_state())
    cycle = engine.recommend_cycle(make_state())

    assert recommendation.source == "ppo-fallback-rule-based"
    assert "PPO fallback" in recommendation.reason
    assert cycle.source == "ppo-fallback-rule-based"
    assert len(cycle.phases) == 4


def test_missing_checkpoint_falls_back_without_crashing(tmp_path):
    engine = PPOEngine(model_path=tmp_path / "missing.zip")

    assert engine.available is False
    assert engine.recommend(make_state()).source == "ppo-fallback-rule-based"


def test_factory_keeps_rule_based_as_default(monkeypatch):
    monkeypatch.delenv("SMARTTWIN_DECISION_ENGINE", raising=False)
    assert isinstance(create_decision_engine(), RuleBasedEngine)


def test_factory_can_enable_ppo_with_injected_model():
    engine = create_decision_engine(mode="ppo", model=FakeModel([0, 0, 0, 0, 0]))
    assert isinstance(engine, PPOEngine)
