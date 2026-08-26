from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


SEED = 42
INTERVAL_SECONDS = 5
INPUT_STEPS = 12
OUTPUT_STEPS = 12
BATCH_SIZE = 32
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2
LEARNING_RATE = 0.001
MAX_EPOCHS = 100
PATIENCE = 20
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15

APPROACHES = ("west", "south", "east", "north")
TRAFFIC_FEATURES = (
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
)
APPROACH_FEATURES = tuple(f"is{approach.title()}" for approach in APPROACHES)
INPUT_FEATURES = TRAFFIC_FEATURES + APPROACH_FEATURES

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_FILE = BASE_DIR / "data" / "processed" / "traffic_per_approach_5s.csv"
OUTPUT_DIR = BASE_DIR / "outputs" / "lstm" / "per_approach"
MODEL_FILE = OUTPUT_DIR / "traffic_lstm_per_approach.pt"
SCALER_FILE = OUTPUT_DIR / "scaler.json"
METADATA_FILE = OUTPUT_DIR / "metadata.json"
PREDICTIONS_FILE = OUTPUT_DIR / "predictions.csv"
METRICS_FILE = OUTPUT_DIR / "metrics_by_approach.json"
HISTORY_FILE = OUTPUT_DIR / "training_history.json"
PLOT_FILE = OUTPUT_DIR / "plots" / "training_validation_loss.png"


def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class SharedApproachLSTM(nn.Module):
    def __init__(
        self,
        input_size: int = len(INPUT_FEATURES),
        hidden_size: int = HIDDEN_SIZE,
        num_layers: int = NUM_LAYERS,
        output_steps: int = OUTPUT_STEPS,
        output_size: int = len(TRAFFIC_FEATURES),
        dropout: float = DROPOUT,
    ) -> None:
        super().__init__()
        self.output_steps = output_steps
        self.output_size = output_size
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(hidden_size, output_steps * output_size)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        sequence, _ = self.lstm(values)
        prediction = self.fc(sequence[:, -1, :])
        return prediction.view(-1, self.output_steps, self.output_size)


@dataclass
class SequenceBundle:
    x: np.ndarray
    y: np.ndarray
    approaches: list[str]
    target_timestamps: list[list[pd.Timestamp]]
    rejected_gaps: int = 0


def load_dataset(path: Path = DATA_FILE) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset belum ada: {path}\nJalankan prepare_data.py terlebih dahulu."
        )
    frame = pd.read_csv(path)
    required = {"timestamp", "approach", *TRAFFIC_FEATURES}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Kolom dataset tidak lengkap: {missing}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "approach", *TRAFFIC_FEATURES])
    frame = frame[frame["approach"].isin(APPROACHES)].copy()
    for feature in TRAFFIC_FEATURES:
        frame[feature] = pd.to_numeric(frame[feature], errors="coerce")
    return frame.dropna(subset=list(TRAFFIC_FEATURES)).sort_values(
        ["timestamp", "approach"]
    ).reset_index(drop=True)


def chronological_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    timestamps = np.array(sorted(frame["timestamp"].unique()))
    train_end = int(len(timestamps) * TRAIN_RATIO)
    val_end = train_end + int(len(timestamps) * VAL_RATIO)
    train_times = set(timestamps[:train_end])
    val_times = set(timestamps[train_end:val_end])
    test_times = set(timestamps[val_end:])
    return (
        frame[frame["timestamp"].isin(train_times)].copy(),
        frame[frame["timestamp"].isin(val_times)].copy(),
        frame[frame["timestamp"].isin(test_times)].copy(),
    )


def fit_scaler(train_frame: pd.DataFrame) -> MinMaxScaler:
    scaler = MinMaxScaler()
    scaler.fit(train_frame[list(TRAFFIC_FEATURES)].to_numpy(dtype=np.float32))
    return scaler


def create_sequences(frame: pd.DataFrame, scaler: MinMaxScaler) -> SequenceBundle:
    x_values: list[np.ndarray] = []
    y_values: list[np.ndarray] = []
    sample_approaches: list[str] = []
    target_timestamps: list[list[pd.Timestamp]] = []
    rejected_gaps = 0
    total_steps = INPUT_STEPS + OUTPUT_STEPS

    for approach_index, approach in enumerate(APPROACHES):
        group = frame[frame["approach"] == approach].sort_values("timestamp")
        traffic = group[list(TRAFFIC_FEATURES)].to_numpy(dtype=np.float32)
        scaled = scaler.transform(traffic).astype(np.float32)
        timestamps = group["timestamp"].reset_index(drop=True)
        one_hot = np.zeros((len(group), len(APPROACHES)), dtype=np.float32)
        one_hot[:, approach_index] = 1.0
        model_input = np.concatenate([scaled, one_hot], axis=1)

        for start in range(max(0, len(group) - total_steps + 1)):
            end = start + total_steps
            window_times = timestamps.iloc[start:end]
            intervals = window_times.diff().dropna().dt.total_seconds()
            if not intervals.eq(INTERVAL_SECONDS).all():
                rejected_gaps += 1
                continue
            x_values.append(model_input[start : start + INPUT_STEPS])
            y_values.append(scaled[start + INPUT_STEPS : end])
            sample_approaches.append(approach)
            target_timestamps.append(list(window_times.iloc[INPUT_STEPS:]))

    x = np.asarray(x_values, dtype=np.float32)
    y = np.asarray(y_values, dtype=np.float32)
    if not len(x):
        raise ValueError("Tidak ada sequence valid setelah pemeriksaan gap timestamp.")
    return SequenceBundle(x, y, sample_approaches, target_timestamps, rejected_gaps)


