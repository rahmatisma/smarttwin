"""Studi forecast ON/OFF pada banyak TrafficState tanpa melatih model.

Seluruh run serial dan dapat diberi jeda agar tidak membebani laptop terus-
menerus. Output menyimpan setiap snapshot dan ringkasan tiga metrik operasional.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for import_path in (ROOT, ROOT / "backend", ROOT / "simulation"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from app.schemas.traffic import ApproachState, TrafficState  # noqa: E402
from app.services.per_approach_forecast_service import (  # noqa: E402
    per_approach_forecast_service,
)
from app.services.traffic_service import TrafficService  # noqa: E402
from scenario_worker import evaluate_state  # noqa: E402


INTERSECTION_ID = "simpang4-pingit"
HISTORY_STEPS = 12
INTERVAL_SECONDS = 5
COMMON_SIMULATION_STEPS = 256


def _timestamp(record: dict[str, Any]) -> datetime:
    state = record["trafficState"]
    raw = state.get("windowEnd") or state["windowStart"]
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


def _to_state(record: dict[str, Any]) -> TrafficState:
    state = record["trafficState"]
    return TrafficState(
        intersectionId=INTERSECTION_ID,
        windowStart=state["windowStart"],
        windowEnd=state["windowEnd"],
        approaches=[ApproachState(**row) for row in record["approaches"]],
    )


def contiguous_histories(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Semua window 12 langkah unik dan berinterval tepat lima detik."""
    latest_by_timestamp = {_timestamp(record): record for record in records}
    ordered = sorted(latest_by_timestamp.items(), key=lambda item: item[0])
    histories = []
    for end in range(HISTORY_STEPS, len(ordered) + 1):
        window = ordered[end - HISTORY_STEPS:end]
        if all(
            (window[index][0] - window[index - 1][0]).total_seconds()
            == INTERVAL_SECONDS
            for index in range(1, len(window))
        ):
            histories.append([item[1] for item in window])
    return histories


def evenly_spaced(items: list[Any], count: int) -> list[Any]:
    if count <= 0:
        raise ValueError("Jumlah snapshot harus lebih besar dari nol")
    if len(items) <= count:
        return items
    indexes = [round(index * (len(items) - 1) / (count - 1)) for index in range(count)]
    return [items[index] for index in indexes]


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def wins(metric: str, direction: str) -> int:
        return sum(
            row["delta"][metric] < 0 if direction == "lower" else row["delta"][metric] > 0
            for row in rows
        )

    count = len(rows)
    averages = {
        metric: sum(row["delta"][metric] for row in rows) / max(1, count)
        for metric in ("avgDelaySeconds", "avgQueueLengthM", "throughputVeh")
    }
    return {
        "snapshots": count,
        "delayImproved": wins("avgDelaySeconds", "lower"),
        "queueImproved": wins("avgQueueLengthM", "lower"),
        "throughputImproved": wins("throughputVeh", "higher"),
        "allThreeImproved": sum(
            row["delta"]["avgDelaySeconds"] < 0
            and row["delta"]["avgQueueLengthM"] < 0
            and row["delta"]["throughputVeh"] > 0
            for row in rows
        ),
        "meanDelta": averages,
    }


