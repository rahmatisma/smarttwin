# ============================================================
# 07_sequence_length_experiment_yolo.py
#
# YOLO Traffic LSTM
# Sequence Length Experiment
#
# Purpose:
#   Compare LSTM performance using different input sequence lengths
#   while keeping:
#       - dataset split
#       - scaler
#       - architecture
#       - hidden size
#       - number of layers
#       - dropout
#       - batch size
#       - learning rate
#       - forecast horizon
#       - optimizer
#       - random seed
#
# Current available window:
#   X_train : (1027, 15, 96)
#   X_val   : (180, 15, 96)
#   X_test  : (252, 15, 96)
#
# Experiments:
#   sequence_length = 5
#   sequence_length = 10
#   sequence_length = 15
#
# ============================================================

import os
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from torch.utils.data import TensorDataset, DataLoader
from sklearn.metrics import mean_absolute_error, mean_squared_error


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "yolo"
)

PROCESSED_DIR = OUTPUT_DIR / "processed"

EXPERIMENT_DIR = (
    OUTPUT_DIR
    / "evaluation"
    / "sequence_experiment"
)

PLOT_DIR = EXPERIMENT_DIR / "plots"

EXPERIMENT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PLOT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ------------------------------------------------------------
# Dataset
# ------------------------------------------------------------

X_TRAIN_PATH = PROCESSED_DIR / "X_train.npy"
Y_TRAIN_PATH = PROCESSED_DIR / "y_train.npy"

X_VAL_PATH = PROCESSED_DIR / "X_val.npy"
Y_VAL_PATH = PROCESSED_DIR / "y_val.npy"

X_TEST_PATH = PROCESSED_DIR / "X_test.npy"
Y_TEST_PATH = PROCESSED_DIR / "y_test.npy"

SCALER_PATH = PROCESSED_DIR / "scaler_X.pkl"

FEATURE_METADATA_PATH = PROCESSED_DIR / "feature_metadata.json"


# ------------------------------------------------------------
# Experiment settings
# ------------------------------------------------------------

SEQUENCE_LENGTHS = [
    5,
    10,
    15,
]

FORECAST_HORIZON = 1

INPUT_SIZE = 96
OUTPUT_SIZE = 96

HIDDEN_SIZE = 128
NUM_LAYERS = 2
DROPOUT = 0.2

BATCH_SIZE = 32
LEARNING_RATE = 0.001

MAX_EPOCHS = 20

PATIENCE = 5

RANDOM_SEED = 42

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# REPRODUCIBILITY
# ============================================================

def set_seed(seed=42):

    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():

        torch.cuda.manual_seed(seed)

        torch.cuda.manual_seed_all(seed)

    # Reproducibility
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


set_seed(RANDOM_SEED)


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 70)
print("YOLO TRAFFIC LSTM SEQUENCE LENGTH EXPERIMENT")
print("=" * 70)

print(f"[INFO] Project root     : {PROJECT_ROOT}")
print(f"[INFO] Processed dir    : {PROCESSED_DIR}")
print(f"[INFO] Experiment dir   : {EXPERIMENT_DIR}")
print(f"[INFO] Device           : {DEVICE}")
print(f"[INFO] Sequence lengths : {SEQUENCE_LENGTHS}")
print(f"[INFO] Forecast horizon : {FORECAST_HORIZON} second")

print("=" * 70)


# ============================================================
# HELPER
# ============================================================

def require_file(path):

    if not path.exists():

        raise FileNotFoundError(
            f"\n[ERROR] Required file tidak ditemukan:\n{path}"
        )


# ============================================================
# VALIDATE FILES
# ============================================================

print()
print("=" * 70)
print("VALIDATING REQUIRED FILES")
print("=" * 70)

required_files = [

    X_TRAIN_PATH,
    Y_TRAIN_PATH,

    X_VAL_PATH,
    Y_VAL_PATH,

    X_TEST_PATH,
    Y_TEST_PATH,

    SCALER_PATH,
    FEATURE_METADATA_PATH,
]

for path in required_files:

    require_file(path)

    print(f"[OK] {path.name}")


# ============================================================
# LOAD DATA
# ============================================================

print()
print("=" * 70)
print("LOADING DATA")
print("=" * 70)

X_train = np.load(X_TRAIN_PATH)
y_train = np.load(Y_TRAIN_PATH)

X_val = np.load(X_VAL_PATH)
y_val = np.load(Y_VAL_PATH)

