"""
07_evaluate_brisbane.py

Evaluate trained Brisbane Traffic LSTM
on the chronological test set.

Input:
    outputs/brisbane/processed/brisbane_processed.csv

Model:
    models/brisbane_lstm_model.pt
    models/brisbane_scaler_X.pkl
    models/brisbane_scaler_y.pkl
    models/brisbane_model_config.json

Outputs:
    outputs/brisbane/metrics/metrics.json
    outputs/brisbane/metrics/test_predictions.csv

    outputs/brisbane/plots/
        brisbane_vehicle_count_forecast.png
        brisbane_density_proxy_forecast.png
        brisbane_queue_proxy_forecast.png

Metrics:
    MAE
    RMSE
    MAPE
"""


from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd

import torch
import torch.nn as nn

import matplotlib.pyplot as plt

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error
)


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
)

METRICS_DIR = (
    OUTPUT_DIR
    / "metrics"
)

PLOT_DIR = (
    OUTPUT_DIR
    / "plots"
)

METRICS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PLOT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_METRICS = (
    METRICS_DIR
    / "metrics.json"
)

OUTPUT_PREDICTIONS = (
    METRICS_DIR
    / "test_predictions.csv"
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
# MAPE
# ============================================================

def calculate_mape(
    actual,
    predicted
):

    actual = np.asarray(actual)
    predicted = np.asarray(predicted)

    mask = np.abs(actual) > 1e-8

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
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    df,
    scaler_X,
    scaler_y,
    input_features,
    target_features,
    sequence_length,
    horizons
):

    X_raw = df[
        input_features
    ].values

    y_raw = df[
        target_features
    ].values

    X_scaled = scaler_X.transform(
        X_raw
    )

    y_scaled = scaler_y.transform(
        y_raw
    )

    X_sequences = []
    y_sequences = []
    timestamps = []

    max_horizon = max(horizons)

    for i in range(
        sequence_length,
        len(df) - max_horizon + 1
    ):

        X_sequences.append(
            X_scaled[
                i - sequence_length:i
            ]
        )

        targets = []

        for horizon in horizons:

            target_index = (
                i + horizon - 1
            )

            targets.append(
                y_scaled[
                    target_index
                ]
            )

        y_sequences.append(
            targets
        )

        timestamps.append(
            df.iloc[i]["timestamp"]
        )

    return (
        np.array(X_sequences),
        np.array(y_sequences),
        timestamps
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BRISBANE LSTM TRAFFIC EVALUATION")
    print("=" * 70)

    # --------------------------------------------------------
    # FILE CHECK
    # --------------------------------------------------------

    required_files = [
        DATA_FILE,
        MODEL_FILE,
        SCALER_X_FILE,
        SCALER_Y_FILE,
        CONFIG_FILE
    ]

    print()
    print("=" * 70)
    print("FILE CHECK")
    print("=" * 70)

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

    train_ratio = config.get(
        "train_ratio",
        0.70
    )

    val_ratio = config.get(
        "val_ratio",
        0.15
    )

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
        f"[INFO] Forecast horizon: "
        f"{horizons}"
    )

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    print(
        f"[INFO] Loading dataset:\n"
        f"       {DATA_FILE}"
    )

    df = pd.read_csv(
        DATA_FILE
    )

    if "timestamp" not in df.columns:

        raise ValueError(
            "Kolom 'timestamp' tidak ditemukan."
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
        f"[INFO] Time range:"
    )

    print(
        f"       {df['timestamp'].min()}"
    )

    print(
        f"       {df['timestamp'].max()}"
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

    missing_before = (
        df[numeric_columns]
        .isna()
        .sum()
        .sum()
    )

    print(
        f"[INFO] Missing numeric values: "
        f"{missing_before}"
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
    # CREATE SEQUENCES
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CREATING TEST SEQUENCES")
    print("=" * 70)

    (
        X,
        y,
        timestamps
    ) = create_sequences(
        df,
        scaler_X,
        scaler_y,
        input_features,
        target_features,
        sequence_length,
        horizons
    )

    if len(X) == 0:

        raise ValueError(
            "Tidak ada sequence yang terbentuk. "
            "Jumlah data terlalu sedikit."
        )

    print(
        f"[INFO] X shape: {X.shape}"
    )

    print(
        f"[INFO] y shape: {y.shape}"
    )

    total_samples = len(X)

    # --------------------------------------------------------
    # CHRONOLOGICAL SPLIT
    # --------------------------------------------------------

    train_end = int(
        total_samples
        * train_ratio
    )

    val_end = int(
        total_samples
        * (
            train_ratio
            + val_ratio
        )
    )

    X_test = X[
        val_end:
    ]

    y_test = y[
        val_end:
    ]

    test_timestamps = timestamps[
        val_end:
    ]

    print()
    print(
        "[INFO] Dataset split:"
    )

    print(
        f"       Train      : "
        f"{train_end}"
    )

    print(
        f"       Validation : "
        f"{val_end - train_end}"
    )

    print(
        f"       Test       : "
        f"{len(X_test)}"
    )

    if len(X_test) == 0:

        raise ValueError(
            "Test set kosong."
        )

    # --------------------------------------------------------
    # DEVICE
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print()
    print(
        f"[INFO] Device: {device}"
    )

    # --------------------------------------------------------
    # MODEL
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

    state_dict = torch.load(
        MODEL_FILE,
        map_location=device,
        weights_only=True
    )

    model.load_state_dict(
        state_dict
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
    # PREDICTION
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PREDICTION")
    print("=" * 70)

    X_tensor = torch.tensor(
        X_test,
        dtype=torch.float32
    ).to(device)

    with torch.no_grad():

        predictions_scaled = (
            model(
                X_tensor
            )
            .cpu()
            .numpy()
        )

    print(
        f"[INFO] Prediction shape: "
        f"{predictions_scaled.shape}"
    )

    # --------------------------------------------------------
    # INVERSE TRANSFORM
    # --------------------------------------------------------

    predictions = np.zeros_like(
        predictions_scaled
    )

    actual = np.zeros_like(
        y_test
    )

    for h in range(
        len(horizons)
    ):

        predictions[:, h, :] = (
            scaler_y.inverse_transform(
                predictions_scaled[
                    :, h, :
                ]
            )
        )

        actual[:, h, :] = (
            scaler_y.inverse_transform(
                y_test[
                    :, h, :
                ]
            )
        )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CALCULATING METRICS")
    print("=" * 70)

    metrics = {}

    for h_index, horizon in enumerate(
        horizons
    ):

        horizon_name = (
            f"{horizon * 15}min"
        )

        metrics[
            horizon_name
        ] = {}

        for target_index, target in enumerate(
            target_features
        ):

            y_true = actual[
                :,
                h_index,
                target_index
            ]

            y_pred = predictions[
                :,
                h_index,
                target_index
            ]

            mae = mean_absolute_error(
                y_true,
                y_pred
            )

            rmse = np.sqrt(
                mean_squared_error(
                    y_true,
                    y_pred
                )
            )

            mape = calculate_mape(
                y_true,
                y_pred
            )

            metrics[
                horizon_name
            ][target] = {
                "MAE": float(mae),
                "RMSE": float(rmse),
                "MAPE_percent": (
                    float(mape)
                    if not np.isnan(mape)
                    else None
                )
            }

    # --------------------------------------------------------
    # SAVE PREDICTIONS
    # --------------------------------------------------------

    prediction_rows = []

    for sample_index in range(
        len(test_timestamps)
    ):

        for h_index, horizon in enumerate(
            horizons
        ):

            row = {
                "timestamp": (
                    test_timestamps[
                        sample_index
                    ]
                ),
                "forecast_horizon": (
                    f"{horizon * 15}min"
                )
            }

            for target_index, target in enumerate(
                target_features
            ):

                row[
                    f"actual_{target}"
                ] = actual[
                    sample_index,
                    h_index,
                    target_index
                ]

                row[
                    f"predicted_{target}"
                ] = predictions[
                    sample_index,
                    h_index,
                    target_index
                ]

            prediction_rows.append(
                row
            )

    prediction_df = pd.DataFrame(
        prediction_rows
    )

    prediction_df.to_csv(
        OUTPUT_PREDICTIONS,
        index=False
    )

    # --------------------------------------------------------
    # SAVE METRICS
    # --------------------------------------------------------

    metrics_output = {
        "model": "TrafficLSTM",
        "dataset": "Brisbane Traffic Data",
        "device": str(device),
        "sequence_length": sequence_length,
        "forecast_horizons": horizons,
        "test_samples": len(X_test),
        "targets": target_features,
        "metrics": metrics
    }

    with open(
        OUTPUT_METRICS,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metrics_output,
            file,
            indent=4
        )

    # --------------------------------------------------------
    # PRINT RESULTS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    print(
        f"[INFO] Test samples: "
        f"{len(X_test)}"
    )

    for horizon, values in metrics.items():

        print()
        print(
            f"{horizon}"
        )

        for target, score in values.items():

            mape_text = (
                f"{score['MAPE_percent']:.2f}%"
                if score["MAPE_percent"] is not None
                else "N/A"
            )

            print(
                f"  {target:20s} "
                f"MAE={score['MAE']:.4f} | "
                f"RMSE={score['RMSE']:.4f} | "
                f"MAPE={mape_text}"
            )

    print()
    print(
        f"[SAVED] Predictions:\n"
        f"        {OUTPUT_PREDICTIONS}"
    )

    # --------------------------------------------------------
    # PLOTS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CREATING PLOTS")
    print("=" * 70)

    # Plot hanya horizon pertama
    horizon_index = 0

    for target_index, target in enumerate(
        target_features
    ):

        actual_values = actual[
            :,
            horizon_index,
            target_index
        ]

        predicted_values = predictions[
            :,
            horizon_index,
            target_index
        ]

        limit = min(
            500,
            len(actual_values)
        )

        plt.figure(
            figsize=(14, 6)
        )

        plt.plot(
            actual_values[:limit],
            label="Actual"
        )

        plt.plot(
            predicted_values[:limit],
            label="Predicted"
        )

        plt.title(
            f"Brisbane {target} - "
            f"{horizons[horizon_index] * 15} Minute Forecast"
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
            / f"brisbane_{target}_forecast.png"
        )

        plt.savefig(
            output_plot,
            dpi=150
        )

        plt.close()

        print(
            f"[SAVED] {output_plot}"
        )

    print()
    print(
        f"[SAVED] Metrics:\n"
        f"        {OUTPUT_METRICS}"
    )

    print()
    print("=" * 70)
    print("BRISBANE EVALUATION COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()