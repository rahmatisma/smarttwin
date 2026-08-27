from datetime import datetime, timezone

from app.schemas.traffic import (
    ApproachState,
    TrafficState,
)
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from decision_engine.rule_based_engine import (
    FIXED_CYCLE_ORDER,
    MAX_GREEN_SECONDS,
    MIN_GREEN_SECONDS,
    RuleBasedEngine,
)


def _make_state(**overrides):
    defaults = {
        "north": {"volume": 5, "queueLengthVeh": 2, "densityIndex": 0.2},
        "south": {"volume": 30, "queueLengthVeh": 20, "densityIndex": 1.0},
        "east": {"volume": 10, "queueLengthVeh": 5, "densityIndex": 0.5},
        "west": {"volume": 2, "queueLengthVeh": 0, "densityIndex": 0.1},
    }
    defaults.update(overrides)

    return TrafficState(
        intersectionId="simpang4-pingit",
        windowStart=datetime.now(timezone.utc),
        windowEnd=datetime.now(timezone.utc),
        approaches=[
            ApproachState(approach=name, **fields)
            for name, fields in defaults.items()
        ],
    )


def test_recommend_cycle_returns_four_phases_in_fixed_order():
    engine = RuleBasedEngine()
    state = _make_state()

    plan = engine.recommend_cycle(state, currentPhase="north")

    assert [p.approach for p in plan.phases] == FIXED_CYCLE_ORDER
    assert len(plan.phases) == 4


def test_recommend_cycle_busier_approach_gets_longer_green():
    engine = RuleBasedEngine()
    state = _make_state()

    plan = engine.recommend_cycle(state)

    by_approach = {p.approach: p for p in plan.phases}

    # south sengaja dibuat paling padat, west paling sepi
    assert by_approach["south"].greenSeconds > by_approach["west"].greenSeconds
    assert by_approach["south"].greenSeconds == MAX_GREEN_SECONDS
    assert by_approach["west"].greenSeconds < by_approach["east"].greenSeconds


def test_recommend_cycle_length_is_sum_of_phases():
    engine = RuleBasedEngine()
    state = _make_state()

    plan = engine.recommend_cycle(state)

    assert plan.cycleLengthSeconds == sum(
        p.greenSeconds for p in plan.phases
    )


def test_recommend_cycle_all_within_allowed_range():
    engine = RuleBasedEngine()
    state = _make_state()

    plan = engine.recommend_cycle(state)

    for phase in plan.phases:
        assert MIN_GREEN_SECONDS <= phase.greenSeconds <= MAX_GREEN_SECONDS


def test_recommend_cycle_missing_approach_defaults_to_minimum():
    engine = RuleBasedEngine()

    state = TrafficState(
        intersectionId="simpang4-pingit",
        windowStart=datetime.now(timezone.utc),
        windowEnd=datetime.now(timezone.utc),
        approaches=[
            ApproachState(approach="south", volume=30, queueLengthVeh=20, densityIndex=1.0),
        ],
    )

    plan = engine.recommend_cycle(state)

    by_approach = {p.approach: p for p in plan.phases}

    assert by_approach["north"].greenSeconds == MIN_GREEN_SECONDS
    assert by_approach["north"].demandScore == 0.0
    assert by_approach["south"].greenSeconds == MAX_GREEN_SECONDS


def test_recommend_cycle_current_phase_passthrough():
    engine = RuleBasedEngine()
    state = _make_state()

    plan = engine.recommend_cycle(state, currentPhase="east")

    assert plan.currentPhase == "east"
