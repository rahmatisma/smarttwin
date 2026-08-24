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
            intersection_id=request.intersection_id,
            limit=1
        )
        
        if not latest_traffic_list:
            # Fallback jika tidak ada data
            recommendation = SignalRecommendation(
                intersection_id=request.intersection_id,
                timestamp=datetime.now(timezone.utc),
                recommended_phase="north",
                recommended_green_seconds=30,
                current_green_seconds=30,
                green_per_approach={"north": 30, "south": 30, "east": 30, "west": 30},
                expected_delay_reduction_percent=0.0,
                confidence=0.5,
                reason="Tidak ada data trafik terbaru.",
                metrics=RecommendationMetrics(queue_length=0, vehicle_count=0, average_speed_kmh=0),
                source="fallback"
            )
        else:
            data = latest_traffic_list[0]
            ts_data = data["trafficState"]
            approaches_data = data["approaches"]
            
            traffic_state = TrafficState(
                intersectionId=request.intersection_id,
                windowStart=ts_data["windowStart"],
                windowEnd=ts_data["windowEnd"],
                approaches=[
                    ApproachState(**app) for app in approaches_data
                ]
            )
            
            recommendation = self.engine.decide(traffic_state, current_green_seconds=30)

        return RecommendationResponse(
            success=True,
            recommendation=recommendation,
        )


recommendation_service = RecommendationService()