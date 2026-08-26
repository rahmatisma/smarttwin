from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from train import (  # noqa: E402
    APPROACHES,
    INPUT_STEPS,
    INTERVAL_SECONDS,
    MODEL_FILE,
    OUTPUT_DIR,
    OUTPUT_STEPS,
    SCALER_FILE,
    TRAFFIC_FEATURES,
    SharedApproachLSTM,
    load_dataset,
)


DEFAULT_OUTPUT = OUTPUT_DIR / "latest_forecast.json"


def load_scaler_parameters(path: Path = SCALER_FILE) -> tuple[np.ndarray, np.ndarray]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("features") != list(TRAFFIC_FEATURES):
        raise ValueError("Urutan fitur scaler tidak cocok dengan model.")
    return np.asarray(data["min"], dtype=np.float32), np.asarray(
        data["scale"], dtype=np.float32
    )


def transform(values: np.ndarray, minimum: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return values * scale + minimum


def inverse_transform(
    values: np.ndarray, minimum: np.ndarray, scale: np.ndarray
) -> np.ndarray:
    return (values - minimum) / scale


def load_model(path: Path, device: torch.device) -> SharedApproachLSTM:
    checkpoint = torch.load(path, map_location=device)
    config = checkpoint.get("modelConfig", {})
    model = SharedApproachLSTM(
        input_size=int(config.get("inputSize", 8)),
        hidden_size=int(config.get("hiddenSize", 64)),
        num_layers=int(config.get("numLayers", 2)),
        output_steps=int(config.get("outputSteps", OUTPUT_STEPS)),
        output_size=int(config.get("outputSize", len(TRAFFIC_FEATURES))),
        dropout=float(config.get("dropout", 0.2)),
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.to(device).eval()
    return model


def latest_contiguous_window(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("timestamp").reset_index(drop=True)
    if len(group) < INPUT_STEPS:
        raise ValueError("Data approach kurang dari 12 timestep.")
    # Cari dari belakang supaya forecast memakai observasi terbaru yang utuh.
    for end in range(len(group), INPUT_STEPS - 1, -1):
        window = group.iloc[end - INPUT_STEPS : end]
        intervals = window["timestamp"].diff().dropna().dt.total_seconds()
        if intervals.eq(INTERVAL_SECONDS).all():
            return window
    raise ValueError("Tidak ditemukan 12 timestep kontigu untuk approach.")


@torch.no_grad()
def forecast_all_approaches(
    frame: pd.DataFrame,
    model_path: Path = MODEL_FILE,
    scaler_path: Path = SCALER_FILE,
) -> dict[str, Any]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(model_path, device)
    minimum, scale = load_scaler_parameters(scaler_path)
    result: dict[str, Any] = {
        "model": "SharedApproachLSTM",
        "generatedFrom": {},
        "forecasts": {},
    }

    for approach_index, approach in enumerate(APPROACHES):
        window = latest_contiguous_window(frame[frame["approach"] == approach])
        traffic = window[list(TRAFFIC_FEATURES)].to_numpy(dtype=np.float32)
        scaled = transform(traffic, minimum, scale)
        one_hot = np.zeros((INPUT_STEPS, len(APPROACHES)), dtype=np.float32)
        one_hot[:, approach_index] = 1.0
        model_input = np.concatenate([scaled, one_hot], axis=1)
        tensor = torch.from_numpy(model_input).unsqueeze(0).to(device)
        prediction_scaled = model(tensor).cpu().numpy()[0]
        prediction = inverse_transform(prediction_scaled, minimum, scale)
        prediction[:, :3] = np.maximum(prediction[:, :3], 0.0)
        prediction[:, 3] = np.clip(prediction[:, 3], 0.0, 1.0)
        last_timestamp = pd.Timestamp(window["timestamp"].iloc[-1])

        result["generatedFrom"][approach] = last_timestamp.isoformat()
        result["forecasts"][approach] = []
        for step in range(OUTPUT_STEPS):
            row: dict[str, Any] = {
                "timestamp": (
                    last_timestamp + timedelta(seconds=(step + 1) * INTERVAL_SECONDS)
                ).isoformat(),
                "secondsAhead": (step + 1) * INTERVAL_SECONDS,
            }
            for feature_index, feature in enumerate(TRAFFIC_FEATURES):
                row[feature] = round(float(prediction[step, feature_index]), 4)
            result["forecasts"][approach].append(row)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict traffic per approach")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    frame = load_dataset(args.input) if args.input else load_dataset()
    result = forecast_all_approaches(frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nTersimpan: {args.output}")


if __name__ == "__main__":
    main()
