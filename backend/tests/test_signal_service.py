from datetime import datetime, timedelta, timezone

from app.services.signal_service import (
    DEFAULT_GREEN_SECONDS,
    YELLOW_SECONDS,
    SignalService,
)

import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from decision_engine.rule_based_engine import (  # noqa: E402
    ApproachPhase,
    CyclePlan,
    FIXED_CYCLE_ORDER,
)


class _TrafficHistoryStub:
    def __init__(self, records):
        self.records = records

    def get_latest_traffic(self, **_kwargs):
        return self.records


class _ForecastStub:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def predict_records(self, _records):
        if self.error:
            raise self.error
        return self.result


def _service_with_fixed_green(seconds: int) -> SignalService:
    """
    SignalService dengan _recompute_cycle_plan() DIPATCH supaya semua
    lengan pakai durasi tetap -- mengisolasi logika tick/advance (yang
    ditest di sini) dari logika demand-based duration ASLI (yang baca
    Supabase sungguhan, sudah ditest sendiri di
    test_rule_based_engine_cycle.py) dan bikin test ini deterministik.
    """
    service = SignalService()

    def fixed_plan(active_approach: str) -> CyclePlan:
        plan = CyclePlan(
            phases=[
                ApproachPhase(
                    approach=approach_name,
                    greenSeconds=seconds,
                    demandScore=0.5,
                )
                for approach_name in FIXED_CYCLE_ORDER
            ],
            cycleLengthSeconds=seconds * len(FIXED_CYCLE_ORDER),
            currentPhase=active_approach,
            source="rule-based",
        )
        service._cycle_plan = plan
        return plan

    service._recompute_cycle_plan = fixed_plan  # type: ignore[method-assign]
    return service


def test_first_call_starts_at_first_cycle_order_with_default_green():
    service = _service_with_fixed_green(30)
    t0 = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)

    status = service.get_live_status(now=t0)

    assert status.currentPhase == FIXED_CYCLE_ORDER[0]
    assert status.remainingSeconds == DEFAULT_GREEN_SECONDS + YELLOW_SECONDS


def test_stays_on_same_phase_before_elapsed():
    service = _service_with_fixed_green(30)
    t0 = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)

    service.get_live_status(now=t0)
    status = service.get_live_status(
        now=t0 + timedelta(seconds=10)
    )

    assert status.currentPhase == FIXED_CYCLE_ORDER[0]
    assert status.remainingSeconds == (
        DEFAULT_GREEN_SECONDS + YELLOW_SECONDS - 10
    )


def test_advances_to_next_phase_after_elapsed():
    service = _service_with_fixed_green(30)
    t0 = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)

    service.get_live_status(now=t0)

    first_phase_total = DEFAULT_GREEN_SECONDS + YELLOW_SECONDS
    status = service.get_live_status(
        now=t0 + timedelta(seconds=first_phase_total + 1)
    )

    assert status.currentPhase == FIXED_CYCLE_ORDER[1]
    # Fase baru pakai durasi dari _green_seconds_for yang dipatch (30),
    # bukan DEFAULT_GREEN_SECONDS lagi.
    assert status.remainingSeconds == 30 + YELLOW_SECONDS - 1


def test_skips_multiple_overdue_phases_without_getting_stuck():
    service = _service_with_fixed_green(10)
    t0 = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)

    service.get_live_status(now=t0)

    first_phase_total = DEFAULT_GREEN_SECONDS + YELLOW_SECONDS
    later_phase_total = 10 + YELLOW_SECONDS

    # Lewati fase 1 penuh + 2 fase later_phase_total penuh + 3 detik
    # ke fase ke-4 -- server "tidak sempat di-poll" cukup lama.
    jump = first_phase_total + (2 * later_phase_total) + 3

    status = service.get_live_status(
        now=t0 + timedelta(seconds=jump)
    )

    assert status.currentPhase == FIXED_CYCLE_ORDER[3]
    assert status.remainingSeconds == later_phase_total - 3


