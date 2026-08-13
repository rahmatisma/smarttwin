"""
03_evaluate.py

Evaluate trained PyTorch LSTM model pada chronological test set.

Konsisten dengan:
    01_prepare_tmu.py
    02_train_lstm.py

INPUT:
    outputs/processed/tmu_processed.csv
    models/lstm_model.pt
    models/scaler_X.pkl
    models/scaler_y.pkl
    models/model_config.json

TARGET:
    1. vehicle_count
    2. speed_value
    3. density_proxy
    4. queue_proxy

OUTPUT:
    outputs/metrics/metrics.json

    outputs/plots/
        vehicle_count_forecast.png
        speed_value_forecast.png
        density_proxy_forecast.png
        queue_proxy_forecast.png

METRICS:
    MAE
    RMSE
    MAPE

FORECAST:
    1 timestep = sekitar 15 menit
"""


from pathlib import Path
import json
import random

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

import matplotlib.pyplot as plt

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)


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

MODEL_DIR = BASE_DIR / "models"

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

METRICS_DIR = (
    BASE_DIR
    / "outputs"
    / "metrics"
)

PLOT_DIR = (
    BASE_DIR
    / "outputs"
    / "plots"
)

METRICS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PLOT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_METRICS = (
    METRICS_DIR
    / "metrics.json"
)


# ============================================================
# REPRODUCIBILITY
# ============================================================

