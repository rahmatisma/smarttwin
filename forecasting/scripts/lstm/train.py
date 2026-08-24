from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset


# ============================================================
# CONFIG
# ============================================================

SEED = 42

INPUT_STEPS = 12          # 12 x 5 detik = 60 detik history
OUTPUT_STEPS = 3          # 3 x 5 detik = 15 detik forecast
NUM_FEATURES = 4

FEATURES = [
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
]

BATCH_SIZE = 32
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2

LEARNING_RATE = 0.001
MAX_EPOCHS = 100
PATIENCE = 20

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

INTERVAL_SECONDS = 5

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"

# Ubah nama folder jika CSV kamu berada di folder berbeda
CROSSING_FILE = DATA_DIR / "crossing_simpang.csv"
SNAPSHOT_FILE = DATA_DIR / "snapshot_zona.csv"

OUTPUT_DIR = BASE_DIR / "outputs" / "lstm"
PLOT_DIR = OUTPUT_DIR / "plots"

MODEL_FILE = OUTPUT_DIR / "traffic_lstm.pt"
ONNX_FILE = OUTPUT_DIR / "traffic_lstm.onnx"
SCALER_FILE = OUTPUT_DIR / "scaler.json"
METADATA_FILE = OUTPUT_DIR / "metadata.json"
PREDICTIONS_FILE = OUTPUT_DIR / "predictions.csv"
HISTORY_FILE = OUTPUT_DIR / "training_history.json"


# ============================================================
# REPRODUCIBILITY
# ============================================================

def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ============================================================
# DEVICE
# ============================================================

def get_device() -> torch.device:
    if torch.cuda.is_available():
        print("CUDA tersedia. Menggunakan GPU.")
        return torch.device("cuda")

    print("CUDA tidak tersedia. Menggunakan CPU.")
    return torch.device("cpu")


# ============================================================
# MODEL
# ============================================================

