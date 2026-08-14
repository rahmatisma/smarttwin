"""
04_predict.py

Generate future traffic forecast using trained LSTM.

Input:
    outputs/processed/tmu_processed.csv

Model:
    models/tmu/lstm_model.pt
    models/tmu/scaler_X.pkl
    models/tmu/scaler_y.pkl
    models/tmu/model_config.json

Output:
    outputs/predictions/forecast.csv

Forecast:
    +15 minutes

Targets:
    - vehicle_count
    - speed_value
    - density_proxy
    - queue_proxy
"""

from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "outputs"
    / "processed"
    / "tmu_processed.csv"
)

MODEL_DIR = BASE_DIR / "models" / "tmu" 

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
    """
    LSTM model yang sama dengan model pada 02_train_lstm.py.

    Input:
        [batch, sequence_length, features]

    Output:
        [batch, number_of_targets]
    """

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

        self.dropout = nn.Dropout(
            dropout
        )

        self.fc = nn.Linear(
            hidden_size,
            output_size,
        )

    def forward(self, x):

        # x:
        # [batch, sequence_length, features]

        lstm_out, _ = self.lstm(x)

        # Ambil output timestep terakhir
        last_output = lstm_out[:, -1, :]

        last_output = self.dropout(
            last_output
        )

        output = self.fc(
            last_output
        )

        return output


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("LSTM TRAFFIC FORECAST GENERATION")
    print("=" * 70)

    # --------------------------------------------------------
    # Check required files
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("FILE CHECK")
    print("=" * 70)

    required_files = [
        DATA_FILE,
        MODEL_FILE,
        SCALER_X_FILE,
        SCALER_Y_FILE,
        CONFIG_FILE,
    ]

    for file_path in required_files:

        if not file_path.exists():

            raise FileNotFoundError(
                f"File tidak ditemukan:\n{file_path}"
            )

        print(
            f"[OK] {file_path.name}"
        )

    # --------------------------------------------------------
    # Load model configuration
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("MODEL CONFIGURATION")
    print("=" * 70)

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        config = json.load(file)

    input_features = config[
        "feature_columns"
    ]

    target_features = config[
        "target_columns"
    ]

    sequence_length = config[
        "sequence_length"
    ]

    hidden_size = config[
        "hidden_size"
    ]

    num_layers = config[
        "num_layers"
    ]

    dropout = config[
        "dropout"
    ]

    forecast_horizon = config[
        "forecast_horizon"
    ]

    print(
        f"[INFO] Input features : "
        f"{len(input_features)}"
    )

    for i, feature in enumerate(
        input_features,
        start=1,
    ):
        print(
            f"       {i:02d}. {feature}"
        )

    print(
        f"\n[INFO] Targets        : "
        f"{len(target_features)}"
    )

    for i, target in enumerate(
        target_features,
        start=1,
    ):
        print(
            f"       {i}. {target}"
        )

    print(
        f"\n[INFO] Sequence length : "
        f"{sequence_length}"
    )

    print(
        f"[INFO] Forecast horizon: "
        f"{forecast_horizon} timestep"
    )

    # --------------------------------------------------------
    # Load dataset
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    print(
        f"[INFO] Loading dataset:"
        f"\n       {DATA_FILE}"
    )

    df = pd.read_csv(
        DATA_FILE,
        parse_dates=["timestamp"],
    )

    df = (
        df.sort_values("timestamp")
        .reset_index(drop=True)
    )

    print(
        f"[INFO] Rows: "
        f"{len(df):,}"
    )

    print(
        f"[INFO] Columns: "
        f"{len(df.columns)}"
    )

    # --------------------------------------------------------
    # Validate data
    # --------------------------------------------------------

    required_columns = (
        ["timestamp"]
        + input_features
        + target_features
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        print(
            "\n[ERROR] Missing columns:"
        )

        for column in missing_columns:
            print(
                f"        - {column}"
            )

        raise ValueError(
            "Dataset tidak memiliki "
            "semua kolom yang dibutuhkan."
        )

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    numeric_columns = list(
        dict.fromkeys(
            input_features
            + target_features
        )
    )

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    missing_count = (
        df[numeric_columns]
        .isna()
        .sum()
        .sum()
    )

    print(
        f"[INFO] Missing numeric values: "
        f"{missing_count}"
    )

    if missing_count > 0:

        df[numeric_columns] = (
            df[numeric_columns]
            .interpolate(method="linear")
            .ffill()
            .bfill()
        )

    missing_after = (
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
    # Check sequence length
    # --------------------------------------------------------

    if len(df) < sequence_length:

        raise ValueError(
            "Jumlah data tidak cukup untuk "
            "membuat sequence."
        )

    # --------------------------------------------------------
    # Load scalers
    # --------------------------------------------------------

    print("\n" + "=" * 70)
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
    # Prepare latest sequence
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("PREPARING LATEST SEQUENCE")
    print("=" * 70)

    latest_data = df[
        input_features
    ].tail(
        sequence_length
    )

    print(
        f"[INFO] Latest timestamp:"
        f"\n       {df['timestamp'].iloc[-1]}"
    )

    print(
        f"[INFO] Sequence shape:"
        f"\n       {latest_data.shape}"
    )

    X_scaled = scaler_X.transform(
        latest_data
    )

    X_tensor = torch.tensor(
        X_scaled,
        dtype=torch.float32,
    ).unsqueeze(0)

    print(
        f"[INFO] Model input shape:"
        f"\n       {tuple(X_tensor.shape)}"
    )

    # --------------------------------------------------------
    # Device
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
    # Load model
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("MODEL LOADING")
    print("=" * 70)

    model = TrafficLSTM(
        input_size=len(
            input_features
        ),
        hidden_size=hidden_size,
        num_layers=num_layers,
        output_size=len(
            target_features
        ),
        dropout=dropout,
    )

    checkpoint = torch.load(
        MODEL_FILE,
        map_location=device,
        weights_only=True,
    )

    # Model dari 02_train_lstm.py
    # menyimpan state_dict di dalam dictionary.
    if (
        isinstance(checkpoint, dict)
        and "model_state_dict" in checkpoint
    ):

        model.load_state_dict(
            checkpoint[
                "model_state_dict"
            ]
        )

    else:

        # Fallback apabila file model
        # langsung berupa state_dict.
        model.load_state_dict(
            checkpoint
        )

    model.to(device)

    model.eval()

    parameter_count = sum(
        p.numel()
        for p in model.parameters()
    )

    print(
        f"[OK] Model loaded:"
        f"\n     {MODEL_FILE}"
    )

    print(
        f"[INFO] Parameters: "
        f"{parameter_count:,}"
    )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("GENERATING FORECAST")
    print("=" * 70)

    with torch.no_grad():

        prediction_scaled = (
            model(
                X_tensor
            )
            .cpu()
            .numpy()
        )

    print(
        f"[INFO] Scaled prediction shape: "
        f"{prediction_scaled.shape}"
    )

    # --------------------------------------------------------
    # Inverse scaling
    # --------------------------------------------------------

    prediction_scaled = (
        prediction_scaled.reshape(
            1,
            -1
        )
    )

    predictions = (
        scaler_y.inverse_transform(
            prediction_scaled
        )
    )

    predictions = predictions[0]

    print(
        f"[INFO] Prediction shape: "
        f"{predictions.shape}"
    )

    # --------------------------------------------------------
    # Extract predictions
    # --------------------------------------------------------

    predicted_values = {}

    for index, target in enumerate(
        target_features
    ):

        predicted_values[target] = (
            predictions[index]
        )

    # --------------------------------------------------------
    # Apply basic physical constraints
    # --------------------------------------------------------

    vehicle_count = max(
        0.0,
        float(
            predicted_values[
                "vehicle_count"
            ]
        )
    )

    speed_value = max(
        0.0,
        float(
            predicted_values[
                "speed_value"
            ]
        )
    )

    density_proxy = max(
        0.0,
        float(
            predicted_values[
                "density_proxy"
            ]
        )
    )

    queue_proxy = max(
        0.0,
        float(
            predicted_values[
                "queue_proxy"
            ]
        )
    )

    # --------------------------------------------------------
    # Forecast timestamp
    # --------------------------------------------------------

    last_timestamp = (
        df["timestamp"].iloc[-1]
    )

    future_timestamp = (
        last_timestamp
        + pd.Timedelta(
            minutes=15
            * forecast_horizon
        )
    )

    # --------------------------------------------------------
    # Create output
    # --------------------------------------------------------

    forecast_row = {

        "timestamp":
            future_timestamp,

        "forecast_horizon":
            f"{15 * forecast_horizon}min",

        "predicted_vehicle_count":
            vehicle_count,

        "predicted_average_speed":
            speed_value,

        "predicted_density":
            density_proxy,

        "predicted_queue":
            queue_proxy,
    }

    forecast_df = pd.DataFrame(
        [forecast_row]
    )

    # --------------------------------------------------------
    # Round values
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
        "predicted_average_speed"
    ] = (
        forecast_df[
            "predicted_average_speed"
        ]
        .round(2)
    )

    forecast_df[
        "predicted_density"
    ] = (
        forecast_df[
            "predicted_density"
        ]
        .round(4)
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
    # Save
    # --------------------------------------------------------

    forecast_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Display result
    # --------------------------------------------------------

    print("\n" + "=" * 70)
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
        f"\n        {OUTPUT_FILE}"
    )

    print("\n" + "=" * 70)
    print("FORECAST COMPLETED")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()