"""
07_evaluate_brisbane.py

Evaluate Brisbane LSTM on chronological test set.

Outputs:

    outputs/brisbane/metrics/metrics.json
    outputs/brisbane/metrics/test_predictions.csv

    outputs/brisbane/plots/
        vehicle_count_forecast.png
        density_proxy_forecast.png
        queue_proxy_forecast.png
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

METRICS_FILE = (
    METRICS_DIR
    / "metrics.json"
)

PREDICTIONS_FILE = (
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
# MAPE
# ============================================================

def calculate_mape(
    actual,
    predicted
):

    actual = np.asarray(
        actual
    )

    predicted = np.asarray(
        predicted
    )

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
                    -
                    predicted[mask]
                )
                /
                actual[mask]
            )
        )
        * 100
    )


# ============================================================
# SEQUENCES
# ============================================================

def create_sequences(
    X,
    y,
    timestamps,
    sequence_length,
    horizon
):

    X_sequences = []

    y_sequences = []

    target_timestamps = []

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

        target_index = (
            i
            + sequence_length
            + horizon
            - 1
        )

        y_sequences.append(
            y[target_index]
        )

        target_timestamps.append(
            timestamps[
                target_index
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
        ),
        target_timestamps
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BRISBANE LSTM TRAFFIC EVALUATION")
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

    print()
    print(
        f"[INFO] Rows: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # ARRAYS
    # --------------------------------------------------------

    X_raw = (
        df[input_features]
        .values
    )

    y_raw = (
        df[target_features]
        .values
    )

    timestamps = (
        df["timestamp"]
        .tolist()
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

    X_scaled = (
        scaler_X.transform(
            X_raw
        )
    )

    y_scaled = (
        scaler_y.transform(
            y_raw
        )
    )

    # --------------------------------------------------------
    # CREATE ALL SEQUENCES
    # --------------------------------------------------------

    (
        X,
        y,
        sequence_timestamps
    ) = create_sequences(
        X_scaled,
        y_scaled,
        timestamps,
        sequence_length,
        horizon
    )

    print()
    print(
        f"[INFO] Total sequences: "
        f"{len(X):,}"
    )

    # --------------------------------------------------------
    # SPLIT
    # --------------------------------------------------------

    total_samples = len(X)

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

    test_timestamps = (
        sequence_timestamps[
            val_end:
        ]
    )

    print()
    print(
        "[INFO] Test samples: "
        f"{len(X_test):,}"
    )

    # --------------------------------------------------------
    # DEVICE
    # --------------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    # --------------------------------------------------------
    # MODEL CONFIG
    # --------------------------------------------------------

    with open(
        MODEL_CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        model_config = json.load(
            file
        )

    model = TrafficLSTM(
        input_size=len(
            input_features
        ),
        hidden_size=model_config[
            "hidden_size"
        ],
        num_layers=model_config[
            "num_layers"
        ],
        output_size=len(
            target_features
        ),
        horizon_count=1,
        dropout=model_config[
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
            .squeeze(1)
        )

    # --------------------------------------------------------
    # INVERSE SCALE
    # --------------------------------------------------------

    predictions = (
        scaler_y.inverse_transform(
            predictions_scaled
        )
    )

    actual = (
        scaler_y.inverse_transform(
            y_test
        )
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    metrics = {}

    print()
    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    for index, target in enumerate(
        target_features
    ):

        y_true = (
            actual[:, index]
        )

        y_pred = (
            predictions[:, index]
        )

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

        metrics[target] = {

            "MAE": float(mae),

            "RMSE": float(rmse),

            "MAPE_percent": (
                float(mape)
                if not np.isnan(mape)
                else None
            )
        }

        print()
        print(target)

        print(
            f"    MAE  : {mae:.4f}"
        )

        print(
            f"    RMSE : {rmse:.4f}"
        )

        if np.isnan(mape):

            print(
                "    MAPE : N/A"
            )

        else:

            print(
                f"    MAPE : {mape:.2f}%"
            )

    # --------------------------------------------------------
    # SAVE PREDICTIONS
    # --------------------------------------------------------

    prediction_data = {

        "timestamp": test_timestamps
    }

    for index, target in enumerate(
        target_features
    ):

        prediction_data[
            f"actual_{target}"
        ] = actual[
            :, index
        ]

        prediction_data[
            f"predicted_{target}"
        ] = predictions[
            :, index
        ]

    predictions_df = pd.DataFrame(
        prediction_data
    )

    predictions_df.to_csv(
        PREDICTIONS_FILE,
        index=False
    )

    # --------------------------------------------------------
    # SAVE METRICS
    # --------------------------------------------------------

    evaluation_summary = {

        "model": "TrafficLSTM",

        "dataset": "Brisbane",

        "device": str(device),

        "forecast_horizon_minutes": (
            horizon
        ),

        "sequence_length": (
            sequence_length
        ),

        "test_samples": (
            len(X_test)
        ),

        "targets": target_features,

        "metrics": metrics,
    }

    with open(
        METRICS_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            evaluation_summary,
            file,
            indent=4
        )

    # --------------------------------------------------------
    # PLOTS
    # --------------------------------------------------------

    print()
    print(
        "=" * 70
    )
    print("CREATING PLOTS")
    print(
        "=" * 70
    )

    for index, target in enumerate(
        target_features
    ):

        plt.figure(
            figsize=(14, 6)
        )

        limit = min(
            500,
            len(actual)
        )

        plt.plot(
            actual[
                :limit,
                index
            ],
            label="Actual"
        )

        plt.plot(
            predictions[
                :limit,
                index
            ],
            label="Predicted"
        )

        plt.title(
            f"{target} - "
            f"Brisbane 15 Minute Forecast"
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
            dpi=150
        )

        plt.close()

        print(
            f"[SAVED] {output_plot}"
        )

    print()
    print(
        f"[SAVED] Metrics:"
    )

    print(
        f"        {METRICS_FILE}"
    )

    print(
        f"[SAVED] Predictions:"
    )

    print(
        f"        {PREDICTIONS_FILE}"
    )

    print()
    print("=" * 70)
    print("EVALUATION COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()