class TrafficLSTM(nn.Module):

    def __init__(
        self,
        input_size: int = NUM_FEATURES,
        hidden_size: int = HIDDEN_SIZE,
        num_layers: int = NUM_LAYERS,
        output_steps: int = OUTPUT_STEPS,
        dropout: float = DROPOUT,
    ):
        super().__init__()

        self.output_steps = output_steps
        self.input_size = input_size

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        self.fc = nn.Linear(
            hidden_size,
            output_steps * input_size,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:

        output, _ = self.lstm(x)

        last_output = output[:, -1, :]

        prediction = self.fc(last_output)

        prediction = prediction.view(
            -1,
            self.output_steps,
            self.input_size,
        )

        return prediction


# ============================================================
# LOAD CROSSING
# ============================================================

def load_crossing_dataset(path: Path) -> pd.DataFrame:

    print("\n[1A] Loading crossing dataset...")

    if not path.exists():
        raise FileNotFoundError(
            f"File crossing tidak ditemukan:\n{path}"
        )

    df = pd.read_csv(path)

    required = [
        "timestamp",
        "jumlah_crossing",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Kolom crossing tidak ditemukan: {missing}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(subset=["timestamp"])

    df["jumlah_crossing"] = pd.to_numeric(
        df["jumlah_crossing"],
        errors="coerce",
    ).fillna(0)

    # ========================================================
    # AGREGASI SEMUA KAMERA / GARIS PADA TIMESTAMP SAMA
    # ========================================================

    result = (
        df.groupby("timestamp", as_index=False)
        ["jumlah_crossing"]
        .sum()
    )

    result = result.rename(
        columns={
            "jumlah_crossing": "vehicleCount"
        }
    )

    result = result.sort_values("timestamp")

    print(
        f"Jumlah timestamp crossing: {len(result)}"
    )

    print(
        result.head(10).to_string(index=False)
    )

    return result[
        [
            "timestamp",
            "vehicleCount",
        ]
    ]


# ============================================================
# LOAD SNAPSHOT ZONA
# ============================================================

def load_snapshot_dataset(path: Path) -> pd.DataFrame:

    print("\n[1B] Loading snapshot zona dataset...")

    if not path.exists():
        raise FileNotFoundError(
            f"File snapshot zona tidak ditemukan:\n{path}"
        )

    df = pd.read_csv(path)

    required = [
        "timestamp",
        "total_di_zona",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Kolom snapshot tidak ditemukan: {missing}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(subset=["timestamp"])

    df["total_di_zona"] = pd.to_numeric(
        df["total_di_zona"],
        errors="coerce",
    ).fillna(0)

    # ========================================================
    # AGREGASI BERDASARKAN TIMESTAMP
    #
    # Snapshot memiliki beberapa kamera/lengan.
    # Kita gunakan MEAN antar kamera/lengan.
    # ========================================================

    result = (
        df.groupby("timestamp", as_index=False)
        ["total_di_zona"]
        .mean()
    )

    # ========================================================
    # NORMALISASI DENSITY
    #
    # 33 = kapasitas zona yang digunakan oleh dataset.
    #
    # Jika project kamu punya kapasitas zona resmi lain,
    # ubah nilai ini.
    # ========================================================

    ZONE_CAPACITY = 33.0

    result["densityIndex"] = (
        result["total_di_zona"] / ZONE_CAPACITY
    ).clip(
        lower=0.0,
        upper=1.0,
    )

    result = result.sort_values("timestamp")

    print(
        f"Jumlah timestamp snapshot: {len(result)}"
    )

    print(
        result.head(10).to_string(index=False)
    )

    return result[
        [
            "timestamp",
            "densityIndex",
        ]
    ]


# ============================================================
# RESAMPLE CROSSING
# ============================================================

def resample_crossing(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df = (
        df.set_index("timestamp")
        [["vehicleCount"]]
        .resample("5s")
        .sum()
        .reset_index()
    )

    return df


# ============================================================
# RESAMPLE SNAPSHOT
# ============================================================

def resample_snapshot(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df = (
        df.set_index("timestamp")
        [["densityIndex"]]
        .resample("5s")
        .mean()
        .reset_index()
    )

    return df


# ============================================================
# MERGE DATASETS
# ============================================================

def merge_datasets(
    crossing: pd.DataFrame,
    snapshot: pd.DataFrame,
) -> pd.DataFrame:

    print("\n[2] Menggabungkan crossing + snapshot zona...")

    # ========================================================
    # PENTING:
    # Crossing hanya punya vehicleCount.
    # Snapshot hanya punya densityIndex.
    # Jangan kirim kedua fitur ke fungsi resample yang sama.
    # ========================================================

    crossing = resample_crossing(crossing)

    snapshot = resample_snapshot(snapshot)

    print(
        f"Crossing setelah resample : {len(crossing)}"
    )

    print(
        f"Snapshot setelah resample : {len(snapshot)}"
    )

    # ========================================================
    # INNER JOIN
    #
    # Hanya timestamp yang tersedia pada kedua dataset
    # yang digunakan.
    # ========================================================

    merged = pd.merge(
        crossing,
        snapshot,
        on="timestamp",
        how="inner",
    )

    merged = merged.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    # ========================================================
    # QUEUE SEMENTARA
    # ========================================================

    merged["queueLengthVeh"] = 0.0
    merged["queueLengthMEst"] = 0.0

    # ========================================================
    # URUTKAN SESUAI MODEL CONTRACT
    # ========================================================

    merged = merged[
        [
            "timestamp",
            "vehicleCount",
            "queueLengthVeh",
            "queueLengthMEst",
            "densityIndex",
        ]
    ]

    # ========================================================
    # HAPUS NILAI INVALID
    # ========================================================

    merged = merged.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    merged = merged.dropna(
        subset=FEATURES
    )

    merged = merged.reset_index(
        drop=True
    )

    print(
        f"Timeline valid: {len(merged)}"
    )

    print("\nContoh hasil gabungan:")

    print(
        merged.head(20).to_string(index=False)
    )

    print("\nDistribusi fitur:")

    print(
        merged[FEATURES].describe()
    )

    # ========================================================
    # INTERVAL
    # ========================================================

    if len(merged) > 1:

        intervals = (
            merged["timestamp"]
            .diff()
            .dt.total_seconds()
            .dropna()
        )

        print("\nInterval dataset:")

        print(
            f"Median : {intervals.median():.1f} detik"
        )

        print(
            f"Minimum: {intervals.min():.1f} detik"
        )

        print(
            f"Maksimum: {intervals.max():.1f} detik"
        )

    return merged


# ============================================================
# CHRONOLOGICAL SPLIT
# ============================================================

def chronological_split(
    df: pd.DataFrame,
):

    print("\n[3] Chronological split...")

    n = len(df)

    train_end = int(
        n * TRAIN_RATIO
    )

    val_end = train_end + int(
        n * VAL_RATIO
    )

    train = df.iloc[
        :train_end
    ].copy()

    val = df.iloc[
        train_end:val_end
    ].copy()

    test = df.iloc[
        val_end:
    ].copy()

    print(
        f"Train: {len(train)}"
    )

    print(
        f"Validation: {len(val)}"
    )

    print(
        f"Test: {len(test)}"
    )

    return train, val, test


# ============================================================
# FIT SCALER
# ============================================================

def fit_scaler(
    train_df: pd.DataFrame,
):

    print("\n[4] Fitting scaler...")

    scaler = MinMaxScaler()

    scaler.fit(
        train_df[FEATURES].values
    )

    return scaler


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    data: np.ndarray,
    input_steps: int = INPUT_STEPS,
    output_steps: int = OUTPUT_STEPS,
):

    x = []
    y = []

    total_length = len(data)

    max_start = (
        total_length
        - input_steps
        - output_steps
        + 1
    )

    for i in range(max_start):

        x.append(
            data[
                i:
                i + input_steps
            ]
        )

        y.append(
            data[
                i + input_steps:
                i + input_steps
                + output_steps
            ]
        )

    return (
        np.asarray(x, dtype=np.float32),
        np.asarray(y, dtype=np.float32),
    )


# ============================================================
# DATASET
# ============================================================

def make_loader(
    x: np.ndarray,
    y: np.ndarray,
    shuffle: bool,
):

    dataset = TensorDataset(
        torch.tensor(x),
        torch.tensor(y),
    )

    return DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=shuffle,
    )


# ============================================================
# TRAIN ONE EPOCH
# ============================================================

def train_one_epoch(
    model,
    loader,
    optimizer,
    criterion,
    device,
):

    model.train()

    total_loss = 0.0
    total_samples = 0

    for x, y in loader:

        x = x.to(device)
        y = y.to(device)

        optimizer.zero_grad()

        prediction = model(x)

        loss = criterion(
            prediction,
            y,
        )

        loss.backward()

        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            max_norm=1.0,
        )

        optimizer.step()

        batch_size = x.size(0)

        total_loss += (
            loss.item()
            * batch_size
        )

        total_samples += batch_size

    return (
        total_loss
        / max(total_samples, 1)
    )


# ============================================================
# VALIDATION
# ============================================================

def evaluate_loss(
    model,
    loader,
    criterion,
    device,
):

    model.eval()

    total_loss = 0.0
    total_samples = 0

    with torch.no_grad():

        for x, y in loader:

            x = x.to(device)
            y = y.to(device)

            prediction = model(x)

            loss = criterion(
                prediction,
                y,
            )

            batch_size = x.size(0)

            total_loss += (
                loss.item()
                * batch_size
            )

            total_samples += batch_size

    return (
        total_loss
        / max(total_samples, 1)
    )


# ============================================================
# PREDICT
# ============================================================

def predict(
    model,
    loader,
    device,
):

    model.eval()

    predictions = []
    targets = []

    with torch.no_grad():

        for x, y in loader:

            x = x.to(device)

            prediction = model(x)

            predictions.append(
                prediction.cpu().numpy()
            )

            targets.append(
                y.numpy()
            )

    if not predictions:

        return (
            np.empty(
                (
                    0,
                    OUTPUT_STEPS,
                    NUM_FEATURES,
                ),
                dtype=np.float32,
            ),
            np.empty(
                (
                    0,
                    OUTPUT_STEPS,
                    NUM_FEATURES,
                ),
                dtype=np.float32,
            ),
        )

    return (
        np.concatenate(
            predictions,
            axis=0,
        ),
        np.concatenate(
            targets,
            axis=0,
        ),
    )


# ============================================================
# INVERSE SCALE
# ============================================================

def inverse_scale_sequences(
    data: np.ndarray,
    scaler: MinMaxScaler,
):

    if data.ndim != 3:

        raise ValueError(
            "Data harus memiliki shape "
            "(samples, timesteps, features). "
            f"Diterima: {data.shape}"
        )

    original_shape = data.shape

    flattened = data.reshape(
        -1,
        original_shape[-1],
    )

    restored = scaler.inverse_transform(
        flattened
    )

    return restored.reshape(
        original_shape
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
):

    y_true_flat = y_true.reshape(
        -1,
        NUM_FEATURES,
    )

    y_pred_flat = y_pred.reshape(
        -1,
        NUM_FEATURES,
    )

    mae = mean_absolute_error(
        y_true_flat,
        y_pred_flat,
    )

    mse = mean_squared_error(
        y_true_flat,
        y_pred_flat,
    )

    rmse = np.sqrt(mse)

    feature_mae = {}

    for index, feature in enumerate(
        FEATURES
    ):

        feature_mae[feature] = (
            mean_absolute_error(
                y_true_flat[:, index],
                y_pred_flat[:, index],
            )
        )

    return (
        mae,
        mse,
        rmse,
        feature_mae,
    )


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def save_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    output_path: Path,
):

    print("\n[11] Saving predictions...")

    rows = []

    sample_count = y_true.shape[0]

    for sample_index in range(
        sample_count
    ):

        for step in range(
            OUTPUT_STEPS
        ):

            row = {
                "sampleIndex": sample_index,
                "forecastStep": step + 1,
            }

            for feature_index, feature in enumerate(
                FEATURES
            ):

                row[
                    f"{feature}_actual"
                ] = float(
                    y_true[
                        sample_index,
                        step,
                        feature_index,
                    ]
                )

                row[
                    f"{feature}_predicted"
                ] = float(
                    y_pred[
                        sample_index,
                        step,
                        feature_index,
                    ]
                )

            rows.append(row)

    result = pd.DataFrame(rows)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Predictions saved: {output_path}"
    )


