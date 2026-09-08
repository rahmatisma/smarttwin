"""Project the same observed population through each signal plan for 60 seconds.

This read-only projection does not publish recommendations or replace the
full-cycle evaluation cache/history.
"""
import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scenario_worker import evaluate_state
from app.services.traffic_snapshot import load_snapshot


def project_snapshot(state):
    result = evaluate_state(state, full_cycle=True, evaluation_horizon_seconds=60)
    for candidate in result["candidates"]:
        metadata = candidate["evaluation"]
        if metadata["durationSeconds"] != 60 or metadata["completedSteps"] != 60:
            raise RuntimeError("Prediksi harus menyelesaikan tepat 60 detik.")
        if candidate.get("finalQueueLengthVehByApproach") is None:
            raise RuntimeError("Antrean akhir prediksi tidak tersedia.")
        candidate["isWinner"] = False
    return {
        "intersectionId": state.intersectionId,
        "status": "completed",
        "updatedAt": result["updatedAt"],
        "candidates": result["candidates"],
        "trafficStateId": state.trafficStateId,
        "inputTimestamp": state.windowEnd.isoformat(),
        "predictionTimestamp": (state.windowEnd + timedelta(seconds=60)).isoformat(),
        "horizonSeconds": 60,
        "initialPhase": "north",
        "assumptions": [
            "Estimasi dimulai dari jumlah kendaraan pada kondisi terpilih; posisi dan kecepatan awal direkonstruksi.",
            "Ketiga skenario dimulai dari awal fase hijau Utara, dengan kondisi kendaraan yang sama.",
            "Kedatangan kendaraan baru di luar kondisi terpilih belum dimodelkan.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = load_snapshot("simpang4-pingit", args.state_id)
    args.output.write_text(json.dumps(project_snapshot(state)), encoding="utf-8")


if __name__ == "__main__":
    main()
