"""Bandingkan panjang histori shared LSTM tanpa menimpa model aktif.

Pemilihan kandidat memakai validation MAE. Test MAE hanya dilaporkan sebagai
audit setelah training dan tidak menjadi dasar pemilihan.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import train as pipeline  # noqa: E402

DEFAULT_OUTPUT = (
    pipeline.BASE_DIR / "outputs" / "lstm" / "per_approach"
    / "sequence_length_experiment.json"
)


def _mae_original(model, bundle, scaler, device) -> float:
    predicted_scaled = pipeline.predict_scaled(model, bundle, device)
    actual = pipeline.inverse_sequences(bundle.y, scaler)
    predicted = pipeline.inverse_sequences(predicted_scaled, scaler)
    predicted[:, :, :3] = np.maximum(predicted[:, :, :3], 0.0)
    predicted[:, :, 3] = np.clip(predicted[:, :, 3], 0.0, 1.0)
    return float(np.mean(np.abs(actual - predicted)))


def run_candidate(input_steps: int, max_epochs: int, patience: int) -> dict:
    pipeline.INPUT_STEPS = input_steps
    pipeline.set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frame = pipeline.load_dataset()
    train_frame, val_frame, test_frame = pipeline.chronological_split(frame)
    scaler = pipeline.fit_scaler(train_frame)

    try:
        train_bundle = pipeline.create_sequences(train_frame, scaler)
        val_bundle = pipeline.create_sequences(val_frame, scaler)
        test_bundle = pipeline.create_sequences(test_frame, scaler)
    except ValueError as exc:
        return {
            "inputSteps": input_steps,
            "historySeconds": input_steps * pipeline.INTERVAL_SECONDS,
            "status": "infeasible",
            "reason": str(exc),
        }

    model = pipeline.SharedApproachLSTM().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=pipeline.LEARNING_RATE)
    best_loss = float("inf")
    best_state = None
    wait = 0
    epochs_run = 0
    for epoch in range(1, max_epochs + 1):
        pipeline.run_epoch(
            model, pipeline.make_loader(train_bundle, True), criterion,
            device, optimizer,
        )
        val_loss = pipeline.run_epoch(
            model, pipeline.make_loader(val_bundle, False), criterion, device
        )
        epochs_run = epoch
        if val_loss < best_loss:
            best_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                break

    if best_state is None:
        raise RuntimeError("Training tidak menghasilkan best state")
    model.load_state_dict(best_state)
    return {
        "inputSteps": input_steps,
        "historySeconds": input_steps * pipeline.INTERVAL_SECONDS,
        "status": "trained",
        "epochsRun": epochs_run,
        "sequenceCounts": {
            "train": len(train_bundle.x),
            "validation": len(val_bundle.x),
            "test": len(test_bundle.x),
        },
        "rejectedGapSequences": {
            "train": train_bundle.rejected_gaps,
            "validation": val_bundle.rejected_gaps,
            "test": test_bundle.rejected_gaps,
        },
        "bestValidationMseNormalized": best_loss,
        "validationMaeOriginal": _mae_original(model, val_bundle, scaler, device),
        "testMaeOriginal": _mae_original(model, test_bundle, scaler, device),
    }


def run_experiment(candidates: list[int], max_epochs: int, patience: int) -> dict:
    results = []
    for candidate in candidates:
        print(f"Eksperimen inputSteps={candidate} ...", flush=True)
        result = run_candidate(candidate, max_epochs, patience)
        results.append(result)
        print(json.dumps(result, indent=2), flush=True)
    trained = [item for item in results if item["status"] == "trained"]
    selected = min(trained, key=lambda item: item["validationMaeOriginal"])
    return {
        "selectionMetric": "validationMaeOriginal",
        "selectionRule": "minimum; test metrics tidak dipakai untuk pemilihan",
        "seed": pipeline.SEED,
        "outputSteps": pipeline.OUTPUT_STEPS,
        "intervalSeconds": pipeline.INTERVAL_SECONDS,
        "maxEpochs": max_epochs,
        "patience": patience,
        "candidates": results,
        "selectedInputSteps": selected["inputSteps"],
        "selectedHistorySeconds": selected["historySeconds"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", nargs="+", type=int, default=[6, 12, 18, 30, 60, 120])
    parser.add_argument("--max-epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if any(value <= 0 for value in args.candidates):
        parser.error("Semua kandidat harus positif")
    result = run_experiment(args.candidates, args.max_epochs, args.patience)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nHasil: {args.output}")
    print(f"Terpilih: {result['selectedInputSteps']} langkah")


if __name__ == "__main__":
    main()