# ============================================================
# SAVE SCALER
# ============================================================

def save_scaler(
    scaler: MinMaxScaler,
    output_path: Path,
):

    data = {
        "features": FEATURES,
        "min": scaler.min_.tolist(),
        "scale": scaler.scale_.tolist(),
        "data_min": scaler.data_min_.tolist(),
        "data_max": scaler.data_max_.tolist(),
        "data_range": scaler.data_range_.tolist(),
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
        )

    print(
        f"Scaler saved: {output_path}"
    )


# ============================================================
# SAVE METADATA
# ============================================================

def save_metadata(
    output_path: Path,
    train_size: int,
    val_size: int,
    test_size: int,
    metrics: dict,
):

    metadata = {

        "project": "SmartTwin",

        "model": "TrafficLSTM",

        "features": FEATURES,

        "inputSteps": INPUT_STEPS,

        "outputSteps": OUTPUT_STEPS,

        "historySeconds":
            INPUT_STEPS
            * INTERVAL_SECONDS,

        "forecastSeconds":
            OUTPUT_STEPS
            * INTERVAL_SECONDS,

        "intervalSeconds":
            INTERVAL_SECONDS,

        "trainRows": train_size,

        "validationRows": val_size,

        "testRows": test_size,

        "modelConfig": {
            "inputSize": NUM_FEATURES,
            "hiddenSize": HIDDEN_SIZE,
            "numLayers": NUM_LAYERS,
            "dropout": DROPOUT,
        },

        "metrics": metrics,

        "queueNote": (
            "queueLengthVeh dan "
            "queueLengthMEst sementara "
            "bernilai 0 karena mekanisme "
            "estimasi antrean CV belum tersedia."
        ),

    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=2,
        )

    print(
        f"Metadata saved: {output_path}"
    )


