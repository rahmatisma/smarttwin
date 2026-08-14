"""
06_train_brisbane.py

Train LSTM traffic forecasting model menggunakan dataset Brisbane.

Input:
    outputs/brisbane/processed/brisbane_processed.csv
    outputs/brisbane/processed/feature_config.json

Output:
    models/brisbane_lstm_model.pt
    models/brisbane_scaler_X.pkl
    models/brisbane_scaler_y.pkl
    models/brisbane_model_config.json

Konfigurasi eksperimen:
    Sequence length : 6 timestep
    Forecast horizon: 1 timestep

CATATAN:
    Timestamp dibaca langsung dari kolom timestamp.
    Kode tidak mengasumsikan bahwa 1 timestep = 15 menit.
"""

from pathlib import Path
import json
import time

import joblib
import numpy as np
import pandas as pd

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from sklearn.preprocessing import StandardScaler


# ============================================================
# PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_FILE = (
    BASE_DIR
    / "outputs"
    / "brisbane"
    / "processed"
    / "brisbane_processed.csv"
)

FEATURE_CONFIG_FILE = (
    BASE_DIR
    / "outputs"
    / "brisbane"
    / "processed"
    / "feature_config.json"
)

MODEL_DIR = (
    BASE_DIR
    / "models"
)

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)

MODEL_FILE = (
    MODEL_DIR
    / "brisbane_lstm_model.pt"
)

SCALER_X_FILE = (
    MODEL_DIR
    / "brisbane_scaler_X.pkl"
)

SCALER_Y_FILE = (
    MODEL_DIR
    / "brisbane_scaler_y.pkl"
)

CONFIG_FILE = (
    MODEL_DIR
    / "brisbane_model_config.json"
)


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================

SEQUENCE_LENGTH = 6

FORECAST_HORIZON = 1

TRAIN_RATIO = 0.70

VAL_RATIO = 0.15

TEST_RATIO = 0.15

HIDDEN_SIZE = 64

NUM_LAYERS = 2

DROPOUT = 0.2

BATCH_SIZE = 32

LEARNING_RATE = 0.001

MAX_EPOCHS = 100

PATIENCE = 12


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# MODEL
# ============================================================

class TrafficLSTM(nn.Module):

    def __init__(
        self,
        input_size,
        hidden_size,
        num_layers,
        output_size,
        dropout
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
            )
        )

        self.dropout = nn.Dropout(
            dropout
        )

        self.fc = nn.Linear(
            hidden_size,
            output_size
        )

    def forward(self, x):

        output, _ = self.lstm(x)

        last_output = (
            output[:, -1, :]
        )

        last_output = (
            self.dropout(
                last_output
            )
        )

        prediction = self.fc(
            last_output
        )

        return prediction


# ============================================================
# LOAD FEATURE CONFIG
# ============================================================

def load_feature_config():

    with open(
        FEATURE_CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(file)

    input_features = config[
        "input_features"
    ]

    target_features = config[
        "target_features"
    ]

    return (
        input_features,
        target_features
    )


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    print(
        f"[INFO] Loading:\n"
        f"       {DATA_FILE}"
    )

    if not DATA_FILE.exists():

        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n"
            f"{DATA_FILE}"
        )

    df = pd.read_csv(
        DATA_FILE
    )

    print(
        f"[INFO] Rows    : {len(df):,}"
    )

    print(
        f"[INFO] Columns : {len(df.columns)}"
    )

    if "timestamp" not in df.columns:

        raise ValueError(
            "Kolom 'timestamp' tidak ditemukan."
        )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    invalid = (
        df["timestamp"]
        .isna()
        .sum()
    )

    print(
        f"[INFO] Invalid timestamps: {invalid}"
    )

    if invalid > 0:

        df = df.dropna(
            subset=["timestamp"]
        )

    df = df.sort_values(
        "timestamp"
    ).reset_index(
        drop=True
    )

    print()
    print(
        "[INFO] Time range:"
    )

    print(
        f"       {df['timestamp'].iloc[0]}"
    )

    print(
        f"       {df['timestamp'].iloc[-1]}"
    )

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    numeric_columns = (
        df.select_dtypes(
            include=np.number
        )
        .columns
        .tolist()
    )

    df[numeric_columns] = (
        df[numeric_columns]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
    )

    df[numeric_columns] = (
        df[numeric_columns]
        .fillna(0)
    )

    return df


