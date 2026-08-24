from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

MIN_GREEN_SECONDS = 15
MAX_GREEN_SECONDS = 60

# Bobot demand.
# Queue dibuat paling penting karena queue menunjukkan kendaraan
# yang sedang benar-benar menunggu di persimpangan.
VOLUME_WEIGHT = 0.30
QUEUE_WEIGHT = 0.50
DENSITY_WEIGHT = 0.20


# ============================================================
# RECOMMENDATION RESULT
# ============================================================

@dataclass
class Recommendation:
    """
    Hasil keputusan Rule-Based Engine.

    Field dibuat mengikuti kebutuhan:
        - simulation/run_tls_simulation.py
        - backend tests
        - simulation result writer
    """

    recommendedPhase: str
    recommendedGreenSeconds: int

    currentGreenSeconds: int
    currentPhase: str

    confidence: float
    expectedDelayReductionPercent: float

    source: str
    reason: str


# ============================================================
# RULE-BASED ENGINE
# ============================================================

class RuleBasedEngine:
    """
    Rule-Based Decision Engine untuk SmartTwin.

    Input:
        TrafficState

    Output:
        Recommendation

    Prinsip:
        1. Hitung demand setiap approach.
        2. Pilih approach dengan demand tertinggi.
        3. Hitung green time berdasarkan demand.
        4. Berikan confidence.
        5. Berikan alasan keputusan.

    Method recommend() sengaja menerima dua nama parameter:

        state=
        trafficState=

    supaya kompatibel dengan pipeline lama maupun baru.
    """

    # ========================================================
    # DEMAND SCORE
    # ========================================================

    def demand_score(
        self,
        approach: Any,
    ) -> float:
        """
        Menghitung demand score satu approach.

        Formula:

            demand =
                0.30 * volumeScore
                + 0.50 * queueScore
                + 0.20 * densityScore

        Normalisasi dibuat sederhana dan stabil untuk rule-based
        system sehingga tidak bergantung pada dataset tertentu.
        """

        volume = self._number(
            self._get(
                approach,
                "volume",
                0,
            )
        )

        queue = self._number(
            self._get(
                approach,
                "queueLengthVeh",
                self._get(
                    approach,
                    "queue",
                    0,
                ),
            )
        )

        density = self._number(
            self._get(
                approach,
                "densityIndex",
                self._get(
                    approach,
                    "density",
                    0,
                ),
            )
        )

        # ----------------------------------------------------
        # Normalisasi
        # ----------------------------------------------------
        #
        # Volume:
        # 0 kendaraan -> 0
        # 50+ kendaraan -> 1
        #
        # Queue:
        # 0 kendaraan -> 0
        # 30+ kendaraan -> 1
        #
        # Density:
        # 0 -> 0
        # 10+ -> 1
        #
        volume_score = self._normalize(
            volume,
            50.0,
        )

        queue_score = self._normalize(
            queue,
            30.0,
        )

        density_score = self._normalize(
            density,
            10.0,
        )

        score = (
            VOLUME_WEIGHT * volume_score
            + QUEUE_WEIGHT * queue_score
            + DENSITY_WEIGHT * density_score
        )

        return round(
            score,
            4,
        )

    # --------------------------------------------------------
    # ALIAS
    # --------------------------------------------------------

    def calculate_demand_score(
        self,
        approach: Any,
    ) -> float:
        """
        Alias supaya kompatibel dengan implementasi/test lama.
        """

        return self.demand_score(
            approach
        )

    # ========================================================
    # GREEN TIME
    # ========================================================

    def green_time(
        self,
        demandScore: float,
    ) -> int:
        """
        Menentukan durasi green berdasarkan demand.

        Demand 0.0  -> minimum green
        Demand 1.0  -> maximum green

        Formula linear:
            15 + demand * (60 - 15)
        """

        try:
            demand = float(
                demandScore
            )
        except (
            TypeError,
            ValueError,
        ):
            demand = 0.0

        demand = max(
            0.0,
            min(
                1.0,
                demand,
            ),
        )

        duration = (
            MIN_GREEN_SECONDS
            + demand
            * (
                MAX_GREEN_SECONDS
                - MIN_GREEN_SECONDS
            )
        )

        return int(
            round(duration)
        )

    # --------------------------------------------------------
    # ALIAS
    # --------------------------------------------------------

    def calculate_green_time(
        self,
        demandScore: float,
    ) -> int:
        """
        Alias untuk kompatibilitas.
        """

        return self.green_time(
            demandScore
        )

    # ========================================================
    # RECOMMEND
    # ========================================================

    def recommend(
        self,
        state: Any = None,
        currentGreenSeconds: int = 15,
        currentPhase: str = "south",
        trafficState: Any = None,
    ) -> Recommendation:
        """
        Menghasilkan rekomendasi adaptive traffic light.

        Bisa dipanggil dengan:

            engine.recommend(
                state=trafficState,
                currentGreenSeconds=15,
                currentPhase="south",
            )

        maupun:

            engine.recommend(
                trafficState=trafficState,
                currentGreenSeconds=15,
                currentPhase="south",
            )

        Ini penting supaya seluruh pipeline lama dan baru
        tetap kompatibel.
        """

        # ====================================================
        # RESOLVE TRAFFIC STATE
        # ====================================================

        if state is None:
            state = trafficState

        if state is None:
            raise ValueError(
                "TrafficState tidak boleh kosong."
            )

        # ====================================================
        # GET APPROACHES
        # ====================================================

        approaches = self._get(
            state,
            "approaches",
            None,
        )

        if approaches is None:
            raise ValueError(
                "TrafficState tidak memiliki approaches."
            )

        approaches = list(
            approaches
        )

        if len(approaches) == 0:
            raise ValueError(
                "TrafficState tidak memiliki approach."
            )

        # ====================================================
        # CALCULATE DEMAND
        # ====================================================

        scoredApproaches: list[
            tuple[Any, float]
        ] = []

        for approach in approaches:

            score = self.demand_score(
                approach
            )

            scoredApproaches.append(
                (
                    approach,
                    score,
                )
            )

        # ====================================================
        # SELECT HIGHEST DEMAND
        # ====================================================

        selectedApproach, selectedScore = max(
            scoredApproaches,
            key=lambda item: item[1],
        )

        # ====================================================
        # APPROACH NAME
        # ====================================================

        recommendedPhase = self._approach_name(
            selectedApproach
        )

        # ====================================================
        # GREEN TIME
        # ====================================================

        recommendedGreenSeconds = (
            self.green_time(
                selectedScore
            )
        )

        # ====================================================
        # CURRENT GREEN
        # ====================================================

        try:
            currentGreen = int(
                currentGreenSeconds
            )
        except (
            TypeError,
            ValueError,
        ):
            currentGreen = MIN_GREEN_SECONDS

        # ====================================================
        # CONFIDENCE
        # ====================================================

        confidence = self._calculate_confidence(
            scoredApproaches
        )

        # ====================================================
        # EXPECTED DELAY REDUCTION
        # ====================================================

        expectedDelayReductionPercent = round(
            selectedScore * 100.0,
            2,
        )

        # ====================================================
        # SELECTED METRICS
        # ====================================================

        volume = self._number(
            self._get(
                selectedApproach,
                "volume",
                0,
            )
        )

        queue = self._number(
            self._get(
                selectedApproach,
                "queueLengthVeh",
                self._get(
                    selectedApproach,
                    "queue",
                    0,
                ),
            )
        )

        density = self._number(
            self._get(
                selectedApproach,
                "densityIndex",
                self._get(
                    selectedApproach,
                    "density",
                    0,
                ),
            )
        )

        # ====================================================
        # REASON
        # ====================================================

        reason = (
            f"Approach {recommendedPhase} memiliki "
            f"demand tertinggi dengan score "
            f"{selectedScore:.2f}. "
            f"Volume={self._format_number(volume)}, "
            f"queue={self._format_number(queue)} kendaraan, "
            f"density={density:.3f}. "
            f"Direkomendasikan green "
            f"{recommendedGreenSeconds} detik."
        )

        # ====================================================
        # RESULT
        # ====================================================

        return Recommendation(
            recommendedPhase=recommendedPhase,
            recommendedGreenSeconds=(
                recommendedGreenSeconds
            ),
            currentGreenSeconds=currentGreen,
            currentPhase=str(
                currentPhase
            ),
            confidence=confidence,
            expectedDelayReductionPercent=(
                expectedDelayReductionPercent
            ),
            source="rule-based",
            reason=reason,
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    def _calculate_confidence(
        self,
        scoredApproaches: list[
            tuple[Any, float]
        ],
    ) -> float:
        """
        Confidence berdasarkan seberapa jelas approach
        terbaik dibandingkan approach lainnya.

        Kalau demand terbaik jauh lebih tinggi:
            confidence tinggi.

        Kalau semua demand hampir sama:
            confidence rendah.
        """

        scores = [
            score
            for _, score
            in scoredApproaches
        ]

        if not scores:
            return 0.0

        highest = max(
            scores
        )

        if len(scores) == 1:
            return round(
                highest,
                2,
            )

        sortedScores = sorted(
            scores,
            reverse=True,
        )

        secondHighest = sortedScores[1]

        margin = (
            highest
            - secondHighest
        )

        confidence = (
            0.5 * highest
            + 0.5 * margin
        )

        return round(
            max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            ),
            2,
        )

    # ========================================================
    # APPROACH NAME
    # ========================================================

    @staticmethod
    def _approach_name(
        approach: Any,
    ) -> str:
        """
        Mengambil nama approach dari:

            "north"

        atau Enum:

            Approach.NORTH

        atau object:

            approach.approach
        """

        value = approach

        if not isinstance(
            approach,
            str,
        ):
            value = getattr(
                approach,
                "approach",
                None,
            )

            if value is None:
                value = getattr(
                    approach,
                    "name",
                    None,
                )

        if value is None:
            return "unknown"

        # Enum value
        enumValue = getattr(
            value,
            "value",
            None,
        )

        if enumValue is not None:
            value = enumValue

        return str(
            value
        ).lower()

    # ========================================================
    # GENERIC GETTER
    # ========================================================

    @staticmethod
    def _get(
        obj: Any,
        field: str,
        default: Any = None,
    ) -> Any:

        if obj is None:
            return default

        if isinstance(
            obj,
            dict,
        ):
            return obj.get(
                field,
                default,
            )

        return getattr(
            obj,
            field,
            default,
        )

    # ========================================================
    # NUMBER
    # ========================================================

    @staticmethod
    def _number(
        value: Any,
    ) -> float:

        if value is None:
            return 0.0

        try:
            return float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    # ========================================================
    # NORMALIZE
    # ========================================================

    @staticmethod
    def _normalize(
        value: float,
        maximum: float,
    ) -> float:

        if maximum <= 0:
            return 0.0

        result = (
            value
            / maximum
        )

        return max(
            0.0,
            min(
                1.0,
                result,
            ),
        )

    # ========================================================
    # FORMAT NUMBER
    # ========================================================

    @staticmethod
    def _format_number(
        value: float,
    ) -> str:

        if float(value).is_integer():
            return str(
                int(value)
            )

        return f"{value:.2f}"