# ============================================================
# SAVE TRAINING HISTORY
# ============================================================

def save_history(
    history: dict,
    output_path: Path,
):

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            history,
            file,
            indent=2,
        )

    print(
        f"Training history saved: {output_path}"
    )


# ============================================================
# TRAINING PLOT
# ============================================================

def save_training_plot(
    history: dict,
    output_path: Path,
):

    import matplotlib.pyplot as plt

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    plt.figure(
        figsize=(10, 6)
    )

    plt.plot(
        history["train_loss"],
        label="Train Loss",
    )

    plt.plot(
        history["val_loss"],
        label="Validation Loss",
    )

    plt.xlabel("Epoch")

    plt.ylabel("MSE Loss")

    plt.title(
        "SmartTwin Traffic LSTM Training"
    )

    plt.legend()

    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=150,
    )

    plt.close()

    print(
        f"Training plot saved: {output_path}"
    )


# ============================================================
# SAVE PYTORCH MODEL
# ============================================================

def save_pytorch_model(
    model: TrafficLSTM,
    output_path: Path,
):

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    checkpoint = {
        "model_state_dict":
            model.state_dict(),

        "features":
            FEATURES,

        "input_steps":
            INPUT_STEPS,

        "output_steps":
            OUTPUT_STEPS,

        "input_size":
            NUM_FEATURES,

        "hidden_size":
            HIDDEN_SIZE,

        "num_layers":
            NUM_LAYERS,

        "dropout":
            DROPOUT,
    }

    torch.save(
        checkpoint,
        output_path,
    )

    print(
        f"PyTorch model saved: {output_path}"
    )


