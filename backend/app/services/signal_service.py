import logging
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.schemas.signal import (
    SignalPhase,
    SignalStatus,
    SignalUpdate,
)
from app.schemas.traffic import ApproachState, TrafficState
from app.services.traffic_service import TrafficService, TrafficServiceError
from app.services.per_approach_forecast_service import (
    PerApproachForecastService,
    per_approach_forecast_service,
)

project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from decision_engine.rule_based_engine import (
    ApproachPhase,
    CyclePlan,
    FIXED_CYCLE_ORDER,
    RuleBasedEngine,
)

logger = logging.getLogger("uvicorn.error")

INTERSECTION_ID = "simpang4-pingit"
FORECAST_HISTORY_LIMIT = 24
FORECAST_WEIGHT = 0.3

# Baseline dunia nyata Simpang Pingit (dicari manual, bukan dari
# formula MIN/MAX_GREEN_SECONDS RuleBasedEngine) -- CUMA dipakai
# untuk fase PERTAMA sebelum ada rekomendasi sama sekali. Fase
# berikutnya selalu pakai hasil recommend_cycle() yang adaptif.
DEFAULT_GREEN_SECONDS = 50

# Tengah rentang 3-5 detik yang jadi acuan.
YELLOW_SECONDS = 4

APPROACH_PHASE_NAMES = {
    "west": "Barat (Jl. Kyai Mojo)",
    "south": "Selatan (Jl. Tentara Pelajar)",
    "east": "Timur (Jl. Pangeran Diponegoro)",
    "north": "Utara (Jl. Magelang)",
}


