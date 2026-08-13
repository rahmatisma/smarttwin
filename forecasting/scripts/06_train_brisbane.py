"""
06_train_brisbane.py

Train LSTM on processed Brisbane traffic time series.
"""

from pathlib import Path
import json
import time

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

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

CONFIG_FILE = (
    BASE_DIR
    / "outputs"
    / "brisbane"
    / "processed"
    / "feature_config.json"
)

MODEL_DIR = (
    BASE_DIR
    / "models"
    / "brisbane"
)

OUTPUT_METRICS_DIR = (
    BASE_DIR
    / "outputs"
    / "brisbane"
    / "metrics"
)

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_METRICS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

MODEL_FILE = (
    MODEL_DIR
    / "lstm_model.pt"
)

SCALER_X_FILE = (
    MODEL_DIR
    / "scaler_X.pkl"
)

SCALER_Y_FILE = (
    MODEL_DIR
    / "scaler_y.pkl"
)

MODEL_CONFIG_FILE = (
    MODEL_DIR
    / "model_config.json"
)

HISTORY_FILE = (
    OUTPUT_METRICS_DIR
    / "training_history.csv"
)

SUMMARY_FILE = (
    OUTPUT_METRICS_DIR
    / "training_summary.json"
)


# ============================================================
# TRAINING CONFIG
# ============================================================

HIDDEN_SIZE = 128

NUM_LAYERS = 2

DROPOUT = 0.20

BATCH_SIZE = 64

EPOCHS = 150

LEARNING_RATE = 0.001