X_test = np.load(X_TEST_PATH)
y_test = np.load(Y_TEST_PATH)


print(f"[INFO] X_train : {X_train.shape}")
print(f"[INFO] y_train : {y_train.shape}")

print(f"[INFO] X_val   : {X_val.shape}")
print(f"[INFO] y_val   : {y_val.shape}")

print(f"[INFO] X_test  : {X_test.shape}")
print(f"[INFO] y_test  : {y_test.shape}")


# ============================================================
# DATA VALIDATION
# ============================================================

print()
print("=" * 70)
print("VALIDATING DATA")
print("=" * 70)


def validate_array(name, array):

    nan_count = np.isnan(array).sum()

    inf_count = np.isinf(array).sum()

    print(
        f"[INFO] {name:<8} | "
        f"NaN: {nan_count:<5} | "
        f"Inf: {inf_count:<5}"
    )

    if nan_count > 0:

        raise ValueError(
            f"{name} contains NaN."
        )

    if inf_count > 0:

        raise ValueError(
            f"{name} contains Inf."
        )


validate_array("X_train", X_train)
validate_array("y_train", y_train)

validate_array("X_val", X_val)
validate_array("y_val", y_val)

validate_array("X_test", X_test)
validate_array("y_test", y_test)


# ============================================================
# SHAPE VALIDATION
# ============================================================

if X_train.ndim != 3:

    raise ValueError(
        f"X_train harus 3D. "
        f"Ditemukan {X_train.ndim}D."
    )

if X_val.ndim != 3:

    raise ValueError(
        f"X_val harus 3D. "
        f"Ditemukan {X_val.ndim}D."
    )

if X_test.ndim != 3:

    raise ValueError(
        f"X_test harus 3D. "
        f"Ditemukan {X_test.ndim}D."
    )


original_sequence_length = X_train.shape[1]

feature_count = X_train.shape[2]


print()
print(f"[INFO] Original sequence length : {original_sequence_length}")
print(f"[INFO] Feature count            : {feature_count}")


if feature_count != INPUT_SIZE:

    raise ValueError(
        f"Expected {INPUT_SIZE} features, "
        f"got {feature_count}."
    )


if y_train.shape[1] != OUTPUT_SIZE:

    raise ValueError(
        f"Expected y_train output size "
        f"{OUTPUT_SIZE}, got {y_train.shape[1]}."
    )


# ============================================================
# VALIDATE SEQUENCE LENGTHS
# ============================================================

for seq_len in SEQUENCE_LENGTHS:

    if seq_len > original_sequence_length:

        raise ValueError(
            f"Sequence length {seq_len} lebih besar "
            f"dari window yang tersedia "
            f"{original_sequence_length}."
        )


# ============================================================
# FEATURE METADATA
# ============================================================

print()
print("=" * 70)
print("LOADING FEATURE METADATA")
print("=" * 70)

with open(
    FEATURE_METADATA_PATH,
    "r",
    encoding="utf-8"
) as f:

    metadata = json.load(f)


if isinstance(metadata, dict):

    feature_metadata = metadata.get(
        "features",
        metadata
    )

else:

    feature_metadata = metadata


if not isinstance(feature_metadata, list):

    raise ValueError(
        "Format feature_metadata.json tidak dikenali."
    )


print(
    f"[INFO] Feature metadata : "
    f"{len(feature_metadata)} features"
)


# ============================================================
# LOAD SCALER
# ============================================================

print()
print("=" * 70)
print("LOADING SCALER")
print("=" * 70)

import joblib


scaler = joblib.load(
    SCALER_PATH
)


print(
    f"[INFO] Scaler type : "
    f"{type(scaler).__name__}"
)


if hasattr(
    scaler,
    "n_features_in_"
):

    print(
        f"[INFO] Scaler features : "
        f"{scaler.n_features_in_}"
    )

    if scaler.n_features_in_ != INPUT_SIZE:

        raise ValueError(
            "Scaler feature count tidak cocok."
        )


print("[OK] Scaler loaded.")


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
        dropout=0.0
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

        self.fc = nn.Linear(
            hidden_size,
            output_size
        )


    def forward(self, x):

        output, _ = self.lstm(x)

        last_output = output[:, -1, :]

        prediction = self.fc(
            last_output
        )

        return prediction


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    actual,
    prediction
):

    mae = mean_absolute_error(
        actual.reshape(-1),
        prediction.reshape(-1)
    )

    mse = mean_squared_error(
        actual.reshape(-1),
        prediction.reshape(-1)
    )

    rmse = np.sqrt(mse)

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "mse": float(mse),
    }


