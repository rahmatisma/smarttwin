from __future__ import annotations

from typing import Any

from app.schemas.traffic import TrafficState

from .rule_based_engine import FIXED_CYCLE_ORDER


FEATURE_NAMES_PER_APPROACH = (
    "volume",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
    "avgSpeedKmh",
)
FEATURE_SCALES = {
    "volume": 60.0,
    "queueLengthVeh": 30.0,
    "queueLengthMEst": 150.0,
    "densityIndex": 33.0,
    "avgSpeedKmh": 60.0,
}
OBSERVATION_SIZE = 25


def _safe_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def build_ppo_observation(
    state: TrafficState,
    *,
    current_phase: str,
    current_green_seconds: int,
) -> list[float]:
    """Kontrak fitur tunggal untuk training dan inference PPO.

    `volume` selalu berarti flow/crossing dalam window TrafficState. Density
    selalu berarti kehadiran kendaraan, sehingga slot 0 dan 3 tidak lagi
    berasal dari besaran SUMO yang sama.
    """
    by_name = {
        str(getattr(item.approach, "value", item.approach)).lower(): item
        for item in state.approaches
    }
    observation: list[float] = []
    for approach in FIXED_CYCLE_ORDER:
        item = by_name.get(approach)
        for feature_name in FEATURE_NAMES_PER_APPROACH:
            value = _safe_float(getattr(item, feature_name, 0))
            observation.append(min(1.0, value / FEATURE_SCALES[feature_name]))

    normalized_phase = str(current_phase).lower()
    observation.extend(
        1.0 if normalized_phase == approach else 0.0
        for approach in FIXED_CYCLE_ORDER
    )
    observation.append(min(1.0, max(0.0, float(current_green_seconds) / 60.0)))
    if len(observation) != OBSERVATION_SIZE:
        raise RuntimeError(f"Observation PPO harus {OBSERVATION_SIZE} fitur")
    return observation
