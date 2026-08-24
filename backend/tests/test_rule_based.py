from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ============================================================
# PATH
# ============================================================

TESTS_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = TESTS_ROOT.parent
PROJECT_ROOT = BACKEND_ROOT.parent


if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ============================================================
# IMPORT
# ============================================================

from app.schemas.traffic import (
    ApproachState,
    TrafficState,
)

from decision_engine.rule_based_engine import (
    RuleBasedEngine,
)


# ============================================================
# HELPER
# ============================================================

def create_approach(
    approach: str,
    volume: int,
    queue: int,
    density: float,
) -> ApproachState:

    return ApproachState(
        approach=approach,
        volume=volume,
        carCount=volume,
        motorcycleCount=0,
        busCount=0,
        truckCount=0,
        queueLengthVeh=queue,
        queueLengthMEst=float(queue),
        densityIndex=density,
        avgSpeedKmh=30.0,
    )


def create_traffic_state(
    approaches: list[ApproachState],
) -> TrafficState:

    return TrafficState(
        intersectionId="simpang4-pingit",
        windowStart="2026-08-15T17:19:15+00:00",
        windowEnd="2026-08-15T17:19:20+00:00",
        approaches=approaches,
    )


# ============================================================
# TEST ENGINE IMPORT
# ============================================================

def test_rule_based_engine_import():

    engine = RuleBasedEngine()

    assert engine is not None


# ============================================================
# TEST DEMAND SCORE
# ============================================================

def test_demand_score():

    engine = RuleBasedEngine()

    approach = create_approach(
        approach="north",
        volume=30,
        queue=20,
        density=1.0,
    )

    score = engine._calculateDemandScore(
        approach
    )

    assert score == pytest.approx(
        1.0
    )


# ============================================================
# TEST GREEN TIME
# ============================================================

def test_green_time_minimum():

    engine = RuleBasedEngine()

    green = engine._calculateGreenTime(
        0.0
    )

    assert green == 15


def test_green_time_maximum():

    engine = RuleBasedEngine()

    green = engine._calculateGreenTime(
        1.0
    )

    assert green == 60


def test_green_time_middle():

    engine = RuleBasedEngine()

    green = engine._calculateGreenTime(
        0.5
    )

    assert green == 38


# ============================================================
# TEST RECOMMENDATION
# ============================================================

def test_recommendation_selects_highest_demand():

    engine = RuleBasedEngine()

    traffic_state = create_traffic_state(
        [
            create_approach(
                approach="north",
                volume=10,
                queue=5,
                density=0.2,
            ),
            create_approach(
                approach="south",
                volume=30,
                queue=20,
                density=1.0,
            ),
            create_approach(
                approach="east",
                volume=5,
                queue=2,
                density=0.1,
            ),
            create_approach(
                approach="west",
                volume=8,
                queue=3,
                density=0.2,
            ),
        ]
    )

    recommendation = engine.recommend(
        state=traffic_state,
        currentGreenSeconds=15,
        currentPhase="south",
    )

    assert (
        recommendation.recommendedPhase
        == "south"
    )

    assert (
        recommendation.recommendedGreenSeconds
        == 60
    )

    assert (
        recommendation.source
        == "rule-based"
    )


# ============================================================
# TEST EMPTY STATE
# ============================================================

def test_empty_traffic_state():

    engine = RuleBasedEngine()

    traffic_state = create_traffic_state(
        []
    )

    with pytest.raises(
        ValueError,
        match="TrafficState tidak memiliki approach",
    ):

        engine.recommend(
            state=traffic_state,
            currentGreenSeconds=15,
            currentPhase="south",
        )