def make_loader(bundle: SequenceBundle, shuffle: bool) -> DataLoader:
    dataset = TensorDataset(torch.from_numpy(bundle.x), torch.from_numpy(bundle.y))
    return DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=shuffle)


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
) -> float:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_samples = 0
    context = torch.enable_grad() if training else torch.no_grad()
    with context:
        for x_batch, y_batch in loader:
            x_batch, y_batch = x_batch.to(device), y_batch.to(device)
            if training:
                optimizer.zero_grad()
            prediction = model(x_batch)
            loss = criterion(prediction, y_batch)
            if training:
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            total_loss += loss.item() * x_batch.size(0)
            total_samples += x_batch.size(0)
    return total_loss / max(total_samples, 1)


@torch.no_grad()
def predict_scaled(model: nn.Module, bundle: SequenceBundle, device: torch.device) -> np.ndarray:
    model.eval()
    predictions = []
    loader = DataLoader(TensorDataset(torch.from_numpy(bundle.x)), batch_size=BATCH_SIZE)
    for (x_batch,) in loader:
        predictions.append(model(x_batch.to(device)).cpu().numpy())
    return np.concatenate(predictions, axis=0)


def inverse_sequences(values: np.ndarray, scaler: MinMaxScaler) -> np.ndarray:
    shape = values.shape
    return scaler.inverse_transform(values.reshape(-1, len(TRAFFIC_FEATURES))).reshape(shape)


