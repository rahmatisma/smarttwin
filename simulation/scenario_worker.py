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

from app.pipeline.traffic_state_builder import (  # noqa: E402
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)

INTERSECTION_ID = "simpang4-pingit"
CACHE_TABLE = "liveScenarioCache"

# Tabel riwayat (append-only). Beda peran dari CACHE_TABLE yang cuma 1 baris
# dan ditimpa tiap siklus: cache dipakai dashboard untuk "sekarang", tabel di
# bawah ini menyimpan jejak "pernah memutuskan apa saja" untuk halaman Riwayat
# dan laporan teknis.
RECOMMENDATIONS_TABLE = "recommendations"
SIMULATIONS_TABLE = "simulations"
SIMULATION_METRICS_TABLE = "simulationMetrics"

# recommendations.intersectionId itu bigint (FK ke intersections.id), bukan
# teks seperti INTERSECTION_ID di atas. Di-cache supaya tidak query tiap siklus.
_intersection_row_id: int | None = None

# Jendela rekaman berjarak 5 detik (lihat cv_csv_bridge.py) -- 12 langkah
# per siklus (interval default 60s) kira-kira 1 menit rekaman per siklus,
# supaya kondisi benar-benar terlihat berbeda antar siklus, bukan cuma
# maju beberapa detik yang nyaris tidak berubah.
REPLAY_STEP_DEFAULT = 12


class ReplaySource:
    """Memutar ulang urutan TrafficState terekam (49 menit, 15 Agustus),
    bukan selalu mengambil kondisi TERBARU seperti loadTrafficState().

    Kenapa ini perlu: kalau CV/data live tidak sedang berjalan, "kondisi
    terbaru" di database tidak pernah berganti -- worker akan mengevaluasi
    kondisi yang SAMA berulang kali walau dipanggil puluhan kali (lihat
    trafficStateId di riwayat: identik semua). Mode ini memutar maju
    melalui 538 kondisi yang sudah terekam, jadi tiap siklus benar-benar
    mengevaluasi situasi berbeda -- datanya asli, cuma urutan
    pemutarannya yang diatur.

    Posisi SENGAJA tidak disimpan ke disk: tiap kali worker dijalankan
    ulang, replay dimulai dari awal lagi. Ini membuat urutan kejadian
    selalu identik antar sesi -- cocok untuk latihan presentasi berkali-
    kali dengan hasil yang bisa direproduksi persis sama.
    """

    def __init__(
        self,
        builder: "TrafficStateBuilder",
        intersection_id: str,
        step: int = REPLAY_STEP_DEFAULT,
    ) -> None:
        self._builder = builder
        self._intersection_id = intersection_id
        self._step = max(1, step)
        self._state_ids: list[int] | None = None
        self._maps: tuple[dict, dict, dict] | None = None
        self._position = 0

    def _ensure_loaded(self) -> None:
        if self._state_ids is not None:
            return

        intersection_map, approach_map, lane_map = (
            self._builder.build_relation_maps()
        )
        self._maps = (intersection_map, approach_map, lane_map)

        row_id = next(
            (
                rid
                for rid, row in intersection_map.items()
                if row.get("intersectionId") == self._intersection_id
            ),
            None,
        )
        if row_id is None:
            raise RuntimeError(
                f"Intersection '{self._intersection_id}' tidak ditemukan "
                "di tabel intersections."
            )

        rows = (
            self._builder.supabase.table("trafficStates")
            .select("id")
            .eq("intersectionId", row_id)
            .order("windowStart", desc=False)
            .execute()
        ).data or []

        self._state_ids = [int(row["id"]) for row in rows]
        if not self._state_ids:
            raise RuntimeError(
                f"Tidak ada trafficStates untuk '{self._intersection_id}' "
                "-- replay butuh data historis yang sudah terekam."
            )

    def next(self):
        """Kembalikan (BuiltTrafficState, posisi_1_basis, total) lalu maju."""
        self._ensure_loaded()
        assert self._state_ids is not None and self._maps is not None

        index = self._position % len(self._state_ids)
        traffic_state_id = self._state_ids[index]
        self._position += self._step

        row = (
            self._builder.supabase.table("trafficStates")
            .select(
                "id, intersectionId, windowStart, windowEnd, source, "
                "processingJobId, createdAt"
            )
            .eq("id", traffic_state_id)
            .limit(1)
            .execute()
        ).data
        if not row:
            raise RuntimeError(
                f"trafficStates id={traffic_state_id} tidak ditemukan "
                "(terhapus setelah daftar ID dimuat?)."
            )

        lane_metrics = self._builder.get_lane_metrics([traffic_state_id])
        intersection_map, approach_map, lane_map = self._maps
        built = self._builder.build_state(
            row[0], lane_metrics, intersection_map, approach_map, lane_map
        )
        if built is None:
            raise RuntimeError(
                f"Gagal membangun TrafficState id={traffic_state_id}."
            )
        return built, index + 1, len(self._state_ids)