PATIENCE = 15


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
        horizon_count,
        dropout
    ):

        super().__init__()

        self.horizon_count = (
            horizon_count
        )

        self.output_size = (
            output_size
        )

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=(
                dropout
                if num_layers > 1
                else 0
            )
        )

        self.dropout = nn.Dropout(
            dropout
        )

        self.fc = nn.Linear(
            hidden_size,
            output_size
            * horizon_count
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

        return prediction.view(
            -1,
            self.horizon_count,
            self.output_size
        )


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    X,
    y,
    sequence_length,
    horizon
):

    X_sequences = []

    y_sequences = []

    max_index = (
        len(X)
        - sequence_length
        - horizon
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

        y_sequences.append(
            y[
                i
                + sequence_length
                + horizon
                - 1
            ]
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

    # --------------------------------------------------------
    # DEVICE
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"[INFO] Device: {device}"
    )

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(file)

    input_features = (
        config["input_features"]
    )

    target_features = (
        config["target_features"]
    )

    sequence_length = (
        config["sequence_length"]
    )

    horizon = (
        config["forecast_horizons"][0]
    )

    train_ratio = (
        config["train_ratio"]
    )

    val_ratio = (
        config["val_ratio"]
    )

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["timestamp"]
    )

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    print(
        f"[INFO] Rows: {len(df):,}"
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    missing_features = [
        feature
        for feature in (
            input_features
            + target_features
        )
        if feature not in df.columns
    ]

    if missing_features:

        raise ValueError(
            "Missing features:\n"
            + "\n".join(
                missing_features
            )
        )

    # --------------------------------------------------------
    # RAW ARRAYS
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
    # CHRONOLOGICAL SPLIT
    # --------------------------------------------------------

    total_rows = len(df)

    train_row_end = int(
        total_rows
        * train_ratio
    )

    val_row_end = int(
        total_rows
        * (
            train_ratio
            + val_ratio
        )
    )

    X_train_raw = (
        X_raw[
            :train_row_end
        ]
    )

    X_val_raw = (
        X_raw[
            train_row_end:
            val_row_end
        ]
    )

    X_test_raw = (
        X_raw[
            val_row_end:
        ]
    )

    y_train_raw = (
        y_raw[
            :train_row_end
        ]
    )

    y_val_raw = (
        y_raw[
            train_row_end:
            val_row_end
        ]
    )

    y_test_raw = (
        y_raw[
            val_row_end:
        ]
    )

    # --------------------------------------------------------
    # SCALERS
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
    # SEQUENCES
    # --------------------------------------------------------

    X_train, y_train = (
        create_sequences(
            X_train_scaled,
            y_train_scaled,
            sequence_length,
            horizon
        )
    )

    X_val, y_val = (
        create_sequences(
            X_val_scaled,
            y_val_scaled,
            sequence_length,
            horizon
        )
    )

    X_test, y_test = (
        create_sequences(
            X_test_scaled,
            y_test_scaled,
            sequence_length,
            horizon
        )
    )

    print()
    print("=" * 70)
    print("SEQUENCE CONFIGURATION")
    print("=" * 70)

    print(
        f"[INFO] Sequence length : "
        f"{sequence_length}"
    )

    print(
        f"[INFO] Forecast horizon: "
        f"{horizon} timestep"
    )

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

    # --------------------------------------------------------
    # DATA LOADERS
    # --------------------------------------------------------

    train_dataset = torch.utils.data.TensorDataset(
        torch.tensor(
            X_train,
            dtype=torch.float32
        ),
        torch.tensor(
            y_train,
            dtype=torch.float32
        )
    )

    val_dataset = torch.utils.data.TensorDataset(
        torch.tensor(
            X_val,
            dtype=torch.float32
        ),
        torch.tensor(
            y_val,
            dtype=torch.float32
        )
    )

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True
    )

    val_loader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False
    )

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    model = TrafficLSTM(
        input_size=len(
            input_features
        ),
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        output_size=len(
            target_features
        ),
        horizon_count=1,
        dropout=DROPOUT
    )

    model.to(device)

    print()
    print("=" * 70)
    print("MODEL")
    print("=" * 70)

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
        f"{sum(p.numel() for p in model.parameters()):,}"
    )

    # --------------------------------------------------------
    # OPTIMIZER
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
        patience=5
    )

    # --------------------------------------------------------
    # TRAINING
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TRAINING")
    print("=" * 70)

    best_val_loss = float("inf")

    best_state = None

    patience_counter = 0

    history = []

    for epoch in range(
        1,
        EPOCHS + 1
    ):

        epoch_start = time.time()

        model.train()

        train_losses = []

        for batch_X, batch_y in (
            train_loader
        ):

            batch_X = (
                batch_X.to(device)
            )

            batch_y = (
                batch_y.to(device)
            )

            optimizer.zero_grad()

            prediction = model(
                batch_X
            ).squeeze(1)

            loss = criterion(
                prediction,
                batch_y
            )

            loss.backward()

            optimizer.step()

            train_losses.append(
                loss.item()
            )

        model.eval()

        val_losses = []

        with torch.no_grad():

            for batch_X, batch_y in (
                val_loader
            ):

                batch_X = (
                    batch_X.to(device)
                )

                batch_y = (
                    batch_y.to(device)
                )

                prediction = model(
                    batch_X
                ).squeeze(1)

                loss = criterion(
                    prediction,
                    batch_y
                )

                val_losses.append(
                    loss.item()
                )

        train_loss = float(
            np.mean(
                train_losses
            )
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
            optimizer.param_groups[0][
                "lr"
            ]
        )

        is_best = (
            val_loss
            <
            best_val_loss
        )

        if is_best:

            best_val_loss = val_loss

            best_state = {
                key: value.cpu().clone()
                for key, value
                in model.state_dict().items()
            }

            patience_counter = 0

        else:

            patience_counter += 1

        elapsed = (
            time.time()
            - epoch_start
        )

        print(
            f"Epoch {epoch:03d}/{EPOCHS} | "
            f"Train: {train_loss:.6f} | "
            f"Val: {val_loss:.6f} | "
            f"LR: {current_lr:.6f} | "
            f"{elapsed:.1f}s "
            f"{'BEST' if is_best else ''}"
        )

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "learning_rate": current_lr,
        })

        if (
            patience_counter
            >= PATIENCE
        ):

            print()
            print(
                "[INFO] Early stopping."
            )

            break

    # --------------------------------------------------------
    # RESTORE BEST MODEL
    # --------------------------------------------------------

    if best_state is not None:

        model.load_state_dict(
            best_state
        )

    # --------------------------------------------------------
    # SAVE MODEL
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

    model_config = {

        "input_features": input_features,

        "target_features": target_features,

        "sequence_length": sequence_length,

        "forecast_horizons": [
            horizon
        ],

        "train_ratio": train_ratio,

        "val_ratio": val_ratio,

        "test_ratio": config[
            "test_ratio"
        ],

        "hidden_size": HIDDEN_SIZE,

        "num_layers": NUM_LAYERS,

        "dropout": DROPOUT,

        "device": str(device),

        "model": "TrafficLSTM",

        "framework": "PyTorch",
    }

    with open(
        MODEL_CONFIG_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            model_config,
            file,
            indent=4
        )

    pd.DataFrame(
        history
    ).to_csv(
        HISTORY_FILE,
        index=False
    )

    training_time = (
        time.time()
        - start_time
    )

    summary = {

        "model": "TrafficLSTM",

        "framework": "PyTorch",

        "device": str(device),

        "parameters": int(
            sum(
                p.numel()
                for p in model.parameters()
            )
        ),

        "sequence_length": (
            sequence_length
        ),

        "forecast_horizon": (
            horizon
        ),

        "train_samples": int(
            len(X_train)
        ),

        "validation_samples": int(
            len(X_val)
        ),

        "test_samples": int(
            len(X_test)
        ),

        "best_validation_loss": (
            float(best_val_loss)
        ),

        "training_time_seconds": (
            float(training_time)
        ),
    }

    with open(
        SUMMARY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=4
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
        f"[OK] Best validation loss: "
        f"{best_val_loss:.6f}"
    )

    print(
        f"[OK] Training time: "
        f"{training_time / 60:.2f} minutes"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()