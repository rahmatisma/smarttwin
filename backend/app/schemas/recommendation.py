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


# ============================================================
# RESPONSE
# ============================================================

class RecommendationResponse(
    CamelCaseModel
):

    success: bool = True

    recommendation: SignalRecommendation