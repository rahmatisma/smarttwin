from __future__ import annotations

from typing import Any, Iterable

from app.schemas.traffic import (
    ApproachState,
    TrafficState,
)


# ============================================================
# CONFIGURATION
# ============================================================

MIN_GREEN_SECONDS = 15
MAX_GREEN_SECONDS = 60

# Nilai referensi untuk normalisasi demand.
#
# Artinya:
# volume 30 kendaraan -> skor volume 1.0
# queue 20 kendaraan  -> skor queue 1.0
# density 10 kendaraan -> skor density 1.0
#
# Kita gunakan MAX dari tiga komponen supaya satu indikator
# yang sangat tinggi tetap bisa membuat approach menjadi prioritas.
REFERENCE_VOLUME = 30.0
REFERENCE_QUEUE = 20.0
REFERENCE_DENSITY = 10.0


# ============================================================
# RECOMMENDATION MODEL
# ============================================================

try:
    from pydantic import BaseModel, Field

    class Recommendation(BaseModel):
        """
        Hasil rekomendasi dari Decision Engine.
        """

        recommendedPhase: str
        recommendedGreenSeconds: int

        currentGreenSeconds: int
        currentPhase: str

        confidence: float = Field(default=0.0)
        expectedDelayReductionPercent: float = Field(default=0.0)

        source: str = "rule-based"
        reason: str = ""

except ImportError:
    # Fallback supaya module tetap bisa di-import jika
    # dependency pydantic belum tersedia.
    from dataclasses import dataclass

    @dataclass
    class Recommendation:
        recommendedPhase: str
        recommendedGreenSeconds: int
        currentGreenSeconds: int
        currentPhase: str
        confidence: float = 0.0
        expectedDelayReductionPercent: float = 0.0
        source: str = "rule-based"
        reason: str = ""


# ============================================================
# RULE BASED ENGINE
# ============================================================