def metric_block(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    actual_flat = actual.reshape(-1, len(TRAFFIC_FEATURES))
    predicted_flat = predicted.reshape(-1, len(TRAFFIC_FEATURES))
    mse = mean_squared_error(actual_flat, predicted_flat)
    return {
        "mae": float(mean_absolute_error(actual_flat, predicted_flat)),
        "mse": float(mse),
        "rmse": float(np.sqrt(mse)),
        "featureMae": {
            feature: float(mean_absolute_error(actual_flat[:, index], predicted_flat[:, index]))
            for index, feature in enumerate(TRAFFIC_FEATURES)
        },
    }


def evaluate_predictions(
    bundle: SequenceBundle,
    actual: np.ndarray,
    predicted: np.ndarray,
    scaler: MinMaxScaler,
) -> tuple[dict[str, Any], np.ndarray]:
    x_traffic = bundle.x[:, :, : len(TRAFFIC_FEATURES)]
    last_scaled = x_traffic[:, -1:, :]
    naive_scaled = np.repeat(last_scaled, OUTPUT_STEPS, axis=1)
    naive = inverse_sequences(naive_scaled, scaler)

    metrics: dict[str, Any] = {
        "overall": metric_block(actual, predicted),
        "naiveBaseline": metric_block(actual, naive),
        "byApproach": {},
    }
    metrics["beatsNaiveBaseline"] = (
        metrics["overall"]["mae"] < metrics["naiveBaseline"]["mae"]
    )
    approach_array = np.asarray(bundle.approaches)
    for approach in APPROACHES:
        mask = approach_array == approach
        if mask.any():
            block = metric_block(actual[mask], predicted[mask])
            baseline = metric_block(actual[mask], naive[mask])
            block["naiveBaseline"] = baseline
            block["beatsNaiveBaseline"] = block["mae"] < baseline["mae"]
            block["samples"] = int(mask.sum())
            metrics["byApproach"][approach] = block
    return metrics, naive


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def save_scaler(scaler: MinMaxScaler) -> None:
    save_json(SCALER_FILE, {
        "features": list(TRAFFIC_FEATURES),
        "min": scaler.min_.tolist(),
        "scale": scaler.scale_.tolist(),
        "dataMin": scaler.data_min_.tolist(),
        "dataMax": scaler.data_max_.tolist(),
    })


def save_predictions(
    bundle: SequenceBundle,
    actual: np.ndarray,
    predicted: np.ndarray,
    naive: np.ndarray,
) -> None:
    rows = []
    for sample_index, approach in enumerate(bundle.approaches):
        for step in range(OUTPUT_STEPS):
            row: dict[str, Any] = {
                "sampleIndex": sample_index,
                "approach": approach,
                "timestamp": bundle.target_timestamps[sample_index][step].isoformat(),
                "forecastStep": step + 1,
                "secondsAhead": (step + 1) * INTERVAL_SECONDS,
            }
            for feature_index, feature in enumerate(TRAFFIC_FEATURES):
                row[f"{feature}Actual"] = float(actual[sample_index, step, feature_index])
                row[f"{feature}Predicted"] = float(predicted[sample_index, step, feature_index])
                row[f"{feature}Naive"] = float(naive[sample_index, step, feature_index])
            rows.append(row)
    PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(PREDICTIONS_FILE, index=False)


def train_model(data_file: Path = DATA_FILE) -> dict[str, Any]:
    set_seed()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frame = load_dataset(data_file)
    train_frame, val_frame, test_frame = chronological_split(frame)
    scaler = fit_scaler(train_frame)
    train_bundle = create_sequences(train_frame, scaler)
    val_bundle = create_sequences(val_frame, scaler)
    test_bundle = create_sequences(test_frame, scaler)

    print(f"Device: {device}")
    print(f"Rows train/val/test: {len(train_frame)}/{len(val_frame)}/{len(test_frame)}")
    print(
        "Sequences train/val/test: "
        f"{len(train_bundle.x)}/{len(val_bundle.x)}/{len(test_bundle.x)}"
    )
    print(
        "Rejected gap sequences: "
        f"{train_bundle.rejected_gaps}/{val_bundle.rejected_gaps}/{test_bundle.rejected_gaps}"
    )

    model = SharedApproachLSTM().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=5
    )
    history = {"trainLoss": [], "validationLoss": []}
    best_loss = float("inf")
    best_state = None
    patience_counter = 0

    for epoch in range(1, MAX_EPOCHS + 1):
        train_loss = run_epoch(
            model, make_loader(train_bundle, True), criterion, device, optimizer
        )
        validation_loss = run_epoch(
            model, make_loader(val_bundle, False), criterion, device
        )
        scheduler.step(validation_loss)
        history["trainLoss"].append(train_loss)
        history["validationLoss"].append(validation_loss)
        print(
            f"Epoch {epoch:03d}/{MAX_EPOCHS} | "
            f"train={train_loss:.6f} | val={validation_loss:.6f}"
        )
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_state = copy.deepcopy(model.state_dict())
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print("Early stopping.")
                break

    if best_state is None:
        raise RuntimeError("Training tidak menghasilkan best state.")
    model.load_state_dict(best_state)
    predicted_scaled = predict_scaled(model, test_bundle, device)
    actual = inverse_sequences(test_bundle.y, scaler)
    predicted = inverse_sequences(predicted_scaled, scaler)

    predicted[:, :, :3] = np.maximum(predicted[:, :, :3], 0.0)
    predicted[:, :, 3] = np.clip(predicted[:, :, 3], 0.0, 1.0)
    metrics, naive = evaluate_predictions(test_bundle, actual, predicted, scaler)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "modelConfig": {
            "inputSize": len(INPUT_FEATURES),
            "hiddenSize": HIDDEN_SIZE,
            "numLayers": NUM_LAYERS,
            "outputSteps": OUTPUT_STEPS,
            "outputSize": len(TRAFFIC_FEATURES),
            "dropout": DROPOUT,
        },
        "trafficFeatures": list(TRAFFIC_FEATURES),
        "approaches": list(APPROACHES),
    }, MODEL_FILE)
    save_scaler(scaler)
    save_json(HISTORY_FILE, history)
    save_json(METRICS_FILE, metrics)
    save_predictions(test_bundle, actual, predicted, naive)

    metadata = {
        "project": "SmartTwin",
        "model": "SharedApproachLSTM",
        "mode": "per-approach",
        "approaches": list(APPROACHES),
        "northDataNote": "north density/queue memakai simpang_tengah sebagai proxy",
        "trafficFeatures": list(TRAFFIC_FEATURES),
        "approachEncoding": "one-hot",
        "inputFeatures": list(INPUT_FEATURES),
        "inputSteps": INPUT_STEPS,
        "outputSteps": OUTPUT_STEPS,
        "intervalSeconds": INTERVAL_SECONDS,
        "historySeconds": INPUT_STEPS * INTERVAL_SECONDS,
        "forecastSeconds": OUTPUT_STEPS * INTERVAL_SECONDS,
        "trainRows": len(train_frame),
        "validationRows": len(val_frame),
        "testRows": len(test_frame),
        "trainSequences": len(train_bundle.x),
        "validationSequences": len(val_bundle.x),
        "testSequences": len(test_bundle.x),
        "modelConfig": {
            "inputSize": len(INPUT_FEATURES),
            "hiddenSize": HIDDEN_SIZE,
            "numLayers": NUM_LAYERS,
            "dropout": DROPOUT,
            "outputSize": len(TRAFFIC_FEATURES),
        },
        "metrics": metrics,
        "fallbackModel": "../traffic_lstm.pt",
    }
    save_json(METADATA_FILE, metadata)

    PLOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 5))
    plt.plot(history["trainLoss"], label="train")
    plt.plot(history["validationLoss"], label="validation")
    plt.xlabel("Epoch")
    plt.ylabel("MSE Loss")
    plt.title("Shared Per-Approach LSTM")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=160)
    plt.close()

    print(json.dumps(metrics, indent=2))
    print(f"\nModel: {MODEL_FILE}")
    return metadata


def main() -> None:
    train_model()


if __name__ == "__main__":
    main()
