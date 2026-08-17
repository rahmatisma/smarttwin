"""
======================================================================
YOLO TRAFFIC LSTM EVALUATION
======================================================================

Purpose:
    Evaluate the trained YOLO Traffic LSTM baseline model.

Pipeline:
    1. Load processed test dataset
    2. Load training configuration
    3. Load scaler
    4. Load best LSTM model
    5. Generate predictions
    6. Validate numerical outputs
    7. Calculate scaled-space metrics
    8. Inverse transform predictions and targets
    9. Calculate original-space metrics
    10. Evaluate per traffic feature
    11. Evaluate per sensor
    12. Save prediction results
    13. Save evaluation reports
    14. Generate plots

Expected directory:

    outputs/
    └── yolo/
        ├── processed/
        │   ├── X_test.npy
        │   ├── y_test.npy
        │   ├── scaler_X.pkl
        │   ├── scaler_y.pkl              # optional but recommended
        │   ├── feature_metadata.json
        │   └── ...
        │
        ├── models/
        │   ├── best_model.pt
        │   ├── training_config.json
        │   └── training_history.json
        │
        └── evaluation/
            ├── plots/
            └── ...
======================================================================
"""

from pathlib import Path
import json
import pickle
import warnings

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

import matplotlib.pyplot as plt

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)

warnings.filterwarnings("ignore")


# ======================================================================
# PATH CONFIGURATION
# ======================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
FORECASTING_DIR = SCRIPT_DIR.parent.parent

OUTPUT_DIR = (
    FORECASTING_DIR
    / "outputs"
    / "yolo"
)

PROCESSED_DIR = (
    OUTPUT_DIR
    / "processed"
)

MODEL_DIR = (
    OUTPUT_DIR
    / "models"
)

EVALUATION_DIR = (
    OUTPUT_DIR
    / "evaluation"
)

PLOT_DIR = (
    EVALUATION_DIR
    / "plots"
)

EVALUATION_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PLOT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ======================================================================
# FILE PATHS
# ======================================================================

X_TEST_PATH = (
    PROCESSED_DIR
    / "X_test.npy"
)

Y_TEST_PATH = (
    PROCESSED_DIR
    / "y_test.npy"
)

# Recommended:
# scaler_y.pkl should be the scaler used for target y.
SCALER_Y_PATH = (
    PROCESSED_DIR
    / "scaler_y.pkl"
)

# Fallback for pipelines that intentionally use
# one scaler for both X and y.
SCALER_X_PATH = (
    PROCESSED_DIR
    / "scaler_X.pkl"
)

MODEL_PATH = (
    MODEL_DIR
    / "best_model.pt"
)

CONFIG_PATH = (
    MODEL_DIR
    / "training_config.json"
)

HISTORY_PATH = (
    MODEL_DIR
    / "training_history.json"
)

FEATURE_METADATA_PATH = (
    PROCESSED_DIR
    / "feature_metadata.json"
)


# ======================================================================
# DEFAULT SENSOR / FEATURE CONFIGURATION
# ======================================================================

APPROACHES = [
    "north",
    "east",
    "south",
    "west",
]

LANES = [
    "lane_1",
    "lane_2",
    "lane_3",
]

FEATURES = [
    "vehicle_count",
    "car_count",
    "motorcycle_count",
    "bus_count",
    "truck_count",
    "queue_length_veh",
    "queue_length_m_est",
    "density_index",
]

NUM_SENSORS = 12
NUM_FEATURES = 8

EXPECTED_OUTPUT_SIZE = (
    NUM_SENSORS
    * NUM_FEATURES
)


# ======================================================================
# UTILITY
# ======================================================================

def print_header(title):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_subheader(title):

    print()
    print("-" * 70)
    print(title)
    print("-" * 70)


def ensure_file(
    path,
    description,
):

    if not path.exists():

        raise FileNotFoundError(
            f"\n[ERROR] {description} tidak ditemukan:\n"
            f"        {path}\n"
        )


def save_json(
    data,
    path,
):

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False,
            default=str,
        )


# ======================================================================
# LOAD TRAINING CONFIG
# ======================================================================