class RuleBasedEngine:
    """
    Rule-Based Decision Engine untuk SmartTwin.

    Fungsi utama:

        TrafficState
              ↓
        Demand Score setiap approach
              ↓
        Approach dengan demand tertinggi
              ↓
        Green time 15 - 60 detik
              ↓
        Recommendation

    Engine ini sengaja dibuat deterministic agar:
    - mudah dites
    - mudah dijelaskan ke juri
    - tidak membutuhkan model ML
    - dapat menjadi fallback ketika PPO belum tersedia
    """

    def __init__(
        self,
        min_green_seconds: int = MIN_GREEN_SECONDS,
        max_green_seconds: int = MAX_GREEN_SECONDS,
    ) -> None:

        self.min_green_seconds = int(min_green_seconds)
        self.max_green_seconds = int(max_green_seconds)

        if self.min_green_seconds <= 0:
            raise ValueError(
                "min_green_seconds harus lebih besar dari 0"
            )

        if self.max_green_seconds < self.min_green_seconds:
            raise ValueError(
                "max_green_seconds harus >= min_green_seconds"
            )

    # ========================================================
    # DEMAND SCORE
    # ========================================================

    def calculate_demand_score(
        self,
        approach: ApproachState,
    ) -> float:
        """
        Menghitung demand score approach.

        Komponen:

        volume
        queueLengthVeh
        densityIndex

        Setiap komponen dinormalisasi ke 0..1.

        Demand final menggunakan nilai maksimum dari
        ketiga indikator agar kondisi ekstrem tidak
        tertutup oleh indikator lain.

        Contoh:

        volume=30
        queue=20
        density=1

        volume_score  = 30 / 30 = 1
        queue_score   = 20 / 20 = 1
        density_score = 1 / 10  = 0.1

        demand = max(1, 1, 0.1)
               = 1.0
        """

        volume = self._safe_float(
            getattr(approach, "volume", 0)
        )

        queue = self._safe_float(
            getattr(approach, "queueLengthVeh", 0)
        )

        density = self._safe_float(
            getattr(approach, "densityIndex", 0)
        )

        volume_score = self._normalize(
            volume,
            REFERENCE_VOLUME,
        )

        queue_score = self._normalize(
            queue,
            REFERENCE_QUEUE,
        )

        density_score = self._normalize(
            density,
            REFERENCE_DENSITY,
        )

        demand_score = max(
            volume_score,
            queue_score,
            density_score,
        )

        return round(
            self._clamp(demand_score, 0.0, 1.0),
            2,
        )

    # ========================================================
    # BACKWARD COMPATIBILITY
    # ========================================================

    def _calculateDemandScore(
        self,
        approach: ApproachState,
    ) -> float:
        """
        Compatibility method.

        Test dan beberapa bagian project lama menggunakan:
            _calculateDemandScore()

        Jangan dihapus.
        """

        return self.calculate_demand_score(approach)

    # ========================================================
    # GREEN TIME
    # ========================================================

    def calculate_green_time(
        self,
        demand_score: float,
    ) -> int:
        """
        Mengubah demand score menjadi green duration.

        Formula linear:

            green =
                MIN_GREEN
                +
                demand * (MAX_GREEN - MIN_GREEN)

        Dengan:

            demand=0.0 -> 15 detik
            demand=0.5 -> 37.5 -> 38 detik
            demand=1.0 -> 60 detik
        """

        demand = self._clamp(
            self._safe_float(demand_score),
            0.0,
            1.0,
        )

        green = (
            self.min_green_seconds
            +
            demand
            * (
                self.max_green_seconds
                - self.min_green_seconds
            )
        )

        return int(round(green))

    # ========================================================
    # BACKWARD COMPATIBILITY
    # ========================================================

    def _calculateGreenTime(
        self,
        demand_score: float,
    ) -> int:
        """
        Compatibility method untuk test/project lama.
        """

        return self.calculate_green_time(demand_score)

    # ========================================================
    # RECOMMEND
    # ========================================================

    def recommend(
        self,
        state: TrafficState,
        currentGreenSeconds: int = 15,
        currentPhase: str = "north",
    ) -> Recommendation:
        """
        Menghasilkan rekomendasi traffic signal.

        Parameter sengaja menggunakan camelCase karena
        dipakai oleh integration test dan simulation runner.
        """

        if state is None:
            raise ValueError(
                "TrafficState tidak boleh None"
            )

        approaches = getattr(
            state,
            "approaches",
            None,
        )

        if approaches is None:
            raise ValueError(
                "TrafficState tidak memiliki approach"
            )

        approaches = list(approaches)

        if len(approaches) == 0:
            raise ValueError(
                "TrafficState tidak memiliki approach"
            )

        # ----------------------------------------------------
        # HITUNG DEMAND SETIAP APPROACH
        # ----------------------------------------------------

        scored: list[tuple[ApproachState, float]] = []

        for approach in approaches:

            score = self._calculateDemandScore(
                approach
            )

            scored.append(
                (
                    approach,
                    score,
                )
            )

        # ----------------------------------------------------
        # PILIH DEMAND TERTINGGI
        # ----------------------------------------------------

        selected_approach, selected_score = max(
            scored,
            key=lambda item: item[1],
        )

        selected_phase = self._approach_to_string(
            selected_approach
        )

        # ----------------------------------------------------
        # GREEN TIME
        # ----------------------------------------------------

        green_seconds = self._calculateGreenTime(
            selected_score
        )

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        confidence = self._calculate_confidence(
            scored
        )

        # ----------------------------------------------------
        # EXPECTED DELAY REDUCTION
        # ----------------------------------------------------

        expected_delay_reduction = round(
            selected_score * 50.0,
            2,
        )

        # ----------------------------------------------------
        # TRAFFIC INFORMATION
        # ----------------------------------------------------

        volume = self._safe_float(
            getattr(
                selected_approach,
                "volume",
                0,
            )
        )

        queue = self._safe_float(
            getattr(
                selected_approach,
                "queueLengthVeh",
                0,
            )
        )

        density = self._safe_float(
            getattr(
                selected_approach,
                "densityIndex",
                0,
            )
        )

        # ----------------------------------------------------
        # REASON
        # ----------------------------------------------------

        reason = (
            f"Approach {selected_phase} memiliki "
            f"demand tertinggi dengan score "
            f"{selected_score:.2f}. "
            f"Volume={int(volume)}, "
            f"queue={int(queue)} kendaraan, "
            f"density={density:.3f}. "
            f"Direkomendasikan green "
            f"{green_seconds} detik."
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        return Recommendation(
            recommendedPhase=selected_phase,
            recommendedGreenSeconds=green_seconds,

            currentGreenSeconds=int(
                currentGreenSeconds
            ),

            currentPhase=str(
                currentPhase
            ),

            confidence=confidence,

            expectedDelayReductionPercent=(
                expected_delay_reduction
            ),

            source="rule-based",

            reason=reason,
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    def _calculate_confidence(
        self,
        scored: Iterable[
            tuple[ApproachState, float]
        ],
    ) -> float:
        """
        Confidence berdasarkan seberapa jelas approach
        terbaik dibandingkan approach kedua.

        Jika hanya ada satu approach:
            confidence = score

        Jika beberapa:
            confidence = score_best - score_second

        Tetapi minimal tetap mempertimbangkan demand
        approach terbaik.
        """

        values = sorted(
            (
                score
                for _, score in scored
            ),
            reverse=True,
        )

        if not values:
            return 0.0

        best = values[0]

        if len(values) == 1:
            return round(
                best,
                2,
            )

        second = values[1]

        # Selisih dominasi.
        dominance = max(
            0.0,
            best - second,
        )

        # Gabungkan demand dan dominasi.
        confidence = (
            0.5 * best
            +
            0.5 * dominance
        )

        return round(
            self._clamp(
                confidence,
                0.0,
                1.0,
            ),
            2,
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float:

        try:

            if value is None:
                return 0.0

            result = float(value)

            if result != result:
                return 0.0

            return result

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:

        return max(
            minimum,
            min(
                maximum,
                value,
            ),
        )

    @classmethod
    def _normalize(
        cls,
        value: float,
        reference: float,
    ) -> float:

        if reference <= 0:
            return 0.0

        return cls._clamp(
            value / reference,
            0.0,
            1.0,
        )

    @staticmethod
    def _approach_to_string(
        approach: ApproachState,
    ) -> str:

        value = getattr(
            approach,
            "approach",
            "",
        )

        if hasattr(
            value,
            "value",
        ):
            value = value.value

        return str(value).lower()


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "RuleBasedEngine",
    "Recommendation",
]