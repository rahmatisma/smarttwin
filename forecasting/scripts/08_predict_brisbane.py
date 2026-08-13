"""
08_predict_brisbane.py

Generate future traffic forecast using trained Brisbane LSTM.

Input:
    outputs/brisbane/processed/brisbane_processed.csv

Model:
    models/brisbane/lstm_model.pt

Output:
    outputs/brisbane/predictions/forecast.csv
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

MODEL_DIR = (
    BASE_DIR
    / "models"
    / "brisbane"
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

CONFIG_FILE = (
    MODEL_DIR
    / "model_config.json"
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
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BRISBANE TRAFFIC FORECAST GENERATION")
    print("=" * 70)

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

    horizons = (
        config["forecast_horizons"]
    )

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["timestamp"]
    )

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    if len(df) < sequence_length:

        raise ValueError(
            "Data tidak cukup untuk "
            "membuat sequence."
        )

    print()
    print(
        f"[INFO] Rows: "
        f"{len(df):,}"
    )

    print(
        f"[INFO] Latest timestamp:"
    )

    print(
        f"       {df['timestamp'].iloc[-1]}"
    )

    # --------------------------------------------------------
    # SCALERS
    # --------------------------------------------------------

    scaler_X = joblib.load(
        SCALER_X_FILE
    )

    scaler_y = joblib.load(
        SCALER_Y_FILE
    )

    # --------------------------------------------------------
    # LAST SEQUENCE
    # --------------------------------------------------------

    latest_data = (
        df[
            input_features
        ]
        .tail(
            sequence_length
        )
    )

    X_scaled = (
        scaler_X.transform(
            latest_data.values
        )
    )

    X_tensor = torch.tensor(
        X_scaled,
        dtype=torch.float32
    ).unsqueeze(0)

    # --------------------------------------------------------
    # DEVICE
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    X_tensor = (
        X_tensor.to(device)
    )

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

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
        dropout=config[
            "dropout"
        ]
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

    # --------------------------------------------------------
    # PREDICTION
    # --------------------------------------------------------

    with torch.no_grad():

        prediction_scaled = (
            model(
                X_tensor
            )
            .cpu()
            .numpy()[0]
        )

    predictions = (
        scaler_y.inverse_transform(
            prediction_scaled
        )
    )

    # --------------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------------

    last_timestamp = (
        df[
            "timestamp"
        ].iloc[-1]
    )

    output_rows = []

    for index, horizon in enumerate(
        horizons
    ):

        future_timestamp = (
            last_timestamp
            +
            pd.Timedelta(
                minutes=15 * horizon
            )
        )

        vehicle_count = max(
            0,
            predictions[
                index,
                0
            ]
        )

        density = max(
            0,
            predictions[
                index,
                1
            ]
        )

        queue = max(
            0,
            predictions[
                index,
                2
            ]
        )

        output_rows.append({

            "timestamp":
                future_timestamp,

            "forecast_horizon":
                f"{15 * horizon}min",

            "predicted_vehicle_count":
                vehicle_count,

            "predicted_density":
                density,

            "predicted_queue":
                queue,
        })

    forecast_df = pd.DataFrame(
        output_rows
    )

    # --------------------------------------------------------
    # ROUND
    # --------------------------------------------------------

    forecast_df[
        "predicted_vehicle_count"
    ] = (
        forecast_df[
            "predicted_vehicle_count"
        ]
        .round()
        .astype(int)
    )

    forecast_df[
        "predicted_density"
    ] = (
        forecast_df[
            "predicted_density"
        ]
        .round(2)
    )

    forecast_df[
        "predicted_queue"
    ] = (
        forecast_df[
            "predicted_queue"
        ]
        .round(2)
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    forecast_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # --------------------------------------------------------
    # RESULT
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
        f"[SAVED] Forecast:"
    )

    print(
        f"        {OUTPUT_FILE}"
    )

    print()
    print("=" * 70)
    print("FORECAST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()