def _make_engine(short_sim_steps: int | None = None) -> ScenarioEngine:
    options = {"short_sim_steps": short_sim_steps} if short_sim_steps is not None else {}
    return ScenarioEngine(
        sumo_binary=sumoBinary,
        sumo_config=sumoConfig,
        tls_id=tlsId,
        approach_to_phase=approachToPhase,
        run_simulation_fn=runSimulation,
        **options,
    )


def evaluate_state(state, *, forecast=None, full_cycle: bool = False,
                   simulation_steps: int | None = None) -> dict[str, Any]:
    """Evaluasi satu state; fungsi ini tidak menyentuh cache/database."""
    engine = _make_engine(simulation_steps)
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
    # LOS + delay per lengan dari kandidat pemenang. Disisipkan ke blob JSON
    # rekomendasi (kolom `recommendation`), BUKAN sebagai kolom baru tabel
    # liveScenarioCache -- supaya tidak perlu migrasi skema.
    recommendation_payload["losByApproach"] = winner.get("losByApproach") or {}
    recommendation_payload["delayByApproachSeconds"] = (
        winner.get("delayByApproachSeconds") or {}
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
    # Simpan ketiga hasil agar Digital Twin tidak menghitung logic sendiri.
    # Retry legacy menjaga worker tetap hidup bila migrasi kolom `candidates`
    # belum dijalankan; endpoint akan mengembalikan candidates=[] secara jujur.
    try:
        (
            supabase.table(CACHE_TABLE)
            .upsert(payload, on_conflict="intersectionId")
            .execute()
        )
    except Exception as exc:
        legacy_payload = {
            key: value for key, value in payload.items()
            if key != "candidates"
        }
        print(
            "[WARN] Kolom liveScenarioCache.candidates belum tersedia; "
            "menulis format legacy. Jalankan backend/app/db/live_scenario_cache.sql. "
            f"Detail: {exc}"
        )
        (
            supabase.table(CACHE_TABLE)
            .upsert(legacy_payload, on_conflict="intersectionId")
            .execute()
        )


def _resolve_intersection_row_id(supabase) -> int | None:
    """intersections.id (bigint) dari intersectionId (teks). Di-cache."""
    global _intersection_row_id

    if _intersection_row_id is not None:
        return _intersection_row_id

    try:
        res = (
            supabase.table("intersections")
            .select("id")
            .eq("intersectionId", INTERSECTION_ID)
            .limit(1)
            .execute()
        )
        if res.data:
            _intersection_row_id = int(res.data[0]["id"])
    except Exception as exc:
        print(f"[WARN] Gagal membaca intersections.id: {exc}")

    return _intersection_row_id


def write_history(supabase, payload: dict[str, Any], state) -> None:
    """Simpan hasil siklus ini sebagai riwayat permanen (append-only).

    Ditulis TIAP siklus, termasuk saat isinya sama dengan siklus sebelumnya --
    penanda "berubah" sengaja TIDAK dihitung di sini, melainkan di halaman
    Riwayat dengan membandingkan baris berurutan. Alasannya: data yang tidak
    ditulis tidak bisa dipulihkan, sedangkan cara menampilkan selalu bisa
    diubah kapan saja.

    Kegagalan di sini TIDAK BOLEH mematikan worker: tugas utama worker adalah
    mengisi cache untuk dashboard live (write_cache di atas). Riwayat itu
    pelengkap, jadi errornya cukup diperingatkan.
    """
    intersection_row_id = _resolve_intersection_row_id(supabase)
    if intersection_row_id is None:
        print("[WARN] intersections.id tidak diketahui; riwayat dilewati.")
        return

    recommendation = payload.get("recommendation") or {}
    cycle_plan = recommendation.get("cyclePlan") or {}
    phases = cycle_plan.get("phases") or []

    if not phases:
        print("[WARN] cyclePlan kosong; riwayat dilewati.")
        return

    timestamp = payload["updatedAt"]

    # Sumber dilaporkan APA ADANYA dari engine -- termasuk saat jatuh ke
    # rule-based karena SUMO gagal/cache basi. Riwayat yang menyembunyikan
    # fallback justru berbahaya: alur terlihat mulus padahal kotak 7/8/9
    # sempat terlewat.
    source = recommendation.get("source") or "unknown"
    winner_id = payload.get("candidateId")

    # ------------------------------------------------------------------
    # 1. recommendations -- satu baris per lengan
    # ------------------------------------------------------------------
    rows = []
    for phase in phases:
        approach = str(phase.get("approach", "")).lower().strip()
        if not approach:
            continue
        rows.append(
            {
                "intersectionId": intersection_row_id,
                "timestamp": timestamp,
                # Nama lengan disimpan dalam bahasa Inggris (north/south/
                # east/west) mengikuti kontrak docs/data-contract.md.
                # Penerjemahan ke Indonesia dilakukan di lapisan tampilan.
                "recommendedPhase": approach,
                "recommendedGreenSeconds": int(phase.get("greenSeconds", 0)),
                "currentGreenSeconds": int(
                    recommendation.get("currentGreenSeconds", 0) or 0
                ),
                "expectedDelayReductionPercent": float(
                    recommendation.get("expectedDelayReductionPercent", 0) or 0
                ),
                "confidence": float(recommendation.get("confidence", 0) or 0),
                "reason": (
                    f"{source} | kandidat={winner_id} | "
                    f"delay={payload.get('avgDelaySeconds')}s | "
                    f"antrean={payload.get('avgQueueLengthM')}m | "
                    f"LOS={payload.get('los')}"
                ),
                "source": source,
            }
        )

    try:
        inserted = (
            supabase.table(RECOMMENDATIONS_TABLE).insert(rows).execute()
        )
        recommendation_id = (
            int(inserted.data[0]["id"]) if inserted.data else None
        )
    except Exception as exc:
        print(f"[WARN] Gagal menyimpan riwayat rekomendasi: {exc}")
        return

    # ------------------------------------------------------------------
    # 2. simulations + 3. simulationMetrics -- satu baris per KANDIDAT,
    #    supaya halaman Riwayat bisa menampilkan perbandingan ketiganya
    #    ("kenapa kandidat ini yang menang"), bukan cuma pemenangnya.
    # ------------------------------------------------------------------
    traffic_state_id = getattr(state, "trafficStateId", None)

    for candidate in payload.get("candidates") or []:
        candidate_id = candidate.get("candidateId")
        try:
            simulation = (
                supabase.table(SIMULATIONS_TABLE)
                .insert(
                    {
                        "intersectionId": intersection_row_id,
                        "trafficStateId": traffic_state_id,
                        "recommendationId": recommendation_id,
                        "simulationName": f"{candidate_id} @ {timestamp}",
                        "simulationType": "scenario-comparison",
                        "engine": source,
                        "status": (
                            "winner" if candidate_id == winner_id else "completed"
                        ),
                        "startedAt": timestamp,
                        "completedAt": timestamp,
                    }
                )
                .execute()
            )
            if not simulation.data:
                continue
            simulation_id = int(simulation.data[0]["id"])

            # LOS sengaja TIDAK disimpan: nilainya murni turunan dari
            # avgDelaySeconds lewat calculate_los(), jadi menyimpannya cuma
            # menduplikasi data yang bisa dihitung ulang kapan saja.
            metrics = [
                ("avgDelaySeconds", candidate.get("avgDelaySeconds"), "s"),
                ("avgQueueLengthM", candidate.get("avgQueueLengthM"), "m"),
                ("throughputVeh", candidate.get("throughputVeh"), "veh"),
            ]
            metric_rows = [
                {
                    "simulationId": simulation_id,
                    "metricName": name,
                    "metricValue": float(value),
                    "unit": unit,
                }
                for name, value, unit in metrics
                if value is not None
            ]
            if metric_rows:
                supabase.table(SIMULATION_METRICS_TABLE).insert(
                    metric_rows
                ).execute()
        except Exception as exc:
            print(f"[WARN] Gagal menyimpan simulasi '{candidate_id}': {exc}")


def evaluate_once(
    supabase,
    *,
    full_cycle: bool = False,
    replay: "ReplaySource | None" = None,
) -> dict[str, Any]:
    if replay is not None:
        state, posisi, total = replay.next()
        print(
            f"[REPLAY] kondisi {posisi}/{total} "
            f"(window {state.windowStart} .. {state.windowEnd})"
        )
        # Forecast dilewati di mode replay -- forecast_client membaca
        # kondisi TERBARU (bukan yang sedang diputar), jadi ikut sertakan
        # forecast di sini akan mencampur dua kerangka waktu berbeda.
        forecast = None
    else:
        state = loadTrafficState()
        forecast = ForecastClient().get_live_forecast()

    payload = evaluate_state(state, forecast=forecast, full_cycle=full_cycle)

    if replay is not None:
        # Ditandai jujur, bukan disamarkan seolah realtime -- sama seperti
        # tim sudah jujur soal memakai rekaman CCTV, bukan stream live.
        payload["recommendation"]["source"] = (
            f"{payload['recommendation']['source']}+replay"
        )

    write_cache(supabase, payload)
    write_history(supabase, payload, state)
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
        dest="full_cycle",
        action="store_true",
        default=True,
        help="Uji tiga program CyclePlan empat lengan (default).",
    )
    parser.add_argument(
        "--single-phase",
        dest="full_cycle",
        action="store_false",
        help="Mode studi lama satu fase; jangan dipakai untuk halaman Digital Twin.",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help=(
            "Putar ulang urutan TrafficState terekam (data historis asli) "
            "alih-alih selalu mengambil kondisi terbaru. Dipakai saat CV "
            "tidak sedang berjalan supaya tiap siklus tetap mengevaluasi "
            "kondisi yang benar-benar berbeda."
        ),
    )
    parser.add_argument(
        "--replay-step",
        type=int,
        default=REPLAY_STEP_DEFAULT,
        help=(
            "Berapa jendela rekaman dilompati tiap siklus replay "
            f"(default {REPLAY_STEP_DEFAULT} -> jendela 5 detik, "
            "jadi kira-kira 1 menit rekaman per siklus)."
        ),
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

    replay_source = None
    if args.replay:
        builder = TrafficStateBuilder(TrafficStateBuilderConfig())
        replay_source = ReplaySource(
            builder, INTERSECTION_ID, step=args.replay_step
        )
        print(
            f"[REPLAY] mode aktif -- melompat {args.replay_step} jendela "
            "per siklus, dimulai dari kondisi paling lama."
        )

    while True:
        try:
            row = evaluate_once(
                supabase, full_cycle=args.full_cycle, replay=replay_source
            )
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