def load_training_config():

    print_header(
        "LOADING TRAINING CONFIGURATION"
    )

    ensure_file(
        CONFIG_PATH,
        "Training configuration",
    )

    with open(
        CONFIG_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        config = json.load(f)

    if not isinstance(
        config,
        dict,
    ):

        raise ValueError(
            "training_config.json harus berupa JSON object."
        )

    print(
        "[INFO] Training configuration:"
    )

    print(
        f"       Dataset          : "
        f"{config.get('dataset', 'N/A')}"
    )

    print(
        f"       Model            : "
        f"{config.get('model', 'N/A')}"
    )

    print(
        f"       Input size       : "
        f"{config.get('input_size', 'N/A')}"
    )

    print(
        f"       Output size      : "
        f"{config.get('output_size', 'N/A')}"
    )

    print(
        f"       Sequence length  : "
        f"{config.get('sequence_length', 'N/A')}"
    )

    print(
        f"       Forecast horizon : "
        f"{config.get('forecast_horizon', 'N/A')} second"
    )

    print(
        f"       Hidden size      : "
        f"{config.get('hidden_size', 'N/A')}"
    )

    print(
        f"       LSTM layers      : "
        f"{config.get('num_layers', 'N/A')}"
    )

    print(
        f"       Dropout          : "
        f"{config.get('dropout', 'N/A')}"
    )

    print(
        f"       Batch size       : "
        f"{config.get('batch_size', 'N/A')}"
    )

    print(
        f"       Learning rate    : "
        f"{config.get('learning_rate', 'N/A')}"
    )

    print(
        f"       Device           : "
        f"{config.get('device', 'N/A')}"
    )

    print(
        "[OK] Training configuration loaded."
    )

    return config


# ======================================================================
# LOAD TEST DATA
# ======================================================================

def load_test_data():

    print_header(
        "LOADING TEST DATA"
    )

    ensure_file(
        X_TEST_PATH,
        "X_test.npy",
    )

    ensure_file(
        Y_TEST_PATH,
        "y_test.npy",
    )

    X_test = np.load(
        X_TEST_PATH
    )

    y_test = np.load(
        Y_TEST_PATH
    )

    print(
        f"[INFO] X_test : {X_test.shape}"
    )

    print(
        f"[INFO] y_test : {y_test.shape}"
    )

    return (
        X_test,
        y_test,
    )


# ======================================================================
# NUMERICAL VALIDATION
# ======================================================================

def validate_test_data(
    X_test,
    y_test,
):

    print_header(
        "NUMERICAL DATA VALIDATION"
    )

    x_nan = int(
        np.isnan(X_test).sum()
    )

    x_inf = int(
        np.isinf(X_test).sum()
    )

    y_nan = int(
        np.isnan(y_test).sum()
    )

    y_inf = int(
        np.isinf(y_test).sum()
    )

    print(
        f"[INFO] X_test | NaN: {x_nan} | Inf: {x_inf}"
    )

    print(
        f"[INFO] y_test | NaN: {y_nan} | Inf: {y_inf}"
    )

    if x_nan > 0:

        raise ValueError(
            "X_test mengandung NaN."
        )

    if x_inf > 0:

        raise ValueError(
            "X_test mengandung Inf."
        )

    if y_nan > 0:

        raise ValueError(
            "y_test mengandung NaN."
        )

    if y_inf > 0:

        raise ValueError(
            "y_test mengandung Inf."
        )

    print(
        "[OK] Test dataset numerically valid."
    )


# ======================================================================
# LOAD TARGET SCALER
# ======================================================================

def load_scaler():

    print_header(
        "LOADING TARGET SCALER"
    )

    # --------------------------------------------------------------
    # Prefer scaler_y.pkl
    # --------------------------------------------------------------

    if SCALER_Y_PATH.exists():

        scaler_path = SCALER_Y_PATH

        print(
            "[INFO] Menggunakan scaler_y.pkl"
        )

    # --------------------------------------------------------------
    # Fallback to scaler_X.pkl
    # --------------------------------------------------------------

    elif SCALER_X_PATH.exists():

        scaler_path = SCALER_X_PATH

        print(
            "[WARN] scaler_y.pkl tidak ditemukan."
        )

        print(
            "[WARN] Menggunakan scaler_X.pkl sebagai fallback."
        )

        print(
            "[WARN] Pastikan scaler_X memang digunakan "
            "untuk target y saat preprocessing."
        )

    else:

        raise FileNotFoundError(
            "\n[ERROR] Scaler tidak ditemukan.\n"
            f"Dicari:\n"
            f"  {SCALER_Y_PATH}\n"
            f"  {SCALER_X_PATH}\n"
        )

    with open(
        scaler_path,
        "rb",
    ) as f:

        scaler = pickle.load(f)

    print(
        f"[INFO] Scaler path : {scaler_path}"
    )

    print(
        f"[INFO] Scaler type : "
        f"{type(scaler).__name__}"
    )

    # --------------------------------------------------------------
    # Validate scaler feature count when available
    # --------------------------------------------------------------

    if hasattr(
        scaler,
        "n_features_in_",
    ):

        print(
            f"[INFO] Scaler features : "
            f"{scaler.n_features_in_}"
        )

    print(
        "[OK] Scaler loaded."
    )

    return (
        scaler,
        scaler_path,
    )


# ======================================================================
# MODEL
# ======================================================================

class TrafficLSTM(
    nn.Module
):

    def __init__(
        self,
        input_size,
        hidden_size,
        num_layers,
        dropout,
        output_size,
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

        self.fc = nn.Linear(
            hidden_size,
            output_size,
        )

    def forward(
        self,
        x,
    ):

        output, _ = self.lstm(x)

        last_output = (
            output[:, -1, :]
        )

        prediction = self.fc(
            last_output
        )

        return prediction


# ======================================================================
# DEVICE
# ======================================================================

def get_device(
    config
):

    configured_device = str(
        config.get(
            "device",
            "cpu",
        )
    ).lower()

    if (
        configured_device == "cuda"
        and torch.cuda.is_available()
    ):

        device = torch.device(
            "cuda"
        )

    else:

        device = torch.device(
            "cpu"
        )

        if configured_device == "cuda":

            print(
                "[WARN] Config meminta CUDA, "
                "tetapi CUDA tidak tersedia."
            )

            print(
                "[WARN] Evaluation menggunakan CPU."
            )

    print(
        f"[INFO] Evaluation device : {device}"
    )

    return device


# ======================================================================
# LOAD MODEL
# ======================================================================

def load_model(
    config,
    device,
):

    print_header(
        "LOADING BEST MODEL"
    )

    ensure_file(
        MODEL_PATH,
        "Best model",
    )

    input_size = int(
        config["input_size"]
    )

    hidden_size = int(
        config["hidden_size"]
    )

    num_layers = int(
        config["num_layers"]
    )

    dropout = float(
        config["dropout"]
    )

    output_size = int(
        config["output_size"]
    )

    model = TrafficLSTM(
        input_size=input_size,
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        output_size=output_size,
    )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=device,
        weights_only=False,
    )

    # --------------------------------------------------------------
    # Support several checkpoint formats
    # --------------------------------------------------------------

    if isinstance(
        checkpoint,
        dict,
    ):

        if "model_state_dict" in checkpoint:

            state_dict = checkpoint[
                "model_state_dict"
            ]

        elif "state_dict" in checkpoint:

            state_dict = checkpoint[
                "state_dict"
            ]

        else:

            # Assume checkpoint itself is state_dict
            state_dict = checkpoint

    else:

        state_dict = checkpoint

    if not isinstance(
        state_dict,
        dict,
    ):

        raise ValueError(
            "Format checkpoint model tidak dikenali."
        )

    # --------------------------------------------------------------
    # Remove possible DataParallel prefix
    # --------------------------------------------------------------

    cleaned_state_dict = {}

    for key, value in state_dict.items():

        if key.startswith(
            "module."
        ):

            new_key = key[
                len("module.") :
            ]

        else:

            new_key = key

        cleaned_state_dict[
            new_key
        ] = value

    model.load_state_dict(
        cleaned_state_dict
    )

    model.to(device)

    model.eval()

    print(
        "[INFO] Model : TrafficLSTM"
    )

    print(
        f"[INFO] Input size  : {input_size}"
    )

    print(
        f"[INFO] Hidden size : {hidden_size}"
    )

    print(
        f"[INFO] Layers      : {num_layers}"
    )

    print(
        f"[INFO] Dropout     : {dropout}"
    )

    print(
        f"[INFO] Output size : {output_size}"
    )

    print(
        f"[INFO] Device      : {device}"
    )

    print(
        "[OK] Best model loaded."
    )

    return model


# ======================================================================
# PREDICTION
# ======================================================================

def generate_predictions(
    model,
    X_test,
    device,
    batch_size=32,
):

    print_header(
        "GENERATING TEST PREDICTIONS"
    )

    X_tensor = torch.tensor(
        X_test,
        dtype=torch.float32,
    )

    dataset = (
        torch.utils.data.TensorDataset(
            X_tensor
        )
    )

    loader = (
        torch.utils.data.DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=False,
        )
    )

    predictions = []

    with torch.no_grad():

        for batch in loader:

            X_batch = (
                batch[0]
                .to(device)
            )

            output = model(
                X_batch
            )

            predictions.append(
                output
                .cpu()
                .numpy()
            )

    if not predictions:

        raise ValueError(
            "Tidak ada prediction yang dihasilkan."
        )

    predictions = np.concatenate(
        predictions,
        axis=0,
    )

    print(
        f"[INFO] Prediction shape : "
        f"{predictions.shape}"
    )

    print(
        "[OK] Prediction completed."
    )

    return predictions


