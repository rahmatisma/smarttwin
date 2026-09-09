import logging
import os
import threading
import time
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

from decision_engine.engine_factory import create_decision_engine

from app.services.signal_service import signal_service

logger = logging.getLogger("uvicorn.error")

# TrafficState baru ditulis ingest CV ~tiap 5 detik, jadi menghitung ulang
# rekomendasi lebih sering dari itu tidak menghasilkan angka baru -- hanya
# membebani Supabase + LSTM. Cache proses (bukan per-request) berumur pendek
# ini membuat: (1) banyak tab dashboard berbagi SATU perhitungan, (2) burst
# refetch akibat satu event WebSocket tidak menjadi N perhitungan paralel.
# Override lewat env RECOMMENDATION_CACHE_TTL_SECONDS ("0" mematikan cache).
def _cache_ttl_seconds() -> float:
    try:
        return max(0.0, float(os.getenv("RECOMMENDATION_CACHE_TTL_SECONDS", "3")))
    except ValueError:
        return 3.0


class RecommendationService:
    def __init__(self, traffic_service=None, cache_service=None):
        self.traffic_service = traffic_service or TrafficService()
        self.cache_service: LiveScenarioCacheService = (
            cache_service or live_scenario_cache_service
        )
        # Default tetap rule-based. PPO hanya aktif lewat env dan memiliki
        # fallback internal bila checkpoint/dependency belum siap.
        self.engine = create_decision_engine()

        self._ttl_seconds = _cache_ttl_seconds()
        self._result_cache: dict[str, tuple[float, RecommendationResponse]] = {}
        self._cache_lock = threading.Lock()
        # Serialisasi perhitungan supaya request yang datang bersamaan (mis.
        # semua tab bereaksi ke event WebSocket yang sama) menunggu satu
        # perhitungan lalu memakai hasil cache-nya, bukan memulai sendiri.
        self._compute_lock = threading.Lock()

    def _cached_response(self, key: str) -> RecommendationResponse | None:
        if self._ttl_seconds <= 0:
            return None
        with self._cache_lock:
            entry = self._result_cache.get(key)
        if entry is None:
            return None
        stored_at, response = entry
        if time.monotonic() - stored_at >= self._ttl_seconds:
            return None
        return response

    def _store_response(self, key: str, response: RecommendationResponse) -> None:
        if self._ttl_seconds <= 0:
            return
        with self._cache_lock:
            self._result_cache[key] = (time.monotonic(), response)

    def get_recommendation(
        self,
        request: RecommendationRequest,
    ) -> RecommendationResponse:

        cache_key = request.intersectionId or "default"

        cached = self._cached_response(cache_key)
        if cached is not None:
            return cached

        with self._compute_lock:
            # Thread lain mungkin sudah menghitung selagi kita menunggu lock.
            cached = self._cached_response(cache_key)
            if cached is not None:
                return cached

            response = self._compute_recommendation(request)
            self._store_response(cache_key, response)
            return response

    def _compute_recommendation(
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
            # utara-timur-selatan-barat), TERPISAH dari
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
                        yellowSeconds=phase.yellowSeconds,
                        redSeconds=phase.redSeconds,
                    )
                    for phase in cycle_plan_result.phases
                ],
                cycleLengthSeconds=cycle_plan_result.cycleLengthSeconds,
                currentPhase=cycle_plan_result.currentPhase,
                source=cycle_plan_result.source,
                totalCycleSeconds=cycle_plan_result.totalCycleSeconds,
            )

            cached_payload = cached.get("recommendation") if cached else None
            if not isinstance(cached_payload, dict):
                cached_payload = None

            # Antrean & throughput per lengan: worker menaruh ini di tiap
            # kandidat (bukan di blob `recommendation`), jadi ambil dari
            # kandidat pemenang. Tanpa ini panel "Kondisi per Lengan" di
            # dashboard menampilkan "-" untuk Antrean/Lewat semua lengan.
            queue_by_approach: dict | None = None
            throughput_by_approach: dict | None = None
            if isinstance(cached, dict):
                candidates = cached.get("candidates")
                winner_id = cached.get("candidateId")
                if isinstance(candidates, list):
                    winner = next(
                        (
                            c for c in candidates
                            if isinstance(c, dict) and c.get("candidateId") == winner_id
                        ),
                        None,
                    )
                    if isinstance(winner, dict):
                        q = winner.get("queueLengthVehByApproach")
                        t = winner.get("throughputVehByApproach")
                        queue_by_approach = q if isinstance(q, dict) else None
                        throughput_by_approach = t if isinstance(t, dict) else None

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
                losByApproach=(
                    cached_payload.get("losByApproach")
                    if isinstance(cached_payload, dict)
                    else None
                ),
                delayByApproachSeconds=(
                    cached_payload.get("delayByApproachSeconds")
                    if isinstance(cached_payload, dict)
                    else None
                ),
                queueLengthVehByApproach=queue_by_approach,
                throughputVehByApproach=throughput_by_approach,
                candidateId=cached.get("candidateId") if cached else None,
            )

        return RecommendationResponse(
            success=True,
            recommendation=recommendation,
        )


recommendation_service = RecommendationService()
