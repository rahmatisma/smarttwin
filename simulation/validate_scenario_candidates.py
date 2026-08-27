"""Validasi kandidat Scenario Generator pada beberapa snapshot dan seed.

Skrip ini hanya membaca histori TrafficState dan menjalankan SUMO. Ia tidak
menulis cache live maupun tabel simulations, sehingga aman dipakai sebagai
eksperimen terpisah dari worker produksi.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SIMULATION_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SIMULATION_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT, SIMULATION_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.schemas.traffic import ApproachState, TrafficState
from app.services.traffic_service import TrafficService
from decision_engine.rule_based_engine import RuleBasedEngine
from run_tls_simulation import approachToPhase, runSimulation, sumoBinary, sumoConfig, tlsId
from scenario_generator import generate_candidate_plans, select_best_scenario, simulate_candidate

DEFAULT_JSON = SIMULATION_ROOT / "outputs" / "scenario_multiseed_validation.json"
DEFAULT_REPORT = PROJECT_ROOT / "docs" / "hasil-validasi-multisnapshot-multiseed.md"


def _pressure(record: dict[str, Any]) -> float:
    approaches = record.get("approaches") or []
    return sum(
        float(row.get("volume", 0) or 0)
        + float(row.get("queueLengthVeh", 0) or 0)
        for row in approaches
        if isinstance(row, dict)
    )


def select_representative_records(
    records: list[dict[str, Any]], count: int = 3
) -> list[dict[str, Any]]:
    """Pilih quantile tekanan rendah-sedang-tinggi secara deterministik."""
    if count <= 0:
        raise ValueError("count harus lebih besar dari nol")
    valid = [
        row for row in records
        if isinstance(row.get("trafficState"), dict)
        and isinstance(row.get("approaches"), list)
        and len(row["approaches"]) == 4
    ]
    if not valid:
        raise ValueError("Tidak ada TrafficState lengkap untuk divalidasi")
    ordered = sorted(valid, key=_pressure)
    target_count = min(count, len(ordered))
    if target_count == 1:
        return [ordered[len(ordered) // 2]]
    indices = [
        round(index * (len(ordered) - 1) / (target_count - 1))
        for index in range(target_count)
    ]
    return [ordered[index] for index in dict.fromkeys(indices)]


def _to_traffic_state(record: dict[str, Any]) -> TrafficState:
    state = record["trafficState"]
    return TrafficState(
        intersectionId="simpang4-pingit",
        windowStart=state["windowStart"],
        windowEnd=state["windowEnd"],
        approaches=[ApproachState(**row) for row in record["approaches"]],
    )


def aggregate_results(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["candidateId"], []).append(row)
    output = {}
    for candidate_id, items in grouped.items():
        delays = [float(item["avgDelaySeconds"]) for item in items]
        queues = [float(item["avgQueueLengthM"]) for item in items]
        throughputs = [float(item["throughputVeh"]) for item in items]
        output[candidate_id] = {
            "runs": len(items),
            "meanDelaySeconds": statistics.fmean(delays),
            "stdevDelaySeconds": statistics.stdev(delays) if len(delays) > 1 else 0.0,
            "meanQueueLengthM": statistics.fmean(queues),
            "stdevQueueLengthM": statistics.stdev(queues) if len(queues) > 1 else 0.0,
            "meanThroughputVeh": statistics.fmean(throughputs),
        }
    return output


def run_validation(snapshot_count: int, seeds: list[int], history_limit: int) -> dict[str, Any]:
    records = TrafficService().get_latest_traffic(
        intersection_id="simpang4-pingit", limit=history_limit
    )
    snapshots = select_representative_records(records, snapshot_count)
    engine = RuleBasedEngine()
    rows: list[dict[str, Any]] = []
    winners: Counter[str] = Counter()

    for snapshot_index, record in enumerate(snapshots, start=1):
        traffic_state = _to_traffic_state(record)
        baseline = engine.recommend(
            state=traffic_state,
            currentGreenSeconds=15,
            currentPhase="south",
        )
        phase = approachToPhase[baseline.recommendedPhase]
        state_id = record["trafficState"].get("id")
        for seed in seeds:
            batch = [
                simulate_candidate(
                    candidate,
                    sumo_binary=sumoBinary,
                    sumo_config=sumoConfig,
                    tls_id=tlsId,
                    sumo_phase=phase,
                    run_simulation_fn=runSimulation,
                    step_limit=90,
                    seed=seed,
                )
                for candidate in generate_candidate_plans(baseline)
            ]
            winner = select_best_scenario(batch)
            winners[winner["candidateId"]] += 1
            for result in batch:
                rows.append({
                    **result,
                    "snapshotIndex": snapshot_index,
                    "trafficStateId": state_id,
                    "pressureScore": _pressure(record),
                    "seed": seed,
                })

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "method": "multi-snapshot, multi-seed simulation parameter validation",
        "snapshotCount": len(snapshots),
        "seeds": seeds,
        "runsPerCandidate": len(snapshots) * len(seeds),
        "winnerCounts": dict(winners),
        "aggregate": aggregate_results(rows),
        "runs": rows,
        "limitations": [
            "Snapshot mengubah keputusan approach/durasi, tetapi route demand SUMO masih statis.",
            "Hasil belum merupakan kalibrasi model terhadap data lapangan.",
            "Forecast tidak dipakai agar pengaruh kandidat durasi diisolasi.",
        ],
    }


def write_outputs(result: dict[str, Any], json_path: Path, report_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Hasil Validasi Multi-Snapshot dan Multi-Seed",
        "",
        f"Dihasilkan: `{result['generatedAt']}`",
        "",
        f"- Snapshot representatif: {result['snapshotCount']}",
        f"- Seed SUMO: {', '.join(map(str, result['seeds']))}",
        f"- Run per kandidat: {result['runsPerCandidate']}",
        "- Forecast: tidak dipakai untuk mengisolasi pengaruh durasi kandidat",
        "",
        "## Hasil agregat",
        "",
        "| Kandidat | Run | Delay mean +/- SD (s) | Antrean mean +/- SD (m) | Throughput mean | Menang |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for candidate_id, summary in result["aggregate"].items():
        lines.append(
            f"| {candidate_id} | {summary['runs']} | "
            f"{summary['meanDelaySeconds']:.2f} +/- {summary['stdevDelaySeconds']:.2f} | "
            f"{summary['meanQueueLengthM']:.2f} +/- {summary['stdevQueueLengthM']:.2f} | "
            f"{summary['meanThroughputVeh']:.2f} | "
            f"{result['winnerCounts'].get(candidate_id, 0)} |"
        )
    lines.extend([
        "",
        "## Batasan",
        "",
        *[f"- {item}" for item in result["limitations"]],
        "",
        "Hasil ini adalah validasi sensitivitas simulasi, bukan bukti optimum universal.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=int, default=3)
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--history-limit", type=int, default=100)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]
    if not seeds:
        parser.error("--seeds minimal berisi satu integer")
    result = run_validation(args.snapshots, seeds, args.history_limit)
    write_outputs(result, args.json, args.report)
    print(f"Validasi selesai: {result['snapshotCount']} snapshot x {len(seeds)} seed")
    print(f"JSON   : {args.json}")
    print(f"Laporan: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
