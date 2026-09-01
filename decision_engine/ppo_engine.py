from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Protocol, Sequence

from app.schemas.traffic import TrafficState

from .rule_based_engine import (
    ApproachPhase,
    CyclePlan,
    FIXED_CYCLE_ORDER,
    MAX_GREEN_SECONDS,
    MIN_GREEN_SECONDS,
    Recommendation,
    RuleBasedEngine,
    YELLOW_SECONDS,
)
from .ppo_features import build_ppo_observation
from .ppo_features import OBSERVATION_SIZE

logger = logging.getLogger(__name__)

PPO_MODEL_ENV = "SMARTTWIN_PPO_MODEL_PATH"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "smarttwin_ppo.zip"
GREEN_STEP_SECONDS = 5
GREEN_OPTIONS = tuple(range(MIN_GREEN_SECONDS, MAX_GREEN_SECONDS + 1, GREEN_STEP_SECONDS))


class PPOModel(Protocol):
    def predict(self, observation: Sequence[float], deterministic: bool = True) -> Any:
        ...


class PPOEngine:
    """PPO opt-in dengan RuleBasedEngine sebagai fallback wajib.

    Action space yang diharapkan: ``MultiDiscrete([10, 10, 10, 10])`` --
    empat durasi hijau (utara, timur, selatan, barat) sesuai urutan
    FIXED_CYCLE_ORDER. PPO TIDAK memilih urutan/fase awal; rotasi sudah
    ditetapkan sistem dan selalu mulai dari fase 0, sama seperti produksi.
    Item pertama memilih approach prioritas; empat item berikutnya memilih
    green-time north/east/south/west dari GREEN_OPTIONS (15..60, step 5).

    Checkpoint Stable-Baselines3 hanya dimuat bila mode PPO diaktifkan. Dengan
    demikian dependency/model PPO tidak menjadi syarat agar demo tetap hidup.
    """

    def __init__(
        self,
        *,
        model: PPOModel | None = None,
        model_path: str | Path | None = None,
        fallback: RuleBasedEngine | None = None,
    ) -> None:
        self.fallback = fallback or RuleBasedEngine()
        configured_path = Path(
            model_path or os.getenv(PPO_MODEL_ENV, str(DEFAULT_MODEL_PATH))
        )
        if not configured_path.is_absolute():
            configured_path = Path(__file__).resolve().parents[1] / configured_path
        self.model_path = configured_path
        self.model = model
        self.load_error: str | None = None

        if self.model is None:
            self.model = self._load_model()

    @property
    def available(self) -> bool:
        return self.model is not None

    def _load_model(self) -> PPOModel | None:
        if not self.model_path.exists():
            self.load_error = f"checkpoint tidak ditemukan: {self.model_path}"
            return None

        try:
            from stable_baselines3 import PPO

            model = PPO.load(str(self.model_path))
            self._validate_model_contract(model)
            return model
        except Exception as exc:
            self.load_error = f"checkpoint gagal dimuat: {type(exc).__name__}: {exc}"
            logger.warning("PPO tidak tersedia, memakai rule-based: %s", self.load_error)
            return None

    @staticmethod
    def _validate_model_contract(model: PPOModel) -> None:
        observation_space = getattr(model, "observation_space", None)
        observation_shape = getattr(observation_space, "shape", None)
        if observation_shape != (OBSERVATION_SIZE,):
            raise ValueError(
                "observation space checkpoint tidak kompatibel: "
                f"diharapkan {(OBSERVATION_SIZE,)}, diterima {observation_shape}"
            )

        action_space = getattr(model, "action_space", None)
        nvec = getattr(action_space, "nvec", None)
        if nvec is None or not hasattr(nvec, "tolist"):
            raise ValueError("action space checkpoint bukan MultiDiscrete")
        action_sizes = [int(value) for value in nvec.tolist()]
        expected = [len(GREEN_OPTIONS)] * len(FIXED_CYCLE_ORDER)
        if action_sizes != expected:
            raise ValueError(
                "action space checkpoint tidak kompatibel: "
                f"diharapkan {expected}, diterima {action_sizes}"
            )

    def build_observation(
        self,
        state: TrafficState,
        *,
        current_phase: str,
        current_green_seconds: int,
        forecast: dict[str, Any] | None = None,
        forecast_weight: float = 0.3,
    ) -> list[float]:
        """Bentuk 21 fitur ternormalisasi dengan urutan yang stabil.

        20 fitur traffic = 4 approach x (volume, queue kendaraan, queue meter,
        density, speed), ditambah one-hot fase aktif (4) dan green saat ini (1).
        Forecast dibaurkan lebih dahulu memakai implementasi yang sama dengan
        RuleBasedEngine agar training dan fallback membaca state yang konsisten.
        """
        projected = self.fallback.apply_forecast(
            state, forecast, forecastWeight=forecast_weight
        )
        return build_ppo_observation(
            projected,
            current_phase=current_phase,
            current_green_seconds=current_green_seconds,
        )

    @staticmethod
    def _flatten_action(raw_action: Any) -> list[int]:
        if isinstance(raw_action, tuple):
            raw_action = raw_action[0]
        if hasattr(raw_action, "tolist"):
            raw_action = raw_action.tolist()
        while isinstance(raw_action, list) and len(raw_action) == 1 and isinstance(raw_action[0], list):
            raw_action = raw_action[0]
        if not isinstance(raw_action, (list, tuple)):
            raise ValueError("action PPO bukan list")
        return [int(value) for value in raw_action]

    def _predict_action(self, observation: list[float]) -> tuple[str, dict[str, int]]:
        if self.model is None:
            raise RuntimeError(self.load_error or "model PPO tidak tersedia")

        action = self._flatten_action(
            self.model.predict(observation, deterministic=True)
        )
        if len(action) != len(FIXED_CYCLE_ORDER):
            raise ValueError(
                f"action PPO wajib {len(FIXED_CYCLE_ORDER)} item, diterima {len(action)}"
            )
        if any(not 0 <= value < len(GREEN_OPTIONS) for value in action):
            raise ValueError("index green-time PPO di luar rentang")

        green_by_approach = {
            approach: GREEN_OPTIONS[action[index]]
            for index, approach in enumerate(FIXED_CYCLE_ORDER)
        }
        # PPO tidak lagi memilih urutan fase (rotasi sudah tetap
        # FIXED_CYCLE_ORDER, sama seperti produksi -- lihat ppo_env
        # _set_action). recommendedPhase diturunkan dari keluaran PPO
        # sendiri: lengan yang DIBERI hijau paling panjang, yaitu lengan
        # yang menurut model paling butuh. Kalau seri, urutan rotasi jadi
        # pemecahnya supaya hasilnya deterministik.
        selected = max(FIXED_CYCLE_ORDER, key=lambda a: (green_by_approach[a], -FIXED_CYCLE_ORDER.index(a)))
        return selected, green_by_approach

    @staticmethod
    def _fallback_source(result: Any, reason: str) -> Any:
        result.source = "ppo-fallback-rule-based"
        result.reason = f"PPO fallback ({reason}). {getattr(result, 'reason', '')}".strip()
        return result

    def recommend(
        self,
        state: TrafficState,
        currentGreenSeconds: int = 15,
        currentPhase: str = "north",
        forecast: dict[str, Any] | None = None,
        forecastWeight: float = 0.3,
    ) -> Recommendation:
        fallback_result = self.fallback.recommend(
            state,
            currentGreenSeconds=currentGreenSeconds,
            currentPhase=currentPhase,
            forecast=forecast,
            forecastWeight=forecastWeight,
        )
        try:
            observation = self.build_observation(
                state,
                current_phase=currentPhase,
                current_green_seconds=currentGreenSeconds,
                forecast=forecast,
                forecast_weight=forecastWeight,
            )
            selected, green_by_approach = self._predict_action(observation)
        except Exception as exc:
            return self._fallback_source(fallback_result, str(exc))

        return Recommendation(
            recommendedPhase=selected,
            recommendedGreenSeconds=green_by_approach[selected],
            currentGreenSeconds=int(currentGreenSeconds),
            currentPhase=str(currentPhase),
            confidence=0.5,
            expectedDelayReductionPercent=0.0,
            source="ppo",
            reason=(
                "PPO memilih fase dan durasi dari TrafficState serta forecast. "
                "Nilai dampak tetap 0 sampai evaluasi SUMO membuktikan perbaikannya."
            ),
        )

    def recommend_cycle(
        self,
        state: TrafficState,
        currentPhase: str = "north",
        forecast: dict[str, Any] | None = None,
        forecastWeight: float = 0.3,
    ) -> CyclePlan:
        fallback_result = self.fallback.recommend_cycle(
            state,
            currentPhase=currentPhase,
            forecast=forecast,
            forecastWeight=forecastWeight,
        )
        try:
            observation = self.build_observation(
                state,
                current_phase=currentPhase,
                current_green_seconds=next(
                    (
                        phase.greenSeconds
                        for phase in fallback_result.phases
                        if phase.approach == currentPhase
                    ),
                    MIN_GREEN_SECONDS,
                ),
                forecast=forecast,
                forecast_weight=forecastWeight,
            )
            _selected, green_by_approach = self._predict_action(observation)
        except Exception as exc:
            fallback_result.source = "ppo-fallback-rule-based"
            return fallback_result

        green_cycle = sum(green_by_approach.values())
        total_cycle = green_cycle + YELLOW_SECONDS * len(FIXED_CYCLE_ORDER)
        phases = [
            ApproachPhase(
                approach=approach,
                greenSeconds=green_by_approach[approach],
                demandScore=0.0,
                yellowSeconds=YELLOW_SECONDS,
                redSeconds=total_cycle - green_by_approach[approach] - YELLOW_SECONDS,
            )
            for approach in FIXED_CYCLE_ORDER
        ]
        return CyclePlan(
            phases=phases,
            cycleLengthSeconds=green_cycle,
            currentPhase=currentPhase,
            source="ppo",
            totalCycleSeconds=total_cycle,
        )
