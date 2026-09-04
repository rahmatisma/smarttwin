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
    PKJI_DS_THRESHOLD,
    PKJI_BASE_SATURATION_FLOW_SMP_PER_HOUR_BY_APPROACH,
    calculate_los,
    los_by_approach,
    build_dynamic_tls_logic,
    generate_cycle_candidate_plans,
    generate_candidate_plans,
    pkji_apply_ds_correction,
    pkji_cycle_and_green_seconds,
    pkji_degree_of_saturation,
    pkji_flow_smp_per_hour,
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


# ============================================================
# PKJI 2023 -- aggressive & balanced
# ============================================================

class _FakeApproach:
    def __init__(self, approach, car=0, motorcycle=0, bus=0, truck=0):
        self.approach = approach
        self.carCount = car
        self.motorcycleCount = motorcycle
        self.busCount = bus
        self.truckCount = truck


class _FakeTrafficState:
    def __init__(self, approaches):
        self.approaches = approaches


def _traffic_state_uneven_demand() -> _FakeTrafficState:
    # north jauh lebih padat dari 3 lengan lain -- didesain supaya total
    # flow ratio < 1 (tidak kena pengaman oversaturasi) TAPI north sendiri
    # cukup jenuh untuk memicu koreksi DS di kandidat aggressive.
    return _FakeTrafficState([
        _FakeApproach("north", car=1, motorcycle=4),
        _FakeApproach("east", car=1, motorcycle=1),
        _FakeApproach("south", motorcycle=2),
        _FakeApproach("west", motorcycle=1),
    ])


def test_pkji_flow_smp_per_hour_converts_vehicle_classes_via_emp():
    # 2 mobil (emp 1.0) + 1 bus (emp 1.3) + 4 motor (emp 0.25) per jendela
    # 5 detik = 2 + 1.3 + 1.0 = 4.3 smp/jendela -> smp/jam = *720.
    approach = _FakeApproach("north", car=2, motorcycle=4, bus=1)
    assert pkji_flow_smp_per_hour(approach) == 4.3 * 720


def test_pkji_cycle_and_green_seconds_gives_more_green_to_higher_demand():
    state = _traffic_state_uneven_demand()
    approaches_by_name = {item.approach: item for item in state.approaches}

    result = pkji_cycle_and_green_seconds(approaches_by_name)

    assert set(result["greenSecondsByApproach"]) == set(FIXED_CYCLE_ORDER)
    assert result["optimumCycleSeconds"] > 0

    green = result["greenSecondsByApproach"]
    # north (demand tertinggi) harus dapat hijau >= lengan yang lebih sepi.
    assert green["north"] >= green["east"] >= green["south"] >= green["west"]
    for value in green.values():
        assert MIN_GREEN_SECONDS <= value <= MAX_GREEN_SECONDS


def test_pkji_cycle_and_green_seconds_caps_oversaturated_intersection():
    # Keempat lengan sengaja dibuat sangat padat -- Sigma FR jauh di atas 1.
    # Rumus Webster mentah akan meledak (penyebut negatif); harus dijepit,
    # bukan crash atau menghasilkan siklus negatif/tak terhingga.
    jammed = _FakeTrafficState([
        _FakeApproach("north", car=20, motorcycle=20),
        _FakeApproach("east", car=20, motorcycle=20),
        _FakeApproach("south", car=20, motorcycle=20),
        _FakeApproach("west", car=20, motorcycle=20),
    ])
    approaches_by_name = {item.approach: item for item in jammed.approaches}

    result = pkji_cycle_and_green_seconds(approaches_by_name)

    assert result["optimumCycleSeconds"] > 0
    for value in result["greenSecondsByApproach"].values():
        assert MIN_GREEN_SECONDS <= value <= MAX_GREEN_SECONDS


def test_pkji_degree_of_saturation_matches_formula_by_hand():
    # Arus jenuh sekarang beda tiap lengan (lebar efektif asli Simpang
    # Pingit, bukan lagi satu angka rata) -- verifikasi lewat definisi:
    # DS = flow / (S_lengan * green/cycle), S_lengan dari konstanta asli.
    green_by_approach = {"north": 30, "east": 15, "south": 15, "west": 15}
    flow_by_approach = {"north": 1800.0, "east": 100.0, "south": 100.0, "west": 100.0}

    ds = pkji_degree_of_saturation(green_by_approach, flow_by_approach)

    cycle = sum(green_by_approach.values()) + 16
    s_north = PKJI_BASE_SATURATION_FLOW_SMP_PER_HOUR_BY_APPROACH["north"]
    expected_north = round(1800.0 / (s_north * (30 / cycle)), 2)
    assert ds["north"] == expected_north


