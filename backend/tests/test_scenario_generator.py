import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

simulation_root = str(Path(project_root) / "simulation")
if simulation_root not in sys.path:
    sys.path.insert(0, simulation_root)

from decision_engine.rule_based_engine import Recommendation  # noqa: E402
from scenario_generator import (  # noqa: E402
    MAX_GREEN_SECONDS,
    MIN_GREEN_SECONDS,
    calculate_los,
    generate_candidate_plans,
    select_best_scenario,
)


def _make_baseline(green_seconds: int) -> Recommendation:
    return Recommendation(
        recommendedPhase="south",
        recommendedGreenSeconds=green_seconds,
        currentGreenSeconds=15,
        currentPhase="north",
        confidence=0.7,
        expectedDelayReductionPercent=10.0,
        source="rule-based",
        reason="test",
    )


# ============================================================
# GENERATE_CANDIDATE_PLANS -- kotak 7
# ============================================================

def test_generate_candidate_plans_returns_three_candidates_same_approach():
    baseline = _make_baseline(green_seconds=40)

    candidates = generate_candidate_plans(baseline)

    assert len(candidates) == 3
    assert {c["candidateId"] for c in candidates} == {
        "baseline",
        "aggressive",
        "balanced",
    }
    assert all(c["approach"] == "south" for c in candidates)


def test_generate_candidate_plans_aggressive_is_20_percent_higher():
    baseline = _make_baseline(green_seconds=40)

    candidates = {
        c["candidateId"]: c for c in generate_candidate_plans(baseline)
    }

    assert candidates["baseline"]["greenSeconds"] == 40
    assert candidates["aggressive"]["greenSeconds"] == round(40 * 1.2)
    assert candidates["balanced"]["greenSeconds"] == round(
        (40 + MIN_GREEN_SECONDS) / 2
    )


def test_generate_candidate_plans_aggressive_clamped_to_max_green():
    # baseline sudah dekat MAX_GREEN_SECONDS -- +20% tidak boleh
    # melebihi batas atas RuleBasedEngine.
    baseline = _make_baseline(green_seconds=MAX_GREEN_SECONDS - 2)

    candidates = {
        c["candidateId"]: c for c in generate_candidate_plans(baseline)
    }

    assert candidates["aggressive"]["greenSeconds"] <= MAX_GREEN_SECONDS


def test_generate_candidate_plans_all_within_allowed_range():
    baseline = _make_baseline(green_seconds=40)

    for candidate in generate_candidate_plans(baseline):
        assert MIN_GREEN_SECONDS <= candidate["greenSeconds"] <= MAX_GREEN_SECONDS


# ============================================================
# CALCULATE_LOS -- kotak 9
# ============================================================

def test_calculate_los_boundaries():
    assert calculate_los(9.9) == "A"
    assert calculate_los(10.0) == "A"
    assert calculate_los(10.1) == "B"
    assert calculate_los(20.0) == "B"
    assert calculate_los(20.1) == "C"
    assert calculate_los(35.0) == "C"
    assert calculate_los(35.1) == "D"
    assert calculate_los(55.0) == "D"
    assert calculate_los(55.1) == "E"
    assert calculate_los(80.0) == "E"
    assert calculate_los(80.1) == "F"
    assert calculate_los(200.0) == "F"


# ============================================================
# SELECT_BEST_SCENARIO -- kotak 10
# ============================================================

def _result(candidate_id, delay, queue_m, throughput=10):
    return {
        "candidateId": candidate_id,
        "approach": "south",
        "greenSeconds": 30,
        "avgDelaySeconds": delay,
        "avgQueueLengthM": queue_m,
        "queueLengthVeh": round(queue_m / 7.0),
        "throughputVeh": throughput,
        "los": calculate_los(delay),
    }


def test_select_best_scenario_picks_lowest_combined_score():
    results = [
        _result("baseline", delay=30.0, queue_m=50.0),
        _result("aggressive", delay=10.0, queue_m=10.0),
        _result("balanced", delay=40.0, queue_m=60.0),
    ]

    winner = select_best_scenario(results)

    assert winner["candidateId"] == "aggressive"


def test_select_best_scenario_is_deterministic():
    results = [
        _result("baseline", delay=25.0, queue_m=30.0),
        _result("aggressive", delay=15.0, queue_m=45.0),
        _result("balanced", delay=20.0, queue_m=20.0),
    ]

    first = select_best_scenario(results)
    second = select_best_scenario(results)

    assert first["candidateId"] == second["candidateId"]


def test_select_best_scenario_raises_on_empty_list():
    try:
        select_best_scenario([])
        assert False, "seharusnya raise ValueError"
    except ValueError:
        pass
