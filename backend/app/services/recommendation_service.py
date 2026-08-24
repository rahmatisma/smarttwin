from datetime import datetime, timezone

from app.schemas.recommendation import (
    RecommendationMetrics,
    RecommendationRequest,
    RecommendationResponse,
    SignalRecommendation,
)
from app.schemas.traffic import TrafficState, ApproachState
from app.services.traffic_service import TrafficService

import sys
from pathlib import Path

# Tambahkan project root ke sys.path agar decision_engine bisa diimport
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from decision_engine.rule_based_engine import RuleBasedEngine

class RecommendationService:
    def __init__(self):
        self.traffic_service = TrafficService()
        self.engine = RuleBasedEngine()

    def get_recommendation(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:

        latest_traffic_list = self.traffic_service.get_latest_traffic(
            intersection_id=request.intersectionId,
            limit=1
        )

        if not latest_traffic_list:
            # Fallback jika tidak ada data
            recommendation = SignalRecommendation(
                intersectionId=request.intersectionId,
                timestamp=datetime.now(timezone.utc),
                recommendedPhase="north",
                recommendedGreenSeconds=30,
                currentGreenSeconds=30,
                expectedDelayReductionPercent=0.0,
                confidence=0.5,
                reason="Tidak ada data trafik terbaru.",
                metrics=RecommendationMetrics(queueLength=0, vehicleCount=0, averageSpeedKmh=0),
                source="fallback"
            )
        else:
            data = latest_traffic_list[0]
            ts_data = data["trafficState"]
            approaches_data = data["approaches"]

            traffic_state = TrafficState(
                intersectionId=request.intersectionId,
                windowStart=ts_data["windowStart"],
                windowEnd=ts_data["windowEnd"],
                approaches=[
                    ApproachState(**app) for app in approaches_data
                ]
            )

            engine_result = self.engine.recommend(
                state=traffic_state,
                currentGreenSeconds=30,
                currentPhase="north",
            )

            selected_approach = next(
                (
                    app for app in traffic_state.approaches
                    if str(getattr(app.approach, "value", app.approach)).lower()
                    == engine_result.recommendedPhase
                ),
                None,
            )

            recommendation = SignalRecommendation(
                intersectionId=request.intersectionId,
                timestamp=datetime.now(timezone.utc),
                recommendedPhase=engine_result.recommendedPhase,
                recommendedGreenSeconds=engine_result.recommendedGreenSeconds,
                currentGreenSeconds=engine_result.currentGreenSeconds,
                expectedDelayReductionPercent=engine_result.expectedDelayReductionPercent,
                confidence=engine_result.confidence,
                reason=engine_result.reason,
                metrics=RecommendationMetrics(
                    queueLength=selected_approach.queueLengthVeh if selected_approach else 0,
                    vehicleCount=selected_approach.volume if selected_approach else 0,
                    averageSpeedKmh=(selected_approach.avgSpeedKmh or 0) if selected_approach else 0,
                ),
                source=engine_result.source,
            )

        return RecommendationResponse(
            success=True,
            recommendation=recommendation,
        )


recommendation_service = RecommendationService()