"""Evaluasi ringan checkpoint LSTM pada seluruh data setelah split train 70%.

Tidak melakukan training. Validation pernah dipakai untuk early stopping, jadi
hasil ini sengaja disebut post-training holdout, bukan independent test.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train import (  # noqa: E402
    MODEL_FILE,
    SCALER_FILE,
    TRAFFIC_FEATURES,
    SharedApproachLSTM,
    chronological_split,
    create_sequences,
    evaluate_predictions,
    fit_scaler,
    inverse_sequences,
    load_dataset,
    predict_scaled,
)


DEFAULT_OUTPUT = (
    SCRIPT_DIR.parents[2]
    / "outputs"
    / "lstm"
    / "per_approach"
    / "metrics_post_training_holdout.json"
)


def _sequence_comparison(actual: np.ndarray, predicted: np.ndarray, naive: np.ndarray) -> dict:
    axes = (1, 2)
    lstm_mae = np.mean(np.abs(actual - predicted), axis=axes)
    naive_mae = np.mean(np.abs(actual - naive), axis=axes)
    tolerance = 1e-9
    wins = int(np.sum(lstm_mae < naive_mae - tolerance))
    losses = int(np.sum(lstm_mae > naive_mae + tolerance))
    ties = int(len(lstm_mae) - wins - losses)
    return {
        "sequences": int(len(lstm_mae)),
        "lstmWins": wins,
        "naiveWins": losses,
        "ties": ties,
        "lstmWinRatePercent": float(wins / max(1, len(lstm_mae)) * 100.0),
        "meanSequenceMaeLstm": float(np.mean(lstm_mae)),
        "meanSequenceMaeNaive": float(np.mean(naive_mae)),
    }


def evaluate_holdout(model_path: Path = MODEL_FILE) -> dict:
    device = torch.device("cpu")
    frame = load_dataset()
    train_frame, validation_frame, test_frame = chronological_split(frame)
    scaler = fit_scaler(train_frame)
    scaler_json = json.loads(SCALER_FILE.read_text(encoding="utf-8"))
    if not np.allclose(scaler.min_, np.asarray(scaler_json["min"])):
        raise ValueError("Scaler tersimpan tidak cocok dengan dataset train.")

    holdout_frame = pd.concat([validation_frame, test_frame]).sort_values(
        ["timestamp", "approach"]
    )
    bundle = create_sequences(holdout_frame, scaler)
    checkpoint = torch.load(model_path, map_location=device)
    config = checkpoint["modelConfig"]
    model = SharedApproachLSTM(
        input_size=config["inputSize"],
        hidden_size=config["hiddenSize"],
        num_layers=config["numLayers"],
        output_steps=config["outputSteps"],
        output_size=config["outputSize"],
        dropout=config["dropout"],
    ).to(device)
    model.load_state_dict(checkpoint["state_dict"])

    prediction_scaled = predict_scaled(model, bundle, device)
    actual = inverse_sequences(bundle.y, scaler)
    predicted = inverse_sequences(prediction_scaled, scaler)
    predicted[:, :, :3] = np.maximum(predicted[:, :, :3], 0.0)
    predicted[:, :, 3] = np.clip(predicted[:, :, 3], 0.0, 1.0)
    metrics, naive = evaluate_predictions(bundle, actual, predicted, scaler)
    metrics.update({
        "evaluationScope": "post-training-holdout",
        "independentTest": False,
        "disclosure": (
            "Gabungan validation+test setelah batas train 70%. Validation pernah "
            "dipakai untuk early stopping; gunakan sebagai robustness evidence, "
            "bukan estimasi generalisasi independent."
        ),
        "rows": int(len(holdout_frame)),
        "sequences": int(len(bundle.x)),
        "rejectedGapSequences": int(bundle.rejected_gaps),
        "sequenceComparison": _sequence_comparison(actual, predicted, naive),
        "trafficFeatures": list(TRAFFIC_FEATURES),
        "device": str(device),
    })
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate existing LSTM on 30% post-train holdout")
    parser.add_argument("--model", type=Path, default=MODEL_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    metrics = evaluate_holdout(args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"\nMetrics: {args.output.resolve()}")


if __name__ == "__main__":
    main()