# ============================================================
# ORIGINAL SCALE
# ============================================================

def inverse_transform(
    scaler,
    data
):

    original_shape = data.shape

    flattened = data.reshape(
        -1,
        original_shape[-1]
    )

    transformed = scaler.inverse_transform(
        flattened
    )

    return transformed.reshape(
        original_shape
    )


# ============================================================
# PREPARE SEQUENCE
# ============================================================

def prepare_sequence(
    X,
    sequence_length
):

    return X[
        :,
        -sequence_length:,
        :
    ]


# ============================================================
# TRAIN FUNCTION
# ============================================================

def train_model(
    X_train_exp,
    y_train_exp,
    X_val_exp,
    y_val_exp,
    sequence_length
):

    print()
    print("-" * 70)

    print(
        f"TRAINING SEQUENCE LENGTH = "
        f"{sequence_length}"
    )

    print("-" * 70)


    train_dataset = TensorDataset(

        torch.tensor(
            X_train_exp,
            dtype=torch.float32
        ),

        torch.tensor(
            y_train_exp,
            dtype=torch.float32
        )
    )


    val_dataset = TensorDataset(

        torch.tensor(
            X_val_exp,
            dtype=torch.float32
        ),

        torch.tensor(
            y_val_exp,
            dtype=torch.float32
        )
    )


    train_loader = DataLoader(

        train_dataset,

        batch_size=BATCH_SIZE,

        shuffle=True
    )


    val_loader = DataLoader(

        val_dataset,

        batch_size=BATCH_SIZE,

        shuffle=False
    )


    model = TrafficLSTM(

        input_size=INPUT_SIZE,

        hidden_size=HIDDEN_SIZE,

        num_layers=NUM_LAYERS,

        output_size=OUTPUT_SIZE,

        dropout=DROPOUT
    ).to(DEVICE)


    criterion = nn.MSELoss()


    optimizer = torch.optim.Adam(

        model.parameters(),

        lr=LEARNING_RATE
    )


    best_val_loss = float("inf")

    best_state = None

    best_epoch = 0

    patience_counter = 0


    history = []


    for epoch in range(
        1,
        MAX_EPOCHS + 1
    ):

        # ----------------------------------------------------
        # TRAIN
        # ----------------------------------------------------

        model.train()

        train_loss_sum = 0.0

        train_count = 0


        for batch_x, batch_y in train_loader:

            batch_x = batch_x.to(
                DEVICE
            )

            batch_y = batch_y.to(
                DEVICE
            )


            optimizer.zero_grad()


            prediction = model(
                batch_x
            )


            loss = criterion(
                prediction,
                batch_y
            )


            loss.backward()


            optimizer.step()


            batch_size_actual = (
                batch_x.size(0)
            )


            train_loss_sum += (
                loss.item()
                * batch_size_actual
            )

            train_count += (
                batch_size_actual
            )


        train_loss = (
            train_loss_sum
            / train_count
        )


        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        model.eval()

        val_loss_sum = 0.0

        val_count = 0


        with torch.no_grad():

            for batch_x, batch_y in val_loader:

                batch_x = batch_x.to(
                    DEVICE
                )

                batch_y = batch_y.to(
                    DEVICE
                )


                prediction = model(
                    batch_x
                )


                loss = criterion(
                    prediction,
                    batch_y
                )


                batch_size_actual = (
                    batch_x.size(0)
                )


                val_loss_sum += (
                    loss.item()
                    * batch_size_actual
                )

                val_count += (
                    batch_size_actual
                )


        val_loss = (
            val_loss_sum
            / val_count
        )


        history.append({

            "epoch": epoch,

            "train_loss": float(
                train_loss
            ),

            "val_loss": float(
                val_loss
            )
        })


        print(

            f"Epoch "
            f"{epoch:02d}/{MAX_EPOCHS} | "

            f"Train Loss: "
            f"{train_loss:.6f} | "

            f"Val Loss: "
            f"{val_loss:.6f}"
        )


        # ----------------------------------------------------
        # EARLY STOPPING
        # ----------------------------------------------------

        if val_loss < best_val_loss:

            best_val_loss = val_loss

            best_epoch = epoch

            patience_counter = 0

            best_state = {
                key: value.detach().cpu().clone()

                for key, value
                in model.state_dict().items()
            }

        else:

            patience_counter += 1


        if patience_counter >= PATIENCE:

            print(
                f"[EARLY STOP] "
                f"patience={PATIENCE}"
            )

            break


    # --------------------------------------------------------
    # RESTORE BEST MODEL
    # --------------------------------------------------------

    if best_state is not None:

        model.load_state_dict(
            best_state
        )


    return (
        model,
        history,
        best_epoch,
        best_val_loss
    )


