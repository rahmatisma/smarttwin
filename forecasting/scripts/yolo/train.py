from __future__ import annotations

import json
import random
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.preprocessing import MinMaxScaler
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset


# ============================================================
# PATH
# ============================================================

# Struktur:
#
# forecasting/
# ├── data/
# │   └── percobaan_logic_simpang.csv
# ├── scripts/
# │   └── yolo/
# │       └── 5_train.py
# └── outputs/
#     └── yolo/
#
# __file__:
# forecasting/scripts/yolo/5_train.py
#
# parents[0] = yolo
# parents[1] = scripts
# parents[2] = forecasting

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs" / "yolo"
PLOT_DIR = OUTPUT_DIR / "plots"

DATA_FILE = DATA_DIR / "percobaan_logic_simpang.csv"

MODEL_FILE = OUTPUT_DIR / "traffic_lstm.pt"
SCALER_FILE = OUTPUT_DIR / "scaler.pkl"
METADATA_FILE = OUTPUT_DIR / "metadata.json"
HISTORY_FILE = OUTPUT_DIR / "training_history.json"
PREDICTIONS_FILE = OUTPUT_DIR / "predictions.csv"


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PLOT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# CONFIGURATION
# ============================================================

RANDOM_SEED = 42

# Data asli kamu dicatat setiap 5 detik.
INTERVAL_SECONDS = 5

# 12 timestep × 5 detik = 60 detik history
LOOKBACK = 12

# 3 timestep × 5 detik = prediksi 15 detik ke depan
HORIZON = 3

# Chronological split
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Training
BATCH_SIZE = 32
EPOCHS = 100
LEARNING_RATE = 0.001
PATIENCE = 15

# LSTM
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2


# ============================================================
# FEATURES
# ============================================================

FEATURE_COLUMNS = [
    "total_di_zona",
    "motor_di_zona",
    "mobil_di_zona",
    "truk_di_zona",
    "bus_di_zona",
]


# ============================================================
# RANDOM SEED
# ============================================================

def set_seed(seed: int = RANDOM_SEED):
    random.seed(seed)
    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # Membuat hasil lebih reproducible
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# DEVICE
# ============================================================

def get_device():
    if torch.cuda.is_available():
        device = torch.device("cuda")

        print(
            "CUDA tersedia:",
            torch.cuda.get_device_name(0),
        )

        return device

    print("CUDA tidak tersedia. Menggunakan CPU.")

    return torch.device("cpu")


# ============================================================
# DATASET CLASS
# ============================================================

class TrafficDataset(Dataset):

    def __init__(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ):
        self.X = torch.tensor(
            X,
            dtype=torch.float32,
        )

        self.y = torch.tensor(
            y,
            dtype=torch.float32,
        )

    def __len__(self):
        return len(self.X)

    def __getitem__(self, index):
        return (
            self.X[index],
            self.y[index],
        )


# ============================================================
# LSTM MODEL
# ============================================================

class TrafficLSTM(nn.Module):

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        num_layers: int,
        horizon: int,
        output_size: int,
        dropout: float,
    ):
        super().__init__()

        self.horizon = horizon
        self.output_size = output_size

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

        self.fc = nn.Linear(
            hidden_size,
            horizon * output_size,
        )

    def forward(self, x):

        # x:
        # [batch, lookback, features]

        output, _ = self.lstm(x)

        # Ambil hidden state timestep terakhir
        last_output = output[:, -1, :]

        prediction = self.fc(last_output)

        prediction = prediction.view(
            -1,
            self.horizon,
            self.output_size,
        )

        return prediction


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("\n[1] Loading dataset...")

    if not DATA_FILE.exists():

        raise FileNotFoundError(
            "\n"
            "Dataset tidak ditemukan!\n\n"
            f"{DATA_FILE}\n\n"
            "Pastikan file berada di:\n"
            f"{DATA_DIR}"
        )

    print("Dataset ditemukan:")
    print(DATA_FILE)

    df = pd.read_csv(DATA_FILE)

    print("\nKolom dataset:")
    print(list(df.columns))

    required_columns = [
        "timestamp",
        "kamera",
        "lengan",
        *FEATURE_COLUMNS,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "\nKolom berikut tidak ditemukan:\n"
            + "\n".join(
                f"- {column}"
                for column in missing_columns
            )
        )

    # Timestamp
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    # Hapus timestamp invalid
    df = df.dropna(
        subset=["timestamp"]
    )

    # Numeric conversion
    for column in FEATURE_COLUMNS:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # Missing numeric values
    df[FEATURE_COLUMNS] = (
        df[FEATURE_COLUMNS]
        .fillna(0)
    )

    # Sort
    df = df.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    print("\nJumlah raw rows:")
    print(len(df))

    print("\nRange waktu:")
    print(
        df["timestamp"].min(),
        "->",
        df["timestamp"].max(),
    )

    return df


