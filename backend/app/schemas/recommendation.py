from datetime import datetime
from typing import Dict

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    intersection_id: str
    simulation_horizon_minutes: int = Field(
        default=15,
        ge=1,
        le=120,
    )


class RecommendationMetrics(BaseModel):
    queue_length: float = Field(ge=0)
    vehicle_count: float = Field(ge=0)
    average_speed_kmh: float = Field(ge=0)


class SignalRecommendation(BaseModel):
    intersection_id: str
    timestamp: datetime

    recommended_phase: str
    recommended_green_seconds: int = Field(ge=0)
    current_green_seconds: int = Field(ge=0)

    expected_delay_reduction_percent: float

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str

    metrics: RecommendationMetrics

    source: str = "pending"


class RecommendationResponse(BaseModel):
    success: bool = True

    recommendation: SignalRecommendation