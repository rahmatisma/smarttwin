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
from app.services.per_approach_forecast_service import per_approach_forecast_service
from app.services.live_scenario_cache_service import (
    LiveScenarioCacheService,
    live_scenario_cache_service,
)

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
    def __init__(self, traffic_service=None, cache_service=None):
        self.traffic_service = traffic_service or TrafficService()
        self.cache_service: LiveScenarioCacheService = (
            cache_service or live_scenario_cache_service
        )
        self.engine = RuleBasedEngine()

    def get_recommendation(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:

        try:
            latest_traffic_list = self.traffic_service.get_latest_traffic(
                intersection_id=request.intersectionId,
                limit=24
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

            # Hasil worker SUMO diprioritaskan hanya selama masih segar.
            # Cache miss/error tidak boleh mengubah availability endpoint.
            cached = self.cache_service.get_fresh(request.intersectionId)

            forecast = None
            try:
                forecast = per_approach_forecast_service.predict_records(latest_traffic_list)
            except Exception as exc:
                logger.warning(
                    "Forecast rekomendasi tidak tersedia, pakai TrafficState saat ini: %s",
                    exc,
                )

            engine_result = self.engine.recommend(
                state=traffic_state,
                currentGreenSeconds=30,
                currentPhase="north",
                forecast=forecast,
                forecastWeight=0.3,
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

            cached_payload = cached.get("recommendation") if cached else None
            if not isinstance(cached_payload, dict):
                cached_payload = None

            if cached_payload:
                engine_result.recommendedPhase = cached_payload["recommendedPhase"]
                engine_result.recommendedGreenSeconds = int(
                    cached_payload["recommendedGreenSeconds"]
                )
                engine_result.expectedDelayReductionPercent = float(
                    cached_payload.get("expectedDelayReductionPercent", 0)
                )
                engine_result.confidence = float(cached_payload.get("confidence", 0.5))
                engine_result.reason = str(cached_payload.get("reason", ""))
                engine_result.source = "scenario-generator"
                cached_cycle = cached_payload.get("cyclePlan")
                if isinstance(cached_cycle, dict):
                    # Jalur full-cycle worker sudah diuji sebagai satu program
                    # SUMO utuh. Gunakan plan itu agar recommendation dan panel
                    # siklus tidak membawa dua keputusan berbeda.
                    cycle_plan = CyclePlanSchema(**cached_cycle)
                    cycle_plan.source = "scenario-generator"
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
                cyclePlan=cycle_plan,
                avgDelaySeconds=cached.get("avgDelaySeconds") if cached else None,
                avgQueueLengthM=cached.get("avgQueueLengthM") if cached else None,
                los=cached.get("los") if cached else None,
                candidateId=cached.get("candidateId") if cached else None,
            )

        return RecommendationResponse(
            success=True,
            recommendation=recommendation,
        )


recommendation_service = RecommendationService()
