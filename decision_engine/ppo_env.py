from __future__ import annotations

import csv
import random
import shutil
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .ppo_engine import GREEN_OPTIONS
from .ppo_features import build_ppo_observation
from .rule_based_engine import FIXED_CYCLE_ORDER, RuleBasedEngine, YELLOW_SECONDS
from app.schemas.traffic import ApproachState, TrafficState

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "simulation/network/simpang4_pingit_live.sumocfg"
DEFAULT_DATA = ROOT / "cv/output/crossing_simpang.csv"
DEFAULT_DENSITY_DATA = ROOT / "cv/output/snapshot_zona.csv"
FEATURE_WINDOW_SECONDS = 5
METERS_PER_QUEUED_VEHICLE = 7.0

CROSS_LABEL_MAP = {
    "selatan": "south",
    "MAGELANG": "north",
    "DIPONEGORO": "east",
    "barat": "west",
}
DENSITY_APPROACH_MAP = {
    "selatan": "south",
    "barat": "west",
    "timur": "east",
    "simpang_tengah": "north",
}

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

# Reward v2: throughput menjadi tujuan utama. Bobot ketiga komponen berjumlah
# 1,0 agar skala reward tetap mudah dibaca dan dibandingkan antar-training.
THROUGHPUT_REWARD_WEIGHT = 0.45
QUEUE_REWARD_WEIGHT = 0.35
WAIT_REWARD_WEIGHT = 0.20

# Ambang saturasi throughput. Investigasi 29 Agustus (lihat
# docs/STATUS-DAN-SISA-KERJA.md item P-1 Temuan C) menemukan nilai lama 15,0
# membuat reward BUTA terhadap throughput: kedatangan nyata 18-26 kendaraan
# per langkah keputusan, sehingga PPO saturasi di 81% langkah dan baseline
# 97% -- selisih throughput_reward cuma 0,0258 dari maksimum 0,45. Akibatnya
# menaikkan throughput di atas ambang tidak memberi reward tambahan sama
# sekali, sementara antrean/tunggu masih terus memberi gradien. Ambang 30,0
# berada di atas maksimum yang teramati (26) supaya perbedaan 18 vs 20
# kendaraan benar-benar terbaca oleh reward.
THROUGHPUT_SATURATION_VEH = 30.0


