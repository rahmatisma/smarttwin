from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable


# ============================================================
# PATH
#
# Supaya file ini bisa diimpor berdiri sendiri (mis. dari test),
# bukan cuma sebagai sibling module run_tls_simulation.py.
# ============================================================

_scenarioGeneratorRoot = Path(__file__).resolve().parent
_projectRoot = _scenarioGeneratorRoot.parent

if str(_projectRoot) not in sys.path:
    sys.path.insert(0, str(_projectRoot))


# ============================================================
# TRACI
#
# Prolog yang sama seperti run_tls_simulation.py -- CLAUDE.md:
# "kedua skrip lakukan sys.path.append($SUMO_HOME/tools) sebelum
# import traci -- pertahankan prolog itu di skrip TraCI baru manapun."
# ============================================================

try:

    import traci

except ModuleNotFoundError:

    sumoHome = os.environ.get("SUMO_HOME")

    if sumoHome:

        toolsDirectory = Path(sumoHome) / "tools"

        if (
            toolsDirectory.exists()
            and str(toolsDirectory) not in sys.path
        ):
            sys.path.insert(0, str(toolsDirectory))

    import traci


from decision_engine.rule_based_engine import (
    MAX_GREEN_SECONDS,
    MIN_GREEN_SECONDS,
    Recommendation,
    RuleBasedEngine,
)


# ============================================================
# KONFIGURASI
# ============================================================

# Jendela simulasi singkat per kandidat -- di tengah rentang 60-120
# detik yang diminta docs/pembagian-tugas-tahap-akhir.md item 1.5
# (bukan 300 detik seperti run penuh di run_tls_simulation.py).
SHORT_SIM_STEPS = 90

# Estimasi meter per kendaraan buat mengubah queueLengthVeh (jumlah
# kendaraan, dari runSimulation()) jadi avg_queue_length_m (meter)
# seperti diminta schema ScenarioResult di docs/data-contract.md.
# Ini ESTIMASI kasar (panjang kendaraan + jarak antar-kendaraan
# rata-rata), bukan pengukuran -- sama seperti pola "_est" lain yang
# sudah dipakai di project ini untuk metrik turunan serupa.
METERS_PER_QUEUED_VEHICLE = 7.0

# HCM 2000, Level of Service simpang bersinyal berdasarkan rata-rata
# control delay per kendaraan (detik). Ambang atas tiap kelas.
_LOS_THRESHOLDS = (
    (10.0, "A"),
    (20.0, "B"),
    (35.0, "C"),
    (55.0, "D"),
    (80.0, "E"),
)


# ============================================================
# KOTAK 9 -- LEVEL OF SERVICE
# ============================================================

def calculate_los(avg_delay_s: float) -> str:
    """
    Level of Service standar HCM 2000 untuk simpang bersinyal,
    berdasarkan rata-rata control delay per kendaraan (detik).
    """

    for threshold, label in _LOS_THRESHOLDS:

        if avg_delay_s <= threshold:
            return label

    return "F"


# ============================================================
# KOTAK 7 -- SCENARIO GENERATOR
# ============================================================

def generate_candidate_plans(
    baseline: Recommendation,
) -> list[dict[str, Any]]:
    """
    3 varian durasi hijau. Ketiganya pakai approach yang sama dari
    baseline (RuleBasedEngine sudah memutuskan lengan mana yang
    paling butuh hijau berikutnya) -- yang dibandingkan di sini cuma
    DURASI-nya, bukan lengan mana yang dipilih.

    Sesuai docs/pembagian-tugas-tahap-akhir.md item 1.5:
      (a) hasil RuleBasedEngine apa adanya
      (b) lebih agresif ke lengan tersibuk (+20%)
      (c) lebih merata antar lengan (ditarik ke arah minimum)
    """

    baselineGreen = baseline.recommendedGreenSeconds

    aggressiveGreen = min(
        MAX_GREEN_SECONDS,
        round(baselineGreen * 1.2),
    )

    balancedGreen = round(
        (baselineGreen + MIN_GREEN_SECONDS) / 2
    )

    return [
        {
            "candidateId": "baseline",
            "approach": baseline.recommendedPhase,
            "greenSeconds": baselineGreen,
        },
        {
            "candidateId": "aggressive",
            "approach": baseline.recommendedPhase,
            "greenSeconds": aggressiveGreen,
        },
        {
            "candidateId": "balanced",
            "approach": baseline.recommendedPhase,
            "greenSeconds": balancedGreen,
        },
    ]


# ============================================================
# KOTAK 8 -- TRAFFIC SIMULATION (per kandidat)
# ============================================================