# ============================================================
# EXPORT ONNX
# ============================================================

def export_onnx(
    model: TrafficLSTM,
    output_path: Path,
):

    print("\n[12] Exporting ONNX model...")

    model = model.cpu()
    model.eval()

    dummy_input = torch.randn(
        1,
        INPUT_STEPS,
        NUM_FEATURES,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:

        torch.onnx.export(
            model,
            dummy_input,
            output_path,
            input_names=[
                "traffic_history"
            ],
            output_names=[
                "traffic_forecast"
            ],
            dynamic_axes={
                "traffic_history": {
                    0: "batch"
                },
                "traffic_forecast": {
                    0: "batch"
                },
            },
            opset_version=17,
        )

        print(
            f"ONNX model saved: {output_path}"
        )

        print(
            f"ONNX file size: "
            f"{output_path.stat().st_size / 1024:.2f} KB"
        )

    except Exception as exc:

        print(
            "ONNX export gagal:"
        )

        print(exc)


# ============================================================
# MAIN
# ============================================================

def main():

    set_seed()

    device = get_device()

    print(
        "Device:",
        device,
    )

    print("\n" + "=" * 70)

    print(
        "SMARTTWIN - TRAFFIC LSTM TRAINING"
    )

    print("=" * 70)

    # ========================================================
    # CONTRACT
    # ========================================================

    print("\nMODEL CONTRACT")

    print(
        f"Features: {FEATURES}"
    )

    print(
        f"Input: {INPUT_STEPS} timestep × "
        f"{NUM_FEATURES} features"
    )

    print(
        f"History: "
        f"{INPUT_STEPS * INTERVAL_SECONDS} seconds"
    )

    print(
        f"Output: {OUTPUT_STEPS} timestep × "
        f"{NUM_FEATURES} features"
    )

    print(
        f"Forecast: "
        f"{OUTPUT_STEPS * INTERVAL_SECONDS} seconds"
    )

    print("\nDATA MAPPING")

    print(
        "crossing_simpang.csv"
    )

    print(
        "  jumlah_crossing → vehicleCount"
    )

    print(
        "\nsnapshot_zona.csv"
    )

    print(
        "  total_di_zona → densityIndex"
    )

    print("\nQueue:")

    print(
        "  queueLengthVeh  → 0 sementara"
    )

    print(
        "  queueLengthMEst → 0 sementara"
    )

    # ========================================================
    # LOAD DATA
    # ========================================================

    crossing_df = load_crossing_dataset(
        CROSSING_FILE
    )

    snapshot_df = load_snapshot_dataset(
        SNAPSHOT_FILE
    )

    # ========================================================
    # MERGE
    # ========================================================

    merged_df = merge_datasets(
        crossing_df,
        snapshot_df,
    )

    if len(merged_df) < (
        INPUT_STEPS
        + OUTPUT_STEPS
        + 10
    ):

        raise ValueError(
            "Data terlalu sedikit untuk "
            "membuat sequence LSTM."
        )

    # ========================================================
    # SPLIT
    # ========================================================

    train_df, val_df, test_df = (
        chronological_split(
            merged_df
        )
    )

    # ========================================================
    # SCALER
    # ========================================================

    scaler = fit_scaler(
        train_df
    )

    train_scaled = scaler.transform(
        train_df[FEATURES].values
    )

    val_scaled = scaler.transform(
        val_df[FEATURES].values
    )

    test_scaled = scaler.transform(
        test_df[FEATURES].values
    )

    # ========================================================
    # SEQUENCES
    # ========================================================

    print("\n[5] Creating sequences...")

    x_train, y_train = create_sequences(
        train_scaled
    )

    x_val, y_val = create_sequences(
        val_scaled
    )

    x_test, y_test = create_sequences(
        test_scaled
    )

    print(
        f"xTrain: {x_train.shape}"
    )

    print(
        f"yTrain: {y_train.shape}"
    )

    print(
        f"xVal: {x_val.shape}"
    )

    print(
        f"yVal: {y_val.shape}"
    )

    print(
        f"xTest: {x_test.shape}"
    )

    print(
        f"yTest: {y_test.shape}"
    )

    # ========================================================
    # LOADERS
    # ========================================================

    train_loader = make_loader(
        x_train,
        y_train,
        shuffle=True,
    )

    val_loader = make_loader(
        x_val,
        y_val,
        shuffle=False,
    )

    test_loader = make_loader(
        x_test,
        y_test,
        shuffle=False,
    )

    # ========================================================
    # MODEL
    # ========================================================

    model = TrafficLSTM()

    model = model.to(device)

    print("\n[6] Model:")

    print(model)

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=5,
    )

    # ========================================================
    # TRAIN
    # ========================================================

    print("\n[7] Training...")

    history = {
        "train_loss": [],
        "val_loss": [],
    }

    best_val_loss = float("inf")

    best_state = None

    patience_counter = 0

    for epoch in range(
        1,
        MAX_EPOCHS + 1,
    ):

        train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            criterion,
            device,
        )

        val_loss = evaluate_loss(
            model,
            val_loader,
            criterion,
            device,
        )

        scheduler.step(
            val_loss
        )

        history[
            "train_loss"
        ].append(
            float(train_loss)
        )

        history[
            "val_loss"
        ].append(
            float(val_loss)
        )

        print(
            f"Epoch {epoch:03d}/{MAX_EPOCHS} "
            f"| Train Loss: {train_loss:.6f} "
            f"| Val Loss: {val_loss:.6f}"
        )

        if val_loss < (
            best_val_loss
            - 1e-6
        ):

            best_val_loss = val_loss

            best_state = {
                key: value.detach()
                .cpu()
                .clone()
                for key, value
                in model.state_dict().items()
            }

            patience_counter = 0

        else:

            patience_counter += 1

        if patience_counter >= PATIENCE:

            print(
                "\nEarly stopping."
            )

            break

    # ========================================================
    # RESTORE BEST MODEL
    # ========================================================

    if best_state is not None:

        model.load_state_dict(
            best_state
        )

    # ========================================================
    # SAVE TRAINING INFO
    # ========================================================

    save_training_plot(
        history,
        PLOT_DIR
        / "training_validation_loss.png",
    )

    save_history(
        history,
        HISTORY_FILE,
    )

    # ========================================================
    # TEST
    # ========================================================

    print("\n[10] Evaluating test set...")

    y_pred_scaled, y_true_scaled = predict(
        model,
        test_loader,
        device,
    )

    if len(y_pred_scaled) == 0:

        raise ValueError(
            "Test sequence kosong."
        )

    # ========================================================
    # INVERSE TRANSFORM
    #
    # PENTING:
    # tetap 3 DIMENSI sampai selesai.
    # Ini mencegah error:
    #
    # IndexError: too many indices...
    # ========================================================

    y_pred = inverse_scale_sequences(
        y_pred_scaled,
        scaler,
    )

    y_true = inverse_scale_sequences(
        y_true_scaled,
        scaler,
    )

    # ========================================================
    # METRICS
    # ========================================================

    mae, mse, rmse, feature_mae = (
        calculate_metrics(
            y_true,
            y_pred,
        )
    )

    print(
        f"\nTest MAE : {mae:.4f}"
    )

    print(
        f"Test MSE : {mse:.4f}"
    )

    print(
        f"Test RMSE: {rmse:.4f}"
    )

    print("\nMAE per feature:")

    for feature in FEATURES:

        print(
            f"  {feature}: "
            f"{feature_mae[feature]:.4f}"
        )

    # ========================================================
    # SAVE PREDICTIONS
    # ========================================================

    save_predictions(
        y_true,
        y_pred,
        PREDICTIONS_FILE,
    )

    # ========================================================
    # SAVE SCALER
    # ========================================================

    save_scaler(
        scaler,
        SCALER_FILE,
    )

    # ========================================================
    # SAVE METADATA
    # ========================================================

    metrics = {
        "mae": float(mae),
        "mse": float(mse),
        "rmse": float(rmse),
        "feature_mae": {
            key: float(value)
            for key, value
            in feature_mae.items()
        },
    }

    save_metadata(
        METADATA_FILE,
        len(train_df),
        len(val_df),
        len(test_df),
        metrics,
    )

    # ========================================================
    # SAVE PYTORCH
    # ========================================================

    save_pytorch_model(
        model,
        MODEL_FILE,
    )

    # ========================================================
    # ONNX
    # ========================================================

    export_onnx(
        model,
        ONNX_FILE,
    )

    # ========================================================
    # FINISH
    # ========================================================

    print("\n" + "=" * 70)

    print(
        "TRAINING SELESAI"
    )

    print("=" * 70)

    print("\nModel PyTorch:")

    print(
        MODEL_FILE
    )

    print("\nModel ONNX:")

    print(
        ONNX_FILE
    )

    print("\nScaler:")

    print(
        SCALER_FILE
    )

    print("\nMetadata:")

    print(
        METADATA_FILE
    )

    print("\nPredictions:")

    print(
        PREDICTIONS_FILE
    )

    print("\nTraining history:")

    print(
        HISTORY_FILE
    )

    print("\nTraining plot:")

    print(
        PLOT_DIR
        / "training_validation_loss.png"
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()