import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "simulation"))
sys.path.insert(0, str(ROOT / "backend"))

import scenario_generator as generator
import run_tls_simulation as runner
from app.pipeline.traffic_state_builder import BuiltTrafficState


def observation():
    return BuiltTrafficState(
        trafficStateId=42, intersectionId="simpang4-pingit",
        windowStart=datetime(2026, 8, 15, tzinfo=timezone.utc),
        windowEnd=datetime(2026, 8, 15, 0, 0, 5, tzinfo=timezone.utc),
        approaches=[dict(approach=arm, carCount=12, motorcycleCount=8,
                         queueLengthVeh=10, queueLengthMEst=30, densityIndex=0.7)
                    for arm in ("north", "east", "south", "west")],
    )


@pytest.mark.parametrize("horizon", [None, 60])
def test_projection_uses_exact_horizon_without_changing_full_cycle_default(monkeypatch, horizon):
    calls = []
    state = observation()

    def simulate(candidate, **kwargs):
        calls.append((candidate, kwargs))
        return {**candidate, "avgDelaySeconds": 10, "avgQueueLengthM": 20,
                "queueLengthVeh": 4, "throughputVeh": 5, "los": "B"}

    monkeypatch.setattr(generator, "simulate_cycle_candidate", simulate)
    engine = generator.ScenarioEngine(sumo_binary="unused", sumo_config="unused", tls_id="test",
                                      approach_to_phase={}, run_simulation_fn=lambda **_: {})
    engine.recommend_full_cycle(state, evaluation_horizon_seconds=horizon)
    assert len(calls) == 3
    assert all(kwargs["traffic_state"] is state for _, kwargs in calls)
    durations = {kwargs["step_limit"] for _, kwargs in calls}
    assert len(durations) == 1
    if horizon:
        assert durations == {60}
    else:
        assert durations.pop() >= max(candidate["totalCycleSeconds"] for candidate, _ in calls)


def fake_connection(*, broken=False):
    frame = [0]
    def step():
        frame[0] += 1
    def ids():
        if broken:
            raise RuntimeError("metric unavailable")
        return ["north_0"]
    return SimpleNamespace(
        simulationStep=step,
        simulation=SimpleNamespace(getArrivedNumber=lambda: 0, getArrivedIDList=lambda: [],
                                   getDepartedNumber=lambda: int(frame[0] == 1), getMinExpectedNumber=lambda: 1),
        vehicle=SimpleNamespace(getIDList=ids, getIDCount=lambda: 1,
                                getAccumulatedWaitingTime=lambda _: 4,
                                getRoadID=lambda _: "north",
                                getSpeed=lambda _: 0 if frame[0] == 1 else 10),
    )


def test_terminal_queue_is_not_peak_and_speed_is_last_step(monkeypatch):
    monkeypatch.setattr(runner, "traci", fake_connection())
    monkeypatch.setattr(runner, "approachForRoad", lambda road: road)
    metrics = runner.runSimulation(step_limit=2, stop_when_empty=False, strict_metrics=True)
    assert metrics["steps"] == 2
    assert metrics["queueLengthVehByApproach"]["north"] == 1
    assert metrics["finalQueueLengthVehByApproach"]["north"] == 0
    assert metrics["finalSpeedKmhByApproach"]["north"] == 36
    assert metrics["finalSpeedKmhByApproach"]["east"] is None
    assert metrics["averageWaitingTimeSecondsByApproach"]["north"] == 4


def test_failed_measurement_cannot_be_reported_as_empty_queue(monkeypatch):
    monkeypatch.setattr(runner, "traci", fake_connection(broken=True))
    with pytest.raises(RuntimeError, match="metric unavailable"):
        runner.runSimulation(step_limit=2, stop_when_empty=False, strict_metrics=True)


@pytest.mark.integration
def test_real_sumo_projects_three_plans_for_exactly_one_minute():
    from forecast_snapshot import project_snapshot
    from app.schemas.digital_twin import ScenarioForecastResponse
    result = ScenarioForecastResponse.model_validate(project_snapshot(observation()))
    assert result.trafficStateId == 42
    assert (result.predictionTimestamp - result.inputTimestamp).total_seconds() == 60
    assert {item.evaluation["completedSteps"] for item in result.candidates} == {60}
    assert len({item.evaluation["demandHash"] for item in result.candidates}) == 1
    assert len({tuple(phase.greenSeconds for phase in item.phases) for item in result.candidates}) > 1
    assert len({tuple(item.finalQueueLengthVehByApproach.values()) for item in result.candidates}) > 1
