"""
02_train_lstm.py

Train LSTM model untuk forecasting kondisi lalu lintas
berdasarkan dataset TMU yang sudah diproses oleh
01_prepare_tmu.py.

INPUT:
    outputs/processed/tmu_processed.csv

TARGET:
    1. vehicle_count
    2. speed_value
    3. density_proxy
    4. queue_proxy

OUTPUT:
    models/lstm_model.pt
    models/scaler_X.pkl
    models/scaler_y.pkl
    models/model_config.json

    outputs/metrics/training_history.csv
    outputs/metrics/training_summary.json
"""

from pathlib import Path
import json
import random
import time

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    BASE_DIR
    / "outputs"
    / "processed"
    / "tmu_processed.csv"
)

MODEL_DIR = BASE_DIR / "models"
METRICS_DIR = BASE_DIR / "outputs" / "metrics"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# REPRODUCIBILITY
# ============================================================

SEED = 42


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


set_seed()


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


# ============================================================
# SEQUENCE CONFIGURATION
# ============================================================

# 16 timestep x sekitar 15 menit
# = sekitar 4 jam histori traffic.

SEQUENCE_LENGTH = 16

# Forecast 1 timestep ke depan.
#
# Data TMU umumnya memiliki interval 15 menit,
# sehingga horizon = 1 berarti sekitar 15 menit
# ke depan.

FORECAST_HORIZON = 1


# ============================================================
# FEATURES
# ============================================================

FEATURE_COLUMNS = [
    # --------------------------------------------------------
    # Current traffic state
    # --------------------------------------------------------

    "vehicle_count",
    "speed_value",

    # --------------------------------------------------------
    # Vehicle composition
    # --------------------------------------------------------

    "vehicles_less_5_2m",
    "vehicles_5_21m_6_6m",
    "vehicles_6_61m_11_6m",
    "vehicles_above_11_6m",

    # --------------------------------------------------------
    # Vehicle composition percentage
    # --------------------------------------------------------

    "pct_vehicles_less_5_2m",
    "pct_vehicles_5_21m_6_6m",
    "pct_vehicles_6_61m_11_6m",
    "pct_vehicles_above_11_6m",

    # --------------------------------------------------------
    # Temporal dynamics
    # --------------------------------------------------------

    "vehicle_count_change",
    "speed_change",

    # --------------------------------------------------------
    # Rolling statistics
    # --------------------------------------------------------

    "vehicle_count_rolling_mean_1h",
    "vehicle_count_rolling_std_1h",
    "speed_rolling_mean_1h",

    # --------------------------------------------------------
    # Time encoding
    # --------------------------------------------------------

    "hour_sin",
    "hour_cos",
    "day_sin",
    "day_cos",
    "is_weekend",
]


# ============================================================
# TARGETS
# ============================================================

TARGET_COLUMNS = [
    "vehicle_count",
    "speed_value",
    "density_proxy",
    "queue_proxy",
]


# ============================================================
# TRAINING CONFIGURATION
# ============================================================

HIDDEN_SIZE = 128
NUM_LAYERS = 2
DROPOUT = 0.2

BATCH_SIZE = 64

EPOCHS = 150

LEARNING_RATE = 0.001

WEIGHT_DECAY = 1e-5

PATIENCE = 15

TRAIN_RATIO = 0.70
VALIDATION_RATIO = 0.15
TEST_RATIO = 0.15


# ============================================================
# LSTM MODEL
# ============================================================

class TrafficLSTM(nn.Module):

    def __init__(
        self,
        input_size,
        hidden_size,
        num_layers,
        output_size,
        dropout,
    ):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=(
                dropout
                if num_layers > 1
                else 0.0
            ),
        )

        self.dropout = nn.Dropout(dropout)

        self.fc = nn.Linear(
            hidden_size,
            output_size,
        )

    def forward(self, x):

        lstm_out, _ = self.lstm(x)

        last_output = lstm_out[:, -1, :]

        last_output = self.dropout(
            last_output
        )

        output = self.fc(last_output)

        return output


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("=" * 70)
    print("LSTM TRAFFIC FORECASTING TRAINING")
    print("=" * 70)

    print("[INFO] Loading dataset:")
    print(f"       {INPUT_FILE}")

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Processed dataset tidak ditemukan:\n"
            f"{INPUT_FILE}\n\n"
            f"Jalankan terlebih dahulu:\n"
            f"python scripts/01_prepare_tmu.py"
        )

    df = pd.read_csv(INPUT_FILE)

    print(
        f"[INFO] Rows: {len(df):,}"
    )

    print(
        f"[INFO] Columns: {len(df.columns)}"
    )

    return df


