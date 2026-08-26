import logging
from datetime import datetime, timezone

from app.schemas.recommendation import (
    ApproachPhaseSchema,
    CyclePlanSchema,
    RecommendationMetrics,
    RecommendationRequest,
    RecommendationResponse,
    SignalRecommendation,
)
from app.schemas.traffic import TrafficState, ApproachState
from app.services.traffic_service import TrafficService, TrafficServiceError

import sys
from pathlib import Path

# Tambahkan project root ke sys.path agar decision_engine bisa diimport
project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from decision_engine.rule_based_engine import RuleBasedEngine

from app.services.signal_service import signal_service

logger = logging.getLogger("uvicorn.error")

class RecommendationService:
    def __init__(self):
        self.traffic_service = TrafficService()
        self.engine = RuleBasedEngine()

    def get_recommendation(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:

        try:
            latest_traffic_list = self.traffic_service.get_latest_traffic(
                intersection_id=request.intersectionId,
                limit=1
            )
        except TrafficServiceError:
            # intersectionId tidak dikenal di database (mis. intersection
            # demo/mock di frontend yang belum ada datanya) -- perlakukan
            # sama seperti "belum ada traffic data", bukan crash 500.
            latest_traffic_list = []
        except Exception as exc:
            # Kegagalan tak terduga (mis. httpx.RemoteProtocolError saat
            # koneksi ke Supabase putus sesaat) TIDAK boleh bikin endpoint
            # ini 500 -- browser melaporkan 500 tanpa header CORS sebagai
            # "blocked by CORS policy" yang membingungkan (bug lama
            # FastAPI/Starlette: ServerErrorMiddleware ada di luar
            # CORSMiddleware). Fallback yang sama seperti "belum ada
            # data" jauh lebih baik daripada dashboard yang crash.
            # logger.warning (bukan .exception) sengaja -- ini sudah
            # ditangani, bukan crash. Traceback penuh cuma bikin log
            # terlihat seperti error fatal padahal endpoint tetap 200.
            logger.warning(
                "get_latest_traffic gagal untuk intersectionId=%s "
                "(%s: %s), jatuh ke fallback",
                request.intersectionId,
                type(exc).__name__,
                exc,
            )
            latest_traffic_list = []

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

            # Rekomendasi 4 lengan sekaligus (rotasi tetap
            # barat-selatan-timur-utara), TERPISAH dari
            # engine.recommend() di atas (yang cuma pilih 1 lengan
            # pemenang). Dua konsep berbeda -- lihat FIXED_CYCLE_ORDER
            # di rule_based_engine.py.
            #
            # SENGAJA baca dari signal_service.get_cycle_plan(), BUKAN
            # menghitung recommend_cycle() sendiri lagi -- supaya
            # angka di panel Rekomendasi Sinyal SELALU sama dengan
            # yang dipakai simulasi rotasi live (panel Status Sinyal).
            # Sebelumnya dua-duanya hitung sendiri-sendiri dan bisa
            # beda angka untuk lengan yang sama.
            cycle_plan_result = signal_service.get_cycle_plan()

            cycle_plan = CyclePlanSchema(
                phases=[
                    ApproachPhaseSchema(
                        approach=phase.approach,
                        greenSeconds=phase.greenSeconds,
                        demandScore=phase.demandScore,
                    )
                    for phase in cycle_plan_result.phases
                ],
                cycleLengthSeconds=cycle_plan_result.cycleLengthSeconds,
                currentPhase=cycle_plan_result.currentPhase,
                source=cycle_plan_result.source,
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
                cyclePlan=cycle_plan,
            )

        return RecommendationResponse(
            success=True,
            recommendation=recommendation,
        )


recommendation_service = RecommendationService()