"""
08_predict_brisbane.py

Generate future traffic forecast using
the trained Brisbane Traffic LSTM.

Input:
    outputs/brisbane/processed/brisbane_processed.csv

Model:
    models/brisbane_lstm_model.pt

Outputs:
    outputs/brisbane/predictions/forecast.csv

Targets:
    vehicle_count
    density_proxy
    queue_proxy
"""


from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

import torch
import torch.nn as nn


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

MODEL_DIR = BASE_DIR / "models"

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

OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "brisbane"
    / "predictions"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "forecast.csv"
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
        horizon_count,
        dropout
    ):

        super().__init__()

        self.horizon_count = horizon_count
        self.output_size = output_size

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
            output_size * horizon_count
        )

    def forward(self, x):

        output, _ = self.lstm(x)

        last_output = output[:, -1, :]

        last_output = self.dropout(
            last_output
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
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BRISBANE TRAFFIC FORECAST GENERATION")
    print("=" * 70)

    # --------------------------------------------------------
    # FILE CHECK
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FILE CHECK")
    print("=" * 70)

    required_files = [
        DATA_FILE,
        MODEL_FILE,
        SCALER_X_FILE,
        SCALER_Y_FILE,
        CONFIG_FILE
    ]

    for file in required_files:

        if not file.exists():

            raise FileNotFoundError(
                f"File tidak ditemukan:\n{file}"
            )

        print(
            f"[OK] {file.name}"
        )

    # --------------------------------------------------------
    # LOAD CONFIG
    # --------------------------------------------------------

    with open(
        CONFIG_FILE,
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

    sequence_length = config[
        "sequence_length"
    ]

    horizons = config[
        "forecast_horizons"
    ]

    print()
    print("=" * 70)
    print("MODEL CONFIGURATION")
    print("=" * 70)

    print(
        f"[INFO] Input features : "
        f"{len(input_features)}"
    )

    for i, feature in enumerate(
        input_features,
        start=1
    ):

        print(
            f"       {i:02d}. {feature}"
        )

    print()
    print(
        f"[INFO] Targets        : "
        f"{len(target_features)}"
    )

    for i, target in enumerate(
        target_features,
        start=1
    ):

        print(
            f"       {i}. {target}"
        )

    print()
    print(
        f"[INFO] Sequence length : "
        f"{sequence_length}"
    )

    print(
        f"[INFO] Forecast horizons: "
        f"{horizons}"
    )

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    df = pd.read_csv(
        DATA_FILE
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["timestamp"]
    )

    df = df.sort_values(
        "timestamp"
    ).reset_index(
        drop=True
    )

    print(
        f"[INFO] Rows: {len(df)}"
    )

    print(
        f"[INFO] Latest timestamp:"
    )

    print(
        f"       {df['timestamp'].iloc[-1]}"
    )

    if len(df) < sequence_length:

        raise ValueError(
            f"Data tidak cukup. "
            f"Dibutuhkan minimal "
            f"{sequence_length} baris."
        )

    # --------------------------------------------------------
    # VALIDATE FEATURES
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
            + "\n".join(missing_columns)
        )

    numeric_columns = list(
        dict.fromkeys(
            required_columns
        )
    )

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df[numeric_columns] = (
        df[numeric_columns]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .interpolate(
            method="linear"
        )
        .ffill()
        .bfill()
    )

    if (
        df[numeric_columns]
        .isna()
        .sum()
        .sum()
        > 0
    ):

        raise ValueError(
            "Masih terdapat missing value."
        )

    # --------------------------------------------------------
    # LOAD SCALERS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SCALER LOADING")
    print("=" * 70)

    scaler_X = joblib.load(
        SCALER_X_FILE
    )

    scaler_y = joblib.load(
        SCALER_Y_FILE
    )

    print(
        "[OK] X scaler loaded."
    )

    print(
        "[OK] Y scaler loaded."
    )

    # --------------------------------------------------------
    # PREPARE LATEST SEQUENCE
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PREPARING LATEST SEQUENCE")
    print("=" * 70)

    latest_data = df[
        input_features
    ].tail(
        sequence_length
    )

    print(
        f"[INFO] Sequence shape:"
    )

    print(
        f"       {latest_data.shape}"
    )

    X_scaled = scaler_X.transform(
        latest_data.values
    )

    X_tensor = torch.tensor(
        X_scaled,
        dtype=torch.float32
    ).unsqueeze(0)

    print(
        f"[INFO] Model input shape:"
    )

    print(
        f"       {tuple(X_tensor.shape)}"
    )

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

    X_tensor = X_tensor.to(
        device
    )

    # --------------------------------------------------------
    # LOAD MODEL
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("MODEL LOADING")
    print("=" * 70)

    model = TrafficLSTM(
        input_size=len(
            input_features
        ),
        hidden_size=config[
            "hidden_size"
        ],
        num_layers=config[
            "num_layers"
        ],
        output_size=len(
            target_features
        ),
        horizon_count=len(
            horizons
        ),
        dropout=config.get(
            "dropout",
            0.0
        )
    )

    model.load_state_dict(
        torch.load(
            MODEL_FILE,
            map_location=device,
            weights_only=True
        )
    )

    model.to(device)
    model.eval()

    print(
        f"[OK] Model loaded:\n"
        f"     {MODEL_FILE}"
    )

    print(
        f"[INFO] Parameters: "
        f"{sum(p.numel() for p in model.parameters()):,}"
    )

    # --------------------------------------------------------
    # PREDICT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("GENERATING FORECAST")
    print("=" * 70)

    with torch.no_grad():

        prediction_scaled = (
            model(
                X_tensor
            )
            .cpu()
            .numpy()[0]
        )

    print(
        f"[INFO] Scaled prediction shape:"
    )

    print(
        f"       {prediction_scaled.shape}"
    )

    # --------------------------------------------------------
    # INVERSE SCALE
    # --------------------------------------------------------

    predictions = (
        scaler_y.inverse_transform(
            prediction_scaled
        )
    )

    # --------------------------------------------------------
    # GENERATE FUTURE TIMESTAMPS
    # --------------------------------------------------------

    last_timestamp = df[
        "timestamp"
    ].iloc[-1]

    output_rows = []

    for index, horizon in enumerate(
        horizons
    ):

        future_timestamp = (
            last_timestamp
            + pd.Timedelta(
                minutes=15 * horizon
            )
        )

        row = {
            "timestamp": future_timestamp,
            "forecast_horizon": (
                f"{15 * horizon}min"
            )
        }

        # ----------------------------------------------------
        # TARGET VALUES
        # ----------------------------------------------------

        for target_index, target in enumerate(
            target_features
        ):

            value = predictions[
                index,
                target_index
            ]

            # Tidak boleh negatif
            value = max(
                0,
                value
            )

            # vehicle_count dibulatkan
            if target == "vehicle_count":

                value = round(
                    value
                )

            else:

                value = round(
                    value,
                    4
                )

            row[
                f"predicted_{target}"
            ] = value

        output_rows.append(
            row
        )

    forecast_df = pd.DataFrame(
        output_rows
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    forecast_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # --------------------------------------------------------
    # PRINT RESULT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FORECAST RESULT")
    print("=" * 70)

    print()

    print(
        forecast_df.to_string(
            index=False
        )
    )

    print()
    print(
        f"[SAVED] Forecast:\n"
        f"        {OUTPUT_FILE}"
    )

    print()
    print("=" * 70)
    print("BRISBANE FORECAST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()