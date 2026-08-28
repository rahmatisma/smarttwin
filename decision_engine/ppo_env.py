from __future__ import annotations

import csv
import random
import shutil
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .ppo_engine import GREEN_OPTIONS
from .rule_based_engine import FIXED_CYCLE_ORDER, YELLOW_SECONDS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "simulation/network/simpang4_pingit_live.sumocfg"
DEFAULT_DATA = ROOT / "cv/output/smarttwin_traffic_data.csv"

EDGE_HULU = {"north": "484349908#0", "south": "134603786#0", "east": "153857851#2", "west": "590064461#0"}
EDGE_MASUK = {"north": "484349908#2", "south": "134603786#2", "east": "153857851#4", "west": "590064461#2"}
EDGE_KELUAR = {"north": "201299423#0", "south": "153857907#0", "east": "590386082#0", "west": "25006154#0"}
TURN_DESTINATIONS = {
    "north": ("south", "east", "west"), "south": ("north", "west", "east"),
    "east": ("west", "north", "south"), "west": ("east", "south", "north"),
}
GREEN_STATE = {
    "south": "GGGggrrrrrrrrrrrrrrr", "east": "rrrrrGGGggrrrrrrrrrr",
    "north": "rrrrrrrrrrGGGggrrrrr", "west": "rrrrrrrrrrrrrrrGGGgg",
}
YELLOW_STATE = {
    "south": "yyyyyrrrrrrrrrrrrrrr", "east": "rrrrryyyyyrrrrrrrrrr",
    "north": "rrrrrrrrrryyyyyrrrrr", "west": "rrrrrrrrrrrrrrryyyyy",
}


def load_demand_profiles(path: str | Path = DEFAULT_DATA) -> list[dict[str, float]]:
    """Aggregate CV lane rows into approach demand profiles (vehicles/minute)."""
    source = Path(path)
    if not source.exists():
        return [{approach: value for approach in FIXED_CYCLE_ORDER} for value in (8.0, 15.0, 25.0)]
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    with source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            approach = str(row.get("approach", "")).lower()
            timestamp = str(row.get("timestamp", ""))
            if approach in FIXED_CYCLE_ORDER and timestamp:
                grouped[timestamp][approach] += max(0.0, float(row.get("vehicle_count", 0) or 0))
    profiles = []
    for values in grouped.values():
        # Rekaman adalah snapshot 5 detik. Faktor 12 mengubah count menjadi veh/min.
        profiles.append({approach: max(3.0, values.get(approach, 0.0) * 12.0) for approach in FIXED_CYCLE_ORDER})
    return profiles or [{approach: 12.0 for approach in FIXED_CYCLE_ORDER}]


