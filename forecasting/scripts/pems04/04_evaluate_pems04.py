import json
import random
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

PROCESSED_DIR = (
    BASE_DIR
    / "outputs"
    / "pems04"
    / "sensor_1_20"
    / "processed"
)

OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "pems04"
    / "sensor_1_20"
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
    exist_ok=True
)

PLOT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

SEQUENCE_LENGTH = 15
FORECAST_HORIZON = 1

HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2

BATCH_SIZE = 64

NUM_SENSORS = 20
NUM_FEATURES = 3

FEATURE_NAMES = [
    "flow",
    "occupancy",
    "speed"
]

SENSOR_START = 1
SENSOR_END = 20

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

    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():

        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# LSTM MODEL
# IMPORTANT:
# This architecture MUST remain identical to 03_train_pems04.py
# ============================================================

class TrafficLSTM(
    nn.Module
):

    def __init__(
        self,
        num_sensors,
        num_features,
        hidden_size=64,
        num_layers=2,
        dropout=0.2
    ):

        super().__init__()

        self.num_sensors = (
            num_sensors
        )

        self.num_features = (
            num_features
        )

        self.input_size = (
            num_sensors
            * num_features
        )

        self.hidden_size = (
            hidden_size
        )

        self.num_layers = (
            num_layers
        )

        self.lstm = nn.LSTM(
            input_size=self.input_size,
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

        # IMPORTANT:
        # Training model uses "output_layer"
        # NOT "fc".
        self.output_layer = nn.Linear(
            hidden_size,
            num_sensors
            * num_features
        )

    def forward(
        self,
        x
    ):

        batch_size = (
            x.size(0)
        )

        # ----------------------------------------------------
        # Input:
        # (batch, sequence, sensors, features)
        #
        # Convert:
        # (batch, sequence, sensors * features)
        # ----------------------------------------------------

        x = x.reshape(
            batch_size,
            x.size(1),
            -1
        )

        lstm_output, _ = (
            self.lstm(x)
        )

        # Last timestep
        last_output = (
            lstm_output[:, -1, :]
        )

        last_output = (
            self.dropout(
                last_output
            )
        )

        output = (
            self.output_layer(
                last_output
            )
        )

        output = output.reshape(
            batch_size,
            self.num_sensors,
            self.num_features
        )

        return output


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print("=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    files = {

        "X_train":
            PROCESSED_DIR
            / "X_train.npy",

        "y_train":
            PROCESSED_DIR
            / "y_train.npy",

        "X_val":
            PROCESSED_DIR
            / "X_val.npy",

        "y_val":
            PROCESSED_DIR
            / "y_val.npy",

        "X_test":
            PROCESSED_DIR
            / "X_test.npy",

        "y_test":
            PROCESSED_DIR
            / "y_test.npy"
    }

    for name, path in files.items():

        if not path.exists():

            raise FileNotFoundError(
                f"File tidak ditemukan: {path}"
            )

    X_train = np.load(
        files["X_train"]
    ).astype(
        np.float32
    )

    y_train = np.load(
        files["y_train"]
    ).astype(
        np.float32
    )

    X_val = np.load(
        files["X_val"]
    ).astype(
        np.float32
    )

    y_val = np.load(
        files["y_val"]
    ).astype(
        np.float32
    )

    X_test = np.load(
        files["X_test"]
    ).astype(
        np.float32
    )

    y_test = np.load(
        files["y_test"]
    ).astype(
        np.float32
    )

    print(
        f"[INFO] X_train : {X_train.shape}"
    )

    print(
        f"[INFO] y_train : {y_train.shape}"
    )

    print(
        f"[INFO] X_val   : {X_val.shape}"
    )

    print(
        f"[INFO] y_val   : {y_val.shape}"
    )

    print(
        f"[INFO] X_test  : {X_test.shape}"
    )

    print(
        f"[INFO] y_test  : {y_test.shape}"
    )

    return (
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test
    )


# ============================================================
# DATA VALIDATION
# ============================================================

def validate_data(
    X_test,
    y_test
):

    print()
    print("=" * 70)
    print("DATA VALIDATION")
    print("=" * 70)

    if X_test.ndim != 4:

        raise ValueError(
            "X_test harus memiliki "
            "shape (samples, timestep, sensors, features)."
        )

    if y_test.ndim != 3:

        raise ValueError(
            "y_test harus memiliki "
            "shape (samples, sensors, features)."
        )

    num_sensors = (
        X_test.shape[2]
    )

    num_features = (
        X_test.shape[3]
    )

    sequence_length = (
        X_test.shape[1]
    )

    if sequence_length != (
        SEQUENCE_LENGTH
    ):

        raise ValueError(
            f"Sequence length tidak sesuai. "
            f"Expected {SEQUENCE_LENGTH}, "
            f"got {sequence_length}."
        )

    if num_sensors != (
        NUM_SENSORS
    ):

        raise ValueError(
            f"Jumlah sensor tidak sesuai. "
            f"Expected {NUM_SENSORS}, "
            f"got {num_sensors}."
        )

    if num_features != (
        NUM_FEATURES
    ):

        raise ValueError(
            f"Jumlah fitur tidak sesuai. "
            f"Expected {NUM_FEATURES}, "
            f"got {num_features}."
        )

    print(
        "[OK] Test input shape valid."
    )

    print(
        f"[INFO] Sequence length : "
        f"{sequence_length}"
    )

    print(
        f"[INFO] Sensors         : "
        f"{num_sensors}"
    )

    print(
        f"[INFO] Features        : "
        f"{num_features}"
    )


# ============================================================
# CREATE TEST DATALOADER
# ============================================================

def create_test_loader(
    X_test,
    y_test
):

    test_dataset = TensorDataset(
        torch.from_numpy(X_test),
        torch.from_numpy(y_test)
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        drop_last=False
    )

    return test_loader


# ============================================================
# LOAD BEST MODEL
# ============================================================

def load_model(
    model_path,
    num_sensors,
    num_features
):

    print()
    print("=" * 70)
    print("MODEL LOADING")
    print("=" * 70)

    if not model_path.exists():

        raise FileNotFoundError(
            f"Best model tidak ditemukan: "
            f"{model_path}"
        )

    print(
        f"[INFO] Model path:"
    )

    print(
        f"       {model_path}"
    )

    # --------------------------------------------------------
    # Build EXACT same architecture as training
    # --------------------------------------------------------

    model = TrafficLSTM(
        num_sensors=num_sensors,
        num_features=num_features,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        dropout=DROPOUT
    )

    # --------------------------------------------------------
    # Load checkpoint
    # --------------------------------------------------------

    checkpoint = torch.load(
        model_path,
        map_location=DEVICE
    )

    # --------------------------------------------------------
    # Training script saves a checkpoint dictionary:
    #
    # {
    #     "epoch": ...,
    #     "model_state_dict": ...,
    #     "optimizer_state_dict": ...,
    #     ...
    # }
    # --------------------------------------------------------

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

        checkpoint_epoch = (
            checkpoint.get(
                "epoch",
                None
            )
        )

        checkpoint_val_loss = (
            checkpoint.get(
                "val_loss",
                None
            )
        )

    else:

        # Fallback if checkpoint is
        # directly a state_dict.
        model.load_state_dict(
            checkpoint
        )

        checkpoint_epoch = None
        checkpoint_val_loss = None

    model = model.to(
        DEVICE
    )

    model.eval()

    print(
        "[OK] Model loaded successfully."
    )

    if checkpoint_epoch is not None:

        print(
            f"[INFO] Best epoch     : "
            f"{checkpoint_epoch}"
        )

    if checkpoint_val_loss is not None:

        print(
            f"[INFO] Best val loss  : "
            f"{checkpoint_val_loss:.6f}"
        )

    parameter_count = sum(
        p.numel()
        for p in model.parameters()
    )

    print(
        f"[INFO] Parameters      : "
        f"{parameter_count:,}"
    )

    return (
        model,
        checkpoint
    )


# ============================================================
# PREDICTION
# ============================================================

def generate_predictions(
    model,
    test_loader
):

    print()
    print("=" * 70)
    print("GENERATING TEST PREDICTIONS")
    print("=" * 70)

    predictions = []
    actuals = []

    start_time = (
        time.time()
    )

    model.eval()

    with torch.no_grad():

        for X_batch, y_batch in (
            test_loader
        ):

            X_batch = (
                X_batch.to(
                    DEVICE
                )
            )

            prediction = (
                model(
                    X_batch
                )
            )

            predictions.append(
                prediction
                .cpu()
                .numpy()
            )

            actuals.append(
                y_batch.numpy()
            )

    predictions = np.concatenate(
        predictions,
        axis=0
    )

    actuals = np.concatenate(
        actuals,
        axis=0
    )

    elapsed = (
        time.time()
        - start_time
    )

    print(
        f"[INFO] Predictions shape : "
        f"{predictions.shape}"
    )

    print(
        f"[INFO] Actual shape      : "
        f"{actuals.shape}"
    )

    print(
        f"[INFO] Inference time    : "
        f"{elapsed:.4f} seconds"
    )

    return (
        predictions,
        actuals,
        elapsed
    )


# ============================================================
# OVERALL METRICS
# ============================================================

def calculate_overall_metrics(
    y_true,
    y_pred
):

    # Flatten all dimensions
    true_flat = (
        y_true.reshape(-1)
    )

    pred_flat = (
        y_pred.reshape(-1)
    )

    error = (
        pred_flat
        - true_flat
    )

    mae = np.mean(
        np.abs(error)
    )

    mse = np.mean(
        error ** 2
    )

    rmse = np.sqrt(
        mse
    )

    # R2
    ss_res = np.sum(
        error ** 2
    )

    ss_tot = np.sum(
        (
            true_flat
            - np.mean(true_flat)
        ) ** 2
    )

    if ss_tot == 0:

        r2 = np.nan

    else:

        r2 = (
            1
            - (
                ss_res
                / ss_tot
            )
        )

    # MAPE
    # Ignore values very close to zero
    non_zero_mask = (
        np.abs(true_flat)
        > 1e-6
    )

    if np.any(
        non_zero_mask
    ):

        mape = np.mean(
            np.abs(
                (
                    true_flat[
                        non_zero_mask
                    ]
                    - pred_flat[
                        non_zero_mask
                    ]
                )
                / true_flat[
                    non_zero_mask
                ]
            )
        ) * 100

    else:

        mape = np.nan

    return {
        "MAE": float(mae),
        "MSE": float(mse),
        "RMSE": float(rmse),
        "MAPE_percent": float(mape),
        "R2": float(r2)
    }


# ============================================================
# METRICS BY FEATURE
# ============================================================

def calculate_feature_metrics(
    y_true,
    y_pred
):

    rows = []

    for feature_index, feature_name in enumerate(
        FEATURE_NAMES
    ):

        true_values = (
            y_true[
                :,
                :,
                feature_index
            ].reshape(-1)
        )

        pred_values = (
            y_pred[
                :,
                :,
                feature_index
            ].reshape(-1)
        )

        error = (
            pred_values
            - true_values
        )

        mae = np.mean(
            np.abs(error)
        )

        mse = np.mean(
            error ** 2
        )

        rmse = np.sqrt(
            mse
        )

        ss_res = np.sum(
            error ** 2
        )

        ss_tot = np.sum(
            (
                true_values
                - np.mean(true_values)
            ) ** 2
        )

        if ss_tot == 0:

            r2 = np.nan

        else:

            r2 = (
                1
                - (
                    ss_res
                    / ss_tot
                )
            )

        non_zero_mask = (
            np.abs(true_values)
            > 1e-6
        )

        if np.any(
            non_zero_mask
        ):

            mape = np.mean(
                np.abs(
                    (
                        true_values[
                            non_zero_mask
                        ]
                        - pred_values[
                            non_zero_mask
                        ]
                    )
                    / true_values[
                        non_zero_mask
                    ]
                )
            ) * 100

        else:

            mape = np.nan

        rows.append(
            {
                "feature":
                    feature_name,

                "MAE":
                    float(mae),

                "MSE":
                    float(mse),

                "RMSE":
                    float(rmse),

                "MAPE_percent":
                    float(mape),

                "R2":
                    float(r2)
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# METRICS BY SENSOR
# ============================================================

def calculate_sensor_metrics(
    y_true,
    y_pred
):

    rows = []

    for sensor_index in range(
        NUM_SENSORS
    ):

        true_values = (
            y_true[
                :,
                sensor_index,
                :
            ].reshape(-1)
        )

        pred_values = (
            y_pred[
                :,
                sensor_index,
                :
            ].reshape(-1)
        )

        error = (
            pred_values
            - true_values
        )

        mae = np.mean(
            np.abs(error)
        )

        mse = np.mean(
            error ** 2
        )

        rmse = np.sqrt(
            mse
        )

        ss_res = np.sum(
            error ** 2
        )

        ss_tot = np.sum(
            (
                true_values
                - np.mean(true_values)
            ) ** 2
        )

        if ss_tot == 0:

            r2 = np.nan

        else:

            r2 = (
                1
                - (
                    ss_res
                    / ss_tot
                )
            )

        rows.append(
            {
                "sensor":
                    sensor_index + 1,

                "MAE":
                    float(mae),

                "MSE":
                    float(mse),

                "RMSE":
                    float(rmse),

                "R2":
                    float(r2)
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# SAVE PREDICTIONS
# ============================================================

def save_predictions(
    y_true,
    y_pred
):

    prediction_path = (
        EVALUATION_DIR
        / "test_predictions.npz"
    )

    np.savez_compressed(
        prediction_path,
        y_true=y_true,
        y_pred=y_pred
    )

    print(
        f"[SAVED] {prediction_path}"
    )

    return prediction_path


# ============================================================
# SAVE METRICS
# ============================================================

def save_metrics(
    overall_metrics,
    feature_metrics,
    sensor_metrics
):

    overall_path = (
        EVALUATION_DIR
        / "overall_metrics.json"
    )

    feature_path = (
        EVALUATION_DIR
        / "feature_metrics.csv"
    )

    sensor_path = (
        EVALUATION_DIR
        / "sensor_metrics.csv"
    )

    with open(
        overall_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            overall_metrics,
            file,
            indent=4
        )

    feature_metrics.to_csv(
        feature_path,
        index=False
    )

    sensor_metrics.to_csv(
        sensor_path,
        index=False
    )

    print(
        f"[SAVED] {overall_path}"
    )

    print(
        f"[SAVED] {feature_path}"
    )

    print(
        f"[SAVED] {sensor_path}"
    )


# ============================================================
# PLOT ACTUAL VS PREDICTED
# ============================================================

def save_prediction_plot(
    y_true,
    y_pred
):

    print()
    print("=" * 70)
    print("SAVING PREDICTION PLOTS")
    print("=" * 70)

    # --------------------------------------------------------
    # Plot selected sensor
    # Sensor 1
    # --------------------------------------------------------

    sensor_index = 0

    # Plot each feature separately
    for feature_index, feature_name in enumerate(
        FEATURE_NAMES
    ):

        plot_path = (
            PLOT_DIR
            / (
                f"sensor_"
                f"{sensor_index + 1}_"
                f"{feature_name}_"
                f"actual_vs_predicted.png"
            )
        )

        # Limit visualized samples
        # to first 500 test samples
        sample_count = min(
            500,
            len(y_true)
        )

        actual = (
            y_true[
                :sample_count,
                sensor_index,
                feature_index
            ]
        )

        predicted = (
            y_pred[
                :sample_count,
                sensor_index,
                feature_index
            ]
        )

        plt.figure(
            figsize=(12, 5)
        )

        plt.plot(
            actual,
            label="Actual"
        )

        plt.plot(
            predicted,
            label="Predicted"
        )

        plt.xlabel(
            "Test sample"
        )

        plt.ylabel(
            feature_name
        )

        plt.title(
            "PEMS04 Sensor 1 - "
            f"{feature_name} "
            "Actual vs Predicted"
        )

        plt.legend()

        plt.grid(
            True,
            alpha=0.3
        )

        plt.tight_layout()

        plt.savefig(
            plot_path,
            dpi=150
        )

        plt.close()

        print(
            f"[SAVED] {plot_path}"
        )


# ============================================================
# SAVE EVALUATION SUMMARY
# ============================================================

def save_evaluation_summary(
    overall_metrics,
    feature_metrics,
    sensor_metrics,
    checkpoint,
    inference_time,
    y_true,
    y_pred
):

    summary_path = (
        EVALUATION_DIR
        / "evaluation_summary.json"
    )

    best_epoch = None
    best_val_loss = None

    if isinstance(
        checkpoint,
        dict
    ):

        best_epoch = (
            checkpoint.get(
                "epoch"
            )
        )

        best_val_loss = (
            checkpoint.get(
                "val_loss"
            )
        )

    summary = {

        "dataset":
            "PEMS04",

        "evaluation_split":
            "test",

        "device":
            str(DEVICE),

        "sensors": {

            "start":
                SENSOR_START,

            "end":
                SENSOR_END,

            "count":
                NUM_SENSORS
        },

        "features":
            FEATURE_NAMES,

        "num_features":
            NUM_FEATURES,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "model": {

            "type":
                "LSTM",

            "hidden_size":
                HIDDEN_SIZE,

            "num_layers":
                NUM_LAYERS,

            "dropout":
                DROPOUT
        },

        "checkpoint": {

            "best_epoch":
                (
                    int(best_epoch)
                    if best_epoch
                    is not None
                    else None
                ),

            "best_validation_loss":
                (
                    float(
                        best_val_loss
                    )
                    if best_val_loss
                    is not None
                    else None
                )
        },

        "test_samples":
            int(
                len(y_true)
            ),

        "prediction_shape":
            list(
                y_pred.shape
            ),

        "inference_time_seconds":
            float(
                inference_time
            ),

        "overall_metrics":
            overall_metrics,

        "feature_metrics":
            feature_metrics.to_dict(
                orient="records"
            ),

        "sensor_metrics":
            sensor_metrics.to_dict(
                orient="records"
            ),

        "files": {

            "predictions":
                "test_predictions.npz",

            "overall_metrics":
                "overall_metrics.json",

            "feature_metrics":
                "feature_metrics.csv",

            "sensor_metrics":
                "sensor_metrics.csv",

            "plots":
                "plots/"
        }
    }

    with open(
        summary_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=4
        )

    print(
        f"[SAVED] {summary_path}"
    )


# ============================================================
# PRINT RESULTS
# ============================================================

def print_results(
    overall_metrics,
    feature_metrics,
    sensor_metrics
):

    print()
    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    print()
    print(
        "[OVERALL TEST METRICS]"
    )

    print(
        f"MAE  : "
        f"{overall_metrics['MAE']:.6f}"
    )

    print(
        f"MSE  : "
        f"{overall_metrics['MSE']:.6f}"
    )

    print(
        f"RMSE : "
        f"{overall_metrics['RMSE']:.6f}"
    )

    print(
        f"MAPE : "
        f"{overall_metrics['MAPE_percent']:.4f}%"
    )

    print(
        f"R2   : "
        f"{overall_metrics['R2']:.6f}"
    )

    print()
    print(
        "[METRICS BY FEATURE]"
    )

    print(
        feature_metrics.to_string(
            index=False
        )
    )

    print()
    print(
        "[METRICS BY SENSOR]"
    )

    print(
        sensor_metrics.to_string(
            index=False
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    set_seed()

    print("=" * 70)
    print(
        "PEMS04 LSTM TRAFFIC FORECASTING "
        "EVALUATION"
    )
    print("=" * 70)

    print(
        f"[INFO] Device: {DEVICE}"
    )

    # --------------------------------------------------------
    # Configuration
    # --------------------------------------------------------

    print("=" * 70)
    print("EVALUATION CONFIGURATION")
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
        f"[INFO] Dropout         : "
        f"{DROPOUT}"
    )

    print(
        f"[INFO] Batch size      : "
        f"{BATCH_SIZE}"
    )

    print(
        f"[INFO] Sensors         : "
        f"{SENSOR_START}-{SENSOR_END}"
    )

    print(
        "[INFO] Features        : "
        "Flow + Occupancy + Speed"
    )

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    (
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test
    ) = load_data()

    # --------------------------------------------------------
    # Validate test data
    # --------------------------------------------------------

    validate_data(
        X_test,
        y_test
    )

    # --------------------------------------------------------
    # Test dataloader
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TEST DATALOADER")
    print("=" * 70)

    test_loader = (
        create_test_loader(
            X_test,
            y_test
        )
    )

    print(
        f"[INFO] Test samples : "
        f"{len(test_loader.dataset)}"
    )

    print(
        f"[INFO] Test batches : "
        f"{len(test_loader)}"
    )

    # --------------------------------------------------------
    # Load best model
    # --------------------------------------------------------

    best_model_path = (
        OUTPUT_DIR
        / "best_model.pth"
    )

    (
        model,
        checkpoint
    ) = load_model(
        model_path=best_model_path,
        num_sensors=NUM_SENSORS,
        num_features=NUM_FEATURES
    )

    # --------------------------------------------------------
    # Generate predictions
    # --------------------------------------------------------

    (
        y_pred,
        y_true,
        inference_time
    ) = generate_predictions(
        model,
        test_loader
    )

    # --------------------------------------------------------
    # Calculate metrics
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CALCULATING METRICS")
    print("=" * 70)

    overall_metrics = (
        calculate_overall_metrics(
            y_true,
            y_pred
        )
    )

    feature_metrics = (
        calculate_feature_metrics(
            y_true,
            y_pred
        )
    )

    sensor_metrics = (
        calculate_sensor_metrics(
            y_true,
            y_pred
        )
    )

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    print_results(
        overall_metrics,
        feature_metrics,
        sensor_metrics
    )

    # --------------------------------------------------------
    # Save predictions
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING PREDICTIONS")
    print("=" * 70)

    save_predictions(
        y_true,
        y_pred
    )

    # --------------------------------------------------------
    # Save metrics
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING METRICS")
    print("=" * 70)

    save_metrics(
        overall_metrics,
        feature_metrics,
        sensor_metrics
    )

    # --------------------------------------------------------
    # Save plots
    # --------------------------------------------------------

    save_prediction_plot(
        y_true,
        y_pred
    )

    # --------------------------------------------------------
    # Save summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING EVALUATION SUMMARY")
    print("=" * 70)

    save_evaluation_summary(
        overall_metrics=overall_metrics,
        feature_metrics=feature_metrics,
        sensor_metrics=sensor_metrics,
        checkpoint=checkpoint,
        inference_time=inference_time,
        y_true=y_true,
        y_pred=y_pred
    )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "EVALUATION PIPELINE COMPLETED"
    )
    print("=" * 70)

    print()
    print(
        "[RESULT]"
    )

    print(
        f"MAE  : "
        f"{overall_metrics['MAE']:.6f}"
    )

    print(
        f"RMSE : "
        f"{overall_metrics['RMSE']:.6f}"
    )

    print(
        f"MAPE : "
        f"{overall_metrics['MAPE_percent']:.4f}%"
    )

    print(
        f"R2   : "
        f"{overall_metrics['R2']:.6f}"
    )

    print()
    print(
        "[OUTPUT]"
    )

    print(
        f"[SAVED] "
        f"{EVALUATION_DIR / 'test_predictions.npz'}"
    )

    print(
        f"[SAVED] "
        f"{EVALUATION_DIR / 'overall_metrics.json'}"
    )

    print(
        f"[SAVED] "
        f"{EVALUATION_DIR / 'feature_metrics.csv'}"
    )

    print(
        f"[SAVED] "
        f"{EVALUATION_DIR / 'sensor_metrics.csv'}"
    )

    print(
        f"[SAVED] "
        f"{EVALUATION_DIR / 'evaluation_summary.json'}"
    )

    print(
        f"[SAVED] "
        f"{PLOT_DIR}"
    )

    print()
    print(
        "[NEXT] Gunakan hasil evaluation "
        "untuk membandingkan performa "
        "Flow, Occupancy, dan Speed."
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()