def simulate_candidate(
    candidate: dict[str, Any],
    *,
    sumo_binary: Any,
    sumo_config: Any,
    tls_id: str,
    sumo_phase: int,
    run_simulation_fn: Callable[..., dict[str, Any]],
    step_limit: int = SHORT_SIM_STEPS,
) -> dict[str, Any]:
    """
    Jalankan SATU kandidat lewat simulasi singkat.

    run_simulation_fn di-suntik dari run_tls_simulation.py (fungsi
    runSimulation() yang sudah ada dan sudah terbukti benar dari item
    1.3) supaya loop pengumpulan metrik TIDAK diduplikasi di sini --
    persis seperti diminta dokumen ("dijalankan lewat logika
    run_tls_simulation.py yang sudah ada").
    """

    command = [
        str(sumo_binary),
        "-c",
        str(sumo_config),
        "--start",
    ]

    traci.start(command)

    try:

        traci.trafficlight.setProgram(
            tls_id,
            "safe-yellow",
        )

        traci.trafficlight.setPhase(
            tls_id,
            sumo_phase,
        )

        traci.trafficlight.setPhaseDuration(
            tls_id,
            candidate["greenSeconds"],
        )

        metrics = run_simulation_fn(
            step_limit=step_limit,
        )

    finally:

        traci.close()

    avgDelaySeconds = metrics["averageWaitingTimeSeconds"]
    queueLengthVeh = metrics["queueLengthVeh"]

    return {
        "candidateId": candidate["candidateId"],
        "approach": candidate["approach"],
        "greenSeconds": candidate["greenSeconds"],
        "avgDelaySeconds": avgDelaySeconds,
        "avgQueueLengthM": round(
            queueLengthVeh * METERS_PER_QUEUED_VEHICLE,
            1,
        ),
        "queueLengthVeh": queueLengthVeh,
        "throughputVeh": metrics["throughputVeh"],
        "los": calculate_los(avgDelaySeconds),
    }


# ============================================================
# KOTAK 10 -- ATURAN SELEKSI (PENGGANTI PPO UNTUK SEKARANG)
# ============================================================