def resolve_sumo_binary(explicit: str | Path | None = None) -> Path:
    candidates = [
        Path(explicit) if explicit else None,
        Path(found) if (found := shutil.which("sumo")) else None,
        ROOT / "simulation/.venv/Lib/site-packages/sumo/bin/sumo.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError("sumo/sumo.exe tidak ditemukan; lihat README-PPO-UNTUK-TIM.md")


class SmartTwinSumoEnv(gym.Env[np.ndarray, np.ndarray]):
    """Single-intersection Gymnasium environment with the inference 25-feature contract."""

    metadata = {"render_modes": []}

    def __init__(self, *, data_path: str | Path = DEFAULT_DATA, config_path: str | Path = DEFAULT_CONFIG,
                 sumo_binary: str | Path | None = None, episode_steps: int = 12,
                 decision_seconds: int = 30, split: str = "train") -> None:
        super().__init__()
        self.profiles = load_demand_profiles(data_path)
        cut = max(1, int(len(self.profiles) * 0.8))
        self.profiles = self.profiles[:cut] if split == "train" else self.profiles[cut:]
        if not self.profiles:
            self.profiles = load_demand_profiles(data_path)
        self.config_path = Path(config_path).resolve()
        self.sumo_binary = resolve_sumo_binary(sumo_binary)
        self.episode_steps, self.decision_seconds = int(episode_steps), int(decision_seconds)
        self.observation_space = spaces.Box(0.0, 1.0, shape=(25,), dtype=np.float32)
        self.action_space = spaces.MultiDiscrete([4, len(GREEN_OPTIONS), len(GREEN_OPTIONS), len(GREEN_OPTIONS), len(GREEN_OPTIONS)])
        self.connection: Any = None
        self.label = f"smarttwin-ppo-{uuid.uuid4().hex}"
        self.rng = random.Random()
        self.step_count = self.vehicle_counter = 0
        self.profile: dict[str, float] = self.profiles[0]
        self.current_phase = "north"
        self.current_green = 30
        self.starvation = {a: 0 for a in FIXED_CYCLE_ORDER}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self.close()
        actual_seed = int(seed if seed is not None else self.np_random.integers(1, 2**31 - 1))
        self.rng.seed(actual_seed)
        self.profile = self.profiles[actual_seed % len(self.profiles)]
        import traci
        traci.start([str(self.sumo_binary), "-c", str(self.config_path), "--start", "--seed", str(actual_seed),
                     "--no-step-log", "true", "--xml-validation", "never"], label=self.label)
        self.connection = traci.getConnection(self.label)
        self._add_vehicle_types()
        self.step_count = self.vehicle_counter = 0
        self.current_phase, self.current_green = "north", 30
        self.starvation = {a: 0 for a in FIXED_CYCLE_ORDER}
        for _ in range(20):
            self._inject_one_second()
            self.connection.simulationStep()
        return self._observation(), self._metrics()

    def _add_vehicle_types(self) -> None:
        existing = set(self.connection.vehicletype.getIDList())
        if "smart_car" not in existing:
            self.connection.vehicletype.copy("DEFAULT_VEHTYPE", "smart_car")

    def _inject_one_second(self) -> None:
        for approach in FIXED_CYCLE_ORDER:
            if self.rng.random() >= min(0.8, self.profile[approach] / 60.0):
                continue
            destination = self.rng.choices(TURN_DESTINATIONS[approach], weights=(0.50, 0.25, 0.25), k=1)[0]
            route_id = f"ppo_route_{self.vehicle_counter}"
            vehicle_id = f"ppo_vehicle_{self.vehicle_counter}"
            self.vehicle_counter += 1
            try:
                self.connection.route.add(route_id, [EDGE_HULU[approach], EDGE_MASUK[approach], EDGE_KELUAR[destination]])
                self.connection.vehicle.add(vehicle_id, route_id, typeID="smart_car", depart="now")
            except Exception:
                pass

    def _set_action(self, action: np.ndarray) -> None:
        selected_index = int(action[0])
        greens = {a: GREEN_OPTIONS[int(action[i + 1])] for i, a in enumerate(FIXED_CYCLE_ORDER)}
        phases = []
        for approach in FIXED_CYCLE_ORDER:
            phases.extend([self.connection.trafficlight.Phase(greens[approach], GREEN_STATE[approach]),
                           self.connection.trafficlight.Phase(YELLOW_SECONDS, YELLOW_STATE[approach])])
        tls_id = self.connection.trafficlight.getIDList()[0]
        logic = self.connection.trafficlight.Logic("smarttwin-ppo", 0, 0, phases=phases)
        self.connection.trafficlight.setProgramLogic(tls_id, logic)
        self.connection.trafficlight.setProgram(tls_id, logic.programID)
        self.connection.trafficlight.setPhase(tls_id, selected_index * 2)
        self.current_phase = FIXED_CYCLE_ORDER[selected_index]
        self.current_green = greens[self.current_phase]
        for approach in FIXED_CYCLE_ORDER:
            self.starvation[approach] = 0 if approach == self.current_phase else self.starvation[approach] + 1

    def step(self, action: np.ndarray):
        self._set_action(action)
        arrived = 0
        for _ in range(self.decision_seconds):
            self._inject_one_second()
            self.connection.simulationStep()
            arrived += int(self.connection.simulation.getArrivedNumber())
        self.step_count += 1
        metrics = self._metrics()
        queue_norm = min(1.0, metrics["queue"] / 40.0)
        wait_norm = min(1.0, metrics["waiting"] / max(1.0, metrics["vehicles"] * 120.0))
        throughput_norm = min(1.0, arrived / 15.0)
        starvation_penalty = 0.05 * sum(max(0, value - 3) for value in self.starvation.values())
        reward = float(0.20 * throughput_norm - 0.50 * queue_norm - 0.30 * wait_norm - starvation_penalty)
        metrics.update({"reward": reward, "throughput_interval": float(arrived), "queue_norm": queue_norm,
                        "wait_norm": wait_norm, "starvation_penalty": starvation_penalty})
        return self._observation(), reward, False, self.step_count >= self.episode_steps, metrics

    def _metrics(self) -> dict[str, float]:
        vehicles = list(self.connection.vehicle.getIDList()) if self.connection else []
        waiting = sum(float(self.connection.vehicle.getAccumulatedWaitingTime(v)) for v in vehicles) if self.connection else 0.0
        queue = sum(self.connection.edge.getLastStepHaltingNumber(EDGE_HULU[a]) + self.connection.edge.getLastStepHaltingNumber(EDGE_MASUK[a]) for a in FIXED_CYCLE_ORDER) if self.connection else 0
        arrived = float(self.connection.simulation.getArrivedNumber()) if self.connection else 0.0
        return {"vehicles": float(len(vehicles)), "queue": float(queue), "waiting": waiting, "arrived": arrived}

    def _observation(self) -> np.ndarray:
        values: list[float] = []
        for approach in FIXED_CYCLE_ORDER:
            edges = (EDGE_HULU[approach], EDGE_MASUK[approach])
            volume = sum(self.connection.edge.getLastStepVehicleNumber(e) for e in edges)
            queue = sum(self.connection.edge.getLastStepHaltingNumber(e) for e in edges)
            speeds = [self.connection.edge.getLastStepMeanSpeed(e) for e in edges]
            speed_kmh = max(0.0, sum(speeds) / len(speeds) * 3.6)
            values.extend([min(1, volume / 60), min(1, queue / 30), min(1, queue * 7 / 150),
                           min(1, volume / 33), min(1, speed_kmh / 60)])
        values.extend(1.0 if self.current_phase == a else 0.0 for a in FIXED_CYCLE_ORDER)
        values.append(min(1.0, self.current_green / 60.0))
        return np.asarray(values, dtype=np.float32)

    def rule_based_action(self) -> np.ndarray:
        demand = [self._observation()[i * 5 + 1] for i in range(4)]
        selected = int(np.argmax(demand))
        green_indexes = [min(len(GREEN_OPTIONS) - 1, max(0, round(value * 9))) for value in demand]
        return np.asarray([selected, *green_indexes], dtype=np.int64)

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
