from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train import (  # noqa: E402
    METRICS_FILE,
    MODEL_FILE,
    SCALER_FILE,
    SharedApproachLSTM,
    chronological_split,
    create_sequences,
    evaluate_predictions,
    fit_scaler,
    inverse_sequences,
    load_dataset,
    predict_scaled,
    save_predictions,
)


def evaluate(model_path: Path = MODEL_FILE) -> dict:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frame = load_dataset()
    train_frame, _, test_frame = chronological_split(frame)
    scaler = fit_scaler(train_frame)

    # Pastikan scaler evaluasi identik dengan scaler artefak tersimpan.
    scaler_json = json.loads(SCALER_FILE.read_text(encoding="utf-8"))
    if not np.allclose(scaler.min_, np.asarray(scaler_json["min"])):
        raise ValueError("Scaler tersimpan tidak cocok dengan dataset train.")

    test_bundle = create_sequences(test_frame, scaler)
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

    prediction_scaled = predict_scaled(model, test_bundle, device)
    actual = inverse_sequences(test_bundle.y, scaler)
    predicted = inverse_sequences(prediction_scaled, scaler)
    predicted[:, :, :3] = np.maximum(predicted[:, :, :3], 0.0)
    predicted[:, :, 3] = np.clip(predicted[:, :, 3], 0.0, 1.0)
    metrics, naive = evaluate_predictions(
        test_bundle, actual, predicted, scaler
    )
    METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    save_predictions(test_bundle, actual, predicted, naive)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate per-approach LSTM")
    parser.add_argument("--model", type=Path, default=MODEL_FILE)
    args = parser.parse_args()
    metrics = evaluate(args.model)
    print(json.dumps(metrics, indent=2))
    print(f"\nMetrics: {METRICS_FILE}")


if __name__ == "__main__":
    main()