# ============================================================
# CHECK TIMESTAMP INTERVAL
# ============================================================

def inspect_timestamp(df):

    print()
    print("=" * 70)
    print("TIMESTAMP ANALYSIS")
    print("=" * 70)

    unique_timestamps = (
        df["timestamp"]
        .drop_duplicates()
        .sort_values()
    )

    print(
        f"[INFO] Unique timestamps: "
        f"{len(unique_timestamps):,}"
    )

    if len(unique_timestamps) < 2:

        raise ValueError(
            "Dataset hanya memiliki "
            "satu timestamp."
        )

    differences = (
        unique_timestamps
        .diff()
        .dropna()
    )

    print(
        "[INFO] Timestamp differences:"
    )

    print(
        differences
        .value_counts()
        .head(10)
    )

    most_common = (
        differences
        .mode()
    )

    if len(most_common) > 0:

        interval = (
            most_common.iloc[0]
        )

        print()
        print(
            f"[INFO] Most common interval:"
        )

        print(
            f"       {interval}"
        )

        print(
            f"[INFO] Approx minutes:"
            f" {interval.total_seconds() / 60:.2f}"
        )

    return unique_timestamps


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    X,
    y,
    sequence_length,
    forecast_horizon
):

    X_sequences = []

    y_sequences = []

    max_index = (
        len(X)
        - sequence_length
        - forecast_horizon
        + 1
    )

    for i in range(
        max_index
    ):

        X_sequences.append(
            X[
                i:
                i + sequence_length
            ]
        )

        target_index = (
            i
            + sequence_length
            + forecast_horizon
            - 1
        )

        y_sequences.append(
            y[target_index]
        )

    return (
        np.asarray(
            X_sequences,
            dtype=np.float32
        ),
        np.asarray(
            y_sequences,
            dtype=np.float32
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    start_time = time.time()

    print("=" * 70)
    print("BRISBANE LSTM TRAFFIC FORECASTING TRAINING")
    print("=" * 70)

    print(
        f"[INFO] Device: {DEVICE}"
    )

    print()
    print("=" * 70)
    print("EXPERIMENT CONFIGURATION")
    print("=" * 70)

    print(
        f"[INFO] Sequence length : "
        f"{SEQUENCE_LENGTH} timestep"
    )

    print(
        f"[INFO] Forecast horizon: "
        f"{FORECAST_HORIZON} timestep"
    )

    print(
        f"[INFO] Hidden size     : "
        f"{HIDDEN_SIZE}"
    )

    print(
        f"[INFO] LSTM layers     : "
        f"{NUM_LAYERS}"
    )

    print(
        f"[INFO] Max epochs      : "
        f"{MAX_EPOCHS}"
    )

    # --------------------------------------------------------
    # Feature config
    # --------------------------------------------------------

    (
        input_features,
        target_features
    ) = load_feature_config()

    print()
    print("=" * 70)
    print("FEATURE CONFIGURATION")
    print("=" * 70)

    print(
        f"[INFO] Input features : "
        f"{len(input_features)}"
    )

    for index, feature in enumerate(
        input_features,
        start=1
    ):

        print(
            f"       {index:02d}. {feature}"
        )

    print()
    print(
        f"[INFO] Targets : "
        f"{len(target_features)}"
    )

    for index, target in enumerate(
        target_features,
        start=1
    ):

        print(
            f"       {index}. {target}"
        )

    # --------------------------------------------------------
    # Data
    # --------------------------------------------------------

    df = load_data()

    inspect_timestamp(
        df
    )

    # --------------------------------------------------------
    # Check features
    # --------------------------------------------------------

    required_columns = (
        input_features
        + target_features
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Kolom berikut tidak ditemukan:\n"
            + "\n".join(
                f"- {column}"
                for column in missing_columns
            )
        )

    # --------------------------------------------------------
    # Remove duplicated timestamps
    #
    # This is important because the processed Brisbane
    # dataset should represent one traffic state per timestep.
    # --------------------------------------------------------

    duplicated = (
        df["timestamp"]
        .duplicated()
        .sum()
    )

    print()
    print(
        f"[INFO] Duplicate timestamps: "
        f"{duplicated:,}"
    )

    if duplicated > 0:

        print(
            "[INFO] Menggunakan aggregation "
            "untuk timestamp yang sama..."
        )

        aggregation = {}

        for column in input_features:

            aggregation[column] = "mean"

        for column in target_features:

            aggregation[column] = "mean"

        aggregation[
            "timestamp"
        ] = "first"

        df = (
            df.groupby(
                "timestamp",
                as_index=False
            )
            .agg(aggregation)
            .sort_values(
                "timestamp"
            )
            .reset_index(
                drop=True
            )
        )

    print()
    print(
        f"[INFO] Rows after timestamp "
        f"aggregation: {len(df):,}"
    )

    # --------------------------------------------------------
    # Minimum data check
    # --------------------------------------------------------

    minimum_required = (
        SEQUENCE_LENGTH
        + FORECAST_HORIZON
        + 10
    )

    if len(df) < minimum_required:

        raise ValueError(
            "\nDATA TIDAK CUKUP.\n\n"
            f"Rows tersedia     : {len(df)}\n"
            f"Minimum diperlukan: {minimum_required}\n"
            f"Sequence length   : {SEQUENCE_LENGTH}\n"
            f"Forecast horizon  : {FORECAST_HORIZON}\n\n"
            "Dataset Brisbane yang kamu gunakan "
            "hanya memiliki sedikit timestamp. "
            "Jumlah baris besar tidak berarti "
            "jumlah timestep besar."
        )

    # --------------------------------------------------------
    # Prepare arrays
    # --------------------------------------------------------

    X_raw = (
        df[input_features]
        .values
    )

    y_raw = (
        df[target_features]
        .values
    )

    # --------------------------------------------------------
    # Chronological split
    #
    # IMPORTANT:
    # Split raw time series BEFORE scaling.
    # --------------------------------------------------------

    total_rows = len(df)

    train_end = int(
        total_rows
        * TRAIN_RATIO
    )

    val_end = int(
        total_rows
        * (
            TRAIN_RATIO
            + VAL_RATIO
        )
    )

    X_train_raw = (
        X_raw[:train_end]
    )

    X_val_raw = (
        X_raw[train_end:val_end]
    )

    X_test_raw = (
        X_raw[val_end:]
    )

    y_train_raw = (
        y_raw[:train_end]
    )

    y_val_raw = (
        y_raw[train_end:val_end]
    )

    y_test_raw = (
        y_raw[val_end:]
    )

    print()
    print("=" * 70)
    print("CHRONOLOGICAL SPLIT")
    print("=" * 70)

    print(
        f"[INFO] Total rows : "
        f"{total_rows:,}"
    )

    print(
        f"[INFO] Train      : "
        f"{len(X_train_raw):,}"
    )

    print(
        f"[INFO] Validation : "
        f"{len(X_val_raw):,}"
    )

    print(
        f"[INFO] Test       : "
        f"{len(X_test_raw):,}"
    )

    # --------------------------------------------------------
    # Scaling
    # --------------------------------------------------------

    scaler_X = StandardScaler()

    scaler_y = StandardScaler()

    X_train_scaled = (
        scaler_X.fit_transform(
            X_train_raw
        )
    )

    X_val_scaled = (
        scaler_X.transform(
            X_val_raw
        )
    )

    X_test_scaled = (
        scaler_X.transform(
            X_test_raw
        )
    )

    y_train_scaled = (
        scaler_y.fit_transform(
            y_train_raw
        )
    )

    y_val_scaled = (
        scaler_y.transform(
            y_val_raw
        )
    )

    y_test_scaled = (
        scaler_y.transform(
            y_test_raw
        )
    )

    # --------------------------------------------------------
    # Sequences
    # --------------------------------------------------------

    (
        X_train,
        y_train
    ) = create_sequences(
        X_train_scaled,
        y_train_scaled,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    (
        X_val,
        y_val
    ) = create_sequences(
        X_val_scaled,
        y_val_scaled,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    (
        X_test,
        y_test
    ) = create_sequences(
        X_test_scaled,
        y_test_scaled,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    print()
    print("=" * 70)
    print("SEQUENCE CREATION")
    print("=" * 70)

    print(
        f"[INFO] X train shape: "
        f"{X_train.shape}"
    )

    print(
        f"[INFO] X val shape  : "
        f"{X_val.shape}"
    )

    print(
        f"[INFO] X test shape : "
        f"{X_test.shape}"
    )

    if len(X_train) == 0:

        raise ValueError(
            "Training sequence = 0. "
            "Data training tidak cukup "
            "untuk sequence length yang dipilih."
        )

    if len(X_val) == 0:

        raise ValueError(
            "Validation sequence = 0."
        )

    if len(X_test) == 0:

        raise ValueError(
            "Test sequence = 0."
        )

    # --------------------------------------------------------
    # DataLoader
    # --------------------------------------------------------

    train_dataset = TensorDataset(
        torch.tensor(
            X_train,
            dtype=torch.float32
        ),
        torch.tensor(
            y_train,
            dtype=torch.float32
        )
    )

    val_dataset = TensorDataset(
        torch.tensor(
            X_val,
            dtype=torch.float32
        ),
        torch.tensor(
            y_val,
            dtype=torch.float32
        )
    )

    test_dataset = TensorDataset(
        torch.tensor(
            X_test,
            dtype=torch.float32
        ),
        torch.tensor(
            y_test,
            dtype=torch.float32
        )
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("MODEL")
    print("=" * 70)

    model = TrafficLSTM(
        input_size=len(
            input_features
        ),
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        output_size=len(
            target_features
        ),
        dropout=DROPOUT
    )

    model.to(
        DEVICE
    )

    parameter_count = sum(
        parameter.numel()
        for parameter in model.parameters()
    )

    print(
        f"[INFO] Input size : "
        f"{len(input_features)}"
    )

    print(
        f"[INFO] Hidden size: "
        f"{HIDDEN_SIZE}"
    )

    print(
        f"[INFO] LSTM layers: "
        f"{NUM_LAYERS}"
    )

    print(
        f"[INFO] Output size: "
        f"{len(target_features)}"
    )

    print(
        f"[INFO] Parameters : "
        f"{parameter_count:,}"
    )

    # --------------------------------------------------------
    # Loss / optimizer
    # --------------------------------------------------------

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=4
    )

    # --------------------------------------------------------
    # Training
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TRAINING")
    print("=" * 70)

    best_val_loss = float(
        "inf"
    )

    best_state = None

    patience_counter = 0

    history = []

    for epoch in range(
        1,
        MAX_EPOCHS + 1
    ):

        epoch_start = time.time()

        # ----------------------------------------------------
        # Train
        # ----------------------------------------------------

        model.train()

        train_losses = []

        for X_batch, y_batch in train_loader:

            X_batch = X_batch.to(
                DEVICE
            )

            y_batch = y_batch.to(
                DEVICE
            )

            optimizer.zero_grad()

            prediction = model(
                X_batch
            )

            loss = criterion(
                prediction,
                y_batch
            )

            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=1.0
            )

            optimizer.step()

            train_losses.append(
                loss.item()
            )

        train_loss = float(
            np.mean(
                train_losses
            )
        )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        model.eval()

        val_losses = []

        with torch.no_grad():

            for X_batch, y_batch in val_loader:

                X_batch = X_batch.to(
                    DEVICE
                )

                y_batch = y_batch.to(
                    DEVICE
                )

                prediction = model(
                    X_batch
                )

                loss = criterion(
                    prediction,
                    y_batch
                )

                val_losses.append(
                    loss.item()
                )

        val_loss = float(
            np.mean(
                val_losses
            )
        )

        scheduler.step(
            val_loss
        )

        current_lr = (
            optimizer.param_groups[0]["lr"]
        )

        epoch_time = (
            time.time()
            - epoch_start
        )

        is_best = (
            val_loss
            <
            best_val_loss
        )

        if is_best:

            best_val_loss = (
                val_loss
            )

            best_state = {
                key: value.detach().cpu().clone()
                for key, value
                in model.state_dict().items()
            }

            patience_counter = 0

        else:

            patience_counter += 1

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "learning_rate": current_lr
        })

        marker = (
            "BEST"
            if is_best
            else ""
        )

        print(
            f"Epoch {epoch:03d}/{MAX_EPOCHS} | "
            f"Train: {train_loss:.6f} | "
            f"Val: {val_loss:.6f} | "
            f"LR: {current_lr:.6f} | "
            f"{epoch_time:.1f}s "
            f"{marker}"
        )

        if patience_counter >= PATIENCE:

            print()
            print(
                "[INFO] Early stopping."
            )

            break

    # --------------------------------------------------------
    # Restore best model
    # --------------------------------------------------------

    if best_state is not None:

        model.load_state_dict(
            best_state
        )

    # --------------------------------------------------------
    # Save model
    # --------------------------------------------------------

    torch.save(
        model.state_dict(),
        MODEL_FILE
    )

    joblib.dump(
        scaler_X,
        SCALER_X_FILE
    )

    joblib.dump(
        scaler_y,
        SCALER_Y_FILE
    )

    # --------------------------------------------------------
    # Save config
    # --------------------------------------------------------

    config = {

        "model": "TrafficLSTM",

        "framework": "PyTorch",

        "device": str(
            DEVICE
        ),

        "input_features":
            input_features,

        "target_features":
            target_features,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "train_ratio":
            TRAIN_RATIO,

        "val_ratio":
            VAL_RATIO,

        "test_ratio":
            TEST_RATIO,

        "hidden_size":
            HIDDEN_SIZE,

        "num_layers":
            NUM_LAYERS,

        "dropout":
            DROPOUT,

        "batch_size":
            BATCH_SIZE,

        "learning_rate":
            LEARNING_RATE,

        "max_epochs":
            MAX_EPOCHS,

        "patience":
            PATIENCE,

        "best_validation_loss":
            float(
                best_val_loss
            ),

        "train_samples":
            int(len(X_train)),

        "validation_samples":
            int(len(X_val)),

        "test_samples":
            int(len(X_test)),

        "total_rows":
            int(total_rows),

        "timestamp_start":
            str(
                df["timestamp"].iloc[0]
            ),

        "timestamp_end":
            str(
                df["timestamp"].iloc[-1]
            )
    }

    with open(
        CONFIG_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            config,
            file,
            indent=4
        )

    # --------------------------------------------------------
    # Save training history
    # --------------------------------------------------------

    history_file = (
        BASE_DIR
        / "outputs"
        / "brisbane"
        / "metrics"
        / "training_history.csv"
    )

    history_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    pd.DataFrame(
        history
    ).to_csv(
        history_file,
        index=False
    )

    # --------------------------------------------------------
    # Final output
    # --------------------------------------------------------

    total_time = (
        time.time()
        - start_time
    )

    print()
    print("=" * 70)
    print("TRAINING COMPLETED")
    print("=" * 70)

    print(
        f"[OK] Model saved:"
    )

    print(
        f"     {MODEL_FILE}"
    )

    print(
        f"[OK] X scaler saved:"
    )

    print(
        f"     {SCALER_X_FILE}"
    )

    print(
        f"[OK] Y scaler saved:"
    )

    print(
        f"     {SCALER_Y_FILE}"
    )

    print(
        f"[OK] Config saved:"
    )

    print(
        f"     {CONFIG_FILE}"
    )

    print(
        f"[OK] Training history saved:"
    )

    print(
        f"     {history_file}"
    )

    print()
    print(
        f"[INFO] Best validation loss: "
        f"{best_val_loss:.6f}"
    )

    print(
        f"[INFO] Training time: "
        f"{total_time / 60:.2f} minutes"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()