# ======================================================================
# SHAPE VALIDATION
# ======================================================================

def validate_prediction_shape(
    predictions,
    y_test,
):

    print_header(
        "PREDICTION SHAPE VALIDATION"
    )

    print(
        f"[INFO] Prediction : "
        f"{predictions.shape}"
    )

    print(
        f"[INFO] Actual     : "
        f"{y_test.shape}"
    )

    if predictions.shape != y_test.shape:

        raise ValueError(
            "\nPrediction shape tidak sama dengan y_test.\n"
            f"Prediction : {predictions.shape}\n"
            f"y_test     : {y_test.shape}\n"
        )

    print(
        "[OK] Prediction shape validation passed."
    )


# ======================================================================
# METRICS
# ======================================================================

def calculate_metrics(
    y_true,
    y_pred,
):

    y_true_flat = (
        np.asarray(y_true)
        .reshape(-1)
    )

    y_pred_flat = (
        np.asarray(y_pred)
        .reshape(-1)
    )

    mse = mean_squared_error(
        y_true_flat,
        y_pred_flat,
    )

    rmse = np.sqrt(
        mse
    )

    mae = mean_absolute_error(
        y_true_flat,
        y_pred_flat,
    )

    return {
        "mse": float(mse),
        "rmse": float(rmse),
        "mae": float(mae),
    }


# ======================================================================
# SCALED METRICS
# ======================================================================

def evaluate_scaled(
    y_test,
    predictions,
):

    print_header(
        "EVALUATION - SCALED SPACE"
    )

    metrics = calculate_metrics(
        y_test,
        predictions,
    )

    print(
        f"[SCALED] MSE  : "
        f"{metrics['mse']:.6f}"
    )

    print(
        f"[SCALED] RMSE : "
        f"{metrics['rmse']:.6f}"
    )

    print(
        f"[SCALED] MAE  : "
        f"{metrics['mae']:.6f}"
    )

    return metrics


# ======================================================================
# INVERSE TRANSFORM
# ======================================================================

def inverse_transform_targets(
    scaler,
    y_test,
    predictions,
):

    print_header(
        "INVERSE TRANSFORM TO ORIGINAL SCALE"
    )

    n_samples = (
        y_test.shape[0]
    )

    n_features = (
        y_test.shape[1]
    )

    print(
        f"[INFO] Samples  : {n_samples}"
    )

    print(
        f"[INFO] Features : {n_features}"
    )

    # --------------------------------------------------------------
    # Validate scaler dimension when possible
    # --------------------------------------------------------------

    if hasattr(
        scaler,
        "n_features_in_",
    ):

        scaler_features = int(
            scaler.n_features_in_
        )

        if (
            scaler_features
            != n_features
        ):

            raise ValueError(
                "\nJumlah feature scaler tidak cocok "
                "dengan y_test.\n"
                f"Scaler : {scaler_features}\n"
                f"y_test: {n_features}\n"
            )

    y_true_original = (
        scaler.inverse_transform(
            y_test
        )
    )

    y_pred_original = (
        scaler.inverse_transform(
            predictions
        )
    )

    print(
        f"[INFO] Actual original shape : "
        f"{y_true_original.shape}"
    )

    print(
        f"[INFO] Prediction original shape : "
        f"{y_pred_original.shape}"
    )

    print(
        "[OK] Inverse transform completed."
    )

    return (
        y_true_original,
        y_pred_original,
    )


# ======================================================================
# ORIGINAL SCALE METRICS
# ======================================================================

def evaluate_original_scale(
    y_true,
    y_pred,
):

    print_header(
        "EVALUATION - ORIGINAL TRAFFIC SCALE"
    )

    metrics = calculate_metrics(
        y_true,
        y_pred,
    )

    print(
        f"[TEST] MSE  : "
        f"{metrics['mse']:.6f}"
    )

    print(
        f"[TEST] RMSE : "
        f"{metrics['rmse']:.6f}"
    )

    print(
        f"[TEST] MAE  : "
        f"{metrics['mae']:.6f}"
    )

    return metrics


# ======================================================================
# FEATURE METADATA LOADER
# ======================================================================

