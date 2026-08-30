from __future__ import annotations

from typing import Any

from app.schemas.traffic import TrafficState

from .rule_based_engine import FIXED_CYCLE_ORDER


FEATURE_NAMES_PER_APPROACH = (
    "volume",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
    "avgSpeedKmh",
)
# Skala normalisasi tiap fitur ke rentang 0-1.
#
# BUG G (diperbaiki 30 Agustus): `volume` dulu memakai skala 60,0 -- nilai yang
# masuk akal kalau satuannya kendaraan/MENIT. Tapi `TrafficState.volume` yang
# benar-benar diisi adalah crossing per JENDELA 5 DETIK. Diukur pada
# cv/output/crossing_simpang.csv (2.152 jendela): maks 9, p95 6, rata-rata 2,07.
# Dengan skala 60, 94,2% nilai jatuh di bawah 0,1 -- fitur terjepit di 3% bawah
# rentangnya dan praktis tidak membawa informasi. Skala 10 memberi rata-rata
# 0,207 dan maksimum 0,900, memakai rentang dengan wajar.
#
# Ini juga sejalan dengan REFERENCE_VOLUME di rule_based_engine.py yang punya
# ketidakcocokan satuan yang sama persis.
#
# Skala lain SENGAJA BELUM diubah meski agak kurang terpakai (queueLengthVeh
# rata-rata 0,091 maks 0,567; densityIndex 0,145/0,576; queueLengthMEst
# 0,128/0,793). Ketiganya masih memakai 57-79% rentang, jadi tidak rusak seperti
# volume -- dan distribusinya akan BERUBAH begitu Bug I & H diperbaiki
# (lingkungan training sekarang 3-5x lebih macet daripada data nyata, lihat Bug
# K). Menyetel ulang sekarang berarti menyetel ke distribusi yang sebentar lagi
# tidak berlaku. Ukur ulang setelah Bug I & H beres.
VOLUME_SCALE_PER_WINDOW = 10.0
FEATURE_SCALES = {
    "volume": VOLUME_SCALE_PER_WINDOW,
    "queueLengthVeh": 30.0,
    "queueLengthMEst": 150.0,
    "densityIndex": 33.0,
    "avgSpeedKmh": 60.0,
}
# BUG J (diperbaiki 30 Agustus): dulu 25 fitur, 4 di antaranya one-hot fase
# aktif. Fitur itu KONSTAN sepanjang training -- terukur `[1,0,0,0]` di seluruh
# observasi -- karena sejak Bug A diperbaiki, satu langkah = satu rotasi penuh
# yang selalu dimulai dari FIXED_CYCLE_ORDER[0].
#
# Itu bukan sekadar 16% masukan yang mubazir. Saat inference, `signal_service`
# memanggil engine dengan `currentPhase=active_approach` yang BERPUTAR keempat
# lengan, sehingga bobot untuk 3 lengan lain -- yang selama training inputnya
# selalu nol dan karena itu tidak pernah mendapat gradien bermakna -- ikut
# aktif dengan nilai yang praktis masih acak. Model diberi derau, bukan
# informasi.
#
# Dihapus daripada dipaksakan: menyamakannya secara benar berarti mengubah satu
# langkah training menjadi satu FASE (bukan satu rotasi), yaitu perubahan
# desain besar yang belum dikerjakan.
OBSERVATION_SIZE = 21


def _safe_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def build_ppo_observation(
    state: TrafficState,
    *,
    current_phase: str,
    current_green_seconds: int,
) -> list[float]:
    """Kontrak fitur tunggal untuk training dan inference PPO.

    `volume` selalu berarti flow/crossing dalam window TrafficState. Density
    selalu berarti kehadiran kendaraan, sehingga slot 0 dan 3 tidak lagi
    berasal dari besaran SUMO yang sama.
    """
    by_name = {
        str(getattr(item.approach, "value", item.approach)).lower(): item
        for item in state.approaches
    }
    observation: list[float] = []
    for approach in FIXED_CYCLE_ORDER:
        item = by_name.get(approach)
        for feature_name in FEATURE_NAMES_PER_APPROACH:
            value = _safe_float(getattr(item, feature_name, 0))
            observation.append(min(1.0, value / FEATURE_SCALES[feature_name]))

    # One-hot fase aktif DIHAPUS -- lihat catatan di OBSERVATION_SIZE.
    # Parameter current_phase dipertahankan agar pemanggil lama tidak error.
    observation.append(min(1.0, max(0.0, float(current_green_seconds) / 60.0)))
    if len(observation) != OBSERVATION_SIZE:
        raise RuntimeError(f"Observation PPO harus {OBSERVATION_SIZE} fitur")
    return observation