# ============================================================
# PREDICTION
# ============================================================

def predict(
    model,
    X
):

    dataset = TensorDataset(

        torch.tensor(
            X,
            dtype=torch.float32
        )
    )


    loader = DataLoader(

        dataset,

        batch_size=BATCH_SIZE,

        shuffle=False
    )


    predictions = []


    model.eval()


    with torch.no_grad():

        for (batch_x,) in loader:

            batch_x = batch_x.to(
                DEVICE
            )

            output = model(
                batch_x
            )

            predictions.append(
                output.cpu().numpy()
            )


    return np.concatenate(
        predictions,
        axis=0
    )


# ============================================================
# EXPERIMENT LOOP
# ============================================================

all_results = []

all_histories = {}


for sequence_length in SEQUENCE_LENGTHS:

    print()
    print("=" * 70)

    print(
        f"EXPERIMENT "
        f"SEQUENCE LENGTH = "
        f"{sequence_length}"
    )

    print("=" * 70)


    # --------------------------------------------------------
    # Prepare data
    # --------------------------------------------------------

    X_train_exp = prepare_sequence(
        X_train,
        sequence_length
    )

    X_val_exp = prepare_sequence(
        X_val,
        sequence_length
    )

    X_test_exp = prepare_sequence(
        X_test,
        sequence_length
    )


    print(
        f"[INFO] X_train experiment : "
        f"{X_train_exp.shape}"
    )

    print(
        f"[INFO] X_val experiment   : "
        f"{X_val_exp.shape}"
    )

    print(
        f"[INFO] X_test experiment  : "
        f"{X_test_exp.shape}"
    )


    # --------------------------------------------------------
    # Reproducibility
    # --------------------------------------------------------

    set_seed(
        RANDOM_SEED
    )


    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    (
        model,
        history,
        best_epoch,
        best_val_loss
    ) = train_model(

        X_train_exp,
        y_train,

        X_val_exp,
        y_val,

        sequence_length
    )


    all_histories[
        str(sequence_length)
    ] = history


    # --------------------------------------------------------
    # Validation prediction
    # --------------------------------------------------------

    val_prediction_scaled = predict(
        model,
        X_val_exp
    )


    # --------------------------------------------------------
    # Test prediction
    # --------------------------------------------------------

    test_prediction_scaled = predict(
        model,
        X_test_exp
    )


    # --------------------------------------------------------
    # Scaled metrics
    # --------------------------------------------------------

    val_metrics_scaled = calculate_metrics(
        y_val,
        val_prediction_scaled
    )


    test_metrics_scaled = calculate_metrics(
        y_test,
        test_prediction_scaled
    )


    # --------------------------------------------------------
    # Inverse transform
    # --------------------------------------------------------

    y_val_original = inverse_transform(
        scaler,
        y_val
    )

    val_prediction_original = inverse_transform(
        scaler,
        val_prediction_scaled
    )


    y_test_original = inverse_transform(
        scaler,
        y_test
    )

    test_prediction_original = inverse_transform(
        scaler,
        test_prediction_scaled
    )


    # --------------------------------------------------------
    # Original scale metrics
    # --------------------------------------------------------

    val_metrics_original = calculate_metrics(
        y_val_original,
        val_prediction_original
    )


    test_metrics_original = calculate_metrics(
        y_test_original,
        test_prediction_original
    )


    # --------------------------------------------------------
    # Save model
    # --------------------------------------------------------

    model_path = (
        EXPERIMENT_DIR
        / f"lstm_seq_{sequence_length}.pt"
    )


    torch.save(

        {
            "model_state_dict":
                model.state_dict(),

            "input_size":
                INPUT_SIZE,

            "hidden_size":
                HIDDEN_SIZE,

            "num_layers":
                NUM_LAYERS,

            "dropout":
                DROPOUT,

            "output_size":
                OUTPUT_SIZE,

            "sequence_length":
                sequence_length,

            "forecast_horizon":
                FORECAST_HORIZON,

            "best_epoch":
                best_epoch,

            "best_val_loss":
                best_val_loss,
        },

        model_path
    )


    print(
        f"[SAVED] {model_path}"
    )


    # --------------------------------------------------------
    # Save history
    # --------------------------------------------------------

    history_path = (
        EXPERIMENT_DIR
        / f"history_seq_{sequence_length}.csv"
    )


    pd.DataFrame(
        history
    ).to_csv(
        history_path,
        index=False
    )


    print(
        f"[SAVED] {history_path}"
    )


    # --------------------------------------------------------
    # Save predictions
    # --------------------------------------------------------

    prediction_path = (
        EXPERIMENT_DIR
        / f"prediction_seq_{sequence_length}.npy"
    )


    np.save(
        prediction_path,
        test_prediction_original
    )


    # --------------------------------------------------------
    # Result row
    # --------------------------------------------------------

    result = {

        "sequence_length":
            sequence_length,

        "forecast_horizon":
            FORECAST_HORIZON,

        "best_epoch":
            best_epoch,

        "best_val_loss":
            best_val_loss,

        # Validation scaled
        "val_scaled_mae":
            val_metrics_scaled["mae"],

        "val_scaled_rmse":
            val_metrics_scaled["rmse"],

        "val_scaled_mse":
            val_metrics_scaled["mse"],

        # Validation original
        "val_original_mae":
            val_metrics_original["mae"],

        "val_original_rmse":
            val_metrics_original["rmse"],

        "val_original_mse":
            val_metrics_original["mse"],

        # Test scaled
        "test_scaled_mae":
            test_metrics_scaled["mae"],

        "test_scaled_rmse":
            test_metrics_scaled["rmse"],

        "test_scaled_mse":
            test_metrics_scaled["mse"],

        # Test original
        "test_original_mae":
            test_metrics_original["mae"],

        "test_original_rmse":
            test_metrics_original["rmse"],

        "test_original_mse":
            test_metrics_original["mse"],
    }


    all_results.append(
        result
    )


    # --------------------------------------------------------
    # Print result
    # --------------------------------------------------------

    print()
    print(
        "[RESULT]"
    )

    print(
        f"Sequence length : "
        f"{sequence_length}"
    )

    print(
        f"Best epoch      : "
        f"{best_epoch}"
    )

    print(
        f"Best val loss   : "
        f"{best_val_loss:.6f}"
    )

    print()

    print(
        "VALIDATION - ORIGINAL SCALE"
    )

    print(
        f"MAE  : "
        f"{val_metrics_original['mae']:.6f}"
    )

    print(
        f"RMSE : "
        f"{val_metrics_original['rmse']:.6f}"
    )

    print(
        f"MSE  : "
        f"{val_metrics_original['mse']:.6f}"
    )

    print()

    print(
        "TEST - ORIGINAL SCALE"
    )

    print(
        f"MAE  : "
        f"{test_metrics_original['mae']:.6f}"
    )

    print(
        f"RMSE : "
        f"{test_metrics_original['rmse']:.6f}"
    )

    print(
        f"MSE  : "
        f"{test_metrics_original['mse']:.6f}"
    )