def test_wraps_around_after_last_approach():
    service = _service_with_fixed_green(10)
    t0 = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)

    service.get_live_status(now=t0)

    first_phase_total = DEFAULT_GREEN_SECONDS + YELLOW_SECONDS
    later_phase_total = 10 + YELLOW_SECONDS

    # Lewati semua 4 fase penuh -- harus balik ke fase pertama lagi.
    jump = first_phase_total + (3 * later_phase_total) + 1

    status = service.get_live_status(
        now=t0 + timedelta(seconds=jump)
    )

    assert status.currentPhase == FIXED_CYCLE_ORDER[0]


def test_phases_dict_only_marks_active_approach_green():
    service = _service_with_fixed_green(30)
    t0 = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)

    status = service.get_live_status(now=t0)

    active = FIXED_CYCLE_ORDER[0]

    for approach_name, phase in status.phases.items():
        if approach_name == active:
            assert phase.state == "green"
            assert phase.durationSeconds == DEFAULT_GREEN_SECONDS
        else:
            # Lengan lain BUKAN 0 lagi -- harus angka asli dari cycle
            # plan yang sama (di sini di-patch tetap 30), supaya
            # panel "Durasi Hijau per Lengan" bisa baca angka yang
            # sama persis lewat get_cycle_plan().
            assert phase.state == "red"
            assert phase.durationSeconds == 30
            assert phase.remainingSeconds == 0


def test_next_phase_points_to_following_approach_in_order():
    service = _service_with_fixed_green(30)
    t0 = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)

    status = service.get_live_status(now=t0)

    assert status.currentPhase == FIXED_CYCLE_ORDER[0]
    assert status.nextPhase == FIXED_CYCLE_ORDER[1]
    assert status.nextPhaseName != ""


def test_get_cycle_plan_matches_phases_shown_in_live_status():
    service = _service_with_fixed_green(30)
    t0 = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)

    status = service.get_live_status(now=t0)
    plan = service.get_cycle_plan()

    plan_by_approach = {p.approach: p.greenSeconds for p in plan.phases}

    for approach_name, phase in status.phases.items():
        if approach_name == status.currentPhase:
            # Fase aktif pakai DEFAULT_GREEN_SECONDS (bootstrap),
            # bukan nilai cycle plan -- itu memang beda secara
            # desain (lihat komentar di SignalService).
            continue

        assert phase.durationSeconds == plan_by_approach[approach_name]


def test_recompute_cycle_plan_passes_forecast_to_decision_engine():
    now = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)
    record = {
        "trafficState": {"windowStart": now, "windowEnd": now},
        "approaches": [
            {"approach": approach, "volume": 1, "queueLengthVeh": 0, "densityIndex": 0}
            for approach in FIXED_CYCLE_ORDER
        ],
    }
    forecast = {"approachForecasts": [{"approaches": []}]}
    service = SignalService(
        traffic_service=_TrafficHistoryStub([record]),
        forecast_service=_ForecastStub(result=forecast),
    )
    captured = {}

    def recommend_cycle(**kwargs):
        captured.update(kwargs)
        return CyclePlan(
            phases=[ApproachPhase(approach=a, greenSeconds=20) for a in FIXED_CYCLE_ORDER],
            cycleLengthSeconds=80,
            currentPhase=kwargs["currentPhase"],
            source="rule-based+forecast",
        )

    service.engine.recommend_cycle = recommend_cycle
    plan = service._recompute_cycle_plan("north")

    assert captured["forecast"] is forecast
    assert captured["forecastWeight"] == 0.3
    assert plan.source == "rule-based+forecast"


def test_recompute_cycle_plan_falls_back_when_forecast_fails():
    now = datetime(2026, 8, 26, 8, 0, 0, tzinfo=timezone.utc)
    record = {
        "trafficState": {"windowStart": now, "windowEnd": now},
        "approaches": [
            {"approach": approach, "volume": 1, "queueLengthVeh": 0, "densityIndex": 0}
            for approach in FIXED_CYCLE_ORDER
        ],
    }
    service = SignalService(
        traffic_service=_TrafficHistoryStub([record]),
        forecast_service=_ForecastStub(error=ValueError("history belum cukup")),
    )

    plan = service._recompute_cycle_plan("north")

    assert plan.source == "rule-based"