def select_best_scenario(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Pilih kandidat dengan skor gabungan delay+antrean paling rendah.

    Dinormalisasi ke nilai TERBURUK di batch ini (bukan ke skala
    absolut) supaya delay (detik) dan antrean (meter) -- dua satuan
    berbeda -- bisa digabung secara adil. Deterministik: dipanggil
    berkali-kali dengan input sama, hasilnya selalu sama.

    Ini pengganti kotak 10 (Adaptive Decision Engine / PPO di diagram
    arsitektur) untuk sekarang -- lihat docs/pembagian-tugas-tahap-akhir.md
    item 1.5 dan 1.6. Kalau PPOEngine (item 1.6) berhasil, fungsi ini
    dan seluruh alur generate-simulate-analisa di atasnya tidak lagi
    dipakai -- PPO langsung menghasilkan keputusan dari state, tidak
    lewat kandidat tetap seperti ini.
    """

    if not results:

        raise ValueError(
            "Tidak ada kandidat skenario untuk dipilih."
        )

    maxDelay = max(
        result["avgDelaySeconds"]
        for result in results
    ) or 1.0

    maxQueue = max(
        result["avgQueueLengthM"]
        for result in results
    ) or 1.0

    def combinedScore(
        result: dict[str, Any],
    ) -> float:

        delayNorm = (
            result["avgDelaySeconds"] / maxDelay
        )

        queueNorm = (
            result["avgQueueLengthM"] / maxQueue
        )

        return (
            0.5 * delayNorm
            + 0.5 * queueNorm
        )

    return min(
        results,
        key=combinedScore,
    )


# ============================================================
# ORKESTRATOR -- INTERFACE SAMA DENGAN RuleBasedEngine
# ============================================================

class ScenarioEngine:
    """
    Isian sementara buat kotak 10 (Adaptive Decision Engine) di
    diagram arsitektur, menggantikan PPO yang belum dikerjakan
    (lihat item 1.6 di docs/pembagian-tugas-tahap-akhir.md).

    Method recommend() PERSIS bentuk RuleBasedEngine.recommend()
    supaya PPOEngine nanti tinggal ditukar tanpa mengubah
    pemanggilnya (run_tls_simulation.py / recommendation_service.py).

    Alur kotak 7-8-9-10:

        RuleBasedEngine (baseline: lengan mana + estimasi durasi)
              |
        generate_candidate_plans()        kotak 7
              |
        simulate_candidate() x3            kotak 8
              |
        calculate_los() per kandidat        kotak 9
              |
        select_best_scenario()             kotak 10
    """

    def __init__(
        self,
        *,
        sumo_binary: Any,
        sumo_config: Any,
        tls_id: str,
        approach_to_phase: dict[str, int],
        run_simulation_fn: Callable[..., dict[str, Any]],
        short_sim_steps: int = SHORT_SIM_STEPS,
    ) -> None:

        self.sumo_binary = sumo_binary
        self.sumo_config = sumo_config
        self.tls_id = tls_id
        self.approach_to_phase = approach_to_phase
        self.run_simulation_fn = run_simulation_fn
        self.short_sim_steps = short_sim_steps

        self._rule_based_engine = RuleBasedEngine()

    def recommend(
        self,
        state: Any,
        currentGreenSeconds: int = 15,
        currentPhase: str = "north",
        forecast: dict[str, Any] | None = None,
        forecastWeight: float = 0.5,
    ) -> Recommendation:

        # ----------------------------------------------------
        # BASELINE (menentukan LENGAN mana yang direkomendasikan)
        # ----------------------------------------------------

        baseline = self._rule_based_engine.recommend(
            state=state,
            currentGreenSeconds=currentGreenSeconds,
            currentPhase=currentPhase,
            forecast=forecast,
            forecastWeight=forecastWeight,
        )

        sumoPhase = self.approach_to_phase.get(
            baseline.recommendedPhase
        )

        if sumoPhase is None:

            raise ValueError(
                "Approach tidak memiliki mapping SUMO phase: "
                f"{baseline.recommendedPhase}"
            )

        # ----------------------------------------------------
        # KOTAK 7-8-9
        # ----------------------------------------------------

        candidates = generate_candidate_plans(baseline)

        results = [
            simulate_candidate(
                candidate,
                sumo_binary=self.sumo_binary,
                sumo_config=self.sumo_config,
                tls_id=self.tls_id,
                sumo_phase=sumoPhase,
                run_simulation_fn=self.run_simulation_fn,
                step_limit=self.short_sim_steps,
            )
            for candidate in candidates
        ]

        print()
        print(
            f"Scenario Generator -- {len(results)} kandidat diuji "
            f"({self.short_sim_steps} langkah tiap kandidat):"
        )

        for result in results:

            print(
                f"  [{result['candidateId']:<10}] "
                f"green={result['greenSeconds']:>3}s  "
                f"delay={result['avgDelaySeconds']:>6.2f}s  "
                f"queue={result['avgQueueLengthM']:>6.1f}m  "
                f"throughput={result['throughputVeh']:>3}  "
                f"LOS={result['los']}"
            )

        # ----------------------------------------------------
        # KOTAK 10
        # ----------------------------------------------------

        winner = select_best_scenario(results)

        print(
            f"  -> Terpilih: '{winner['candidateId']}' "
            f"(green={winner['greenSeconds']}s, LOS {winner['los']})"
        )

        baselineResult = next(
            result
            for result in results
            if result["candidateId"] == "baseline"
        )

        # ----------------------------------------------------
        # DELAY REDUCTION -- dihitung ULANG dari data simulasi
        # asli (bukan formula taksiran demand_score * 50 yang
        # dipakai RuleBasedEngine), karena sekarang benar-benar
        # ada angka delay hasil simulasi buat dibandingkan.
        # ----------------------------------------------------

        if baselineResult["avgDelaySeconds"] > 0:

            delayReductionPercent = round(
                max(
                    0.0,
                    (
                        baselineResult["avgDelaySeconds"]
                        - winner["avgDelaySeconds"]
                    )
                    / baselineResult["avgDelaySeconds"]
                    * 100,
                ),
                2,
            )

        else:

            delayReductionPercent = 0.0

        reason = (
            f"Scenario Generator menguji {len(results)} kandidat "
            f"durasi hijau untuk approach {baseline.recommendedPhase} "
            f"lewat simulasi singkat ({self.short_sim_steps} langkah "
            f"per kandidat). Kandidat '{winner['candidateId']}' "
            f"(green={winner['greenSeconds']}s) terpilih: "
            f"delay={winner['avgDelaySeconds']:.2f}s (LOS {winner['los']}), "
            f"queue={winner['avgQueueLengthM']:.1f}m, "
            f"throughput={winner['throughputVeh']} kendaraan -- "
            f"skor gabungan delay+antrean paling rendah dibanding "
            f"{len(results) - 1} kandidat lain."
        )

        return Recommendation(
            recommendedPhase=baseline.recommendedPhase,
            recommendedGreenSeconds=winner["greenSeconds"],
            currentGreenSeconds=baseline.currentGreenSeconds,
            currentPhase=baseline.currentPhase,
            confidence=baseline.confidence,
            expectedDelayReductionPercent=delayReductionPercent,
            source="scenario-generator",
            reason=reason,
        )