# ============================================================
# SAVE RESULT TABLE
# ============================================================

print()
print("=" * 70)
print("SAVING EXPERIMENT RESULTS")
print("=" * 70)


results_df = pd.DataFrame(
    all_results
)


results_df = results_df.sort_values(
    by="val_original_mae"
)


results_path = (
    EXPERIMENT_DIR
    / "sequence_length_results.csv"
)


results_df.to_csv(
    results_path,
    index=False
)


print(
    f"[SAVED] {results_path}"
)


# ============================================================
# SAVE JSON REPORT
# ============================================================

report = {

    "experiment":
        "sequence_length",

    "dataset":
        "YOLO Traffic Dataset",

    "model":
        "LSTM",

    "input_size":
        INPUT_SIZE,

    "output_size":
        OUTPUT_SIZE,

    "hidden_size":
        HIDDEN_SIZE,

    "num_layers":
        NUM_LAYERS,

    "dropout":
        DROPOUT,

    "batch_size":
        BATCH_SIZE,

    "learning_rate":
        LEARNING_RATE,

    "max_epochs":
        MAX_EPOCHS,

    "patience":
        PATIENCE,

    "forecast_horizon":
        FORECAST_HORIZON,

    "sequence_lengths":
        SEQUENCE_LENGTHS,

    "results":
        all_results
}


report_path = (
    EXPERIMENT_DIR
    / "sequence_length_experiment_report.json"
)