def _floor_five_seconds(timestamp: str) -> str:
    parsed = datetime.fromisoformat(str(timestamp).strip().replace("Z", "+00:00"))
    return parsed.replace(second=(parsed.second // 5) * 5, microsecond=0).isoformat()


def load_demand_profiles(
    path: str | Path = DEFAULT_DATA,
    density_path: str | Path = DEFAULT_DENSITY_DATA,
) -> list[dict[str, float]]:
    """Bangun demand veh/min dari pasangan CSV yang dipakai ingest produksi.

    Flow hanya berasal dari `crossing_simpang.csv`. `snapshot_zona.csv`
    menentukan window/lengan yang benar-benar memiliki pengukuran kehadiran;
    kedua populasi sengaja tidak dijumlahkan.
    """
    crossing_source, density_source = Path(path), Path(density_path)
    missing = [str(item) for item in (crossing_source, density_source) if not item.exists()]
    if missing:
        raise FileNotFoundError(
            "Dataset PPO produksi belum tersedia: " + ", ".join(missing)
        )

    measured: dict[str, set[str]] = defaultdict(set)
    with density_source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            approach = DENSITY_APPROACH_MAP.get(str(row.get("lengan", "")))
            timestamp = str(row.get("timestamp", ""))
            if approach and timestamp:
                measured[_floor_five_seconds(timestamp)].add(approach)

    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    with crossing_source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            approach = CROSS_LABEL_MAP.get(str(row.get("label_garis", "")))
            timestamp = str(row.get("timestamp", ""))
            if approach and timestamp:
                grouped[_floor_five_seconds(timestamp)][approach] += max(
                    0.0, float(row.get("jumlah_crossing", 0) or 0)
                )

    timestamps = sorted(set(grouped).intersection(measured))
    profiles = [
        {
            approach: grouped[timestamp].get(approach, 0.0) * (60.0 / FEATURE_WINDOW_SECONDS)
            for approach in FIXED_CYCLE_ORDER
        }
        for timestamp in timestamps
        if measured[timestamp]
    ]
    if not profiles:
        raise ValueError("Dataset crossing/snapshot tidak mempunyai window yang dapat dipasangkan")
    return profiles


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

    def __init__(self, *, data_path: str | Path = DEFAULT_DATA,
                 density_data_path: str | Path = DEFAULT_DENSITY_DATA,
                 config_path: str | Path = DEFAULT_CONFIG,
                 sumo_binary: str | Path | None = None, episode_steps: int = 12,
                 decision_seconds: int = 30, split: str = "train") -> None:
        super().__init__()
        self.profiles = load_demand_profiles(data_path, density_data_path)
        cut = max(1, int(len(self.profiles) * 0.8))
        self.profiles = self.profiles[:cut] if split == "train" else self.profiles[cut:]
        if not self.profiles:
            self.profiles = load_demand_profiles(data_path, density_data_path)
        self.config_path = Path(config_path).resolve()
        self.sumo_binary = resolve_sumo_binary(sumo_binary)
        self.episode_steps, self.decision_seconds = int(episode_steps), int(decision_seconds)
        self.observation_space = spaces.Box(0.0, 1.0, shape=(25,), dtype=np.float32)
        # Empat durasi hijau saja (utara, timur, selatan, barat). Urutan rotasi
        # bukan keputusan PPO -- lihat _set_action().
        self.action_space = spaces.MultiDiscrete([len(GREEN_OPTIONS)] * len(FIXED_CYCLE_ORDER))
        self.connection: Any = None
        self.rule_based_engine = RuleBasedEngine()
        self.label = f"smarttwin-ppo-{uuid.uuid4().hex}"
        self.rng = random.Random()
        self.step_count = self.vehicle_counter = 0
        self.profile: dict[str, float] = self.profiles[0]
        self.current_phase = FIXED_CYCLE_ORDER[0]
        self.current_green = 30
        self.current_greens: dict[str, int] = {a: 30 for a in FIXED_CYCLE_ORDER}
        self.recent_crossings = {a: 0 for a in FIXED_CYCLE_ORDER}

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
        self.current_phase, self.current_green = FIXED_CYCLE_ORDER[0], 30
        self.current_greens = {a: 30 for a in FIXED_CYCLE_ORDER}
        self.recent_crossings = {a: 0 for a in FIXED_CYCLE_ORDER}
        for _ in range(20):
            self._inject_one_second()
            self.connection.simulationStep()
        # Observation awal mewakili window flow 5 detik, bukan seluruh warm-up.
        self.recent_crossings = {
            approach: max(0, round(self.profile[approach] * FEATURE_WINDOW_SECONDS / 60.0))
            for approach in FIXED_CYCLE_ORDER
        }
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
                self.recent_crossings[approach] += 1
            except Exception:
                pass

    def _set_action(self, action: np.ndarray) -> None:
        """Pasang program TLS dari 4 durasi hijau -- PERSIS seperti produksi.

        Action HANYA berisi durasi hijau per lengan; urutan rotasi sudah
        ditetapkan FIXED_CYCLE_ORDER (utara-timur-selatan-barat) dan tidak
        boleh diputuskan PPO. Sebelum 29 Agustus action[0] memilih fase awal
        lalu dipasang lewat setPhase(selected*2) -- itu tuas kendali yang
        TIDAK ADA di produksi (sumo_controller.apply_cycle_plan dan
        scenario_generator sama-sama memakai setPhase(tls_id, 0) tetap).
        Ketidakcocokan itu membuat baseline dihukum penalti starvation atas
        perilaku yang produksi tidak pernah lakukan, dan menyumbang 80,5%
        keunggulan reward PPO. Lihat docs/STATUS-DAN-SISA-KERJA.md item P-1
        Temuan D.
        """
        greens = {a: GREEN_OPTIONS[int(action[i])] for i, a in enumerate(FIXED_CYCLE_ORDER)}
        phases = []
        for approach in FIXED_CYCLE_ORDER:
            phases.extend([self.connection.trafficlight.Phase(greens[approach], GREEN_STATE[approach]),
                           self.connection.trafficlight.Phase(YELLOW_SECONDS, YELLOW_STATE[approach])])
        tls_id = self.connection.trafficlight.getIDList()[0]
        logic = self.connection.trafficlight.Logic("smarttwin-ppo", 0, 0, phases=phases)
        self.connection.trafficlight.setProgramLogic(tls_id, logic)
        self.connection.trafficlight.setProgram(tls_id, logic.programID)
        self.connection.trafficlight.setPhase(tls_id, 0)
        self.current_greens = greens

    def _sync_active_phase(self) -> None:
        """Selaraskan current_phase dengan fase yang BENAR-BENAR aktif di SUMO.

        Dulu current_phase diisi dari action[0] (fase yang dipilih PPO).
        Sekarang rotasi berjalan sendiri, jadi fase aktif harus dibaca dari
        simulasi -- ini juga lebih cocok dengan inference, karena di produksi
        SignalService meneruskan fase yang sedang hijau sungguhan.
        Program kita berpola [hijau, kuning] x 4, jadi index // 2 memetakan
        balik ke lengan di FIXED_CYCLE_ORDER.
        """
        try:
            tls_id = self.connection.trafficlight.getIDList()[0]
            index = int(self.connection.trafficlight.getPhase(tls_id))
        except Exception:
            return
        approach = FIXED_CYCLE_ORDER[(index // 2) % len(FIXED_CYCLE_ORDER)]
        self.current_phase = approach
        self.current_green = self.current_greens.get(approach, self.current_green)

    def step(self, action: np.ndarray):
        self._set_action(action)
        arrived = 0
        for second in range(self.decision_seconds):
            if second == self.decision_seconds - FEATURE_WINDOW_SECONDS:
                self.recent_crossings = {a: 0 for a in FIXED_CYCLE_ORDER}
            self._inject_one_second()
            self.connection.simulationStep()
            arrived += int(self.connection.simulation.getArrivedNumber())
        self.step_count += 1
        self._sync_active_phase()
        metrics = self._metrics()
        queue_norm = min(1.0, metrics["queue"] / 40.0)
        wait_norm = min(1.0, metrics["waiting"] / max(1.0, metrics["vehicles"] * 120.0))
        throughput_norm = min(1.0, arrived / THROUGHPUT_SATURATION_VEH)
        throughput_reward = THROUGHPUT_REWARD_WEIGHT * throughput_norm
        queue_penalty = QUEUE_REWARD_WEIGHT * queue_norm
        wait_penalty = WAIT_REWARD_WEIGHT * wait_norm
        # Penalti starvation DIHAPUS 29 Agustus: program TLS sekarang selalu
        # dipasang sebagai rotasi penuh 4 lengan dan selalu mulai dari fase 0,
        # sama seperti produksi -- tidak ada lengan yang bisa tidak kebagian
        # hijau, jadi penalti itu tidak punya kondisi pemicu yang sah lagi.
        reward = float(throughput_reward - queue_penalty - wait_penalty)
        metrics.update({"reward": reward, "throughput_interval": float(arrived), "queue_norm": queue_norm,
                        "wait_norm": wait_norm,
                        "throughput_reward": throughput_reward, "queue_penalty": queue_penalty,
                        "wait_penalty": wait_penalty})
        return self._observation(), reward, False, self.step_count >= self.episode_steps, metrics

    def _metrics(self) -> dict[str, float]:
        vehicles = list(self.connection.vehicle.getIDList()) if self.connection else []
        waiting = sum(float(self.connection.vehicle.getAccumulatedWaitingTime(v)) for v in vehicles) if self.connection else 0.0
        queue = sum(self.connection.edge.getLastStepHaltingNumber(EDGE_HULU[a]) + self.connection.edge.getLastStepHaltingNumber(EDGE_MASUK[a]) for a in FIXED_CYCLE_ORDER) if self.connection else 0
        arrived = float(self.connection.simulation.getArrivedNumber()) if self.connection else 0.0
        return {"vehicles": float(len(vehicles)), "queue": float(queue), "waiting": waiting, "arrived": arrived}

    def _observation(self) -> np.ndarray:
        state = self._traffic_state()
        return np.asarray(
            build_ppo_observation(
                state,
                current_phase=self.current_phase,
                current_green_seconds=self.current_green,
            ),
            dtype=np.float32,
        )

    def _traffic_state(self) -> TrafficState:
        approaches: list[ApproachState] = []
        for approach in FIXED_CYCLE_ORDER:
            edges = (EDGE_HULU[approach], EDGE_MASUK[approach])
            queue = sum(self.connection.edge.getLastStepHaltingNumber(e) for e in edges)
            density = sum(self.connection.edge.getLastStepVehicleNumber(e) for e in edges)
            speeds = [self.connection.edge.getLastStepMeanSpeed(e) for e in edges]
            speed_kmh = max(0.0, sum(speeds) / len(speeds) * 3.6)
            approaches.append(ApproachState(
                approach=approach,
                volume=int(self.recent_crossings[approach]),
                queueLengthVeh=int(queue),
                queueLengthMEst=float(queue) * METERS_PER_QUEUED_VEHICLE,
                densityIndex=float(density),
                avgSpeedKmh=float(speed_kmh),
            ))
        window_end = datetime.now(timezone.utc)
        return TrafficState(
            intersectionId="simpang4-pingit",
            windowStart=window_end - timedelta(seconds=FEATURE_WINDOW_SECONDS),
            windowEnd=window_end,
            approaches=approaches,
        )

    def rule_based_action(self) -> np.ndarray:
        """Baseline pembanding: durasi hijau dari RuleBasedEngine asli.

        Memakai recommend_cycle() saja -- itu yang benar-benar dipakai
        produksi (SignalService) untuk menentukan durasi keempat lengan.
        recommend() (pemilihan satu lengan pemenang) sengaja TIDAK dipakai
        lagi di sini sejak 29 Agustus, karena env tidak lagi memberi PPO
        maupun baseline kendali atas urutan fase.
        """
        cycle = self.rule_based_engine.recommend_cycle(
            self._traffic_state(), currentPhase=self.current_phase
        )
        green_by_approach = {phase.approach: phase.greenSeconds for phase in cycle.phases}
        green_indexes = [
            min(range(len(GREEN_OPTIONS)), key=lambda index: abs(GREEN_OPTIONS[index] - green_by_approach[approach]))
            for approach in FIXED_CYCLE_ORDER
        ]
        return np.asarray(green_indexes, dtype=np.int64)

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None