# ============================================================
# AGGREGATE TO INTERSECTION TIMESTEP
# ============================================================

def prepare_timeseries(df: pd.DataFrame):

    print("\n[2] Preparing time series...")

    print(
        "Data akan diagregasi berdasarkan timestamp."
    )

    print(
        "kamera/lengan tidak dijadikan feature langsung."
    )

    # Karena satu timestamp memiliki beberapa kamera/lengan,
    # kita jumlahkan seluruh kendaraan dari semua lengan.
    #
    # Contoh:
    #
    # 16:30:10
    # CCTV_1 selatan
    # CCTV_2 tengah
    # CCTV_3 barat
    # CCTV_4 timur
    #
    # menjadi satu timestep:
    #
    # 16:30:10
    # total_di_zona = seluruh lengan

    ts_df = (
        df.groupby("timestamp")[
            FEATURE_COLUMNS
        ]
        .sum()
        .reset_index()
    )

    # Pastikan urut
    ts_df = ts_df.sort_values(
        "timestamp"
    ).reset_index(drop=True)

    # Tampilkan statistik
    print(
        "\nJumlah timestep setelah agregasi:",
        len(ts_df),
    )

    print(
        "Range waktu:",
        ts_df["timestamp"].min(),
        "->",
        ts_df["timestamp"].max(),
    )

    print("\nContoh data setelah agregasi:")

    print(
        ts_df.head(10).to_string(
            index=False
        )
    )

    # Cek interval
    intervals = (
        ts_df["timestamp"]
        .diff()
        .dt.total_seconds()
        .dropna()
    )

    if len(intervals) > 0:

        print(
            "\nInterval median:",
            intervals.median(),
            "detik",
        )

        print(
            "Interval minimum:",
            intervals.min(),
            "detik",
        )

        print(
            "Interval maksimum:",
            intervals.max(),
            "detik",
        )

    return ts_df


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    values: np.ndarray,
    lookback: int,
    horizon: int,
):

    X = []
    y = []

    total_length = len(values)

    max_start = (
        total_length
        - lookback
        - horizon
        + 1
    )

    for start in range(max_start):

        end = start + lookback

        target_end = (
            end + horizon
        )

        X.append(
            values[start:end]
        )

        y.append(
            values[end:target_end]
        )

    X = np.asarray(
        X,
        dtype=np.float32,
    )

    y = np.asarray(
        y,
        dtype=np.float32,
    )

    return X, y


# ============================================================
# PLOT 1
# TRAINING VS VALIDATION LOSS
# ============================================================

def plot_training_validation_loss(
    history,
):

    plt.figure(
        figsize=(10, 6)
    )

    epochs = range(
        1,
        len(
            history["train_loss"]
        ) + 1,
    )

    plt.plot(
        epochs,
        history["train_loss"],
        label="Training Loss",
        linewidth=2,
    )

    plt.plot(
        epochs,
        history["val_loss"],
        label="Validation Loss",
        linewidth=2,
    )

    plt.title(
        "LSTM Training vs Validation Loss"
    )

    plt.xlabel("Epoch")

    plt.ylabel("MSE Loss")

    plt.legend()

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.tight_layout()

    output_file = (
        PLOT_DIR
        / "training_validation_loss.png"
    )

    plt.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    print(
        "Plot saved:",
        output_file,
    )


