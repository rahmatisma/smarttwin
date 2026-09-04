from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# BASE CONFIG
# ============================================================

class CamelCaseModel(BaseModel):

    model_config = ConfigDict(
        populate_by_name=True,
    )


# ============================================================
# REQUEST
# ============================================================

class RecommendationRequest(
    CamelCaseModel
):

    intersectionId: str

    simulationHorizonMinutes: int = Field(
        default=15,
        ge=1,
        le=120,
    )


# ============================================================
# METRICS
# ============================================================

class RecommendationMetrics(
    CamelCaseModel
):

    queueLength: float = Field(
        ge=0
    )

    vehicleCount: float = Field(
        ge=0
    )

    averageSpeedKmh: float = Field(
        ge=0
    )


# ============================================================
# CYCLE PLAN (rekomendasi 4 lengan sekaligus, rotasi tetap)
# ============================================================

class ApproachPhaseSchema(
    CamelCaseModel
):

    approach: str

    greenSeconds: int = Field(
        ge=0
    )

    demandScore: float = Field(
        ge=0.0,
        le=1.0,
    )

    yellowSeconds: int = Field(default=4, ge=0)

    redSeconds: int = Field(default=0, ge=0)


class CyclePlanSchema(
    CamelCaseModel
):

    phases: list[ApproachPhaseSchema]

    cycleLengthSeconds: int = Field(
        ge=0
    )

    currentPhase: str

    source: str = "rule-based"

    totalCycleSeconds: int = Field(default=0, ge=0)


# ============================================================
# SIGNAL RECOMMENDATION
# ============================================================

class SignalRecommendation(
    CamelCaseModel
):

    intersectionId: str

    timestamp: datetime

    recommendedPhase: str

    recommendedGreenSeconds: int = Field(
        ge=0
    )

    currentGreenSeconds: int = Field(
        ge=0
    )

    expectedDelayReductionPercent: float

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str

    metrics: RecommendationMetrics

    source: str = "pending"

    cyclePlan: CyclePlanSchema | None = None

    avgDelaySeconds: float | None = Field(default=None, ge=0)

    avgQueueLengthM: float | None = Field(default=None, ge=0)

    los: str | None = None

    # LOS HCM per lengan (north/south/east/west -> "A".."F"). HCM menilai
    # LOS per lengan; `los` di atas adalah rata-rata seluruh simpang yang
    # bisa menyembunyikan satu lengan macet. Lengan tanpa data -> null.
    losByApproach: dict[str, str | None] | None = None

    # Rata-rata delay (detik) per lengan, sumber angka losByApproach.
    delayByApproachSeconds: dict[str, float | None] | None = None

    candidateId: str | None = None


# ============================================================
# RESPONSE
# ============================================================

class RecommendationResponse(
    CamelCaseModel
):

    success: bool = True

    recommendation: SignalRecommendation