with open(
    report_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        report,
        f,
        indent=4
    )


print(
    f"[SAVED] {report_path}"
)


# ============================================================
# PLOT RESULTS
# ============================================================

print()
print("=" * 70)
print("CREATING RESULT PLOTS")
print("=" * 70)


import matplotlib.pyplot as plt


# ------------------------------------------------------------
# Validation MAE
# ------------------------------------------------------------

plt.figure(
    figsize=(10, 6)
)

plt.plot(

    results_df[
        "sequence_length"
    ],

    results_df[
        "val_original_mae"
    ],

    marker="o"
)

plt.xlabel(
    "Sequence Length"
)

plt.ylabel(
    "Validation MAE"
)

plt.title(
    "YOLO Traffic LSTM - Validation MAE vs Sequence Length"
)

plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


path = (
    PLOT_DIR
    / "validation_mae_vs_sequence_length.png"
)


plt.savefig(
    path,
    dpi=150
)

plt.close()


print(
    f"[SAVED] {path}"
)


# ------------------------------------------------------------
# Test MAE
# ------------------------------------------------------------

plt.figure(
    figsize=(10, 6)
)

plt.plot(

    results_df[
        "sequence_length"
    ],

    results_df[
        "test_original_mae"
    ],

    marker="o"
)

plt.xlabel(
    "Sequence Length"
)

plt.ylabel(
    "Test MAE"
)

plt.title(
    "YOLO Traffic LSTM - Test MAE vs Sequence Length"
)

plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


path = (
    PLOT_DIR
    / "test_mae_vs_sequence_length.png"
)


plt.savefig(
    path,
    dpi=150
)

plt.close()


print(
    f"[SAVED] {path}"
)


# ------------------------------------------------------------
# Test RMSE
# ------------------------------------------------------------

plt.figure(
    figsize=(10, 6)
)

plt.plot(

    results_df[
        "sequence_length"
    ],

    results_df[
        "test_original_rmse"
    ],

    marker="o"
)

plt.xlabel(
    "Sequence Length"
)

plt.ylabel(
    "Test RMSE"
)

plt.title(
    "YOLO Traffic LSTM - Test RMSE vs Sequence Length"
)

plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


path = (
    PLOT_DIR
    / "test_rmse_vs_sequence_length.png"
)


plt.savefig(
    path,
    dpi=150
)

plt.close()


print(
    f"[SAVED] {path}"
)


# ============================================================
# BEST RESULT
# ============================================================

best_mae_row = results_df.iloc[
    results_df[
        "val_original_mae"
    ].argmin()
]


best_rmse_row = results_df.iloc[
    results_df[
        "val_original_rmse"
    ].argmin()
]


print()
print("=" * 70)
print("SEQUENCE LENGTH EXPERIMENT SUMMARY")
print("=" * 70)


print()
print(
    "RESULTS:"
)

print(
    results_df[
        [
            "sequence_length",
            "best_epoch",
            "val_original_mae",
            "val_original_rmse",
            "test_original_mae",
            "test_original_rmse",
        ]
    ].to_string(
        index=False
    )
)


print()
print(
    "[BEST BY VALIDATION MAE]"
)

print(
    f"Sequence length : "
    f"{int(best_mae_row['sequence_length'])}"
)

print(
    f"Validation MAE  : "
    f"{best_mae_row['val_original_mae']:.6f}"
)


print()
print(
    "[BEST BY VALIDATION RMSE]"
)

print(
    f"Sequence length : "
    f"{int(best_rmse_row['sequence_length'])}"
)

print(
    f"Validation RMSE : "
    f"{best_rmse_row['val_original_rmse']:.6f}"
)


# ============================================================
# IMPORTANT WARNING
# ============================================================

print()
print("=" * 70)
print("IMPORTANT")
print("=" * 70)

print(
    "[INFO] Test set digunakan untuk evaluasi akhir."
)

print(
    "[INFO] Pemilihan sequence length sebaiknya "
    "berdasarkan validation performance."
)

print(
    "[INFO] Jangan memilih sequence length "
    "hanya berdasarkan test MAE."
)

print(
    "[INFO] Forecast horizon masih tetap "
    "1 second pada eksperimen ini."
)

print(
    "[INFO] Horizon >1 second membutuhkan "
    "rebuilding windows dari time-series kontinu."
)


print()
print("=" * 70)
print("SEQUENCE LENGTH EXPERIMENT COMPLETED")
print("=" * 70)