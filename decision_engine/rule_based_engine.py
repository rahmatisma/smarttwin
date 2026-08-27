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
# CYCLE PLAN (rekomendasi 4 lengan sekaligus)
#
# Rotasi lampu di simpang ini TETAP (barat -> selatan -> timur ->
# utara -> barat, siklus real-world biasa) -- yang direkomendasikan
# BUKAN "lengan mana dapat giliran" (itu domain Recommendation di
# atas), tapi "berapa detik tiap lengan" dalam satu putaran siklus.
# ============================================================

FIXED_CYCLE_ORDER = ["west", "south", "east", "north"]

try:

    class ApproachPhase(BaseModel):
        approach: str
        greenSeconds: int
        demandScore: float = Field(default=0.0)

    class CyclePlan(BaseModel):
        phases: list[ApproachPhase]
        cycleLengthSeconds: int
        currentPhase: str
        source: str = "rule-based"

except NameError:
    # BaseModel tidak terdefinisi kalau blok pydantic di atas gagal
    # import -- pakai dataclass yang sama seperti Recommendation.
    from dataclasses import dataclass, field

    @dataclass
    class ApproachPhase:
        approach: str
        greenSeconds: int
        demandScore: float = 0.0

    @dataclass
    class CyclePlan:
        phases: list = field(default_factory=list)
        cycleLengthSeconds: int = 0
        currentPhase: str = "west"
        source: str = "rule-based"


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
        forecast: dict[str, Any] | None = None,
        forecastWeight: float = 0.5,
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

        decision_state = self.apply_forecast(
            state,
            forecast,
            forecastWeight=forecastWeight,
        )
        forecast_used = bool(
            (forecast or {}).get("approachForecasts")
        )

        approaches = getattr(
            decision_state,
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
            f"flowCrossing={int(volume)}, "
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

            source=(
                "rule-based+forecast"
                if forecast_used
                else "rule-based"
            ),

            reason=reason,
        )

    # ========================================================
    # RECOMMEND CYCLE (4 lengan sekaligus)
    # ========================================================

    def recommend_cycle(
        self,
        state: TrafficState,
        currentPhase: str = "west",
        forecast: dict[str, Any] | None = None,
        forecastWeight: float = 0.5,
    ) -> CyclePlan:
        """
        Rekomendasi durasi hijau untuk KE-4 lengan sekaligus, dalam
        urutan rotasi tetap FIXED_CYCLE_ORDER (barat-selatan-timur-
        utara). Beda dari recommend(): di sana cuma SATU lengan
        pemenang yang dapat durasi, di sini KE-4-nya dihitung, tiap
        lengan independen pakai calculate_demand_score() +
        calculate_green_time() yang sama persis dengan recommend()
        -- tidak ada rumus baru, cuma dipanggil 4x.

        Lengan yang tidak ada datanya di state (approaches tidak
        lengkap) dapat demandScore=0.0 dan greenSeconds minimum --
        bukan error, karena TrafficState di lapangan bisa saja belum
        punya semua 4 lengan pada suatu window.
        """

        if state is None:

            raise ValueError(
                "TrafficState tidak boleh None"
            )

        decision_state = self.apply_forecast(
            state,
            forecast,
            forecastWeight=forecastWeight,
        )
        forecast_used = bool(
            (forecast or {}).get("approachForecasts")
        )

        approaches = getattr(
            decision_state,
            "approaches",
            None,
        )

        if approaches is None:

            raise ValueError(
                "TrafficState tidak memiliki approach"
            )

        approach_by_name = {
            self._approach_to_string(approach): approach
            for approach in approaches
        }

        phases: list[ApproachPhase] = []

        for approach_name in FIXED_CYCLE_ORDER:

            approach = approach_by_name.get(
                approach_name
            )

            if approach is None:

                phases.append(
                    ApproachPhase(
                        approach=approach_name,
                        greenSeconds=self.min_green_seconds,
                        demandScore=0.0,
                    )
                )

                continue

            score = self._calculateDemandScore(
                approach
            )

            green_seconds = self._calculateGreenTime(
                score
            )

            phases.append(
                ApproachPhase(
                    approach=approach_name,
                    greenSeconds=green_seconds,
                    demandScore=score,
                )
            )

        return CyclePlan(
            phases=phases,
            cycleLengthSeconds=sum(
                phase.greenSeconds
                for phase in phases
            ),
            currentPhase=str(currentPhase),
            source=(
                "rule-based+forecast"
                if forecast_used
                else "rule-based"
            ),
        )

    def apply_forecast(
        self,
        state: TrafficState,
        forecast: dict[str, Any] | None,
        *,
        forecastWeight: float = 0.5,
    ) -> TrafficState:
        """Gabungkan state saat ini dengan horizon forecast terakhir.

        Fungsi ini opsional: tanpa forecast perilaku engine tetap identik.
        Bobot 0.5 membuat keputusan mempertimbangkan kondisi sekarang dan
        prediksi 60 detik ke depan secara seimbang.
        """

        if forecast is None:
            return state

        weight = self._clamp(float(forecastWeight), 0.0, 1.0)
        horizons = forecast.get("approachForecasts") or []
        if not horizons:
            return state

        predicted_approaches = horizons[-1].get("approaches") or []
        predicted_by_name = {
            str(item.get("approach", "")).lower(): item
            for item in predicted_approaches
        }

        projected_approaches = []
        for approach in state.approaches:
            name = self._approach_to_string(approach)
            predicted = predicted_by_name.get(name)
            if predicted is None:
                projected_approaches.append(approach)
                continue

            def blend(current: float, future: float) -> float:
                return (1.0 - weight) * current + weight * future

            current_volume = self._safe_float(
                getattr(approach, "volume", 0)
            )
            projected_volume = round(blend(
                current_volume,
                self._safe_float(predicted.get("vehicleCount", 0)),
            ))
            composition_scale = (
                projected_volume / current_volume
                if current_volume > 0
                else 1.0
            )

            updates = {
                "volume": projected_volume,
                "queueLengthVeh": round(blend(
                    self._safe_float(getattr(approach, "queueLengthVeh", 0)),
                    self._safe_float(predicted.get("queueLengthVeh", 0)),
                )),
                "queueLengthMEst": max(0.0, blend(
                    self._safe_float(getattr(approach, "queueLengthMEst", 0)),
                    self._safe_float(predicted.get("queueLengthMEst", 0)),
                )),
                "densityIndex": self._clamp(blend(
                    self._safe_float(getattr(approach, "densityIndex", 0)),
                    self._safe_float(predicted.get("densityIndex", 0)),
                ), 0.0, 1.0),
            }
            for count_field in (
                "carCount",
                "motorcycleCount",
                "busCount",
                "truckCount",
            ):
                updates[count_field] = max(
                    0,
                    round(
                        self._safe_float(getattr(approach, count_field, 0))
                        * composition_scale
                    ),
                )
            projected_approaches.append(approach.model_copy(update=updates))

        return state.model_copy(update={"approaches": projected_approaches})

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
