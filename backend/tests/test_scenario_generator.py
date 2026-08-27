import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

simulation_root = str(Path(project_root) / "simulation")
if simulation_root not in sys.path:
    sys.path.insert(0, simulation_root)

from decision_engine.rule_based_engine import (  # noqa: E402
    ApproachPhase,
    CyclePlan,
    FIXED_CYCLE_ORDER,
    Recommendation,
)
from scenario_generator import (  # noqa: E402
    MAX_GREEN_SECONDS,
    MIN_GREEN_SECONDS,
    AGGRESSIVE_GREEN_INCREMENT_SECONDS,
    calculate_los,
    build_dynamic_tls_logic,
    generate_cycle_candidate_plans,
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


def test_generate_candidate_plans_aggressive_uses_calibrated_increment():
    baseline = _make_baseline(green_seconds=40)

    candidates = {
        c["candidateId"]: c for c in generate_candidate_plans(baseline)
    }

    assert candidates["baseline"]["greenSeconds"] == 40
    assert candidates["aggressive"]["greenSeconds"] == (
        40 + AGGRESSIVE_GREEN_INCREMENT_SECONDS
    )
    assert candidates["balanced"]["greenSeconds"] == round(
        (40 + MIN_GREEN_SECONDS) / 2
    )


def test_generate_candidate_plans_aggressive_clamped_to_max_green():
    # baseline sudah dekat MAX_GREEN_SECONDS -- increment tidak boleh
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


def _baseline_cycle() -> CyclePlan:
    return CyclePlan(
        phases=[
            ApproachPhase(approach="north", greenSeconds=30, demandScore=0.4),
            ApproachPhase(approach="east", greenSeconds=25, demandScore=0.3),
            ApproachPhase(approach="south", greenSeconds=40, demandScore=0.8),
            ApproachPhase(approach="west", greenSeconds=20, demandScore=0.1),
        ],
        cycleLengthSeconds=115,
        currentPhase="north",
        source="rule-based",
    )


def test_generate_full_cycle_candidates_keep_four_approaches():
    candidates = generate_cycle_candidate_plans(_baseline_cycle())
    assert [item["candidateId"] for item in candidates] == [
        "baseline", "aggressive", "balanced"
    ]
    assert all(
        [phase["approach"] for phase in item["phases"]]
        == FIXED_CYCLE_ORDER
        for item in candidates
    )
    for candidate in candidates:
        assert candidate["totalCycleSeconds"] == (
            candidate["cycleLengthSeconds"] + 4 * 4
        )
        for phase in candidate["phases"]:
            assert phase["yellowSeconds"] == 4
            assert phase["redSeconds"] == (
                candidate["totalCycleSeconds"]
                - phase["greenSeconds"]
                - phase["yellowSeconds"]
            )


def test_full_cycle_aggressive_only_extends_busiest_approach():
    candidates = {
        item["candidateId"]: item
        for item in generate_cycle_candidate_plans(_baseline_cycle())
    }
    base = {p["approach"]: p["greenSeconds"] for p in candidates["baseline"]["phases"]}
    aggressive = {
        p["approach"]: p["greenSeconds"]
        for p in candidates["aggressive"]["phases"]
    }
    assert aggressive["south"] == 41
    assert all(
        aggressive[name] == base[name]
        for name in ("west", "east", "north")
    )


def test_dynamic_tls_logic_has_green_and_yellow_for_every_approach():
    candidate = generate_cycle_candidate_plans(_baseline_cycle())[0]
    logic = build_dynamic_tls_logic(candidate)
    assert logic.programID == "smarttwin-baseline"
    assert len(logic.phases) == 8
    assert [round(phase.duration) for phase in logic.phases[::2]] == [
        30, 25, 40, 20
    ]
    assert [round(phase.duration) for phase in logic.phases[1::2]] == [4, 4, 4, 4]


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