def test_pkji_apply_ds_correction_extends_saturated_approach_until_threshold():
    green_by_approach = {"north": 30, "east": 15, "south": 15, "west": 15}
    # north jauh melebihi kapasitas pada hijau 30 detik.
    flow_by_approach = {"north": 3000.0, "east": 200.0, "south": 100.0, "west": 100.0}

    adjusted, ds_after = pkji_apply_ds_correction(green_by_approach, flow_by_approach)

    assert adjusted["north"] > green_by_approach["north"]
    assert adjusted["north"] <= MAX_GREEN_SECONDS
    # Koreksi berhenti begitu DS turun ke ambang ATAU mentok MAX_GREEN --
    # salah satu dari dua kondisi ini harus benar.
    assert ds_after["north"] <= PKJI_DS_THRESHOLD or adjusted["north"] == MAX_GREEN_SECONDS


def test_pkji_apply_ds_correction_does_not_shrink_underused_approach():
    green_by_approach = {"north": 30, "east": 15, "south": 15, "west": 15}
    flow_by_approach = {"north": 100.0, "east": 100.0, "south": 100.0, "west": 100.0}

    adjusted, _ = pkji_apply_ds_correction(green_by_approach, flow_by_approach)

    assert all(adjusted[name] >= green_by_approach[name] for name in green_by_approach)


def test_generate_full_cycle_candidates_use_pkji_when_traffic_state_given():
    baseline = _baseline_cycle()
    state = _traffic_state_uneven_demand()

    candidates = {
        item["candidateId"]: item
        for item in generate_cycle_candidate_plans(baseline, traffic_state=state)
    }

    # baseline TIDAK BOLEH berubah -- itu satu-satunya alasan dia tetap
    # dipakai sebagai pembanding before/after di tempat lain.
    baseline_green = {
        p["approach"]: p["greenSeconds"] for p in candidates["baseline"]["phases"]
    }
    original_green = {
        phase.approach: phase.greenSeconds for phase in baseline.phases
    }
    assert baseline_green == original_green
    assert "pkjiFlowRatioByApproach" not in candidates["baseline"]

    # aggressive & balanced membawa jejak PKJI (bukti buat juri).
    for candidate_id in ("aggressive", "balanced"):
        candidate = candidates[candidate_id]
        assert set(candidate["pkjiFlowRatioByApproach"]) == set(FIXED_CYCLE_ORDER)
        assert set(candidate["pkjiDegreeOfSaturationByApproach"]) == set(
            FIXED_CYCLE_ORDER
        )
        for phase in candidate["phases"]:
            assert MIN_GREEN_SECONDS <= phase["greenSeconds"] <= MAX_GREEN_SECONDS

    # aggressive menerapkan koreksi DS di ATAS hasil proporsional balanced
    # -- tidak pernah mengurangi hijau lengan mana pun.
    balanced_green = {
        p["approach"]: p["greenSeconds"] for p in candidates["balanced"]["phases"]
    }
    aggressive_green = {
        p["approach"]: p["greenSeconds"] for p in candidates["aggressive"]["phases"]
    }
    assert all(
        aggressive_green[name] >= balanced_green[name] for name in FIXED_CYCLE_ORDER
    )


def test_generate_full_cycle_candidates_fallback_without_traffic_state():
    # Tanpa traffic_state, harus tetap jatuh ke heuristik lama -- tidak
    # ada pemanggil lama yang tiba-tiba error atau dapat kunci pkji*.
    candidates = generate_cycle_candidate_plans(_baseline_cycle())
    for candidate in candidates:
        assert "pkjiFlowRatioByApproach" not in candidate
        assert "pkjiDegreeOfSaturationByApproach" not in candidate


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


def test_los_by_approach_grades_each_arm_separately():
    hasil = los_by_approach({
        "north": 8.0,     # A
        "south": 61.5,    # E
        "east": 22.0,     # C
        "west": None,     # tanpa data
    })
    assert hasil == {
        "north": "A",
        "south": "E",
        "east": "C",
        "west": None,
    }


def test_los_by_approach_empty_when_no_data():
    assert los_by_approach(None) == {}
    assert los_by_approach({}) == {}


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
