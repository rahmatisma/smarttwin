import csv

import numpy as np
import pytest

from app.schemas.traffic import ApproachState, TrafficState
from decision_engine.ppo_engine import GREEN_OPTIONS, PPOEngine
from decision_engine.ppo_env import (
    BAGI_ARUS_DUA_ARAH,
    FEATURE_WINDOW_SECONDS,
    SKALA_PERMINTAAN,
    SmartTwinSumoEnv,
    load_demand_profiles,
)
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

    # BUG O: `jumlah_crossing` menghitung kedua arah lalu lintas (garis hitung CV
    # tidak memfilter arah, dan jalan pendekatnya dua arah), jadi angkanya dibagi
    # BAGI_ARUS_DUA_ARAH sebelum dipakai sebagai permintaan satu arah.
    # Lalu dikalikan SKALA_PERMINTAAN (kalibrasi pemodelan, lihat ppo_env.py).
    #
    # Ekspektasi DITURUNKAN dari konstanta, bukan ditulis sebagai angka mati.
    # SKALA_PERMINTAAN adalah kalibrasi yang memang dirancang berubah setiap
    # kali lingkungan training berubah (0,40 -> 0,60 pada 2 September 2026
    # ketika koridor pendekat dipanjangkan). Yang harus dikunci test ini
    # adalah RUMUS-nya -- crossing / 2 arah * skala, lalu per-5-detik
    # dijadikan per-menit -- bukan hasil satu kalibrasi tertentu.
    per_menit = 60.0 / FEATURE_WINDOW_SECONDS
    magelang = 2 / BAGI_ARUS_DUA_ARAH * SKALA_PERMINTAAN * per_menit
    diponegoro = 1 / BAGI_ARUS_DUA_ARAH * SKALA_PERMINTAAN * per_menit

    assert len(profiles) == 1
    assert profiles[0] == pytest.approx(
        {"north": magelang, "east": diponegoro, "south": 0.0, "west": 0.0}
    )
    # DIPONEGORO tepat separuh MAGELANG -- mengunci proporsi antar-lengan
    # supaya kalibrasi tidak bisa diam-diam mengubah bentuk permintaan.
    assert profiles[0]["east"] == pytest.approx(profiles[0]["north"] / 2)
