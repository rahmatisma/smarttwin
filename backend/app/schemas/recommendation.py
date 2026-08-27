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


class CyclePlanSchema(
    CamelCaseModel
):

    phases: list[ApproachPhaseSchema]

    cycleLengthSeconds: int = Field(
        ge=0
    )

    currentPhase: str

    source: str = "rule-based"


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

    candidateId: str | None = None


# ============================================================
# RESPONSE
# ============================================================

class RecommendationResponse(
    CamelCaseModel
):

    success: bool = True

    recommendation: SignalRecommendation