def _write_markdown(result: dict[str, Any], path: Path) -> None:
    summary = result["summary"]
    lines = [
        "# Studi Multi-Snapshot Forecast LSTM",
        "",
        f"Dihasilkan: {result['generatedAt']}",
        "",
        "Tidak ada training pada studi ini. Checkpoint LSTM yang sudah ada "
        "dipakai untuk inferensi, lalu setiap TrafficState diuji forecast OFF/ON "
        "dengan Scenario Generator dan SUMO secara serial. Kedua kondisi memakai "
        f"horizon identik {COMMON_SIMULATION_STEPS} langkah agar throughput adil.",
        "",
        f"- Snapshot: {summary['snapshots']}",
        f"- Delay membaik: {summary['delayImproved']}/{summary['snapshots']}",
        f"- Antrean membaik: {summary['queueImproved']}/{summary['snapshots']}",
        f"- Throughput membaik: {summary['throughputImproved']}/{summary['snapshots']}",
        f"- Ketiganya membaik bersamaan: {summary['allThreeImproved']}/{summary['snapshots']}",
        "",
        "| Timestamp | Δ delay (s) | Δ antrean (m) | Δ throughput |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {row['timestamp']} | {row['delta']['avgDelaySeconds']:+.2f} | "
        f"{row['delta']['avgQueueLengthM']:+.2f} | {row['delta']['throughputVeh']:+d} |"
        for row in result["runs"]
    )
    lines.extend([
        "",
        "Δ = dengan forecast − tanpa forecast. Nilai negatif lebih baik untuk "
        "delay/antrean; nilai positif lebih baik untuk throughput. Hasil ini "
        "berasal dari satu sesi rekaman dan bukan validasi lintas hari.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_batch(snapshot_count: int, history_limit: int, pause_seconds: float,
              full_cycle: bool) -> dict[str, Any]:
    records = TrafficService().get_latest_traffic(
        intersection_id=INTERSECTION_ID,
        limit=history_limit,
    )
    histories = evenly_spaced(contiguous_histories(records), snapshot_count)
    if len(histories) < snapshot_count:
        raise RuntimeError(
            f"Hanya tersedia {len(histories)} snapshot kontinu; diminta {snapshot_count}."
        )

    runs = []
    for index, history in enumerate(histories, start=1):
        state = _to_state(history[-1])
        forecast = per_approach_forecast_service.predict_records(history)
        # Horizon wajib sama antar-kondisi. Tanpa nilai tetap, full-cycle ON
        # yang lebih pendek berhenti lebih awal dan throughput terlihat turun
        # hanya karena durasi observasinya lebih singkat.
        without = evaluate_state(
            state, forecast=None, full_cycle=full_cycle,
            simulation_steps=COMMON_SIMULATION_STEPS,
        )
        with_forecast = evaluate_state(
            state, forecast=forecast, full_cycle=full_cycle,
            simulation_steps=COMMON_SIMULATION_STEPS,
        )
        delta = {
            "avgDelaySeconds": with_forecast["avgDelaySeconds"] - without["avgDelaySeconds"],
            "avgQueueLengthM": with_forecast["avgQueueLengthM"] - without["avgQueueLengthM"],
            "throughputVeh": int(with_forecast["throughputVeh"] - without["throughputVeh"]),
        }
        runs.append({
            "index": index,
            "timestamp": state.windowEnd.isoformat(),
            "withoutForecast": without,
            "withForecast": with_forecast,
            "delta": delta,
        })
        print(f"Snapshot {index}/{snapshot_count}: {delta}")
        if pause_seconds and index < snapshot_count:
            time.sleep(pause_seconds)

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": (
            "existing LSTM checkpoint; forecastWeight 0.3; serial SUMO; "
            f"common horizon {COMMON_SIMULATION_STEPS} steps"
        ),
        "fullCycle": full_cycle,
        "runs": runs,
        "summary": _summary(runs),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=int, default=10)
    parser.add_argument("--history-limit", type=int, default=100)
    parser.add_argument("--pause-seconds", type=float, default=2.0)
    parser.add_argument("--single-phase", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("simulation/outputs/forecast_impact_batch.json"))
    parser.add_argument("--report", type=Path, default=Path("docs/hasil-studi-forecast-multi-snapshot.md"))
    args = parser.parse_args()
    if not 10 <= args.snapshots <= 20:
        parser.error("--snapshots harus 10 sampai 20 sesuai protokol audit")
    result = run_batch(
        args.snapshots, args.history_limit, max(0.0, args.pause_seconds), not args.single_phase
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_markdown(result, args.report)
    print(json.dumps(result["summary"], indent=2))
    print(f"Data: {args.output.resolve()}")
    print(f"Laporan: {args.report.resolve()}")


if __name__ == "__main__":
    main()