class SignalService:
    """
    Simulasi rotasi lampu yang benar-benar "hidup" -- satu lengan
    aktif pada satu waktu, urutan tetap FIXED_CYCLE_ORDER, durasi
    tiap lengan dihitung dari RuleBasedEngine.recommend_cycle() (data
    demand TERBARU saat lengan itu MULAI, bukan snapshot beku).

    Pola "lazy tick": tidak ada thread/scheduler terpisah. Tiap kali
    get_live_status() dipanggil (dashboard poll tiap 5 detik), method
    ini mengecek berdasarkan wall-clock apakah fase aktif sudah
    harus pindah, dan pindah kalau sudah waktunya. Menghitung
    recommend_cycle() itu murni aritmatika (<1ms) -- jadi ini setara
    secara observable dengan "dihitung di depan selagi fase
    sebelumnya jalan", tanpa perlu infrastruktur async terpisah.
    """

    def __init__(
        self,
        traffic_service: Optional[TrafficService] = None,
        forecast_service: Optional[PerApproachForecastService] = None,
    ) -> None:

        self.traffic_service = (
            traffic_service
            if traffic_service is not None
            else TrafficService()
        )

        self.engine = RuleBasedEngine()
        self.forecast_service = forecast_service or per_approach_forecast_service

        self._lock = threading.Lock()

        # Diisi lazy pada panggilan pertama get_live_status().
        self._phase_index: int = 0
        self._phase_green_seconds: int = DEFAULT_GREEN_SECONDS
        self._phase_started_at: Optional[datetime] = None

        # Cache rencana 4 lengan sekaligus -- SATU sumber yang dipakai
        # bareng oleh get_live_status() (fase aktif + fase berikutnya)
        # DAN RecommendationService lewat get_cycle_plan(), supaya
        # panel Rekomendasi Sinyal & Status Sinyal tidak pernah beda
        # angka untuk lengan yang sama.
        self._cycle_plan: Optional[CyclePlan] = None

        # Fallback manual push (POST /signal/status), dipertahankan
        # apa adanya untuk kompatibilitas.
        self._pushed_status: Optional[SignalStatus] = None

    # ========================================================
    # MANUAL PUSH (dipertahankan, tidak dihapus)
    # ========================================================

    def update_status(
        self,
        update: SignalUpdate,
    ) -> SignalStatus:

        status = SignalStatus(
            intersectionId=update.intersectionId,
            timestamp=datetime.now(timezone.utc),
            currentPhase=update.currentPhase,
            phaseName=update.phaseName,
            remainingSeconds=update.remainingSeconds,
            cycleTimeSeconds=update.cycleTimeSeconds,
            phases=update.phases,
            source="backend",
        )

        self._pushed_status = status

        return status

    def get_status(self) -> Optional[SignalStatus]:
        return self._pushed_status

    def get_demo_status(self) -> SignalStatus:
        return SignalStatus(
            intersectionId="intersection_01",
            timestamp=datetime.now(timezone.utc),
            currentPhase="NS_GREEN",
            phaseName="North-South Green",
            remainingSeconds=24,
            cycleTimeSeconds=90,
            phases={
                "NS_GREEN": SignalPhase(
                    phaseId="NS_GREEN",
                    state="green",
                    durationSeconds=35,
                    remainingSeconds=24,
                ),
                "NS_YELLOW": SignalPhase(
                    phaseId="NS_YELLOW",
                    state="yellow",
                    durationSeconds=4,
                    remainingSeconds=0,
                ),
                "EW_GREEN": SignalPhase(
                    phaseId="EW_GREEN",
                    state="green",
                    durationSeconds=35,
                    remainingSeconds=0,
                ),
                "EW_YELLOW": SignalPhase(
                    phaseId="EW_YELLOW",
                    state="yellow",
                    durationSeconds=4,
                    remainingSeconds=0,
                ),
            },
            source="demo",
        )

    # ========================================================
    # LIVE TICK
    # ========================================================

    def _fetch_traffic_history(self) -> list[dict]:

        try:
            latest = self.traffic_service.get_latest_traffic(
                intersection_id=INTERSECTION_ID,
                limit=FORECAST_HISTORY_LIMIT,
            )
        except TrafficServiceError:
            return []
        except Exception:
            logger.warning(
                "get_latest_traffic gagal saat tick SignalService, "
                "pakai DEFAULT_GREEN_SECONDS",
                exc_info=True,
            )
            return []

        if not latest:
            return []

        return latest

    def _traffic_state_from_record(self, data: dict) -> TrafficState:

        ts_data = data["trafficState"]
        approaches_data = data["approaches"]

        return TrafficState(
            intersectionId=INTERSECTION_ID,
            windowStart=ts_data["windowStart"],
            windowEnd=ts_data["windowEnd"],
            approaches=[
                ApproachState(**app) for app in approaches_data
            ],
        )

    def _recompute_cycle_plan(
        self,
        active_approach: str,
    ) -> CyclePlan:
        """
        Hitung ULANG rencana ke-4 lengan sekaligus (recommend_cycle())
        pakai TrafficState terbaru, simpan ke cache. Dipanggil tiap
        kali fase aktif berpindah (jadi selalu segar relatif ke fase
        yang baru mulai), dan lewat get_cycle_plan() untuk
        RecommendationService.

        Kalau belum ada TrafficState sama sekali, TETAP kembalikan
        CyclePlan (semua lengan DEFAULT_GREEN_SECONDS) alih-alih None
        -- downstream (phases dict, get_cycle_plan()) jadi tidak perlu
        menangani kasus kosong secara khusus, sama seperti fallback
        di RecommendationService.
        """

        history = self._fetch_traffic_history()
        state = self._traffic_state_from_record(history[0]) if history else None
        forecast = None
        if history:
            try:
                forecast = self.forecast_service.predict_records(history)
            except Exception as exc:
                logger.warning("Forecast live tidak tersedia, pakai TrafficState saat ini: %s", exc)

        if state is not None:

            plan = self.engine.recommend_cycle(
                state=state,
                currentPhase=active_approach,
                forecast=forecast,
                forecastWeight=FORECAST_WEIGHT,
            )

        else:
            total_cycle_seconds = (
                (DEFAULT_GREEN_SECONDS + YELLOW_SECONDS)
                * len(FIXED_CYCLE_ORDER)
            )
            plan = CyclePlan(
                phases=[
                    ApproachPhase(
                        approach=approach_name,
                        greenSeconds=DEFAULT_GREEN_SECONDS,
                        demandScore=0.0,
                        yellowSeconds=YELLOW_SECONDS,
                        redSeconds=(
                            total_cycle_seconds
                            - DEFAULT_GREEN_SECONDS
                            - YELLOW_SECONDS
                        ),
                    )
                    for approach_name in FIXED_CYCLE_ORDER
                ],
                cycleLengthSeconds=(
                    DEFAULT_GREEN_SECONDS * len(FIXED_CYCLE_ORDER)
                ),
                currentPhase=active_approach,
                source="rule-based",
                totalCycleSeconds=total_cycle_seconds,
            )

        self._cycle_plan = plan

        return plan

    def get_cycle_plan(self) -> CyclePlan:
        """
        Dipakai RecommendationService supaya panel "Durasi Hijau per
        Lengan" baca angka yang SAMA dengan yang dipakai simulasi
        rotasi ini -- bukan menghitung recommend_cycle() sendiri lagi
        (itu yang sebelumnya bikin dua panel bisa beda angka).
        """

        with self._lock:

            if self._cycle_plan is None:

                self._recompute_cycle_plan(
                    FIXED_CYCLE_ORDER[self._phase_index]
                )

            return self._cycle_plan

    def get_live_status(
        self,
        now: Optional[datetime] = None,
    ) -> SignalStatus:

        current_time = now or datetime.now(timezone.utc)

        with self._lock:

            if self._phase_started_at is None:
                # Fase pertama sejak backend nyala -- belum ada
                # rekomendasi buat lengan AKTIF ini, pakai baseline
                # dunia nyata. Tapi tetap hitung cycle plan penuh
                # sekarang juga, supaya 3 lengan lain langsung punya
                # angka asli sejak awal (bukan nunggu transisi
                # pertama).
                self._phase_index = 0
                self._phase_green_seconds = DEFAULT_GREEN_SECONDS
                self._phase_started_at = current_time
                self._recompute_cycle_plan(FIXED_CYCLE_ORDER[0])

            phase_total_seconds = (
                self._phase_green_seconds + YELLOW_SECONDS
            )

            elapsed = (
                current_time - self._phase_started_at
            ).total_seconds()

            # Bisa lebih dari satu fase terlewat kalau server sempat
            # tidak di-poll -- loop supaya tidak nyangkut.
            while elapsed >= phase_total_seconds:

                self._phase_started_at = (
                    self._phase_started_at
                    + timedelta(seconds=phase_total_seconds)
                )

                self._phase_index = (
                    self._phase_index + 1
                ) % len(FIXED_CYCLE_ORDER)

                next_approach = FIXED_CYCLE_ORDER[
                    self._phase_index
                ]

                plan = self._recompute_cycle_plan(next_approach)

                self._phase_green_seconds = next(
                    (
                        phase.greenSeconds
                        for phase in plan.phases
                        if phase.approach == next_approach
                    ),
                    DEFAULT_GREEN_SECONDS,
                )

                elapsed = (
                    current_time - self._phase_started_at
                ).total_seconds()

                phase_total_seconds = (
                    self._phase_green_seconds + YELLOW_SECONDS
                )

            approach = FIXED_CYCLE_ORDER[self._phase_index]

            next_index = (
                self._phase_index + 1
            ) % len(FIXED_CYCLE_ORDER)

            next_approach = FIXED_CYCLE_ORDER[next_index]

            remaining_seconds = max(
                0,
                round(phase_total_seconds - elapsed),
            )

            green_seconds_by_approach = {
                phase.approach: phase.greenSeconds
                for phase in self._cycle_plan.phases
            } if self._cycle_plan else {}

            phases = {
                approach_name: SignalPhase(
                    phaseId=approach_name,
                    state="green" if approach_name == approach else "red",
                    durationSeconds=(
                        self._phase_green_seconds
                        if approach_name == approach
                        else green_seconds_by_approach.get(
                            approach_name,
                            DEFAULT_GREEN_SECONDS,
                        )
                    ),
                    remainingSeconds=(
                        remaining_seconds
                        if approach_name == approach
                        else 0
                    ),
                )
                for approach_name in FIXED_CYCLE_ORDER
            }

            return SignalStatus(
                intersectionId=INTERSECTION_ID,
                timestamp=current_time,
                currentPhase=approach,
                phaseName=APPROACH_PHASE_NAMES.get(approach, approach),
                remainingSeconds=remaining_seconds,
                cycleTimeSeconds=(
                    self._phase_green_seconds + YELLOW_SECONDS
                ),
                phases=phases,
                nextPhase=next_approach,
                nextPhaseName=APPROACH_PHASE_NAMES.get(
                    next_approach, next_approach
                ),
                source="rule-based",
            )


signal_service = SignalService()