# ============================================================
# PLOT 2
# ACTUAL VS PREDICTED
# ============================================================

def plot_actual_vs_predicted(
    timestamps,
    actual,
    predicted,
):

    # Gunakan target horizon pertama.
    # Jadi kita membandingkan prediksi
    # 5 detik ke depan dengan aktualnya.

    actual_first = actual[:, 0, :]
    predicted_first = predicted[:, 0, :]

    total_actual = (
        actual_first.sum(axis=1)
    )

    total_predicted = (
        predicted_first.sum(axis=1)
    )

    plt.figure(
        figsize=(14, 6)
    )

    plt.plot(
        timestamps,
        total_actual,
        label="Actual",
        linewidth=2,
    )

    plt.plot(
        timestamps,
        total_predicted,
        label="Predicted",
        linewidth=2,
        linestyle="--",
    )

    plt.title(
        "Actual vs Predicted Traffic"
    )

    plt.xlabel("Time")

    plt.ylabel(
        "Total Vehicles"
    )

    plt.legend()

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.xticks(
        rotation=30
    )

    plt.tight_layout()

    output_file = (
        PLOT_DIR
        / "actual_vs_predicted.png"
    )

    plt.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    print(
        "Plot saved:",
        output_file,
    )


# ============================================================
# PLOT 3
# TRAIN / VALIDATION / TEST SPLIT
# ============================================================

def plot_train_val_test_split(
    df,
    train_end,
    val_end,
):

    timestamps = df[
        "timestamp"
    ]

    total = df[
        FEATURE_COLUMNS
    ].sum(axis=1)

    plt.figure(
        figsize=(14, 6)
    )

    plt.plot(
        timestamps,
        total,
        linewidth=1.8,
        label="Traffic",
    )

    if train_end > 0:

        plt.axvline(
            timestamps.iloc[
                train_end - 1
            ],
            linestyle="--",
            linewidth=2,
            label="Train / Validation",
        )

    if val_end > 0:

        plt.axvline(
            timestamps.iloc[
                val_end - 1
            ],
            linestyle="--",
            linewidth=2,
            label="Validation / Test",
        )

    plt.title(
        "Chronological Train / Validation / Test Split"
    )

    plt.xlabel("Time")

    plt.ylabel(
        "Total Vehicles"
    )

    plt.legend()

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.xticks(
        rotation=30
    )

    plt.tight_layout()

    output_file = (
        PLOT_DIR
        / "train_val_test_split.png"
    )

    plt.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    print(
        "Plot saved:",
        output_file,
    )


# ============================================================
# PLOT 4
# FEATURE PREDICTION
# ============================================================