def load_feature_metadata():

    print_header(
        "LOADING FEATURE METADATA"
    )

    ensure_file(
        FEATURE_METADATA_PATH,
        "Feature metadata",
    )

    with open(
        FEATURE_METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        metadata = json.load(f)

    if not isinstance(
        metadata,
        dict,
    ):

        raise ValueError(
            "feature_metadata.json harus berupa dictionary."
        )

    if "features" not in metadata:

        raise ValueError(
            "feature_metadata.json tidak memiliki key 'features'."
        )

    feature_metadata = (
        metadata["features"]
    )

    if not isinstance(
        feature_metadata,
        list,
    ):

        raise ValueError(
            "metadata['features'] harus berupa list."
        )

    if len(
        feature_metadata
    ) != EXPECTED_OUTPUT_SIZE:

        raise ValueError(
            "Jumlah feature metadata tidak sesuai.\n"
            f"Ditemukan : {len(feature_metadata)}\n"
            f"Diharapkan: {EXPECTED_OUTPUT_SIZE}"
        )

    required_keys = [
        "index",
        "sensor_id",
        "approach",
        "lane_id",
        "feature",
    ]

    for i, item in enumerate(
        feature_metadata
    ):

        if not isinstance(
            item,
            dict,
        ):

            raise ValueError(
                f"Metadata index {i} bukan dictionary."
            )

        for key in required_keys:

            if key not in item:

                raise ValueError(
                    f"Metadata index {i} "
                    f"tidak memiliki key '{key}'."
                )

        if item["index"] != i:

            raise ValueError(
                "Index metadata tidak berurutan.\n"
                f"Posisi    : {i}\n"
                f"Metadata  : {item['index']}"
            )

        if item["feature"] not in FEATURES:

            raise ValueError(
                f"Feature tidak dikenal: "
                f"{item['feature']}"
            )

    print(
        f"[INFO] Feature metadata loaded : "
        f"{len(feature_metadata)} features"
    )

    # --------------------------------------------------------------
    # Validate sensor count
    # --------------------------------------------------------------

    sensor_ids = sorted(
        {
            item["sensor_id"]
            for item in feature_metadata
        }
    )

    print(
        f"[INFO] Sensor count : "
        f"{len(sensor_ids)}"
    )

    print(
        f"[INFO] Sensor IDs   : "
        f"{sensor_ids}"
    )

    if len(
        sensor_ids
    ) != NUM_SENSORS:

        raise ValueError(
            "Jumlah sensor metadata tidak sesuai.\n"
            f"Ditemukan : {len(sensor_ids)}\n"
            f"Diharapkan: {NUM_SENSORS}"
        )

    # --------------------------------------------------------------
    # Validate 8 features per sensor
    # --------------------------------------------------------------

    for sensor_id in sensor_ids:

        sensor_features = [
            item["feature"]
            for item in feature_metadata
            if item["sensor_id"] == sensor_id
        ]

        if len(
            sensor_features
        ) != NUM_FEATURES:

            raise ValueError(
                f"Sensor {sensor_id} memiliki "
                f"{len(sensor_features)} feature, "
                f"diharapkan {NUM_FEATURES}."
            )

    print(
        "[OK] Feature metadata validation passed."
    )

    return feature_metadata


# ======================================================================
# PER FEATURE EVALUATION
# ======================================================================

def evaluate_per_feature(
    y_true,
    y_pred,
    feature_metadata,
):

    print_header(
        "EVALUATION PER TRAFFIC FEATURE"
    )

    if (
        y_true.shape
        != y_pred.shape
    ):

        raise ValueError(
            f"Shape y_true dan y_pred berbeda:\n"
            f"y_true: {y_true.shape}\n"
            f"y_pred: {y_pred.shape}"
        )

    if (
        len(feature_metadata)
        != y_true.shape[1]
    ):

        raise ValueError(
            f"Jumlah metadata ({len(feature_metadata)}) "
            f"tidak sama dengan output model "
            f"({y_true.shape[1]})."
        )

    # ==============================================================
    # DETAIL SENSOR + FEATURE
    # ==============================================================

    detailed_rows = []

    for feature_idx, metadata in enumerate(
        feature_metadata
    ):

        true_values = (
            y_true[:, feature_idx]
        )

        pred_values = (
            y_pred[:, feature_idx]
        )

        mse = mean_squared_error(
            true_values,
            pred_values,
        )

        rmse = np.sqrt(
            mse
        )

        mae = mean_absolute_error(
            true_values,
            pred_values,
        )

        detailed_rows.append(
            {
                "index": feature_idx,
                "sensor_id": metadata[
                    "sensor_id"
                ],
                "approach": metadata[
                    "approach"
                ],
                "lane_id": metadata[
                    "lane_id"
                ],
                "feature": metadata[
                    "feature"
                ],
                "mae": float(mae),
                "rmse": float(rmse),
                "mse": float(mse),
            }
        )

    detailed_df = pd.DataFrame(
        detailed_rows
    )

    # ==============================================================
    # AGGREGATE BY TRAFFIC FEATURE
    # ==============================================================

    aggregate_rows = []

    for feature in FEATURES:

        indices = [
            i
            for i, metadata in enumerate(
                feature_metadata
            )
            if metadata["feature"] == feature
        ]

        if not indices:
            continue

        true_values = (
            y_true[:, indices]
        )

        pred_values = (
            y_pred[:, indices]
        )

        true_flat = (
            true_values
            .reshape(-1)
        )

        pred_flat = (
            pred_values
            .reshape(-1)
        )

        mse = mean_squared_error(
            true_flat,
            pred_flat,
        )

        rmse = np.sqrt(
            mse
        )

        mae = mean_absolute_error(
            true_flat,
            pred_flat,
        )

        aggregate_rows.append(
            {
                "feature": feature,
                "mae": float(mae),
                "rmse": float(rmse),
                "mse": float(mse),
                "feature_count": len(indices),
            }
        )

    aggregate_df = pd.DataFrame(
        aggregate_rows
    )

    # ==============================================================
    # PRINT
    # ==============================================================

    print()
    print(
        "-" * 70
    )

    print(
        "PER TRAFFIC FEATURE"
    )

    print(
        "-" * 70
    )

    if not aggregate_df.empty:

        print(
            aggregate_df.to_string(
                index=False,
                float_format=lambda x:
                    f"{x:.6f}",
            )
        )

    print()
    print(
        "-" * 70
    )

    print(
        "DETAILED SENSOR-FEATURE"
    )

    print(
        "-" * 70
    )

    print(
        detailed_df.to_string(
            index=False,
            float_format=lambda x:
                f"{x:.6f}",
        )
    )

    # ==============================================================
    # SAVE CSV
    # ==============================================================

    detailed_path = (
        EVALUATION_DIR
        / "metrics_per_sensor_feature.csv"
    )

    aggregate_path = (
        EVALUATION_DIR
        / "metrics_per_feature.csv"
    )

    detailed_df.to_csv(
        detailed_path,
        index=False,
    )

    aggregate_df.to_csv(
        aggregate_path,
        index=False,
    )

    print(
        f"\n[SAVED] {detailed_path}"
    )

    print(
        f"[SAVED] {aggregate_path}"
    )

    return (
        detailed_df,
        aggregate_df,
    )


# ======================================================================
# PER SENSOR EVALUATION
# ======================================================================

def evaluate_per_sensor(
    y_true,
    y_pred,
    feature_metadata,
):

    print_header(
        "EVALUATION PER SENSOR"
    )

    sensor_groups = {}

    # --------------------------------------------------------------
    # Group feature indices by sensor
    # --------------------------------------------------------------

    for index, metadata in enumerate(
        feature_metadata
    ):

        sensor_id = metadata[
            "sensor_id"
        ]

        if sensor_id not in sensor_groups:

            sensor_groups[
                sensor_id
            ] = []

        sensor_groups[
            sensor_id
        ].append(index)

    rows = []

    for sensor_id in sorted(
        sensor_groups.keys()
    ):

        indices = sensor_groups[
            sensor_id
        ]

        true_values = (
            y_true[:, indices]
        )

        pred_values = (
            y_pred[:, indices]
        )

        true_flat = (
            true_values
            .reshape(-1)
        )

        pred_flat = (
            pred_values
            .reshape(-1)
        )

        mse = mean_squared_error(
            true_flat,
            pred_flat,
        )

        rmse = np.sqrt(
            mse
        )

        mae = mean_absolute_error(
            true_flat,
            pred_flat,
        )

        metadata = (
            feature_metadata[
                indices[0]
            ]
        )

        rows.append(
            {
                "sensor_id": sensor_id,
                "approach": metadata[
                    "approach"
                ],
                "lane_id": metadata[
                    "lane_id"
                ],
                "sensor": (
                    f"{metadata['approach']}/"
                    f"{metadata['lane_id']}"
                ),
                "mae": float(mae),
                "rmse": float(rmse),
                "mse": float(mse),
                "feature_count": len(indices),
            }
        )

    sensor_df = pd.DataFrame(
        rows
    )

    print()
    print(
        "-" * 70
    )

    print(
        "PER SENSOR"
    )

    print(
        "-" * 70
    )

    if not sensor_df.empty:

        print(
            sensor_df.to_string(
                index=False,
                float_format=lambda x:
                    f"{x:.6f}",
            )
        )

    sensor_path = (
        EVALUATION_DIR
        / "metrics_per_sensor.csv"
    )

    sensor_df.to_csv(
        sensor_path,
        index=False,
    )

    print(
        f"\n[SAVED] {sensor_path}"
    )

    return sensor_df


# ======================================================================
# SAVE PREDICTIONS
# ======================================================================

def save_predictions(
    y_test_scaled,
    y_true_original,
    y_pred_original,
):

    print_header(
        "SAVING PREDICTIONS"
    )

    scaled_path = (
        EVALUATION_DIR
        / "y_test_actual_scaled.npy"
    )

    original_actual_path = (
        EVALUATION_DIR
        / "y_test_actual_original.npy"
    )

    original_prediction_path = (
        EVALUATION_DIR
        / "y_test_prediction_original.npy"
    )

    np.save(
        scaled_path,
        np.asarray(
            y_test_scaled,
            dtype=np.float32,
        ),
    )

    np.save(
        original_actual_path,
        np.asarray(
            y_true_original,
            dtype=np.float32,
        ),
    )

    np.save(
        original_prediction_path,
        np.asarray(
            y_pred_original,
            dtype=np.float32,
        ),
    )

    print(
        f"[SAVED] {scaled_path}"
    )

    print(
        f"[SAVED] {original_actual_path}"
    )

    print(
        f"[SAVED] {original_prediction_path}"
    )


# ======================================================================
# PREDICTION CSV
# ======================================================================

def save_prediction_csv(
    y_true,
    y_pred,
    feature_metadata,
):

    print_header(
        "CREATING PREDICTION CSV"
    )

    rows = []

    for sample_idx in range(
        y_true.shape[0]
    ):

        for feature_idx, metadata in enumerate(
            feature_metadata
        ):

            actual = float(
                y_true[
                    sample_idx,
                    feature_idx,
                ]
            )

            prediction = float(
                y_pred[
                    sample_idx,
                    feature_idx,
                ]
            )

            error = (
                prediction
                - actual
            )

            absolute_error = abs(
                error
            )

            rows.append(
                {
                    "sample": sample_idx,
                    "index": feature_idx,
                    "sensor_id": metadata[
                        "sensor_id"
                    ],
                    "approach": metadata[
                        "approach"
                    ],
                    "lane_id": metadata[
                        "lane_id"
                    ],
                    "feature": metadata[
                        "feature"
                    ],
                    "actual": actual,
                    "prediction": prediction,
                    "error": error,
                    "absolute_error": absolute_error,
                }
            )

    df = pd.DataFrame(
        rows
    )

    output_path = (
        EVALUATION_DIR
        / "predictions_long.csv"
    )

    df.to_csv(
        output_path,
        index=False,
    )

    print(
        f"[SAVED] {output_path}"
    )

    return df


# ======================================================================
# TRAINING HISTORY PLOT
# ======================================================================

def plot_training_history():

    print_header(
        "PLOTTING TRAINING HISTORY"
    )

    if not HISTORY_PATH.exists():

        print(
            "[WARN] training_history.json tidak ditemukan."
        )

        return

    with open(
        HISTORY_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        history = json.load(f)

    if not isinstance(
        history,
        dict,
    ):

        print(
            "[WARN] Format training_history tidak dikenali."
        )

        return

    train_loss = history.get(
        "train_loss",
        history.get(
            "train_losses"
        ),
    )

    val_loss = history.get(
        "val_loss",
        history.get(
            "val_losses"
        ),
    )

    if (
        train_loss is None
        or val_loss is None
    ):

        print(
            "[WARN] train_loss / val_loss tidak ditemukan."
        )

        return

    min_length = min(
        len(train_loss),
        len(val_loss),
    )

    if min_length == 0:

        print(
            "[WARN] Training history kosong."
        )

        return

    train_loss = train_loss[
        :min_length
    ]

    val_loss = val_loss[
        :min_length
    ]

    epochs = range(
        1,
        min_length + 1,
    )

    plt.figure(
        figsize=(10, 6)
    )

    plt.plot(
        epochs,
        train_loss,
        label="Train Loss",
    )

    plt.plot(
        epochs,
        val_loss,
        label="Validation Loss",
    )

    plt.xlabel(
        "Epoch"
    )

    plt.ylabel(
        "MSE Loss"
    )

    plt.title(
        "YOLO Traffic LSTM Training History"
    )

    plt.legend()

    plt.grid(
        alpha=0.3
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / "training_validation_loss.png"
    )

    plt.savefig(
        output_path,
        dpi=200,
    )

    plt.close()

    print(
        f"[SAVED] {output_path}"
    )


# ======================================================================
# FEATURE METRIC PLOT
# ======================================================================

def plot_feature_metrics(
    feature_df,
):

    print_header(
        "PLOTTING FEATURE METRICS"
    )

    if feature_df.empty:

        print(
            "[WARN] Feature metrics kosong."
        )

        return

    # --------------------------------------------------------------
    # MAE
    # --------------------------------------------------------------

    plt.figure(
        figsize=(12, 6)
    )

    plt.bar(
        feature_df["feature"],
        feature_df["mae"],
    )

    plt.xlabel(
        "Traffic Feature"
    )

    plt.ylabel(
        "MAE"
    )

    plt.title(
        "MAE per Traffic Feature"
    )

    plt.xticks(
        rotation=45,
        ha="right",
    )

    plt.grid(
        axis="y",
        alpha=0.3,
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / "mae_per_feature.png"
    )

    plt.savefig(
        output_path,
        dpi=200,
    )

    plt.close()

    print(
        f"[SAVED] {output_path}"
    )

    # --------------------------------------------------------------
    # RMSE
    # --------------------------------------------------------------

    plt.figure(
        figsize=(12, 6)
    )

    plt.bar(
        feature_df["feature"],
        feature_df["rmse"],
    )

    plt.xlabel(
        "Traffic Feature"
    )

    plt.ylabel(
        "RMSE"
    )

    plt.title(
        "RMSE per Traffic Feature"
    )

    plt.xticks(
        rotation=45,
        ha="right",
    )

    plt.grid(
        axis="y",
        alpha=0.3,
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / "rmse_per_feature.png"
    )

    plt.savefig(
        output_path,
        dpi=200,
    )

    plt.close()

    print(
        f"[SAVED] {output_path}"
    )


# ======================================================================
# SENSOR METRIC PLOT
# ======================================================================

def plot_sensor_metrics(
    sensor_df,
):

    print_header(
        "PLOTTING SENSOR METRICS"
    )

    if sensor_df.empty:

        print(
            "[WARN] Sensor metrics kosong."
        )

        return

    plt.figure(
        figsize=(12, 6)
    )

    plt.bar(
        sensor_df["sensor"],
        sensor_df["mae"],
    )

    plt.xlabel(
        "Sensor"
    )

    plt.ylabel(
        "MAE"
    )

    plt.title(
        "MAE per Traffic Sensor"
    )

    plt.xticks(
        rotation=45,
        ha="right",
    )

    plt.grid(
        axis="y",
        alpha=0.3,
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / "mae_per_sensor.png"
    )

    plt.savefig(
        output_path,
        dpi=200,
    )

    plt.close()

    print(
        f"[SAVED] {output_path}"
    )

    # --------------------------------------------------------------
    # RMSE
    # --------------------------------------------------------------

    plt.figure(
        figsize=(12, 6)
    )

    plt.bar(
        sensor_df["sensor"],
        sensor_df["rmse"],
    )

    plt.xlabel(
        "Sensor"
    )

    plt.ylabel(
        "RMSE"
    )

    plt.title(
        "RMSE per Traffic Sensor"
    )

    plt.xticks(
        rotation=45,
        ha="right",
    )

    plt.grid(
        axis="y",
        alpha=0.3,
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / "rmse_per_sensor.png"
    )

    plt.savefig(
        output_path,
        dpi=200,
    )

    plt.close()

    print(
        f"[SAVED] {output_path}"
    )


# ======================================================================
# ACTUAL VS PREDICTION PLOT
# ======================================================================

def plot_actual_vs_prediction(
    y_true,
    y_pred,
    feature_metadata,
):

    print_header(
        "PLOTTING ACTUAL VS PREDICTION"
    )

    selected_features = [
        "vehicle_count",
        "motorcycle_count",
        "queue_length_veh",
        "density_index",
    ]

    for feature in selected_features:

        indices = [
            i
            for i, metadata in enumerate(
                feature_metadata
            )
            if metadata["feature"] == feature
        ]

        if not indices:

            print(
                f"[WARN] Feature {feature} tidak ditemukan."
            )

            continue

        # ----------------------------------------------------------
        # Average across all sensors
        # ----------------------------------------------------------

        actual = np.mean(
            y_true[:, indices],
            axis=1,
        )

        prediction = np.mean(
            y_pred[:, indices],
            axis=1,
        )

        # ----------------------------------------------------------
        # Limit displayed samples
        # ----------------------------------------------------------

        n = min(
            len(actual),
            250,
        )

        x = np.arange(
            n
        )

        plt.figure(
            figsize=(12, 6)
        )

        plt.plot(
            x,
            actual[:n],
            label="Actual",
        )

        plt.plot(
            x,
            prediction[:n],
            label="Prediction",
        )

        plt.xlabel(
            "Test Sample"
        )

        plt.ylabel(
            feature
        )

        plt.title(
            f"Actual vs Prediction - {feature}"
        )

        plt.legend()

        plt.grid(
            alpha=0.3
        )

        plt.tight_layout()

        safe_name = (
            feature.replace(
                "_",
                "-",
            )
        )

        output_path = (
            PLOT_DIR
            / (
                "actual_vs_prediction_"
                f"{safe_name}.png"
            )
        )

        plt.savefig(
            output_path,
            dpi=200,
        )

        plt.close()

        print(
            f"[SAVED] {output_path}"
        )


# ======================================================================
# ERROR DISTRIBUTION
# ======================================================================

def plot_error_distribution(
    y_true,
    y_pred,
):

    print_header(
        "PLOTTING ERROR DISTRIBUTION"
    )

    error = (
        y_pred
        - y_true
    ).reshape(-1)

    plt.figure(
        figsize=(10, 6)
    )

    plt.hist(
        error,
        bins=50,
    )

    plt.xlabel(
        "Prediction Error"
    )

    plt.ylabel(
        "Frequency"
    )

    plt.title(
        "Prediction Error Distribution"
    )

    plt.grid(
        axis="y",
        alpha=0.3,
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / "prediction_error_distribution.png"
    )

    plt.savefig(
        output_path,
        dpi=200,
    )

    plt.close()

    print(
        f"[SAVED] {output_path}"
    )


# ======================================================================
# SAVE FINAL REPORT
# ======================================================================

def save_final_report(
    config,
    scaler_path,
    scaled_metrics,
    original_metrics,
    feature_df,
    detailed_feature_df,
    sensor_df,
):

    print_header(
        "SAVING FINAL EVALUATION REPORT"
    )

    report = {

        # ----------------------------------------------------------
        # Dataset
        # ----------------------------------------------------------

        "dataset": config.get(
            "dataset"
        ),

        # ----------------------------------------------------------
        # Model
        # ----------------------------------------------------------

        "model": {

            "architecture": config.get(
                "model"
            ),

            "input_size": config.get(
                "input_size"
            ),

            "hidden_size": config.get(
                "hidden_size"
            ),

            "num_layers": config.get(
                "num_layers"
            ),

            "dropout": config.get(
                "dropout"
            ),

            "output_size": config.get(
                "output_size"
            ),
        },

        # ----------------------------------------------------------
        # Forecast
        # ----------------------------------------------------------

        "forecast": {

            "sequence_length": config.get(
                "sequence_length"
            ),

            "forecast_horizon": config.get(
                "forecast_horizon"
            ),
        },

        # ----------------------------------------------------------
        # Scaler
        # ----------------------------------------------------------

        "scaler": {

            "path": str(
                scaler_path
            ),

            "type": type(
                pickle.load(
                    open(
                        scaler_path,
                        "rb",
                    )
                )
            ).__name__,
        },

        # ----------------------------------------------------------
        # Metrics
        # ----------------------------------------------------------

        "test_metrics_scaled":
            scaled_metrics,

        "test_metrics_original_scale":
            original_metrics,

        # ----------------------------------------------------------
        # Feature metrics
        # ----------------------------------------------------------

        "metrics_per_feature":
            feature_df.to_dict(
                orient="records"
            ),

        # ----------------------------------------------------------
        # Sensor metrics
        # ----------------------------------------------------------

        "metrics_per_sensor":
            sensor_df.to_dict(
                orient="records"
            ),

        # ----------------------------------------------------------
        # Detailed sensor-feature metrics
        # ----------------------------------------------------------

        "metrics_per_sensor_feature":
            detailed_feature_df.to_dict(
                orient="records"
            ),

        # ----------------------------------------------------------
        # Best / worst
        # ----------------------------------------------------------

        "best_feature_mae": (

            float(
                feature_df[
                    "mae"
                ].min()
            )

            if not feature_df.empty

            else None
        ),

        "worst_feature_mae": (

            float(
                feature_df[
                    "mae"
                ].max()
            )

            if not feature_df.empty

            else None
        ),

        "best_sensor_mae": (

            float(
                sensor_df[
                    "mae"
                ].min()
            )

            if not sensor_df.empty

            else None
        ),

        "worst_sensor_mae": (

            float(
                sensor_df[
                    "mae"
                ].max()
            )

            if not sensor_df.empty

            else None
        ),

        # ----------------------------------------------------------
        # Evaluation directory
        # ----------------------------------------------------------

        "evaluation_directory":
            str(
                EVALUATION_DIR
            ),
    }

    output_path = (
        EVALUATION_DIR
        / "evaluation_report.json"
    )

    save_json(
        report,
        output_path,
    )

    print(
        f"[SAVED] {output_path}"
    )

    return report


# ======================================================================
# MAIN
# ======================================================================

def main():

    print()

    print(
        "=" * 70
    )

    print(
        "YOLO TRAFFIC LSTM EVALUATION"
    )

    print(
        "=" * 70
    )

    print(
        f"[INFO] Output directory : "
        f"{OUTPUT_DIR}"
    )

    print(
        f"[INFO] Evaluation dir   : "
        f"{EVALUATION_DIR}"
    )

    # ==============================================================
    # CONFIG
    # ==============================================================

    config = (
        load_training_config()
    )

    # ==============================================================
    # DEVICE
    # ==============================================================

    device = get_device(
        config
    )

    # ==============================================================
    # LOAD FEATURE METADATA
    # ==============================================================

    feature_metadata = (
        load_feature_metadata()
    )

    # ==============================================================
    # LOAD TEST DATA
    # ==============================================================

    (
        X_test,
        y_test,
    ) = load_test_data()

    # ==============================================================
    # NUMERICAL VALIDATION
    # ==============================================================

    validate_test_data(
        X_test,
        y_test,
    )

    # ==============================================================
    # CONFIG SHAPE
    # ==============================================================

    expected_input_size = int(
        config[
            "input_size"
        ]
    )

    expected_output_size = int(
        config[
            "output_size"
        ]
    )

    if (
        expected_output_size
        != EXPECTED_OUTPUT_SIZE
    ):

        raise ValueError(
            "\nOutput size pada config tidak sesuai "
            "dengan struktur metadata.\n"
            f"Config : {expected_output_size}\n"
            f"Metadata: {EXPECTED_OUTPUT_SIZE}\n"
        )

    # ==============================================================
    # X TEST SHAPE
    # ==============================================================

    if X_test.ndim != 3:

        raise ValueError(
            f"X_test harus 3 dimensi.\n"
            f"Ditemukan: {X_test.ndim}"
        )

    if y_test.ndim != 2:

        raise ValueError(
            f"y_test harus 2 dimensi.\n"
            f"Ditemukan: {y_test.ndim}"
        )

    if (
        X_test.shape[2]
        != expected_input_size
    ):

        raise ValueError(
            "\nInput size mismatch.\n"
            f"Config : {expected_input_size}\n"
            f"X_test: {X_test.shape[2]}"
        )

    if (
        y_test.shape[1]
        != expected_output_size
    ):

        raise ValueError(
            "\nOutput size mismatch.\n"
            f"Config : {expected_output_size}\n"
            f"y_test: {y_test.shape[1]}"
        )

    if (
        y_test.shape[1]
        != len(feature_metadata)
    ):

        raise ValueError(
            "\nMetadata/output mismatch.\n"
            f"Metadata : {len(feature_metadata)}\n"
            f"y_test   : {y_test.shape[1]}"
        )

    print(
        "[OK] Dataset shape matches "
        "training configuration."
    )

    # ==============================================================
    # LOAD SCALER
    # ==============================================================

    (
        scaler,
        scaler_path,
    ) = load_scaler()

    # ==============================================================
    # LOAD MODEL
    # ==============================================================

    model = load_model(
        config,
        device,
    )

    # ==============================================================
    # GENERATE PREDICTIONS
    # ==============================================================

    predictions = (
        generate_predictions(
            model=model,
            X_test=X_test,
            device=device,
            batch_size=int(
                config.get(
                    "batch_size",
                    32,
                )
            ),
        )
    )

    # ==============================================================
    # PREDICTION NUMERICAL VALIDATION
    # ==============================================================

    prediction_nan = int(
        np.isnan(
            predictions
        ).sum()
    )

    prediction_inf = int(
        np.isinf(
            predictions
        ).sum()
    )

    print(
        f"[INFO] Prediction | "
        f"NaN: {prediction_nan} | "
        f"Inf: {prediction_inf}"
    )

    if (
        prediction_nan > 0
        or prediction_inf > 0
    ):

        raise ValueError(
            "Prediction mengandung NaN atau Inf."
        )

    # ==============================================================
    # PREDICTION SHAPE
    # ==============================================================

    validate_prediction_shape(
        predictions,
        y_test,
    )

    # ==============================================================
    # SCALED METRICS
    # ==============================================================

    scaled_metrics = (
        evaluate_scaled(
            y_test,
            predictions,
        )
    )

    # ==============================================================
    # INVERSE TRANSFORM
    # ==============================================================

    (
        y_true_original,
        y_pred_original,
    ) = inverse_transform_targets(
        scaler,
        y_test,
        predictions,
    )

    # ==============================================================
    # ORIGINAL SCALE METRICS
    # ==============================================================

    original_metrics = (
        evaluate_original_scale(
            y_true_original,
            y_pred_original,
        )
    )

    # ==============================================================
    # PER FEATURE
    # ==============================================================

    (
        detailed_feature_df,
        feature_df,
    ) = evaluate_per_feature(
        y_true_original,
        y_pred_original,
        feature_metadata,
    )

    # ==============================================================
    # PER SENSOR
    # ==============================================================

    sensor_df = (
        evaluate_per_sensor(
            y_true_original,
            y_pred_original,
            feature_metadata,
        )
    )

    # ==============================================================
    # SAVE PREDICTIONS
    # ==============================================================

    save_predictions(
        y_test_scaled=y_test,
        y_true_original=y_true_original,
        y_pred_original=y_pred_original,
    )

    # ==============================================================
    # SAVE PREDICTION CSV
    # ==============================================================

    save_prediction_csv(
        y_true_original,
        y_pred_original,
        feature_metadata,
    )

    # ==============================================================
    # PLOTS
    # ==============================================================

    plot_training_history()

    plot_feature_metrics(
        feature_df
    )

    plot_sensor_metrics(
        sensor_df
    )

    plot_actual_vs_prediction(
        y_true_original,
        y_pred_original,
        feature_metadata,
    )

    plot_error_distribution(
        y_true_original,
        y_pred_original,
    )

    # ==============================================================
    # FINAL REPORT
    # ==============================================================

    save_final_report(
        config=config,
        scaler_path=scaler_path,
        scaled_metrics=scaled_metrics,
        original_metrics=original_metrics,
        feature_df=feature_df,
        detailed_feature_df=detailed_feature_df,
        sensor_df=sensor_df,
    )

    # ==============================================================
    # FINAL SUMMARY
    # ==============================================================

    print_header(
        "YOLO LSTM EVALUATION SUMMARY"
    )

    print()
    print(
        "[MODEL]"
    )

    print(
        f"Architecture       : "
        f"{config.get('model')}"
    )

    print(
        f"Sequence length    : "
        f"{config.get('sequence_length')}"
    )

    print(
        f"Forecast horizon   : "
        f"{config.get('forecast_horizon')} second"
    )

    print(
        f"Hidden size        : "
        f"{config.get('hidden_size')}"
    )

    print(
        f"LSTM layers        : "
        f"{config.get('num_layers')}"
    )

    print(
        f"Output size        : "
        f"{config.get('output_size')}"
    )

    print()

    print(
        "[TEST - SCALED SPACE]"
    )

    print(
        f"MAE  : "
        f"{scaled_metrics['mae']:.6f}"
    )

    print(
        f"RMSE : "
        f"{scaled_metrics['rmse']:.6f}"
    )

    print(
        f"MSE  : "
        f"{scaled_metrics['mse']:.6f}"
    )

    print()

    print(
        "[TEST - ORIGINAL SCALE]"
    )

    print(
        f"MAE  : "
        f"{original_metrics['mae']:.6f}"
    )

    print(
        f"RMSE : "
        f"{original_metrics['rmse']:.6f}"
    )

    print(
        f"MSE  : "
        f"{original_metrics['mse']:.6f}"
    )

    print()

    print(
        "[OUTPUT]"
    )

    print(
        f"Evaluation directory:"
    )

    print(
        f"{EVALUATION_DIR}"
    )

    print()

    print(
        "[NEXT]"
    )

    print(
        "1. Review training/validation loss."
    )

    print(
        "2. Review MAE/RMSE per traffic feature."
    )

    print(
        "3. Review MAE/RMSE per sensor."
    )

    print(
        "4. Review detailed sensor-feature metrics."
    )

    print(
        "5. Review actual vs prediction plots."
    )

    print(
        "6. Review prediction error distribution."
    )

    print(
        "7. Establish the baseline."
    )

    print(
        "8. Experiment with sequence length."
    )

    print(
        "9. Experiment with temporal resolution."
    )

    print(
        "10. Only then perform hyperparameter tuning."
    )

    print()

    print(
        "=" * 70
    )

    print(
        "YOLO LSTM EVALUATION COMPLETED"
    )

    print(
        "=" * 70
    )


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":

    main()