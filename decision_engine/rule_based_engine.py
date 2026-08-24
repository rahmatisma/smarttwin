"""
SMARTTWIN — DECISION ENGINE (rule-based)

Ambil TrafficState (kontrak resmi, backend/app/schemas/traffic.py) lalu
putuskan lengan mana yang paling layak dapat giliran hijau berikutnya,
berapa lama, dan seberapa yakin keputusan itu -- dibungkus jadi
SignalRecommendation (backend/app/schemas/recommendation.py), skema
YANG SAMA dipakai backend/app/services/recommendation_service.py
(sebelum ini isinya hardcode: confidence=0.75, source="pending").

Kenapa target-nya backend/app/schemas/, BUKAN docs/data-contract.md:
    data-contract.md punya versi SignalRecommendation sendiri
    (chosen_scenario: ScenarioResult, expected_improvement_pct, engine)
    tapi itu TIDAK PERNAH diimplementasikan -- tidak ada ScenarioResult
    di backend sama sekali. Yang benar-benar hidup dan dipakai endpoint
    asli adalah versi di backend/app/schemas/recommendation.py.
    Menyasar itu berarti sekali jalan langsung kompatibel dengan
    recommendation_service.py, bukan kontrak di atas kertas yang belum
    ada konsumennya.

Arsitektur sengaja dipisah jadi interface (DecisionEngine) dan
implementasi (RuleBasedEngine) supaya nanti bisa di-swap ke PPO
tanpa mengubah kode yang memanggilnya — cukup ganti instance-nya:

    engine = RuleBasedEngine()   # sekarang
    engine = PPOEngine()         # nanti, kalau sudah ada

Kenapa cuma SATU recommended_phase (bukan alokasi 4 lengan sekaligus):
    Bentuk SignalRecommendation di backend memang satu keputusan per
    panggilan ("lengan mana yang harus jadi hijau berikutnya"), bukan
    rencana siklus penuh. Ini juga cocok dengan cara
    simulation/run_tls_simulation.py:create_phase_plan() sudah bekerja
    sekarang (pilih SATU lengan dengan antrean tertinggi tiap kali
    dipanggil) -- jadi keputusan ini dirancang untuk dipanggil ULANG
    tiap kali perlu fase berikutnya, bukan sekali di awal siklus.
    Alokasi proporsional ke SEMUA lengan (largest-remainder, total
    120 detik) tetap dihitung secara internal untuk menentukan
    recommended_green_seconds lengan terpilih -- cuma tidak semua
    lengan diekspos di SignalRecommendation, karena skemanya memang
    tidak punya tempat untuk itu.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)

from app.schemas.recommendation import (  # noqa: E402
    RecommendationMetrics,
    SignalRecommendation,
)
from app.schemas.traffic import ApproachState, TrafficState  # noqa: E402


# ============================================================
# KONSTANTA ATURAN
# ============================================================

TOTAL_WAKTU_SIKLUS = 120   # detik, tetap untuk satu siklus lampu
WAKTU_HIJAU_MIN = 15       # detik, jatah minimum tiap lengan
BOBOT_KENDARAAN_BESAR = 2  # pengali skor untuk truk dan bus


# ============================================================
# INTERFACE
# ============================================================

class DecisionEngine:
    """
    Kontrak yang harus dipenuhi semua engine keputusan sinyal,
    baik yang rule-based sekarang maupun PPO nanti.
    """

    def decide(
        self,
        traffic_state: TrafficState,
        current_green_seconds: int | None = None,
    ) -> SignalRecommendation:
        raise NotImplementedError


# ============================================================
# IMPLEMENTASI RULE-BASED
# ============================================================

class RuleBasedEngine(DecisionEngine):
    """
    Bagi waktu hijau satu siklus (120 detik) ke tiap lengan secara
    proporsional terhadap skor kepadatannya (semua lengan tetap dapat
    jatah minimum 15 detik), lalu rekomendasikan lengan dengan skor
    tertinggi sebagai fase hijau berikutnya.
    """

    def decide(
        self,
        traffic_state: TrafficState,
        current_green_seconds: int | None = None,
    ) -> SignalRecommendation:
        approaches = traffic_state.approaches
        jumlah_lengan = len(approaches)

        skor_per_approach = {
            a.approach: self._hitung_skor(a) for a in approaches
        }
        approach_by_name = {a.approach: a for a in approaches}

        total_skor = sum(skor_per_approach.values())

        # Sisa waktu di luar jatah minimum semua lengan, dibagi
        # proporsional berdasarkan skor.
        sisa_waktu = TOTAL_WAKTU_SIKLUS - (WAKTU_HIJAU_MIN * jumlah_lengan)

        green_per_approach: dict[str, int] = {}
        sisa_pecahan: dict[str, float] = {}

        # Floor (bukan round()) tiap porsi dulu. round() independen per
        # lengan itu sumber bug lama: total dari beberapa round() terpisah
        # bisa meleset dari 120, karena tiap pembulatan dilakukan sendiri
        # tanpa tahu apa yang terjadi di lengan lain.
        for approach, skor in skor_per_approach.items():
            if total_skor > 0:
                porsi = (skor / total_skor) * sisa_waktu
            else:
                # Semua lengan sepi (skor 0 semua) — bagi rata sisa
                # waktu supaya tidak ZeroDivisionError.
                porsi = sisa_waktu / jumlah_lengan

            green_exact = WAKTU_HIJAU_MIN + porsi
            green_floor = int(green_exact)

            green_per_approach[approach] = green_floor
            sisa_pecahan[approach] = green_exact - green_floor

        # Metode largest remainder: detik yang "hilang" karena semua
        # porsi di-floor tadi dikembalikan satu-satu ke lengan dengan
        # sisa pecahan TERBESAR dulu. Menjamin total selalu tepat
        # TOTAL_WAKTU_SIKLUS tanpa pernah perlu koreksi negatif.
        total_terisi = sum(green_per_approach.values())
        sisa_detik = TOTAL_WAKTU_SIKLUS - total_terisi

        urutan_pecahan_terbesar = sorted(
            sisa_pecahan, key=sisa_pecahan.get, reverse=True
        )
        for approach in urutan_pecahan_terbesar[:sisa_detik]:
            green_per_approach[approach] += 1

        # Lengan dengan skor tertinggi -- itu yang direkomendasikan
        # jadi fase hijau berikutnya.
        top_approach = max(skor_per_approach, key=skor_per_approach.get)
        top_state = approach_by_name[top_approach]
        top_green = green_per_approach[top_approach]
        top_skor = skor_per_approach[top_approach]

        current_green = (
            current_green_seconds
            if current_green_seconds is not None
            else WAKTU_HIJAU_MIN
        )

        return SignalRecommendation(
            intersection_id=traffic_state.intersectionId,
            timestamp=datetime.now(timezone.utc),
            recommended_phase=top_approach,
            recommended_green_seconds=top_green,
            current_green_seconds=current_green,
            green_per_approach=green_per_approach,
            expected_delay_reduction_percent=self._estimasi_pengurangan_delay(
                top_green, current_green
            ),
            confidence=self._hitung_confidence(skor_per_approach, top_approach),
            reason=self._buat_alasan(top_approach, top_state, top_skor),
            metrics=RecommendationMetrics(
                queue_length=float(top_state.queueLengthVeh),
                vehicle_count=float(top_state.volume),
                average_speed_kmh=top_state.avgSpeedKmh or 0.0,
            ),
            source="rule-based",
        )

    @staticmethod
    def _hitung_skor(approach_state: ApproachState) -> float:
        """
        skor = volume + (truck * 2) + (bus * 2)

        truk & bus dibobot 2x karena butuh waktu hijau lebih lama untuk
        melintas dibanding motor/mobil.
        """
        return (
            approach_state.volume
            + (approach_state.truckCount * BOBOT_KENDARAAN_BESAR)
            + (approach_state.busCount * BOBOT_KENDARAAN_BESAR)
        )

    @staticmethod
    def _hitung_confidence(
        skor_per_approach: dict[str, float], top_approach: str
    ) -> float:
        """
        Proporsi skor lengan terpilih terhadap total skor semua lengan --
        makin dominan satu lengan dibanding lengan lain, makin yakin
        keputusannya. 0.5 (netral) kalau semua lengan sepi -- tidak ada
        sinyal kuat ke arah mana pun.
        """
        total = sum(skor_per_approach.values())
        if total <= 0:
            return 0.5
        return round(skor_per_approach[top_approach] / total, 2)

    @staticmethod
    def _estimasi_pengurangan_delay(
        green_baru: int, green_sekarang: int
    ) -> float:
        """
        Proxy KASAR, BUKAN pengukuran -- pengukuran delay yang sebenarnya
        butuh evaluasi SUMO nyata (itu peran ScenarioResult di
        docs/data-contract.md, belum ada implementasinya di backend).
        Sampai itu ada, dipakai selisih relatif waktu hijau baru vs
        sekarang sebagai indikasi arah (searah, bukan presisi delay).
        """
        if green_sekarang <= 0:
            return 0.0
        return round(
            max(0.0, (green_baru - green_sekarang) / green_sekarang * 100), 1
        )

    @staticmethod
    def _buat_alasan(approach: str, state: ApproachState, skor: float) -> str:
        return (
            f"Lengan {approach} punya skor kepadatan tertinggi "
            f"({skor:.0f}, volume={state.volume}, "
            f"antrean={state.queueLengthVeh} kendaraan)."
        )


# ============================================================
# TEST SEDERHANA
# ============================================================

if __name__ == "__main__":
    import json

    contoh_traffic_state = TrafficState(
        intersectionId="simpang4-pingit",
        windowStart=datetime.now(timezone.utc),
        windowEnd=datetime.now(timezone.utc),
        approaches=[
            ApproachState(approach="south", volume=9, motorcycleCount=2, carCount=6, truckCount=1, queueLengthVeh=4),
            ApproachState(approach="north", volume=3, motorcycleCount=1, carCount=2, truckCount=0, queueLengthVeh=1),
            ApproachState(approach="west", volume=7, motorcycleCount=3, carCount=4, truckCount=0, queueLengthVeh=3),
            ApproachState(approach="east", volume=2, motorcycleCount=2, carCount=0, truckCount=0, queueLengthVeh=0),
        ],
    )

    engine = RuleBasedEngine()
    rekomendasi = engine.decide(contoh_traffic_state, current_green_seconds=20)

    print("Input  (TrafficState):")
    print(contoh_traffic_state.model_dump_json(indent=2))

    print("\nOutput (SignalRecommendation):")
    print(rekomendasi.model_dump_json(indent=2))