# ============================================================
# VALIDATE DATA
# ============================================================

def validate_data(df):

    print("\n" + "=" * 70)
    print("DATA VALIDATION")
    print("=" * 70)

    required_columns = (
        ["timestamp"]
        + FEATURE_COLUMNS
        + TARGET_COLUMNS
    )

    # Hilangkan duplikasi nama kolom
    required_columns = list(
        dict.fromkeys(required_columns)
    )

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:

        print("[ERROR] Missing columns:")

        for col in missing_columns:
            print(f"        - {col}")

        raise ValueError(
            "Dataset tidak memiliki semua "
            "kolom yang dibutuhkan."
        )

    print("[OK] Semua feature tersedia.")
    print("[OK] Semua target tersedia.")

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    invalid_timestamp = (
        df["timestamp"].isna().sum()
    )

    if invalid_timestamp > 0:

        print(
            f"[WARNING] Invalid timestamp: "
            f"{invalid_timestamp}"
        )

        df = df.dropna(
            subset=["timestamp"]
        )

    # --------------------------------------------------------
    # Sort chronological
    # --------------------------------------------------------

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Numeric columns
    # --------------------------------------------------------

    # Jangan gunakan:
    #
    # df[FEATURE_COLUMNS + TARGET_COLUMNS] = ...
    #
    # karena vehicle_count dan speed_value
    # muncul di kedua list.

    numeric_columns = list(
        dict.fromkeys(
            FEATURE_COLUMNS
            + TARGET_COLUMNS
        )
    )

    # Convert satu per satu
    # supaya aman dari duplicate column issue.

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    missing_before = int(
        df[numeric_columns]
        .isna()
        .sum()
        .sum()
    )

    print(
        f"[INFO] Missing numeric values: "
        f"{missing_before}"
    )

    # --------------------------------------------------------
    # Interpolation
    # --------------------------------------------------------

    if missing_before > 0:

        df[numeric_columns] = (
            df[numeric_columns]
            .interpolate(
                method="linear"
            )
            .ffill()
            .bfill()
        )

    missing_after = int(
        df[numeric_columns]
        .isna()
        .sum()
        .sum()
    )

    print(
        f"[INFO] Missing after cleaning: "
        f"{missing_after}"
    )

    if missing_after > 0:

        raise ValueError(
            "Masih terdapat missing values "
            "setelah preprocessing."
        )

    # --------------------------------------------------------
    # Time information
    # --------------------------------------------------------

    print(
        "[INFO] Time range:"
        f"\n       {df['timestamp'].min()}"
        f"\n       {df['timestamp'].max()}"
    )

    return df


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    X,
    y,
    sequence_length,
    forecast_horizon,
):

    X_sequences = []
    y_targets = []

    max_start = (
        len(X)
        - sequence_length
        - forecast_horizon
        + 1
    )

    for i in range(max_start):

        X_end = (
            i
            + sequence_length
        )

        y_index = (
            X_end
            + forecast_horizon
            - 1
        )

        X_sequences.append(
            X[i:X_end]
        )

        y_targets.append(
            y[y_index]
        )

    return (
        np.asarray(
            X_sequences,
            dtype=np.float32,
        ),
        np.asarray(
            y_targets,
            dtype=np.float32,
        ),
    )


# ============================================================
# TRAIN ONE EPOCH
# ============================================================

def train_one_epoch(
    model,
    loader,
    criterion,
    optimizer,
):

    model.train()

    total_loss = 0.0

    for X_batch, y_batch in loader:

        X_batch = X_batch.to(
            DEVICE
        )

        y_batch = y_batch.to(
            DEVICE
        )

        optimizer.zero_grad()

        predictions = model(
            X_batch
        )

        loss = criterion(
            predictions,
            y_batch,
        )

        loss.backward()

        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            max_norm=1.0,
        )

        optimizer.step()

        total_loss += (
            loss.item()
            * X_batch.size(0)
        )

    return (
        total_loss
        / len(loader.dataset)
    )


# ============================================================
# VALIDATION
# ============================================================

