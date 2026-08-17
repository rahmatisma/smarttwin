from datetime import datetime, timezone

from app.schemas.recommendation import (
    RecommendationMetrics,
    RecommendationRequest,
    RecommendationResponse,
    SignalRecommendation,
)


class RecommendationService:

    def get_recommendation(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:

        recommendation = SignalRecommendation(
            intersection_id=request.intersection_id,
            timestamp=datetime.now(timezone.utc),

            recommended_phase="NS_GREEN",

            recommended_green_seconds=40,

            current_green_seconds=35,

            expected_delay_reduction_percent=8.5,

            confidence=0.75,

            reason=(
                "Antrean berada pada tingkat sedang. "
                "Green time disesuaikan secara moderat."
            ),

            metrics=RecommendationMetrics(
                queue_length=17,
                vehicle_count=42,
                average_speed_kmh=28.5,
            ),

            source="pending",
        )

        return RecommendationResponse(
            success=True,
            recommendation=recommendation,
        )


recommendation_service = RecommendationService()