SEED = 42

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)


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
    """
    Model yang harus sama persis dengan 02_train_lstm.py.

    Input:
        [batch, sequence_length, features]

    Output:
        [batch, target_count]
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

        lstm_out, _ = self.lstm(x)

        last_output = (
            lstm_out[:, -1, :]
        )

        last_output = self.dropout(
            last_output
        )

        output = self.fc(
            last_output
        )

        return output


# ============================================================
# LOAD CONFIG
# ============================================================

def load_config():

    print("=" * 70)
    print("MODEL CONFIGURATION")
    print("=" * 70)

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Model config tidak ditemukan:\n"
            f"{CONFIG_FILE}\n\n"
            "Jalankan 02_train_lstm.py terlebih dahulu."
        )

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        config = json.load(file)

    # --------------------------------------------------------
    # Ambil nama kolom sesuai 02_train_lstm.py
    # --------------------------------------------------------

    feature_columns = config.get(
        "feature_columns"
    )

    target_columns = config.get(
        "target_columns"
    )

    sequence_length = config.get(
        "sequence_length"
    )

    forecast_horizon = config.get(
        "forecast_horizon"
    )

    if not feature_columns:
        raise ValueError(
            "model_config.json tidak memiliki "
            "'feature_columns'."
        )

    if not target_columns:
        raise ValueError(
            "model_config.json tidak memiliki "
            "'target_columns'."
        )

    if sequence_length is None:
        raise ValueError(
            "model_config.json tidak memiliki "
            "'sequence_length'."
        )

    if forecast_horizon is None:
        raise ValueError(
            "model_config.json tidak memiliki "
            "'forecast_horizon'."
        )

    print(
        f"[INFO] Features: "
        f"{len(feature_columns)}"
    )

    for i, feature in enumerate(
        feature_columns,
        start=1,
    ):
        print(
            f"       {i:02d}. {feature}"
        )

    print(
        f"\n[INFO] Targets: "
        f"{len(target_columns)}"
    )

    for i, target in enumerate(
        target_columns,
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

    return (
        config,
        feature_columns,
        target_columns,
        sequence_length,
        forecast_horizon,
    )


# ============================================================
# LOAD DATA
# ============================================================

def load_data(
    feature_columns,
    target_columns,
):

    print("\n" + "=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n"
            f"{DATA_FILE}\n\n"
            "Jalankan terlebih dahulu:\n"
            "python scripts/01_prepare_tmu.py"
        )

    df = pd.read_csv(
        DATA_FILE
    )

    print(
        f"[INFO] Loading dataset:"
        f"\n       {DATA_FILE}"
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
    # Required columns
    # --------------------------------------------------------

    required_columns = (
        ["timestamp"]
        + feature_columns
        + target_columns
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

    return df


# ============================================================
# VALIDATE DATA
# ============================================================

def validate_data(
    df,
    feature_columns,
    target_columns,
):

    print("\n" + "=" * 70)
    print("DATA VALIDATION")
    print("=" * 70)

    print(
        "[OK] Semua feature tersedia."
    )

    print(
        "[OK] Semua target tersedia."
    )

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
        df.sort_values("timestamp")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    numeric_columns = (
        feature_columns
        + target_columns
    )

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Missing values
    # --------------------------------------------------------

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
    # FIX:
    # Jangan melakukan:
    #
    # df[numeric_columns] = (
    #     df[numeric_columns]
    #     .interpolate(...)
    # )
    #
    # karena bisa menyebabkan:
    # Columns must be same length as key
    #
    # Kita proses setiap kolom satu per satu.
    # --------------------------------------------------------

    for column in numeric_columns:

        df[column] = (
            df[column]
            .interpolate(
                method="linear"
            )
            .ffill()
            .bfill()
        )

    # --------------------------------------------------------
    # Check after cleaning
    # --------------------------------------------------------

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
    # Time range
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
    df,
    scaler_X,
    scaler_y,
    feature_columns,
    target_columns,
    sequence_length,
    forecast_horizon,
):

    X_raw = df[
        feature_columns
    ].values

    y_raw = df[
        target_columns
    ].values

    # --------------------------------------------------------
    # Scale
    # --------------------------------------------------------

    X_scaled = scaler_X.transform(
        X_raw
    )

    y_scaled = scaler_y.transform(
        y_raw
    )

    X_sequences = []
    y_targets = []
    timestamps = []

    # --------------------------------------------------------
    # Sequence generation
    #
    # Sama dengan 02_train_lstm.py:
    #
    # sequence:
    #     i : i + sequence_length
    #
    # target:
    #     i + sequence_length
    #     untuk horizon = 1
    # --------------------------------------------------------

    max_start = (
        len(df)
        - sequence_length
        - forecast_horizon
        + 1
    )

    for i in range(max_start):

        sequence_end = (
            i + sequence_length
        )

        target_index = (
            sequence_end
            + forecast_horizon
            - 1
        )

        X_sequences.append(
            X_scaled[
                i:sequence_end
            ]
        )

        y_targets.append(
            y_scaled[
                target_index
            ]
        )

        timestamps.append(
            df.iloc[
                target_index
            ]["timestamp"]
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
        timestamps,
    )


# ============================================================
# CALCULATE MAPE
# ============================================================

def calculate_mape(
    actual,
    predicted,
):

    actual = np.asarray(
        actual,
        dtype=np.float64,
    )

    predicted = np.asarray(
        predicted,
        dtype=np.float64,
    )

    # Hindari pembagian dengan nol
    mask = (
        np.abs(actual)
        > 1e-8
    )

    if not np.any(mask):
        return np.nan

    return (
        np.mean(
            np.abs(
                (
                    actual[mask]
                    - predicted[mask]
                )
                / actual[mask]
            )
        )
        * 100
    )


# ============================================================
# LOAD MODEL
# ============================================================

def load_model(
    config,
    feature_columns,
    target_columns,
):

    print("\n" + "=" * 70)
    print("MODEL LOADING")
    print("=" * 70)

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Model tidak ditemukan:\n"
            f"{MODEL_FILE}"
        )

    # --------------------------------------------------------
    # Model architecture harus sama dengan training
    # --------------------------------------------------------

    model = TrafficLSTM(
        input_size=len(
            feature_columns
        ),
        hidden_size=config[
            "hidden_size"
        ],
        num_layers=config[
            "num_layers"
        ],
        output_size=len(
            target_columns
        ),
        dropout=config[
            "dropout"
        ],
    )

    # --------------------------------------------------------
    # Load checkpoint
    # --------------------------------------------------------

    checkpoint = torch.load(
        MODEL_FILE,
        map_location=DEVICE,
        weights_only=False,
    )

    # 02_train_lstm.py menyimpan dictionary
    # dengan key "model_state_dict"

    if isinstance(
        checkpoint,
        dict
    ) and "model_state_dict" in checkpoint:

        model.load_state_dict(
            checkpoint[
                "model_state_dict"
            ]
        )

    else:

        # Fallback jika suatu saat
        # model disimpan langsung
        model.load_state_dict(
            checkpoint
        )

    model.to(DEVICE)
    model.eval()

    parameter_count = sum(
        parameter.numel()
        for parameter
        in model.parameters()
    )

    print(
        f"[OK] Model loaded:"
        f"\n     {MODEL_FILE}"
    )

    print(
        f"[INFO] Parameters: "
        f"{parameter_count:,}"
    )

    print(
        f"[INFO] Device: "
        f"{DEVICE}"
    )

    return model


# ============================================================
# PREDICT
# ============================================================

def predict(
    model,
    X_test,
):

    X_tensor = torch.tensor(
        X_test,
        dtype=torch.float32,
    ).to(DEVICE)

    predictions = []

    # --------------------------------------------------------
    # Batch prediction supaya RAM tetap ringan
    # --------------------------------------------------------

    batch_size = 256

    with torch.no_grad():

        for start in range(
            0,
            len(X_tensor),
            batch_size,
        ):

            end = (
                start
                + batch_size
            )

            batch = X_tensor[
                start:end
            ]

            batch_prediction = (
                model(batch)
                .cpu()
                .numpy()
            )

            predictions.append(
                batch_prediction
            )

    return np.concatenate(
        predictions,
        axis=0,
    )


# ============================================================
# INVERSE TRANSFORM
# ============================================================

def inverse_transform_targets(
    predictions_scaled,
    actual_scaled,
    scaler_y,
):

    predictions = (
        scaler_y.inverse_transform(
            predictions_scaled
        )
    )

    actual = (
        scaler_y.inverse_transform(
            actual_scaled
        )
    )

    return (
        predictions,
        actual,
    )


# ============================================================
# CALCULATE METRICS
# ============================================================

def calculate_metrics(
    actual,
    predictions,
    target_columns,
):

    metrics = {}

    for target_index, target in enumerate(
        target_columns
    ):

        y_true = actual[
            :,
            target_index,
        ]

        y_pred = predictions[
            :,
            target_index,
        ]

        mae = mean_absolute_error(
            y_true,
            y_pred,
        )

        rmse = np.sqrt(
            mean_squared_error(
                y_true,
                y_pred,
            )
        )

        mape = calculate_mape(
            y_true,
            y_pred,
        )

        metrics[target] = {
            "MAE": float(mae),
            "RMSE": float(rmse),
            "MAPE_percent": (
                float(mape)
                if not np.isnan(mape)
                else None
            ),
        }

    return metrics


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def save_predictions(
    timestamps,
    actual,
    predictions,
    target_columns,
    forecast_horizon,
):

    output_file = (
        METRICS_DIR
        / "test_predictions.csv"
    )

    result = pd.DataFrame(
        {
            "timestamp": timestamps,
        }
    )

    result[
        "forecast_horizon"
    ] = (
        forecast_horizon
        * 15
    )

    # --------------------------------------------------------
    # Actual + predicted
    # --------------------------------------------------------

    for index, target in enumerate(
        target_columns
    ):

        result[
            f"actual_{target}"
        ] = actual[
            :,
            index,
        ]

        result[
            f"predicted_{target}"
        ] = predictions[
            :,
            index,
        ]

    result.to_csv(
        output_file,
        index=False,
    )

    print(
        f"[SAVED] Predictions:"
        f"\n        {output_file}"
    )

    return result


# ============================================================
# PLOT
# ============================================================

def create_plots(
    actual,
    predictions,
    target_columns,
    forecast_horizon,
):

    print("\n" + "=" * 70)
    print("CREATING PLOTS")
    print("=" * 70)

    plot_limit = min(
        500,
        len(actual),
    )

    for target_index, target in enumerate(
        target_columns
    ):

        actual_values = actual[
            :plot_limit,
            target_index,
        ]

        predicted_values = predictions[
            :plot_limit,
            target_index,
        ]

        plt.figure(
            figsize=(14, 6)
        )

        plt.plot(
            actual_values,
            label="Actual",
        )

        plt.plot(
            predicted_values,
            label="Predicted",
        )

        plt.title(
            f"{target} - "
            f"{forecast_horizon * 15} Minute Forecast"
        )

        plt.xlabel(
            "Test Samples"
        )

        plt.ylabel(
            target
        )

        plt.legend()

        plt.tight_layout()

        output_plot = (
            PLOT_DIR
            / f"{target}_forecast.png"
        )

        plt.savefig(
            output_plot,
            dpi=150,
        )

        plt.close()

        print(
            f"[SAVED] {output_plot}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("LSTM TRAFFIC FORECASTING EVALUATION")
    print("=" * 70)

    print(
        f"[INFO] Device: "
        f"{DEVICE}"
    )

    # --------------------------------------------------------
    # Load configuration
    # --------------------------------------------------------

    (
        config,
        feature_columns,
        target_columns,
        sequence_length,
        forecast_horizon,
    ) = load_config()

    # --------------------------------------------------------
    # Load dataset
    # --------------------------------------------------------

    df = load_data(
        feature_columns,
        target_columns,
    )

    # --------------------------------------------------------
    # Validate dataset
    # --------------------------------------------------------

    df = validate_data(
        df,
        feature_columns,
        target_columns,
    )

    # --------------------------------------------------------
    # Load scalers
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("SCALER LOADING")
    print("=" * 70)

    if not SCALER_X_FILE.exists():
        raise FileNotFoundError(
            f"X scaler tidak ditemukan:\n"
            f"{SCALER_X_FILE}"
        )

    if not SCALER_Y_FILE.exists():
        raise FileNotFoundError(
            f"Y scaler tidak ditemukan:\n"
            f"{SCALER_Y_FILE}"
        )

    scaler_X = joblib.load(
        SCALER_X_FILE
    )

    scaler_y = joblib.load(
        SCALER_Y_FILE
    )

    print(
        f"[OK] X scaler loaded."
    )

    print(
        f"[OK] Y scaler loaded."
    )

    # --------------------------------------------------------
    # Create sequences
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("CREATING TEST SEQUENCES")
    print("=" * 70)

    (
        X_sequences,
        y_sequences,
        timestamps,
    ) = create_sequences(
        df,
        scaler_X,
        scaler_y,
        feature_columns,
        target_columns,
        sequence_length,
        forecast_horizon,
    )

    print(
        f"[INFO] X shape: "
        f"{X_sequences.shape}"
    )

    print(
        f"[INFO] y shape: "
        f"{y_sequences.shape}"
    )

    print(
        f"[INFO] Total sequences: "
        f"{len(X_sequences):,}"
    )

    # --------------------------------------------------------
    # Temporal split
    #
    # Harus konsisten dengan 02_train_lstm.py:
    #
    # Train      70%
    # Validation 15%
    # Test       15%
    # --------------------------------------------------------

    total_sequences = len(
        X_sequences
    )

    train_end = int(
        total_sequences
        * config["train_ratio"]
    )

    validation_end = int(
        total_sequences
        * (
            config["train_ratio"]
            + config["validation_ratio"]
        )
    )

    X_test = X_sequences[
        validation_end:
    ]

    y_test = y_sequences[
        validation_end:
    ]

    test_timestamps = timestamps[
        validation_end:
    ]

    print(
        "\n[INFO] Dataset split:"
    )

    print(
        f"       Train      : "
        f"{train_end:,}"
    )

    print(
        f"       Validation : "
        f"{validation_end - train_end:,}"
    )

    print(
        f"       Test       : "
        f"{len(X_test):,}"
    )

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    model = load_model(
        config,
        feature_columns,
        target_columns,
    )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("PREDICTION")
    print("=" * 70)

    predictions_scaled = predict(
        model,
        X_test,
    )

    print(
        f"[INFO] Prediction shape: "
        f"{predictions_scaled.shape}"
    )

    # --------------------------------------------------------
    # Inverse scaling
    # --------------------------------------------------------

    (
        predictions,
        actual,
    ) = inverse_transform_targets(
        predictions_scaled,
        y_test,
        scaler_y,
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("CALCULATING METRICS")
    print("=" * 70)

    metrics = calculate_metrics(
        actual,
        predictions,
        target_columns,
    )

    # --------------------------------------------------------
    # Build final metrics JSON
    # --------------------------------------------------------

    metrics_output = {

        "model": "TrafficLSTM",

        "framework": "PyTorch",

        "device": str(DEVICE),

        "forecast_horizon": {
            "timesteps": forecast_horizon,
            "minutes": (
                forecast_horizon
                * 15
            ),
        },

        "sequence_length":
            sequence_length,

        "test_samples":
            len(X_test),

        "targets":
            target_columns,

        "metrics":
            metrics,
    }

    # --------------------------------------------------------
    # Save metrics
    # --------------------------------------------------------

    with open(
        OUTPUT_METRICS,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metrics_output,
            file,
            indent=4,
        )

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    print(
        f"[INFO] Forecast horizon: "
        f"{forecast_horizon * 15} minutes"
    )

    print(
        f"[INFO] Test samples: "
        f"{len(X_test):,}"
    )

    print()

    for target, scores in metrics.items():

        print(
            f"{target}"
        )

        print(
            f"    MAE  : "
            f"{scores['MAE']:.4f}"
        )

        print(
            f"    RMSE : "
            f"{scores['RMSE']:.4f}"
        )

        if scores[
            "MAPE_percent"
        ] is not None:

            print(
                f"    MAPE : "
                f"{scores['MAPE_percent']:.2f}%"
            )

        else:

            print(
                f"    MAPE : N/A"
            )

        print()

    # --------------------------------------------------------
    # Save predictions
    # --------------------------------------------------------

    save_predictions(
        test_timestamps,
        actual,
        predictions,
        target_columns,
        forecast_horizon,
    )

    # --------------------------------------------------------
    # Create plots
    # --------------------------------------------------------

    create_plots(
        actual,
        predictions,
        target_columns,
        forecast_horizon,
    )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print(
        f"\n[SAVED] Metrics:"
        f"\n        {OUTPUT_METRICS}"
    )

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETED")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()