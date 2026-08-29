import csv

import numpy as np
import pytest

from app.schemas.traffic import ApproachState, TrafficState
from decision_engine.ppo_engine import GREEN_OPTIONS, PPOEngine
from decision_engine.ppo_env import SmartTwinSumoEnv, load_demand_profiles
from decision_engine.rule_based_engine import FIXED_CYCLE_ORDER, RuleBasedEngine


class _Model:
    def predict(self, observation, deterministic=True):
        return np.asarray([0, 0, 0, 0, 0]), None


def _state() -> TrafficState:
    return TrafficState(
        intersectionId="simpang4-pingit",
        windowStart="2026-08-29T10:00:00+07:00",
        windowEnd="2026-08-29T10:00:05+07:00",
        approaches=[
            ApproachState(
                approach=approach,
                volume=2 + index,
                queueLengthVeh=3 + index,
                queueLengthMEst=(3 + index) * 7,
                densityIndex=8 + index * 2,
                avgSpeedKmh=30 - index,
            )
            for index, approach in enumerate(FIXED_CYCLE_ORDER)
        ],
    )


def test_training_and_inference_share_exact_observation_contract():
    state = _state()
    inference = PPOEngine(model=_Model()).build_observation(
        state, current_phase="east", current_green_seconds=35
    )
    env = object.__new__(SmartTwinSumoEnv)
    env.current_phase = "east"
    env.current_green = 35
    env._traffic_state = lambda: state

    training = SmartTwinSumoEnv._observation(env).tolist()

    assert training == pytest.approx(inference)
    # Volume/crossing dan density/kehadiran tidak lagi merupakan fitur duplikat.
    assert training[0] != training[3]


def test_evaluation_baseline_maps_real_rule_based_engine_to_action_space():
    state = _state()
    engine = RuleBasedEngine()
    env = object.__new__(SmartTwinSumoEnv)
    env.rule_based_engine = engine
    env.current_phase = "north"
    env.current_green = 30
    env._traffic_state = lambda: state

    action = SmartTwinSumoEnv.rule_based_action(env)
    cycle = engine.recommend_cycle(state, currentPhase="north")

    # Action = 4 durasi hijau saja. Sejak 29 Agustus PPO maupun baseline
    # tidak lagi memilih fase awal (rotasi tetap FIXED_CYCLE_ORDER, sama
    # seperti produksi) -- lihat docs/STATUS-DAN-SISA-KERJA.md item P-1.
    assert len(action) == len(FIXED_CYCLE_ORDER)
    for index, phase in enumerate(cycle.phases):
        mapped_green = GREEN_OPTIONS[action[index]]
        assert abs(mapped_green - phase.greenSeconds) == min(
            abs(option - phase.greenSeconds) for option in GREEN_OPTIONS
        )


def test_demand_profiles_use_crossing_flow_and_current_snapshot_windows(tmp_path):
    crossing = tmp_path / "crossing_simpang.csv"
    snapshot = tmp_path / "snapshot_zona.csv"
    with crossing.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "label_garis", "jumlah_crossing"])
        writer.writeheader()
        writer.writerow({"timestamp": "2026-08-29 10:00:00", "label_garis": "MAGELANG", "jumlah_crossing": 2})
        writer.writerow({"timestamp": "2026-08-29 10:00:00", "label_garis": "DIPONEGORO", "jumlah_crossing": 1})
    with snapshot.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "lengan", "total_di_zona"])
        writer.writeheader()
        writer.writerow({"timestamp": "2026-08-29 10:00:01", "lengan": "simpang_tengah", "total_di_zona": 20})
        writer.writerow({"timestamp": "2026-08-29 10:00:04", "lengan": "timur", "total_di_zona": 30})

    profiles = load_demand_profiles(crossing, snapshot)

    assert profiles == [{"north": 24.0, "east": 12.0, "south": 0.0, "west": 0.0}]
