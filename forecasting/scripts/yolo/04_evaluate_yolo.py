import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import matplotlib.pyplot as plt

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

PROCESSED_DIR = (
    BASE_DIR
    / "outputs"
    / "yolo"
    / "processed"
)

MODEL_DIR = (
    BASE_DIR
    / "outputs"
    / "yolo"
    / "models"
)

METRICS_DIR = (
    BASE_DIR
    / "outputs"
    / "yolo"
    / "metrics"
)

PREDICTION_FILE = (
    BASE_DIR
    / "outputs"
    / "yolo"
    / "test_predictions.npz"
)

SCALER_PATH = (
    PROCESSED_DIR
    / "scaler_X.pkl"
)

CONFIG_PATH = (
    PROCESSED_DIR
    / "yolo_config.json"
)

SENSOR_CONFIG_PATH = (
    PROCESSED_DIR
    / "sensor_config.json"
)

FEATURE_METADATA_PATH = (
    PROCESSED_DIR
    / "feature_metadata.json"
)

BEST_MODEL_PATH = (
    MODEL_DIR
    / "best_model.pth"
)

METRICS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PLOTS_DIR = (
    BASE_DIR
    / "outputs"
    / "yolo"
    / "plots"
)

PLOTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================

DATASET_NAME = "YOLO Traffic Dataset"

INTERSECTION_ID = "simpang4-pingit"

SEQUENCE_LENGTH = 15

FORECAST_HORIZON = 1

NUM_SENSORS = 12

FEATURES_PER_SENSOR = 8

INPUT_SIZE = (
    NUM_SENSORS
    * FEATURES_PER_SENSOR
)

OUTPUT_SIZE = INPUT_SIZE

HIDDEN_SIZE = 64

NUM_LAYERS = 2

DROPOUT = 0.2

FEATURE_NAMES = [
    "vehicle_count",
    "car_count",
    "motorcycle_count",
    "bus_count",
    "truck_count",
    "queue_length_veh",
    "queue_length_m_est",
    "density_index"
]

SENSOR_START = 1

SENSOR_END = 12

RANDOM_SEED = 42


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# REPRODUCIBILITY
# ============================================================

def set_seed(
    seed=RANDOM_SEED
):

    np.random.seed(
        seed
    )

    torch.manual_seed(
        seed
    )

    if torch.cuda.is_available():

        torch.cuda.manual_seed_all(
            seed
        )

    torch.backends.cudnn.deterministic = True

    torch.backends.cudnn.benchmark = False


# ============================================================
# LSTM MODEL
# ============================================================

class TrafficLSTM(
    nn.Module
):

    def __init__(
        self,
        input_size,
        hidden_size=64,
        num_layers=2,
        output_size=96,
        dropout=0.2
    ):

        super().__init__()

        self.input_size = input_size

        self.hidden_size = hidden_size

        self.num_layers = num_layers

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
            )
        )

        self.dropout = nn.Dropout(
            dropout
        )

        self.output_layer = nn.Linear(
            hidden_size,
            output_size
        )

    def forward(
        self,
        x
    ):

        lstm_output, _ = self.lstm(
            x
        )

        last_output = (
            lstm_output[:, -1, :]
        )

        last_output = self.dropout(
            last_output
        )

        output = self.output_layer(
            last_output
        )

        return output


# ============================================================
# LOAD JSON
# ============================================================

def load_json(
    path
):

    if not path.exists():

        print(
            f"[WARNING] File tidak ditemukan:"
        )

        print(
            f"          {path}"
        )

        return None

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


# ============================================================
# LOAD CONFIGURATION
# ============================================================

def load_configuration():

    config = load_json(
        CONFIG_PATH
    )

    if config is not None:

        print(
            "[OK] yolo_config.json loaded."
        )

    else:

        print(
            "[WARNING] Menggunakan konfigurasi default."
        )

    return config


# ============================================================
# LOAD SCALER
# ============================================================