def evaluate_loss(
    model,
    loader,
    criterion,
):

    model.eval()

    total_loss = 0.0

    with torch.no_grad():

        for X_batch, y_batch in loader:

            X_batch = X_batch.to(
                DEVICE
            )

            y_batch = y_batch.to(
                DEVICE
            )

            predictions = model(
                X_batch
            )

            loss = criterion(
                predictions,
                y_batch,
            )

            total_loss += (
                loss.item()
                * X_batch.size(0)
            )

    return (
        total_loss
        / len(loader.dataset)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    start_time = time.time()

    print(
        f"[INFO] Device: {DEVICE}"
    )

    if DEVICE.type == "cpu":

        print(
            "[INFO] Training menggunakan CPU."
        )

        print(
            "[INFO] Model dikonfigurasi agar "
            "tetap relatif ringan untuk laptop."
        )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    df = load_data()

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    df = validate_data(df)

    # --------------------------------------------------------
    # Feature / target extraction
    # --------------------------------------------------------

    X_raw = (
        df[FEATURE_COLUMNS]
        .values
    )

    y_raw = (
        df[TARGET_COLUMNS]
        .values
    )

    print("\n" + "=" * 70)
    print(
        "FEATURE / TARGET CONFIGURATION"
    )
    print("=" * 70)

    print(
        f"[INFO] Input features: "
        f"{len(FEATURE_COLUMNS)}"
    )

    for i, feature in enumerate(
        FEATURE_COLUMNS,
        start=1,
    ):

        print(
            f"       {i:02d}. {feature}"
        )

    print(
        f"\n[INFO] Targets: "
        f"{len(TARGET_COLUMNS)}"
    )

    for i, target in enumerate(
        TARGET_COLUMNS,
        start=1,
    ):

        print(
            f"       {i}. {target}"
        )

    # --------------------------------------------------------
    # Determine raw temporal split
    # --------------------------------------------------------

    total_rows = len(X_raw)

    train_end = int(
        total_rows
        * TRAIN_RATIO
    )

    validation_end = int(
        total_rows
        * (
            TRAIN_RATIO
            + VALIDATION_RATIO
        )
    )

    # --------------------------------------------------------
    # Scaling
    # --------------------------------------------------------

    scaler_X = StandardScaler()

    scaler_y = StandardScaler()

    scaler_X.fit(
        X_raw[:train_end]
    )

    scaler_y.fit(
        y_raw[:train_end]
    )

    X_scaled = scaler_X.transform(
        X_raw
    )

    y_scaled = scaler_y.transform(
        y_raw
    )

    # --------------------------------------------------------
    # Create sequences
    # --------------------------------------------------------

    X_sequences, y_sequences = (
        create_sequences(
            X_scaled,
            y_scaled,
            SEQUENCE_LENGTH,
            FORECAST_HORIZON,
        )
    )

    print("\n" + "=" * 70)
    print(
        "SEQUENCE CONFIGURATION"
    )
    print("=" * 70)

    print(
        f"[INFO] Sequence length : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[INFO] Forecast horizon: "
        f"{FORECAST_HORIZON}"
    )

    print(
        f"[INFO] X shape         : "
        f"{X_sequences.shape}"
    )

    print(
        f"[INFO] y shape         : "
        f"{y_sequences.shape}"
    )

    # --------------------------------------------------------
    # Sequence split
    # --------------------------------------------------------

    sequence_count = len(
        X_sequences
    )

    train_seq_end = int(
        sequence_count
        * TRAIN_RATIO
    )

    validation_seq_end = int(
        sequence_count
        * (
            TRAIN_RATIO
            + VALIDATION_RATIO
        )
    )

    X_train = X_sequences[
        :train_seq_end
    ]

    y_train = y_sequences[
        :train_seq_end
    ]

    X_validation = X_sequences[
        train_seq_end:
        validation_seq_end
    ]

    y_validation = y_sequences[
        train_seq_end:
        validation_seq_end
    ]

    X_test = X_sequences[
        validation_seq_end:
    ]

    y_test = y_sequences[
        validation_seq_end:
    ]

    print(
        "\n[INFO] Dataset split:"
    )

    print(
        f"       Train      : "
        f"{len(X_train):,}"
    )

    print(
        f"       Validation : "
        f"{len(X_validation):,}"
    )

    print(
        f"       Test       : "
        f"{len(X_test):,}"
    )

    # --------------------------------------------------------
    # Tensor conversion
    # --------------------------------------------------------

    X_train_tensor = torch.tensor(
        X_train,
        dtype=torch.float32,
    )

    y_train_tensor = torch.tensor(
        y_train,
        dtype=torch.float32,
    )

    X_validation_tensor = torch.tensor(
        X_validation,
        dtype=torch.float32,
    )

    y_validation_tensor = torch.tensor(
        y_validation,
        dtype=torch.float32,
    )

    # --------------------------------------------------------
    # DataLoader
    # --------------------------------------------------------

    train_dataset = TensorDataset(
        X_train_tensor,
        y_train_tensor,
    )

    validation_dataset = TensorDataset(
        X_validation_tensor,
        y_validation_tensor,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    validation_loader = DataLoader(
        validation_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = TrafficLSTM(
        input_size=len(
            FEATURE_COLUMNS
        ),
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        output_size=len(
            TARGET_COLUMNS
        ),
        dropout=DROPOUT,
    ).to(DEVICE)

    parameter_count = sum(
        p.numel()
        for p in model.parameters()
    )

    print("\n" + "=" * 70)
    print("MODEL")
    print("=" * 70)

    print(
        f"[INFO] Input size  : "
        f"{len(FEATURE_COLUMNS)}"
    )

    print(
        f"[INFO] Hidden size : "
        f"{HIDDEN_SIZE}"
    )

    print(
        f"[INFO] LSTM layers : "
        f"{NUM_LAYERS}"
    )

    print(
        f"[INFO] Output size : "
        f"{len(TARGET_COLUMNS)}"
    )

    print(
        f"[INFO] Parameters  : "
        f"{parameter_count:,}"
    )

    # --------------------------------------------------------
    # Loss / optimizer
    # --------------------------------------------------------

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    scheduler = (
        torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=0.5,
            patience=5,
            min_lr=1e-6,
        )
    )

    # --------------------------------------------------------
    # Training
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("TRAINING")
    print("=" * 70)

    history = []

    best_validation_loss = float(
        "inf"
    )

    patience_counter = 0

    best_model_state = None

    training_start = time.time()

    for epoch in range(
        1,
        EPOCHS + 1,
    ):

        epoch_start = time.time()

        train_loss = train_one_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
        )

        validation_loss = evaluate_loss(
            model,
            validation_loader,
            criterion,
        )

        scheduler.step(
            validation_loss
        )

        current_lr = (
            optimizer
            .param_groups[0]["lr"]
        )

        epoch_time = (
            time.time()
            - epoch_start
        )

        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss":
                    validation_loss,
                "learning_rate":
                    current_lr,
                "epoch_time_seconds":
                    epoch_time,
            }
        )

        if (
            validation_loss
            < best_validation_loss
        ):

            best_validation_loss = (
                validation_loss
            )

            best_model_state = {
                key:
                    value.detach()
                    .cpu()
                    .clone()
                for key, value
                in model.state_dict()
                .items()
            }

            patience_counter = 0

            status = "BEST"

        else:

            patience_counter += 1

            status = ""

        print(
            f"Epoch "
            f"{epoch:03d}/{EPOCHS} | "
            f"Train: "
            f"{train_loss:.6f} | "
            f"Val: "
            f"{validation_loss:.6f} | "
            f"LR: "
            f"{current_lr:.6f} | "
            f"{epoch_time:.1f}s "
            f"{status}"
        )

        if (
            patience_counter
            >= PATIENCE
        ):

            print(
                "\n[INFO] Early stopping."
            )

            break

    training_time = (
        time.time()
        - training_start
    )

    # --------------------------------------------------------
    # Restore best model
    # --------------------------------------------------------

    if best_model_state is not None:

        model.load_state_dict(
            best_model_state
        )

    # --------------------------------------------------------
    # Save model
    # --------------------------------------------------------

    model_path = (
        MODEL_DIR
        / "lstm_model.pt"
    )

    torch.save(
        {
            "model_state_dict":
                model.state_dict(),

            "model_class":
                "TrafficLSTM",

            "input_size":
                len(FEATURE_COLUMNS),

            "hidden_size":
                HIDDEN_SIZE,

            "num_layers":
                NUM_LAYERS,

            "output_size":
                len(TARGET_COLUMNS),

            "dropout":
                DROPOUT,

            "sequence_length":
                SEQUENCE_LENGTH,

            "forecast_horizon":
                FORECAST_HORIZON,

            "feature_columns":
                FEATURE_COLUMNS,

            "target_columns":
                TARGET_COLUMNS,
        },
        model_path,
    )

    # --------------------------------------------------------
    # Save scalers
    # --------------------------------------------------------

    scaler_X_path = (
        MODEL_DIR
        / "scaler_X.pkl"
    )

    scaler_y_path = (
        MODEL_DIR
        / "scaler_y.pkl"
    )

    joblib.dump(
        scaler_X,
        scaler_X_path,
    )

    joblib.dump(
        scaler_y,
        scaler_y_path,
    )

    # --------------------------------------------------------
    # Save model config
    # --------------------------------------------------------

    config = {

        "framework": "pytorch",

        "model_type": "LSTM",

        "device_used":
            str(DEVICE),

        "feature_columns":
            FEATURE_COLUMNS,

        "target_columns":
            TARGET_COLUMNS,

        "input_size":
            len(FEATURE_COLUMNS),

        "output_size":
            len(TARGET_COLUMNS),

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "hidden_size":
            HIDDEN_SIZE,

        "num_layers":
            NUM_LAYERS,

        "dropout":
            DROPOUT,

        "batch_size":
            BATCH_SIZE,

        "epochs_configured":
            EPOCHS,

        "epochs_trained":
            len(history),

        "learning_rate":
            LEARNING_RATE,

        "weight_decay":
            WEIGHT_DECAY,

        "early_stopping_patience":
            PATIENCE,

        "train_ratio":
            TRAIN_RATIO,

        "validation_ratio":
            VALIDATION_RATIO,

        "test_ratio":
            TEST_RATIO,

        "seed":
            SEED,

        "best_validation_loss":
            float(
                best_validation_loss
            ),

        "training_time_seconds":
            float(training_time),

        "dataset_rows":
            len(df),

        "sequence_count":
            sequence_count,
    }

    config_path = (
        MODEL_DIR
        / "model_config.json"
    )

    with open(
        config_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            config,
            f,
            indent=4,
        )

    # --------------------------------------------------------
    # Save training history
    # --------------------------------------------------------

    history_df = pd.DataFrame(
        history
    )

    history_path = (
        METRICS_DIR
        / "training_history.csv"
    )

    history_df.to_csv(
        history_path,
        index=False,
    )

    # --------------------------------------------------------
    # Save summary
    # --------------------------------------------------------

    summary = {

        "status": "completed",

        "model":
            "TrafficLSTM",

        "framework":
            "PyTorch",

        "device":
            str(DEVICE),

        "input_features":
            len(FEATURE_COLUMNS),

        "targets":
            TARGET_COLUMNS,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "dataset_rows":
            len(df),

        "training_sequences":
            len(X_train),

        "validation_sequences":
            len(X_validation),

        "test_sequences":
            len(X_test),

        "epochs_trained":
            len(history),

        "best_validation_loss":
            float(
                best_validation_loss
            ),

        "training_time_seconds":
            float(training_time),

        "model_file":
            str(model_path),

        "scaler_X_file":
            str(scaler_X_path),

        "scaler_y_file":
            str(scaler_y_path),

        "config_file":
            str(config_path),
    }

    summary_path = (
        METRICS_DIR
        / "training_summary.json"
    )

    with open(
        summary_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            indent=4,
        )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    total_time = (
        time.time()
        - start_time
    )

    print("\n" + "=" * 70)
    print("TRAINING COMPLETED")
    print("=" * 70)

    print(
        f"[OK] Model saved:\n"
        f"     {model_path}"
    )

    print(
        f"[OK] X scaler saved:\n"
        f"     {scaler_X_path}"
    )

    print(
        f"[OK] Y scaler saved:\n"
        f"     {scaler_y_path}"
    )

    print(
        f"[OK] Model config saved:\n"
        f"     {config_path}"
    )

    print(
        f"[OK] Training history saved:\n"
        f"     {history_path}"
    )

    print(
        f"[OK] Training summary saved:\n"
        f"     {summary_path}"
    )

    print("\n[INFO] Final targets:")

    for i, target in enumerate(
        TARGET_COLUMNS,
        start=1,
    ):

        print(
            f"       {i}. {target}"
        )

    print(
        f"\n[INFO] Best validation loss: "
        f"{best_validation_loss:.6f}"
    )

    print(
        f"[INFO] Training time: "
        f"{training_time / 60:.2f} minutes"
    )

    print(
        f"[INFO] Total execution time: "
        f"{total_time / 60:.2f} minutes"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()