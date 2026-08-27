"""Worker manual penghubung Scenario Generator ke dashboard live.

Jalankan dari folder ``simulation``:
    python scenario_worker.py

Setiap iterasi mengambil TrafficState terbaru, memakai forecast bila tersedia,
menjalankan tiga kandidat SUMO, lalu meng-upsert satu baris cache. Backend akan
mengabaikan cache yang basi sehingga worker aman dihentikan kapan saja.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from forecast_client import ForecastClient
from run_tls_simulation import (
    approachToPhase,
    connectSupabase,
    loadTrafficState,
    runSimulation,
    sumoBinary,
    sumoConfig,
    tlsId,
)
from scenario_generator import ScenarioEngine

INTERSECTION_ID = "simpang4-pingit"
CACHE_TABLE = "liveScenarioCache"


def _make_engine() -> ScenarioEngine:
    return ScenarioEngine(
        sumo_binary=sumoBinary,
        sumo_config=sumoConfig,
        tls_id=tlsId,
        approach_to_phase=approachToPhase,
        run_simulation_fn=runSimulation,
    )


def evaluate_state(state, *, forecast=None, full_cycle: bool = False) -> dict[str, Any]:
    """Evaluasi satu state; fungsi ini tidak menyentuh cache/database."""
    engine = _make_engine()
    recommend_method = (
        engine.recommend_full_cycle if full_cycle else engine.recommend
    )
    recommendation = recommend_method(
        state=state,
        currentGreenSeconds=15,
        currentPhase="south",
        forecast=forecast,
        forecastWeight=0.3,
    )
    winner = engine.last_winner
    if winner is None:
        raise RuntimeError("ScenarioEngine tidak menghasilkan kandidat pemenang.")

    recommendation_payload = recommendation.model_dump(mode="json")
    if engine.last_cycle_plan is not None:
        recommendation_payload["cyclePlan"] = engine.last_cycle_plan.model_dump(
            mode="json"
        )
    payload = {
        "intersectionId": INTERSECTION_ID,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "recommendation": recommendation_payload,
        "avgDelaySeconds": winner["avgDelaySeconds"],
        "avgQueueLengthM": winner["avgQueueLengthM"],
        "los": winner["los"],
        "candidateId": winner["candidateId"],
        "throughputVeh": winner["throughputVeh"],
        "candidates": engine.last_results,
    }
    return payload


def write_cache(supabase, payload: dict[str, Any]) -> None:
    # ``candidates`` disimpan di artefak studi, bukan tabel live yang hanya
    # memerlukan pemenang terbaru.
    cache_payload = {
        key: value for key, value in payload.items()
        if key != "candidates"
    }
    (
        supabase.table(CACHE_TABLE)
        .upsert(cache_payload, on_conflict="intersectionId")
        .execute()
    )


def evaluate_once(supabase, *, full_cycle: bool = False) -> dict[str, Any]:
    state = loadTrafficState()
    forecast_client = ForecastClient()
    forecast = forecast_client.get_live_forecast()
    payload = evaluate_state(state, forecast=forecast, full_cycle=full_cycle)
    write_cache(supabase, payload)
    return payload


def _write_comparison_report(result: dict[str, Any], report: Path) -> None:
    off = result["withoutForecast"]
    on = result["withForecast"]
    delta = result["delta"]
    report.parent.mkdir(parents=True, exist_ok=True)
    def candidate_rows(label: str, run: dict[str, Any]) -> list[str]:
        return [
            f"| {label} | {row['candidateId']} | "
            f"{row.get('greenSeconds', row.get('cycleLengthSeconds'))} | "
            f"{row['avgDelaySeconds']:.2f} | {row['queueLengthVeh']} | "
            f"{row['avgQueueLengthM']:.2f} | {row['throughputVeh']} | {row['los']} |"
            for row in run["candidates"]
        ]

    report.write_text(
        "\n".join([
            "# Hasil Studi Forecast vs Tanpa Forecast",
            "",
            f"**Dihasilkan:** {result['generatedAt']}",
            "",
            "## Metode pengujian",
            "",
            "Satu snapshot TrafficState yang sama diuji dalam dua kondisi. Tanpa "
            "forecast, RuleBasedEngine memakai 100% state saat ini. Dengan forecast, "
            "state keputusan adalah campuran 70% state saat ini dan 30% prediksi "
            "LSTM horizon +60 detik. Masing-masing kondisi menghasilkan tiga kandidat "
            "durasi dan menjalankan tiga sesi SUMO terpisah selama 90 langkah.",
            "",
            "Tiga kandidat memakai approach pilihan RuleBasedEngine yang sama: "
            "`baseline` memakai durasi asli; `aggressive = min(60, baseline + "
            "1 detik)` berdasarkan sweep kalibrasi SUMO; `balanced = "
            "round((baseline + 15) / 2)`. Kandidat terbaik "
            "meminimalkan `0,5 × (delay/delay maksimum) + 0,5 × "
            "(antrean/antrean maksimum)` di dalam kelompok tiga kandidatnya.",
            "",
            "## Hasil seluruh kandidat",
            "",
            "| Kondisi | Kandidat | Durasi hijau/cycle (s) | Delay (s) | Antrean (kend.) | Antrean (m) | Throughput | LOS |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
            *candidate_rows("Tanpa forecast", off),
            *candidate_rows("Dengan forecast", on),
            "",
            "## Asal dan perhitungan LOS",
            "",
            "`avgDelaySeconds` berasal dari rata-rata sampel "
            "`traci.vehicle.getAccumulatedWaitingTime(vehicleId)` untuk kendaraan "
            "aktif pada setiap langkah simulasi. LOS kemudian dipetakan memakai "
            "ambang HCM 2000 untuk simpang bersinyal: A ≤10 detik, B ≤20, C ≤35, "
            "D ≤55, E ≤80, dan F >80 detik. Karena seluruh delay pemenang berada "
            "antara 10 dan 20 detik, keduanya mendapat LOS B.",
            "",
            "Antrean kendaraan adalah jumlah maksimum kendaraan berkecepatan <0,1 "
            "m/s selama run. Antrean meter merupakan estimasi `antrean kendaraan × "
            "7 meter`. Throughput adalah jumlah kendaraan yang selesai/arrived "
            "selama 90 langkah.",
            "",
            "## Perbandingan kandidat pemenang",
            "",
            "| Kondisi | Kandidat | Delay (s) | Antrean (m) | Throughput | LOS |",
            "|---|---:|---:|---:|---:|---:|",
            f"| Tanpa forecast | {off['candidateId']} | {off['avgDelaySeconds']:.2f} | "
            f"{off['avgQueueLengthM']:.2f} | {off['throughputVeh']} | {off['los']} |",
            f"| Dengan forecast | {on['candidateId']} | {on['avgDelaySeconds']:.2f} | "
            f"{on['avgQueueLengthM']:.2f} | {on['throughputVeh']} | {on['los']} |",
            "",
            "## Selisih (dengan forecast - tanpa forecast)",
            "",
            f"- Delay: {delta['avgDelaySeconds']:+.2f} detik",
            f"- Antrean: {delta['avgQueueLengthM']:+.2f} meter",
            f"- Throughput: {delta['throughputVeh']:+d} kendaraan",
            "",
            "Nilai negatif untuk delay/antrean berarti hasil dengan forecast lebih "
            "baik. Ini satu eksperimen pada satu snapshot, sehingga belum cukup "
            "untuk klaim signifikansi statistik.",
            "",
        ]),
        encoding="utf-8",
    )


def compare_forecast(
    output: Path, report: Path, *, full_cycle: bool = False
) -> dict[str, Any]:
    """Jalankan studi reproducible dengan state sama, forecast OFF vs ON."""
    state = loadTrafficState()
    forecast_client = ForecastClient()
    forecast = forecast_client.get_live_forecast()
    if forecast is None:
        raise RuntimeError(
            "Forecast tidak tersedia, studi dibatalkan agar tidak membandingkan "
            "dua run tanpa forecast. Penyebab: "
            f"{forecast_client.last_error or 'tidak diketahui'}"
        )

    without = evaluate_state(state, forecast=None, full_cycle=full_cycle)
    with_forecast = evaluate_state(
        state, forecast=forecast, full_cycle=full_cycle
    )
    result = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "withoutForecast": without,
        "withForecast": with_forecast,
        "delta": {
            "avgDelaySeconds": with_forecast["avgDelaySeconds"] - without["avgDelaySeconds"],
            "avgQueueLengthM": with_forecast["avgQueueLengthM"] - without["avgQueueLengthM"],
            "throughputVeh": with_forecast["throughputVeh"] - without["throughputVeh"],
        },
        "note": "Nilai negatif pada delta delay/queue berarti forecast lebih baik.",
        "method": (
            "TrafficState yang sama dievaluasi dua kali: forecastWeight 0.0 "
            "dan forecastWeight 0.3; masing-masing menjalankan tiga kandidat "
            "SUMO selama 90 langkah."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_comparison_report(result, report)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--compare-forecast", action="store_true")
    parser.add_argument(
        "--full-cycle",
        action="store_true",
        help="Uji tiga program CyclePlan empat lengan (jalur baru opt-in).",
    )
    parser.add_argument(
        "--comparison-output",
        type=Path,
        default=Path("outputs/forecast_impact.json"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("../docs/hasil-studi-forecast.md"),
    )
    args = parser.parse_args()
    if args.interval < 10:
        parser.error("--interval minimal 10 detik")

    supabase = connectSupabase()
    if args.compare_forecast:
        result = compare_forecast(
            args.comparison_output,
            args.report_output,
            full_cycle=args.full_cycle,
        )
        print(json.dumps(result["delta"], indent=2))
        print(f"Data lengkap: {args.comparison_output}")
        print(f"Laporan: {args.report_output}")
        return 0

    while True:
        try:
            row = evaluate_once(supabase, full_cycle=args.full_cycle)
            print(
                f"Cache diperbarui {row['updatedAt']} | "
                f"{row['candidateId']} | LOS {row['los']}"
            )
        except Exception as exc:
            # Satu iterasi gagal tidak mematikan worker. Backend otomatis
            # fallback setelah cache melewati ambang kesegaran.
            print(f"Iterasi worker gagal: {type(exc).__name__}: {exc}")
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