def load_scaler():

    if not SCALER_PATH.exists():

        raise FileNotFoundError(
            f"Scaler tidak ditemukan:\n"
            f"{SCALER_PATH}"
        )

    scaler = joblib.load(
        SCALER_PATH
    )

    print(
        "[OK] Scaler loaded."
    )

    print(
        f"[INFO] Scaler feature count : "
        f"{len(scaler.mean_)}"
    )

    if len(scaler.mean_) != INPUT_SIZE:

        raise ValueError(
            "Jumlah feature pada scaler tidak sesuai.\n"
            f"Expected : {INPUT_SIZE}\n"
            f"Got      : {len(scaler.mean_)}"
        )

    return scaler


# ============================================================
# LOAD TEST DATA
# ============================================================

def load_test_data():

    X_test_path = (
        PROCESSED_DIR
        / "X_test.npy"
    )

    y_test_path = (
        PROCESSED_DIR
        / "y_test.npy"
    )

    if not X_test_path.exists():

        raise FileNotFoundError(
            f"X_test tidak ditemukan:\n"
            f"{X_test_path}"
        )

    if not y_test_path.exists():

        raise FileNotFoundError(
            f"y_test tidak ditemukan:\n"
            f"{y_test_path}"
        )

    X_test = np.load(
        X_test_path
    ).astype(
        np.float32
    )

    y_test = np.load(
        y_test_path
    ).astype(
        np.float32
    )

    print("=" * 70)

    print(
        "TEST DATA"
    )

    print("=" * 70)

    print(
        f"[INFO] X_test : {X_test.shape}"
    )

    print(
        f"[INFO] y_test : {y_test.shape}"
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if X_test.ndim != 3:

        raise ValueError(
            "X_test harus memiliki 3 dimensi:\n"
            "(samples, sequence, features)"
        )

    if y_test.ndim != 2:

        raise ValueError(
            "y_test harus memiliki 2 dimensi:\n"
            "(samples, features)"
        )

    if X_test.shape[1] != SEQUENCE_LENGTH:

        raise ValueError(
            f"Sequence length tidak sesuai.\n"
            f"Expected : {SEQUENCE_LENGTH}\n"
            f"Got      : {X_test.shape[1]}"
        )

    if X_test.shape[2] != INPUT_SIZE:

        raise ValueError(
            f"Input feature count tidak sesuai.\n"
            f"Expected : {INPUT_SIZE}\n"
            f"Got      : {X_test.shape[2]}"
        )

    if y_test.shape[1] != OUTPUT_SIZE:

        raise ValueError(
            f"Output feature count tidak sesuai.\n"
            f"Expected : {OUTPUT_SIZE}\n"
            f"Got      : {y_test.shape[1]}"
        )

    if X_test.shape[0] != y_test.shape[0]:

        raise ValueError(
            "Jumlah sample X_test dan y_test berbeda."
        )

    if np.isnan(X_test).any():

        raise ValueError(
            "X_test mengandung NaN."
        )

    if np.isnan(y_test).any():

        raise ValueError(
            "y_test mengandung NaN."
        )

    if np.isinf(X_test).any():

        raise ValueError(
            "X_test mengandung Inf."
        )

    if np.isinf(y_test).any():

        raise ValueError(
            "y_test mengandung Inf."
        )

    print(
        "[OK] Test data valid."
    )

    return (
        X_test,
        y_test
    )


# ============================================================
# LOAD TRAINED MODEL
# ============================================================

def load_model():

    if not BEST_MODEL_PATH.exists():

        raise FileNotFoundError(
            f"Best model tidak ditemukan:\n"
            f"{BEST_MODEL_PATH}"
        )

    print("=" * 70)

    print(
        "MODEL LOADING"
    )

    print("=" * 70)

    print(
        f"[INFO] Model path:"
    )

    print(
        f"       {BEST_MODEL_PATH}"
    )

    model = TrafficLSTM(
        input_size=INPUT_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        output_size=OUTPUT_SIZE,
        dropout=DROPOUT
    )

    checkpoint = torch.load(
        BEST_MODEL_PATH,
        map_location=DEVICE
    )

    if (
        isinstance(
            checkpoint,
            dict
        )
        and "model_state_dict"
        in checkpoint
    ):

        model.load_state_dict(
            checkpoint[
                "model_state_dict"
            ]
        )

        best_epoch = checkpoint.get(
            "epoch",
            None
        )

        best_val_loss = checkpoint.get(
            "val_loss",
            None
        )

        print(
            "[OK] Checkpoint loaded."
        )

        if best_epoch is not None:

            print(
                f"[INFO] Best epoch    : "
                f"{best_epoch}"
            )

        if best_val_loss is not None:

            print(
                f"[INFO] Best val loss : "
                f"{best_val_loss:.6f}"
            )

    else:

        model.load_state_dict(
            checkpoint
        )

        print(
            "[OK] State dict loaded."
        )

    model = model.to(
        DEVICE
    )

    model.eval()

    parameter_count = sum(
        p.numel()
        for p in model.parameters()
    )

    print(
        f"[INFO] Parameters : "
        f"{parameter_count:,}"
    )

    return model


# ============================================================
# LOAD SAVED TEST PREDICTION
# ============================================================

def load_saved_prediction():

    if not PREDICTION_FILE.exists():

        print(
            "[WARNING] test_predictions.npz tidak ditemukan."
        )

        return None

    print("=" * 70)

    print(
        "LOADING SAVED PREDICTION"
    )

    print("=" * 70)

    data = np.load(
        PREDICTION_FILE
    )

    print(
        f"[INFO] NPZ keys : "
        f"{data.files}"
    )

    prediction = None

    # --------------------------------------------------------
    # Cari key prediction
    # --------------------------------------------------------

    possible_keys = [
        "prediction",
        "predictions",
        "y_pred",
        "test_predictions"
    ]

    for key in possible_keys:

        if key in data.files:

            prediction = data[key]

            print(
                f"[OK] Prediction loaded "
                f"from key: {key}"
            )

            break

    if prediction is None:

        print(
            "[WARNING] Tidak menemukan array prediction."
        )

        return None

    prediction = prediction.astype(
        np.float32
    )

    print(
        f"[INFO] Prediction shape : "
        f"{prediction.shape}"
    )

    return prediction


# ============================================================
# GENERATE PREDICTION
# ============================================================

def generate_prediction(
    model,
    X_test
):

    print("=" * 70)

    print(
        "GENERATING TEST PREDICTION"
    )

    print("=" * 70)

    input_tensor = torch.from_numpy(
        X_test
    ).float()

    input_tensor = input_tensor.to(
        DEVICE
    )

    start_time = time.time()

    with torch.no_grad():

        prediction = model(
            input_tensor
        )

    inference_time = (
        time.time()
        - start_time
    )

    prediction = (
        prediction
        .detach()
        .cpu()
        .numpy()
    )

    print(
        f"[INFO] Prediction shape : "
        f"{prediction.shape}"
    )

    print(
        f"[INFO] Inference time   : "
        f"{inference_time:.4f} seconds"
    )

    print(
        f"[INFO] Avg/sample       : "
        f"{inference_time / len(X_test):.6f} seconds"
    )

    return (
        prediction,
        inference_time
    )


# ============================================================
# INVERSE SCALING
# ============================================================

def inverse_transform(
    data,
    scaler,
    name
):

    print("=" * 70)

    print(
        f"INVERSE SCALING - {name}"
    )

    print("=" * 70)

    if data.ndim != 2:

        raise ValueError(
            f"{name} harus berbentuk "
            f"(samples, features).\n"
            f"Got: {data.shape}"
        )

    if data.shape[1] != INPUT_SIZE:

        raise ValueError(
            f"Jumlah feature {name} tidak sesuai.\n"
            f"Expected : {INPUT_SIZE}\n"
            f"Got      : {data.shape[1]}"
        )

    # --------------------------------------------------------
    # IMPORTANT
    #
    # YOLO scaler dibuat menggunakan 96 feature langsung.
    #
    # Jadi:
    #
    # (samples, 96)
    #
    # langsung inverse_transform.
    #
    # JANGAN reshape menjadi (sensor, feature).
    # --------------------------------------------------------

    result = scaler.inverse_transform(
        data
    )

    print(
        f"[OK] {name} berhasil "
        f"dikembalikan ke skala asli."
    )

    return result


# ============================================================
# SAFE MAPE
# ============================================================

def calculate_mape(
    actual,
    prediction
):

    actual = np.asarray(
        actual
    )

    prediction = np.asarray(
        prediction
    )

    mask = (
        np.abs(actual) > 1e-8
    )

    if not np.any(mask):

        return np.nan

    return (
        np.mean(
            np.abs(
                (
                    actual[mask]
                    - prediction[mask]
                )
                /
                np.abs(
                    actual[mask]
                )
            )
        )
        * 100
    )


# ============================================================
# SMAPE
# ============================================================

def calculate_smape(
    actual,
    prediction
):

    actual = np.asarray(
        actual
    )

    prediction = np.asarray(
        prediction
    )

    denominator = (
        np.abs(actual)
        + np.abs(prediction)
    )

    mask = (
        denominator > 1e-8
    )

    if not np.any(mask):

        return np.nan

    return (
        np.mean(
            2
            * np.abs(
                prediction[mask]
                - actual[mask]
            )
            /
            denominator[mask]
        )
        * 100
    )


# ============================================================
# CALCULATE METRICS
# ============================================================

def calculate_metrics(
    actual,
    prediction
):

    actual_flat = actual.reshape(
        -1
    )

    prediction_flat = prediction.reshape(
        -1
    )

    mae = mean_absolute_error(
        actual_flat,
        prediction_flat
    )

    mse = mean_squared_error(
        actual_flat,
        prediction_flat
    )

    rmse = np.sqrt(
        mse
    )

    r2 = r2_score(
        actual_flat,
        prediction_flat
    )

    mape = calculate_mape(
        actual_flat,
        prediction_flat
    )

    smape = calculate_smape(
        actual_flat,
        prediction_flat
    )

    return {
        "MAE": float(mae),
        "MSE": float(mse),
        "RMSE": float(rmse),
        "MAPE_percent": (
            float(mape)
            if not np.isnan(mape)
            else None
        ),
        "sMAPE_percent": (
            float(smape)
            if not np.isnan(smape)
            else None
        ),
        "R2": float(r2)
    }


# ============================================================
# OVERALL METRICS
# ============================================================

def evaluate_overall(
    actual,
    prediction
):

    print("=" * 70)

    print(
        "OVERALL TEST EVALUATION"
    )

    print("=" * 70)

    metrics = calculate_metrics(
        actual,
        prediction
    )

    print()

    print(
        "[OVERALL TEST METRICS]"
    )

    print(
        f"MAE   : "
        f"{metrics['MAE']:.6f}"
    )

    print(
        f"MSE   : "
        f"{metrics['MSE']:.6f}"
    )

    print(
        f"RMSE  : "
        f"{metrics['RMSE']:.6f}"
    )

    print(
        f"MAPE  : "
        f"{metrics['MAPE_percent']:.4f}%"
    )

    print(
        f"sMAPE : "
        f"{metrics['sMAPE_percent']:.4f}%"
    )

    print(
        f"R2    : "
        f"{metrics['R2']:.6f}"
    )

    return metrics


# ============================================================
# PER FEATURE
# ============================================================

def evaluate_per_feature(
    actual,
    prediction
):

    print("=" * 70)

    print(
        "EVALUATION PER FEATURE"
    )

    print("=" * 70)

    rows = []

    for feature_index, feature_name in enumerate(
        FEATURE_NAMES
    ):

        # ----------------------------------------------------
        # Ambil feature dari setiap sensor
        #
        # Layout:
        #
        # sensor 1:
        #   feature 0..7
        #
        # sensor 2:
        #   feature 0..7
        #
        # ...
        #
        # ----------------------------------------------------

        indices = np.arange(
            feature_index,
            INPUT_SIZE,
            FEATURES_PER_SENSOR
        )

        actual_feature = (
            actual[:, indices]
            .reshape(-1)
        )

        prediction_feature = (
            prediction[:, indices]
            .reshape(-1)
        )

        metrics = calculate_metrics(
            actual_feature,
            prediction_feature
        )

        rows.append(
            {
                "feature": feature_name,
                "MAE": metrics["MAE"],
                "MSE": metrics["MSE"],
                "RMSE": metrics["RMSE"],
                "MAPE_percent": metrics[
                    "MAPE_percent"
                ],
                "sMAPE_percent": metrics[
                    "sMAPE_percent"
                ],
                "R2": metrics["R2"]
            }
        )

    dataframe = pd.DataFrame(
        rows
    )

    print()

    print(
        dataframe.to_string(
            index=False,
            float_format=lambda x:
                f"{x:.6f}"
        )
    )

    output_path = (
        METRICS_DIR
        / "evaluation_per_feature.csv"
    )

    dataframe.to_csv(
        output_path,
        index=False
    )

    print()

    print(
        f"[SAVED] {output_path}"
    )

    return dataframe


# ============================================================
# PER SENSOR
# ============================================================

def evaluate_per_sensor(
    actual,
    prediction
):

    print("=" * 70)

    print(
        "EVALUATION PER SENSOR"
    )

    print("=" * 70)

    rows = []

    for sensor_index in range(
        NUM_SENSORS
    ):

        start = (
            sensor_index
            * FEATURES_PER_SENSOR
        )

        end = (
            start
            + FEATURES_PER_SENSOR
        )

        actual_sensor = (
            actual[:, start:end]
            .reshape(-1)
        )

        prediction_sensor = (
            prediction[:, start:end]
            .reshape(-1)
        )

        metrics = calculate_metrics(
            actual_sensor,
            prediction_sensor
        )

        sensor_id = (
            SENSOR_START
            + sensor_index
        )

        rows.append(
            {
                "sensor": sensor_id,
                "MAE": metrics["MAE"],
                "MSE": metrics["MSE"],
                "RMSE": metrics["RMSE"],
                "MAPE_percent": metrics[
                    "MAPE_percent"
                ],
                "sMAPE_percent": metrics[
                    "sMAPE_percent"
                ],
                "R2": metrics["R2"]
            }
        )

    dataframe = pd.DataFrame(
        rows
    )

    print()

    print(
        dataframe.to_string(
            index=False,
            float_format=lambda x:
                f"{x:.6f}"
        )
    )

    output_path = (
        METRICS_DIR
        / "evaluation_per_sensor.csv"
    )

    dataframe.to_csv(
        output_path,
        index=False
    )

    print()

    print(
        f"[SAVED] {output_path}"
    )

    return dataframe


# ============================================================
# PER SENSOR + FEATURE
# ============================================================

def evaluate_sensor_feature(
    actual,
    prediction
):

    print("=" * 70)

    print(
        "EVALUATION PER SENSOR + FEATURE"
    )

    print("=" * 70)

    rows = []

    for sensor_index in range(
        NUM_SENSORS
    ):

        sensor_id = (
            SENSOR_START
            + sensor_index
        )

        base_index = (
            sensor_index
            * FEATURES_PER_SENSOR
        )

        for feature_index, feature_name in enumerate(
            FEATURE_NAMES
        ):

            column_index = (
                base_index
                + feature_index
            )

            actual_values = (
                actual[:, column_index]
            )

            prediction_values = (
                prediction[:, column_index]
            )

            metrics = calculate_metrics(
                actual_values,
                prediction_values
            )

            rows.append(
                {
                    "sensor": sensor_id,
                    "feature": feature_name,
                    "MAE": metrics["MAE"],
                    "MSE": metrics["MSE"],
                    "RMSE": metrics["RMSE"],
                    "MAPE_percent": metrics[
                        "MAPE_percent"
                    ],
                    "sMAPE_percent": metrics[
                        "sMAPE_percent"
                    ],
                    "R2": metrics["R2"]
                }
            )

    dataframe = pd.DataFrame(
        rows
    )

    output_path = (
        METRICS_DIR
        / "evaluation_sensor_feature.csv"
    )

    dataframe.to_csv(
        output_path,
        index=False
    )

    print(
        f"[SAVED] {output_path}"
    )

    return dataframe


# ============================================================
# SAVE PREDICTION COMPARISON
# ============================================================

def save_prediction_comparison(
    actual,
    prediction
):

    rows = []

    # --------------------------------------------------------
    # Simpan beberapa sample pertama.
    #
    # Ini bukan untuk menggantikan seluruh hasil evaluasi.
    # Hanya untuk inspeksi.
    # --------------------------------------------------------

    max_samples = min(
        100,
        actual.shape[0]
    )

    for sample_index in range(
        max_samples
    ):

        for sensor_index in range(
            NUM_SENSORS
        ):

            sensor_id = (
                SENSOR_START
                + sensor_index
            )

            base_index = (
                sensor_index
                * FEATURES_PER_SENSOR
            )

            row = {
                "sample": sample_index,
                "sensor": sensor_id
            }

            for feature_index, feature_name in enumerate(
                FEATURE_NAMES
            ):

                column_index = (
                    base_index
                    + feature_index
                )

                row[
                    f"actual_{feature_name}"
                ] = float(
                    actual[
                        sample_index,
                        column_index
                    ]
                )

                row[
                    f"predicted_{feature_name}"
                ] = float(
                    prediction[
                        sample_index,
                        column_index
                    ]
                )

            rows.append(
                row
            )

    dataframe = pd.DataFrame(
        rows
    )

    output_path = (
        METRICS_DIR
        / "prediction_comparison.csv"
    )

    dataframe.to_csv(
        output_path,
        index=False
    )

    print(
        f"[SAVED] {output_path}"
    )

    return dataframe


# ============================================================
# SAVE NUMPY RESULTS
# ============================================================

def save_evaluation_arrays(
    actual,
    prediction
):

    output_path = (
        METRICS_DIR
        / "evaluation_arrays.npz"
    )

    np.savez(
        output_path,
        actual=actual,
        prediction=prediction
    )

    print(
        f"[SAVED] {output_path}"
    )


# ============================================================
# PLOT ACTUAL VS PREDICTION
# ============================================================

def plot_feature_prediction(
    actual,
    prediction,
    sensor_index=0,
    feature_index=0,
    max_points=200
):

    sensor_id = (
        SENSOR_START
        + sensor_index
    )

    feature_name = (
        FEATURE_NAMES[
            feature_index
        ]
    )

    column_index = (
        sensor_index
        * FEATURES_PER_SENSOR
        + feature_index
    )

    actual_values = (
        actual[
            :max_points,
            column_index
        ]
    )

    prediction_values = (
        prediction[
            :max_points,
            column_index
        ]
    )

    plt.figure(
        figsize=(12, 5)
    )

    plt.plot(
        actual_values,
        label="Actual"
    )

    plt.plot(
        prediction_values,
        label="Prediction"
    )

    plt.title(
        f"Actual vs Prediction - "
        f"Sensor {sensor_id} - "
        f"{feature_name}"
    )

    plt.xlabel(
        "Test sample"
    )

    plt.ylabel(
        feature_name
    )

    plt.legend()

    plt.grid(
        alpha=0.3
    )

    plt.tight_layout()

    filename = (
        f"actual_vs_prediction_"
        f"sensor_{sensor_id}_"
        f"{feature_name}.png"
    )

    output_path = (
        PLOTS_DIR
        / filename
    )

    plt.savefig(
        output_path,
        dpi=150
    )

    plt.close()

    print(
        f"[SAVED] {output_path}"
    )


# ============================================================
# PLOT ALL FEATURES - SENSOR 1
# ============================================================

def plot_all_features_sensor(
    actual,
    prediction,
    sensor_index=0,
    max_points=200
):

    sensor_id = (
        SENSOR_START
        + sensor_index
    )

    for feature_index in range(
        FEATURES_PER_SENSOR
    ):

        plot_feature_prediction(
            actual=actual,
            prediction=prediction,
            sensor_index=sensor_index,
            feature_index=feature_index,
            max_points=max_points
        )


# ============================================================
# SAVE SUMMARY JSON
# ============================================================

def save_summary(
    overall_metrics,
    feature_metrics,
    sensor_metrics,
    inference_time,
    prediction_source
):

    summary = {

        "dataset": DATASET_NAME,

        "intersection": INTERSECTION_ID,

        "evaluation_type": (
            "chronological held-out test set"
        ),

        "sequence_length": (
            SEQUENCE_LENGTH
        ),

        "forecast_horizon": (
            FORECAST_HORIZON
        ),

        "sensors": {
            "start": SENSOR_START,
            "end": SENSOR_END,
            "count": NUM_SENSORS
        },

        "features_per_sensor": (
            FEATURES_PER_SENSOR
        ),

        "input_size": (
            INPUT_SIZE
        ),

        "output_size": (
            OUTPUT_SIZE
        ),

        "features": FEATURE_NAMES,

        "model": {

            "type": "LSTM",

            "hidden_size": (
                HIDDEN_SIZE
            ),

            "num_layers": (
                NUM_LAYERS
            ),

            "dropout": (
                DROPOUT
            )
        },

        "prediction_source": (
            prediction_source
        ),

        "inference_time_seconds": (
            float(inference_time)
        ),

        "overall_metrics": (
            overall_metrics
        ),

        "feature_metrics": (
            feature_metrics.to_dict(
                orient="records"
            )
        ),

        "sensor_metrics": (
            sensor_metrics.to_dict(
                orient="records"
            )
        )
    }

    output_path = (
        METRICS_DIR
        / "evaluation_summary.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=4
        )

    print(
        f"[SAVED] {output_path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    set_seed()

    print("=" * 70)

    print(
        "YOLO TRAFFIC LSTM EVALUATION"
    )

    print("=" * 70)

    print(
        f"[INFO] Device : {DEVICE}"
    )

    print()

    print("=" * 70)

    print(
        "EVALUATION CONFIGURATION"
    )

    print("=" * 70)

    print(
        f"[INFO] Dataset          : "
        f"{DATASET_NAME}"
    )

    print(
        f"[INFO] Intersection     : "
        f"{INTERSECTION_ID}"
    )

    print(
        f"[INFO] Sensors          : "
        f"{NUM_SENSORS}"
    )

    print(
        f"[INFO] Features/sensor  : "
        f"{FEATURES_PER_SENSOR}"
    )

    print(
        f"[INFO] Input size       : "
        f"{INPUT_SIZE}"
    )

    print(
        f"[INFO] Output size      : "
        f"{OUTPUT_SIZE}"
    )

    print(
        f"[INFO] Sequence length  : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[INFO] Forecast horizon : "
        f"{FORECAST_HORIZON}"
    )

    print()

    print(
        "[INFO] Features:"
    )

    for feature in FEATURE_NAMES:

        print(
            f"       - {feature}"
        )

    # --------------------------------------------------------
    # Configuration
    # --------------------------------------------------------

    load_configuration()

    # --------------------------------------------------------
    # Scaler
    # --------------------------------------------------------

    scaler = load_scaler()

    # --------------------------------------------------------
    # Test data
    # --------------------------------------------------------

    (
        X_test,
        y_test_scaled
    ) = load_test_data()

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = load_model()

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    saved_prediction = (
        load_saved_prediction()
    )

    prediction_source = (
        "saved test_predictions.npz"
    )

    if saved_prediction is not None:

        # ----------------------------------------------------
        # Pastikan shape sesuai
        # ----------------------------------------------------

        if (
            saved_prediction.shape
            != y_test_scaled.shape
        ):

            print(
                "[WARNING] Shape prediction "
                "tidak sesuai dengan y_test."
            )

            print(
                f"[INFO] Prediction : "
                f"{saved_prediction.shape}"
            )

            print(
                f"[INFO] y_test     : "
                f"{y_test_scaled.shape}"
            )

            print(
                "[INFO] Prediction akan "
                "digenerate ulang dari best model."
            )

            (
                prediction_scaled,
                inference_time
            ) = generate_prediction(
                model=model,
                X_test=X_test
            )

            prediction_source = (
                "best_model.pth"
            )

        else:

            prediction_scaled = (
                saved_prediction
            )

            inference_time = 0.0

            print(
                "[OK] Menggunakan prediction "
                "dari training."
            )

    else:

        (
            prediction_scaled,
            inference_time
        ) = generate_prediction(
            model=model,
            X_test=X_test
        )

        prediction_source = (
            "best_model.pth"
        )

    # --------------------------------------------------------
    # Inverse scaling
    # --------------------------------------------------------

    y_test_original = (
        inverse_transform(
            data=y_test_scaled,
            scaler=scaler,
            name="y_test"
        )
    )

    prediction_original = (
        inverse_transform(
            data=prediction_scaled,
            scaler=scaler,
            name="prediction"
        )
    )

    # --------------------------------------------------------
    # Physical cleaning
    #
    # Semua traffic count/density/queue
    # tidak boleh negatif.
    # --------------------------------------------------------

    y_test_original = np.maximum(
        y_test_original,
        0
    )

    prediction_original = np.maximum(
        prediction_original,
        0
    )

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    overall_metrics = (
        evaluate_overall(
            actual=y_test_original,
            prediction=prediction_original
        )
    )

    # --------------------------------------------------------
    # Feature
    # --------------------------------------------------------

    feature_metrics = (
        evaluate_per_feature(
            actual=y_test_original,
            prediction=prediction_original
        )
    )

    # --------------------------------------------------------
    # Sensor
    # --------------------------------------------------------

    sensor_metrics = (
        evaluate_per_sensor(
            actual=y_test_original,
            prediction=prediction_original
        )
    )

    # --------------------------------------------------------
    # Sensor + feature
    # --------------------------------------------------------

    evaluate_sensor_feature(
        actual=y_test_original,
        prediction=prediction_original
    )

    # --------------------------------------------------------
    # Comparison
    # --------------------------------------------------------

    save_prediction_comparison(
        actual=y_test_original,
        prediction=prediction_original
    )

    # --------------------------------------------------------
    # Arrays
    # --------------------------------------------------------

    save_evaluation_arrays(
        actual=y_test_original,
        prediction=prediction_original
    )

    # --------------------------------------------------------
    # Plot
    #
    # Sensor 1, semua feature.
    # --------------------------------------------------------

    plot_all_features_sensor(
        actual=y_test_original,
        prediction=prediction_original,
        sensor_index=0,
        max_points=200
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    save_summary(
        overall_metrics=overall_metrics,
        feature_metrics=feature_metrics,
        sensor_metrics=sensor_metrics,
        inference_time=inference_time,
        prediction_source=prediction_source
    )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print()

    print("=" * 70)

    print(
        "YOLO LSTM EVALUATION COMPLETED"
    )

    print("=" * 70)

    print()

    print(
        "[OVERALL TEST RESULT]"
    )

    print(
        f"MAE   : "
        f"{overall_metrics['MAE']:.6f}"
    )

    print(
        f"MSE   : "
        f"{overall_metrics['MSE']:.6f}"
    )

    print(
        f"RMSE  : "
        f"{overall_metrics['RMSE']:.6f}"
    )

    print(
        f"MAPE  : "
        f"{overall_metrics['MAPE_percent']:.4f}%"
    )

    print(
        f"sMAPE : "
        f"{overall_metrics['sMAPE_percent']:.4f}%"
    )

    print(
        f"R2    : "
        f"{overall_metrics['R2']:.6f}"
    )

    print()

    print(
        "[OUTPUT]"
    )

    print(
        f"[SAVED] "
        f"{METRICS_DIR / 'evaluation_per_feature.csv'}"
    )

    print(
        f"[SAVED] "
        f"{METRICS_DIR / 'evaluation_per_sensor.csv'}"
    )

    print(
        f"[SAVED] "
        f"{METRICS_DIR / 'evaluation_sensor_feature.csv'}"
    )

    print(
        f"[SAVED] "
        f"{METRICS_DIR / 'prediction_comparison.csv'}"
    )

    print(
        f"[SAVED] "
        f"{METRICS_DIR / 'evaluation_arrays.npz'}"
    )

    print(
        f"[SAVED] "
        f"{METRICS_DIR / 'evaluation_summary.json'}"
    )

    print()

    print(
        f"[PLOTS]"
    )

    print(
        f"[SAVED] "
        f"{PLOTS_DIR}"
    )

    print()

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()