def plot_feature_prediction(
    timestamps,
    actual,
    predicted,
):

    actual_first = actual[:, 0, :]
    predicted_first = predicted[:, 0, :]

    feature_names = [
        "Total Vehicles",
        "Motorcycles",
        "Cars",
        "Trucks",
        "Buses",
    ]

    fig, axes = plt.subplots(
        len(FEATURE_COLUMNS),
        1,
        figsize=(14, 16),
    )

    for i, ax in enumerate(axes):

        ax.plot(
            timestamps,
            actual_first[:, i],
            label="Actual",
            linewidth=1.8,
        )

        ax.plot(
            timestamps,
            predicted_first[:, i],
            label="Predicted",
            linewidth=1.8,
            linestyle="--",
        )

        ax.set_title(
            feature_names[i]
        )

        ax.set_ylabel(
            "Vehicles"
        )

        ax.grid(
            True,
            alpha=0.3,
        )

        ax.legend()

    axes[-1].set_xlabel(
        "Time"
    )

    plt.suptitle(
        "Actual vs Predicted by Vehicle Type",
        fontsize=16,
    )

    plt.xticks(
        rotation=30
    )

    plt.tight_layout(
        rect=[
            0,
            0,
            1,
            0.97,
        ]
    )

    output_file = (
        PLOT_DIR
        / "feature_prediction.png"
    )

    plt.savefig(
        output_file,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    print(
        "Plot saved:",
        output_file,
    )


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def save_predictions(
    timestamps,
    actual,
    predicted,
):

    rows = []

    for i in range(
        len(timestamps)
    ):

        row = {
            "timestamp": timestamps[i]
        }

        for feature_index, feature in enumerate(
            FEATURE_COLUMNS
        ):

            row[
                f"actual_{feature}"
            ] = float(
                actual[
                    i,
                    0,
                    feature_index,
                ]
            )

            row[
                f"predicted_{feature}"
            ] = float(
                predicted[
                    i,
                    0,
                    feature_index,
                ]
            )

        rows.append(row)

    predictions_df = pd.DataFrame(
        rows
    )

    predictions_df.to_csv(
        PREDICTIONS_FILE,
        index=False,
    )

    print(
        "\nPredictions saved:",
        PREDICTIONS_FILE,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    set_seed()

    device = get_device()

    print()
    print("=" * 70)
    print(
        "SMARTTWIN - YOLO TRAFFIC FORECASTING"
    )
    print("=" * 70)

    print("\nConfiguration:")

    print(
        "LOOKBACK:",
        LOOKBACK,
        f"({LOOKBACK * INTERVAL_SECONDS} detik)",
    )

    print(
        "HORIZON:",
        HORIZON,
        f"({HORIZON * INTERVAL_SECONDS} detik)",
    )

    print(
        "TRAIN:",
        f"{TRAIN_RATIO * 100:.0f}%",
    )

    print(
        "VALIDATION:",
        f"{VAL_RATIO * 100:.0f}%",
    )

    print(
        "TEST:",
        f"{TEST_RATIO * 100:.0f}%",
    )

    print("\nDataset:")
    print(DATA_FILE)

    print("\nOutput:")
    print(OUTPUT_DIR)

    # ========================================================
    # LOAD
    # ========================================================

    raw_df = load_data()

    # ========================================================
    # PREPARE TIME SERIES
    # ========================================================

    df = prepare_timeseries(
        raw_df
    )

    # ========================================================
    # CHECK DATA SIZE
    # ========================================================

    minimum_required = (
        LOOKBACK
        + HORIZON
        + 10
    )

    if len(df) < minimum_required:

        raise ValueError(
            "\nData terlalu sedikit untuk training LSTM.\n"
            f"Jumlah timestep: {len(df)}\n"
            f"Minimal: {minimum_required}\n"
        )

    # ========================================================
    # CHRONOLOGICAL SPLIT
    # ========================================================

    print("\n[3] Chronological split...")

    n = len(df)

    train_end = int(
        n * TRAIN_RATIO
    )

    val_end = int(
        n * (
            TRAIN_RATIO
            + VAL_RATIO
        )
    )

    train_df = df.iloc[
        :train_end
    ].copy()

    val_df = df.iloc[
        train_end:val_end
    ].copy()

    test_df = df.iloc[
        val_end:
    ].copy()

    print(
        "Train:",
        len(train_df),
        "timesteps",
    )

    print(
        "Validation:",
        len(val_df),
        "timesteps",
    )

    print(
        "Test:",
        len(test_df),
        "timesteps",
    )

    # ========================================================
    # PLOT SPLIT
    # ========================================================

    plot_train_val_test_split(
        df,
        train_end,
        val_end,
    )

    # ========================================================
    # SCALER
    # ========================================================

    print("\n[4] Fitting scaler...")

    scaler = MinMaxScaler()

    scaler.fit(
        train_df[
            FEATURE_COLUMNS
        ]
    )

    train_values = scaler.transform(
        train_df[
            FEATURE_COLUMNS
        ]
    )

    val_values = scaler.transform(
        val_df[
            FEATURE_COLUMNS
        ]
    )

    test_values = scaler.transform(
        test_df[
            FEATURE_COLUMNS
        ]
    )

    # ========================================================
    # CREATE SEQUENCES
    # ========================================================

    print(
        "\n[5] Creating LSTM sequences..."
    )

    X_train, y_train = create_sequences(
        train_values,
        LOOKBACK,
        HORIZON,
    )

    X_val, y_val = create_sequences(
        val_values,
        LOOKBACK,
        HORIZON,
    )

    X_test, y_test = create_sequences(
        test_values,
        LOOKBACK,
        HORIZON,
    )

    print(
        "X_train:",
        X_train.shape,
    )

    print(
        "y_train:",
        y_train.shape,
    )

    print(
        "X_val:",
        X_val.shape,
    )

    print(
        "y_val:",
        y_val.shape,
    )

    print(
        "X_test:",
        X_test.shape,
    )

    print(
        "y_test:",
        y_test.shape,
    )

    if len(X_train) == 0:

        raise ValueError(
            "Sequence TRAIN kosong."
        )

    if len(X_val) == 0:

        raise ValueError(
            "Sequence VALIDATION kosong."
        )

    if len(X_test) == 0:

        raise ValueError(
            "Sequence TEST kosong."
        )

    # ========================================================
    # DATASET
    # ========================================================

    train_dataset = TrafficDataset(
        X_train,
        y_train,
    )

    val_dataset = TrafficDataset(
        X_val,
        y_val,
    )

    test_dataset = TrafficDataset(
        X_test,
        y_test,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    # ========================================================
    # MODEL
    # ========================================================

    input_size = len(
        FEATURE_COLUMNS
    )

    model = TrafficLSTM(
        input_size=input_size,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        horizon=HORIZON,
        output_size=input_size,
        dropout=DROPOUT,
    )

    model = model.to(device)

    print("\n[6] Model:")

    print(model)

    # ========================================================
    # LOSS / OPTIMIZER
    # ========================================================

    criterion = nn.MSELoss()

    optimizer = Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )

    # ========================================================
    # TRAINING
    # ========================================================

    print("\n[7] Training...")
    print("=" * 70)

    best_val_loss = float(
        "inf"
    )

    patience_counter = 0

    history = {
        "train_loss": [],
        "val_loss": [],
    }

    for epoch in range(
        1,
        EPOCHS + 1,
    ):

        # ====================================================
        # TRAIN
        # ====================================================

        model.train()

        train_losses = []

        for X_batch, y_batch in train_loader:

            X_batch = X_batch.to(
                device
            )

            y_batch = y_batch.to(
                device
            )

            optimizer.zero_grad()

            prediction = model(
                X_batch
            )

            loss = criterion(
                prediction,
                y_batch,
            )

            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=1.0,
            )

            optimizer.step()

            train_losses.append(
                loss.item()
            )

        train_loss = float(
            np.mean(train_losses)
        )

        # ====================================================
        # VALIDATION
        # ====================================================

        model.eval()

        val_losses = []

        with torch.no_grad():

            for X_batch, y_batch in val_loader:

                X_batch = X_batch.to(
                    device
                )

                y_batch = y_batch.to(
                    device
                )

                prediction = model(
                    X_batch
                )

                loss = criterion(
                    prediction,
                    y_batch,
                )

                val_losses.append(
                    loss.item()
                )

        val_loss = float(
            np.mean(val_losses)
        )

        history[
            "train_loss"
        ].append(train_loss)

        history[
            "val_loss"
        ].append(val_loss)

        print(
            f"Epoch {epoch:03d}/{EPOCHS} | "
            f"Train Loss: {train_loss:.6f} | "
            f"Val Loss: {val_loss:.6f}"
        )

        # ====================================================
        # SAVE BEST MODEL
        # ====================================================

        if val_loss < best_val_loss:

            best_val_loss = val_loss

            patience_counter = 0

            torch.save(
                {
                    "model_state_dict":
                        model.state_dict(),

                    "input_size":
                        input_size,

                    "hidden_size":
                        HIDDEN_SIZE,

                    "num_layers":
                        NUM_LAYERS,

                    "horizon":
                        HORIZON,

                    "output_size":
                        input_size,

                    "dropout":
                        DROPOUT,
                },
                MODEL_FILE,
            )

        else:

            patience_counter += 1

        # ====================================================
        # EARLY STOPPING
        # ====================================================

        if (
            patience_counter
            >= PATIENCE
        ):

            print(
                "\nEarly stopping."
            )

            break

    print("=" * 70)

    # ========================================================
    # SAVE TRAINING HISTORY
    # ========================================================

    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            history,
            file,
            indent=4,
        )

    # ========================================================
    # PLOT LOSS
    # ========================================================

    print(
        "\n[8] Generating training plots..."
    )

    plot_training_validation_loss(
        history
    )

    # ========================================================
    # LOAD BEST MODEL
    # ========================================================

    print(
        "\n[9] Loading best model..."
    )

    checkpoint = torch.load(
        MODEL_FILE,
        map_location=device,
    )

    model.load_state_dict(
        checkpoint[
            "model_state_dict"
        ]
    )

    model.eval()

    # ========================================================
    # TEST
    # ========================================================

    print(
        "\n[10] Testing..."
    )

    predictions = []

    actuals = []

    with torch.no_grad():

        for X_batch, y_batch in test_loader:

            X_batch = X_batch.to(
                device
            )

            prediction = model(
                X_batch
            )

            predictions.append(
                prediction
                .cpu()
                .numpy()
            )

            actuals.append(
                y_batch.numpy()
            )

    predictions = np.concatenate(
        predictions,
        axis=0,
    )

    actuals = np.concatenate(
        actuals,
        axis=0,
    )

    # ========================================================
    # INVERSE TRANSFORM
    # ========================================================

    predictions_flat = (
        predictions.reshape(
            -1,
            input_size,
        )
    )

    actuals_flat = (
        actuals.reshape(
            -1,
            input_size,
        )
    )

    predictions_original = (
        scaler.inverse_transform(
            predictions_flat
        )
    )

    actuals_original = (
        scaler.inverse_transform(
            actuals_flat
        )
    )

    predictions_original = (
        predictions_original.reshape(
            predictions.shape
        )
    )

    actuals_original = (
        actuals_original.reshape(
            actuals.shape
        )
    )

    # Jangan sampai prediksi negatif
    predictions_original = np.maximum(
        predictions_original,
        0,
    )

    # ========================================================
    # METRICS
    # ========================================================

    mae = mean_absolute_error(
        actuals_original.reshape(
            -1,
            input_size,
        ),
        predictions_original.reshape(
            -1,
            input_size,
        ),
    )

    mse = mean_squared_error(
        actuals_original.reshape(
            -1,
            input_size,
        ),
        predictions_original.reshape(
            -1,
            input_size,
        ),
    )

    rmse = np.sqrt(mse)

    print(
        "\nTest MAE:",
        f"{mae:.4f}",
    )

    print(
        "Test MSE:",
        f"{mse:.4f}",
    )

    print(
        "Test RMSE:",
        f"{rmse:.4f}",
    )

    # ========================================================
    # METRICS PER FEATURE
    # ========================================================

    print(
        "\nMetrics per feature:"
    )

    feature_metrics = {}

    for i, feature in enumerate(
        FEATURE_COLUMNS
    ):

        feature_actual = (
            actuals_original[
                :, :, i
            ].reshape(-1)
        )

        feature_predicted = (
            predictions_original[
                :, :, i
            ].reshape(-1)
        )

        feature_mae = (
            mean_absolute_error(
                feature_actual,
                feature_predicted,
            )
        )

        feature_rmse = np.sqrt(
            mean_squared_error(
                feature_actual,
                feature_predicted,
            )
        )

        feature_metrics[
            feature
        ] = {
            "mae":
                float(
                    feature_mae
                ),
            "rmse":
                float(
                    feature_rmse
                ),
        }

        print(
            f"{feature:20s} "
            f"MAE={feature_mae:.4f} "
            f"RMSE={feature_rmse:.4f}"
        )

    # ========================================================
    # TEST TIMESTAMPS
    # ========================================================

    # Untuk setiap sequence, target pertama berada
    # setelah LOOKBACK timestep.

    test_timestamps = test_df[
        "timestamp"
    ].iloc[
        LOOKBACK:
        LOOKBACK + len(actuals_original)
    ].reset_index(
        drop=True
    )

    # ========================================================
    # SAVE PREDICTIONS CSV
    # ========================================================

    print(
        "\n[11] Saving predictions..."
    )

    save_predictions(
        test_timestamps,
        actuals_original,
        predictions_original,
    )

    # ========================================================
    # PLOT ACTUAL VS PREDICTED
    # ========================================================

    plot_actual_vs_predicted(
        test_timestamps,
        actuals_original,
        predictions_original,
    )

    # ========================================================
    # PLOT FEATURE PREDICTION
    # ========================================================

    plot_feature_prediction(
        test_timestamps,
        actuals_original,
        predictions_original,
    )

    # ========================================================
    # SAVE SCALER
    # ========================================================

    joblib.dump(
        scaler,
        SCALER_FILE,
    )

    # ========================================================
    # METADATA
    # ========================================================

    metadata = {

        "dataset":
            str(DATA_FILE),

        "features":
            FEATURE_COLUMNS,

        "input_size":
            input_size,

        "lookback":
            LOOKBACK,

        "lookback_seconds":
            LOOKBACK
            * INTERVAL_SECONDS,

        "horizon":
            HORIZON,

        "horizon_seconds":
            HORIZON
            * INTERVAL_SECONDS,

        "interval_seconds":
            INTERVAL_SECONDS,

        "train_ratio":
            TRAIN_RATIO,

        "validation_ratio":
            VAL_RATIO,

        "test_ratio":
            TEST_RATIO,

        "batch_size":
            BATCH_SIZE,

        "epochs":
            EPOCHS,

        "learning_rate":
            LEARNING_RATE,

        "patience":
            PATIENCE,

        "hidden_size":
            HIDDEN_SIZE,

        "num_layers":
            NUM_LAYERS,

        "dropout":
            DROPOUT,

        "random_seed":
            RANDOM_SEED,

        "best_val_loss":
            float(
                best_val_loss
            ),

        "test_mae":
            float(mae),

        "test_mse":
            float(mse),

        "test_rmse":
            float(rmse),

        "feature_metrics":
            feature_metrics,

        "num_raw_rows":
            int(len(raw_df)),

        "num_timesteps":
            int(len(df)),

        "num_train_sequences":
            int(len(X_train)),

        "num_validation_sequences":
            int(len(X_val)),

        "num_test_sequences":
            int(len(X_test)),
    }

    with open(
        METADATA_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4,
        )

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    print("\n" + "=" * 70)

    print(
        "TRAINING SELESAI"
    )

    print("=" * 70)

    print(
        "\nModel:"
    )

    print(
        MODEL_FILE
    )

    print(
        "\nScaler:"
    )

    print(
        SCALER_FILE
    )

    print(
        "\nMetadata:"
    )

    print(
        METADATA_FILE
    )

    print(
        "\nTraining history:"
    )

    print(
        HISTORY_FILE
    )

    print(
        "\nPredictions:"
    )

    print(
        PREDICTIONS_FILE
    )

    print(
        "\nPlots:"
    )

    print(
        PLOT_DIR
    )

    print("\nFiles plot:")

    print(
        "1.",
        PLOT_DIR
        / "training_validation_loss.png",
    )

    print(
        "2.",
        PLOT_DIR
        / "actual_vs_predicted.png",
    )

    print(
        "3.",
        PLOT_DIR
        / "train_val_test_split.png",
    )

    print(
        "4.",
        PLOT_DIR
        / "feature_prediction.png",
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()