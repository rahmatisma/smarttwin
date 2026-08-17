"""
======================================================================
YOLO TRAFFIC LSTM HYPERPARAMETER EXPERIMENT
======================================================================

Purpose:
    Experiment with LSTM hyperparameters after selecting:
        - sequence length = 5
        - forecast horizon = 1 second

Hyperparameters:
    - hidden_size
    - num_layers
    - dropout
    - learning_rate
    - batch_size

Selection rule:
    Best configuration is selected using VALIDATION MAE.
    TEST is used only for final evaluation.

Output:
    outputs/yolo/evaluation/hyperparameter_experiment/

======================================================================
"""

from pathlib import Path
import json
import random
import copy

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import joblib
import matplotlib.pyplot as plt


# ======================================================================
# CONFIGURATION
# ======================================================================

SEED = 42

SEQUENCE_LENGTH = 5
FORECAST_HORIZON = 1

INPUT_SIZE = 96
OUTPUT_SIZE = 96

MAX_EPOCHS = 20
PATIENCE = 5

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ----------------------------------------------------------------------
# Hyperparameter configurations
# ----------------------------------------------------------------------
#
# Jangan terlalu banyak kombinasi dulu.
# Kita ingin eksperimen yang cukup informatif tetapi masih realistis
# dijalankan di CPU.
#
# Config 1:
# baseline architecture
#
# Config 2:
# smaller model
#
# Config 3:
# larger hidden size
#
# Config 4:
# more regularization
#
# Config 5:
# smaller learning rate
# ----------------------------------------------------------------------

EXPERIMENTS = [
    {
        "experiment_id": "config_01",
        "hidden_size": 128,
        "num_layers": 2,
        "dropout": 0.2,
        "learning_rate": 0.001,
        "batch_size": 32,
    },
    {
        "experiment_id": "config_02",
        "hidden_size": 64,
        "num_layers": 1,
        "dropout": 0.0,
        "learning_rate": 0.001,
        "batch_size": 32,
    },
    {
        "experiment_id": "config_03",
        "hidden_size": 256,
        "num_layers": 2,
        "dropout": 0.2,
        "learning_rate": 0.001,
        "batch_size": 32,
    },
    {
        "experiment_id": "config_04",
        "hidden_size": 128,
        "num_layers": 2,
        "dropout": 0.3,
        "learning_rate": 0.001,
        "batch_size": 32,
    },
    {
        "experiment_id": "config_05",
        "hidden_size": 128,
        "num_layers": 2,
        "dropout": 0.2,
        "learning_rate": 0.0005,
        "batch_size": 32,
    },
    {
        "experiment_id": "config_06",
        "hidden_size": 128,
        "num_layers": 2,
        "dropout": 0.2,
        "learning_rate": 0.001,
        "batch_size": 16,
    },
]


# ======================================================================
# PATHS
# ======================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "yolo"
)

PROCESSED_DIR = OUTPUT_DIR / "processed"

EVALUATION_DIR = (
    OUTPUT_DIR
    / "evaluation"
)

EXPERIMENT_DIR = (
    EVALUATION_DIR
    / "hyperparameter_experiment"
)

PLOTS_DIR = EXPERIMENT_DIR / "plots"

EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


# ======================================================================
# FILE PATHS
# ======================================================================

X_TRAIN_PATH = PROCESSED_DIR / "X_train.npy"
Y_TRAIN_PATH = PROCESSED_DIR / "y_train.npy"

X_VAL_PATH = PROCESSED_DIR / "X_val.npy"
Y_VAL_PATH = PROCESSED_DIR / "y_val.npy"

X_TEST_PATH = PROCESSED_DIR / "X_test.npy"
Y_TEST_PATH = PROCESSED_DIR / "y_test.npy"

TIMESTEP_MATRIX_PATH = PROCESSED_DIR / "timestep_matrix.npy"

SCALER_PATH = PROCESSED_DIR / "scaler_X.pkl"

FEATURE_METADATA_PATH = PROCESSED_DIR / "feature_metadata.json"


# ======================================================================
# REPRODUCIBILITY
# ======================================================================

def set_seed(seed: int = 42):

    random.seed(seed)
    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


set_seed(SEED)


# ======================================================================
# PRINT HEADER
# ======================================================================

print()
print("=" * 70)
print("YOLO TRAFFIC LSTM HYPERPARAMETER EXPERIMENT")
print("=" * 70)

print(f"[INFO] Dataset             : YOLO Traffic Dataset")
print(f"[INFO] Device              : {DEVICE}")
print(f"[INFO] Sequence length    : {SEQUENCE_LENGTH}")
print(f"[INFO] Forecast horizon   : {FORECAST_HORIZON} second")
print(f"[INFO] Input size         : {INPUT_SIZE}")
print(f"[INFO] Output size        : {OUTPUT_SIZE}")
print(f"[INFO] Max epochs         : {MAX_EPOCHS}")
print(f"[INFO] Early stop patience: {PATIENCE}")
print(f"[INFO] Number experiments : {len(EXPERIMENTS)}")

print("=" * 70)


# ======================================================================
# DATASET
# ======================================================================

class TrafficDataset(Dataset):

    def __init__(self, X, y):

        self.X = torch.tensor(
            X,
            dtype=torch.float32
        )

        self.y = torch.tensor(
            y,
            dtype=torch.float32
        )

    def __len__(self):

        return len(self.X)

    def __getitem__(self, index):

        return self.X[index], self.y[index]


# ======================================================================
# MODEL
# ======================================================================

class TrafficLSTM(nn.Module):

    def __init__(
        self,
        input_size,
        hidden_size,
        num_layers,
        output_size,
        dropout
    ):

        super().__init__()

        # PyTorch ignores dropout when num_layers = 1.
        # We explicitly use 0.0 in that case to avoid warnings.

        lstm_dropout = (
            dropout
            if num_layers > 1
            else 0.0
        )

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=lstm_dropout
        )

        self.fc = nn.Linear(
            hidden_size,
            output_size
        )

    def forward(self, x):

        output, _ = self.lstm(x)

        # Last timestep
        last_output = output[:, -1, :]

        prediction = self.fc(last_output)

        return prediction


# ======================================================================
# VALIDATION REQUIRED FILES
# ======================================================================

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

for file_path in required_files:

    if not file_path.exists():

        raise FileNotFoundError(
            f"[ERROR] Required file tidak ditemukan:\n"
            f"{file_path}"
        )

    print(f"[OK] {file_path.name}")

print()
print("[OK] Semua required files tersedia.")


# ======================================================================
# LOAD DATA
# ======================================================================

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


# ======================================================================
# DATA VALIDATION
# ======================================================================

print()
print("=" * 70)
print("VALIDATING DATA")
print("=" * 70)


def validate_array(name, array):

    nan_count = np.isnan(array).sum()
    inf_count = np.isinf(array).sum()

    print(
        f"[INFO] {name:<8} | "
        f"NaN: {nan_count:<6} | "
        f"Inf: {inf_count:<6}"
    )

    if nan_count > 0 or inf_count > 0:

        raise ValueError(
            f"{name} contains NaN or Inf."
        )


validate_array("X_train", X_train)
validate_array("y_train", y_train)

validate_array("X_val", X_val)
validate_array("y_val", y_val)

validate_array("X_test", X_test)
validate_array("y_test", y_test)


# ======================================================================
# SEQUENCE LENGTH VALIDATION
# ======================================================================

original_sequence_length = X_train.shape[1]

print()
print(f"[INFO] Original sequence length : {original_sequence_length}")
print(f"[INFO] Experiment sequence     : {SEQUENCE_LENGTH}")
print(f"[INFO] Feature count           : {X_train.shape[2]}")


if original_sequence_length < SEQUENCE_LENGTH:

    raise ValueError(
        "SEQUENCE_LENGTH lebih besar daripada "
        "sequence length dataset."
    )


# ======================================================================
# TRIM SEQUENCE
# ======================================================================

def trim_sequence(X, sequence_length):

    if X.shape[1] == sequence_length:

        return X.copy()

    return X[:, -sequence_length:, :].copy()


X_train_exp = trim_sequence(
    X_train,
    SEQUENCE_LENGTH
)

X_val_exp = trim_sequence(
    X_val,
    SEQUENCE_LENGTH
)

X_test_exp = trim_sequence(
    X_test,
    SEQUENCE_LENGTH
)


print()
print("=" * 70)
print("PREPARING EXPERIMENT DATA")
print("=" * 70)

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


# ======================================================================
# LOAD SCALER
# ======================================================================

print()
print("=" * 70)
print("LOADING SCALER")
print("=" * 70)

scaler = joblib.load(SCALER_PATH)

print(
    f"[INFO] Scaler type     : "
    f"{type(scaler).__name__}"
)

print(
    f"[INFO] Scaler features : "
    f"{getattr(scaler, 'n_features_in_', 'unknown')}"
)

print("[OK] Scaler loaded.")


# ======================================================================
# MODEL METRICS
# ======================================================================

def calculate_metrics(y_true, y_pred):

    error = y_pred - y_true

    mae = np.mean(
        np.abs(error)
    )

    mse = np.mean(
        error ** 2
    )

    rmse = np.sqrt(mse)

    return mae, rmse, mse


# ======================================================================
# ORIGINAL SCALE CONVERSION
# ======================================================================

def inverse_transform_targets(
    scaler,
    values
):

    original_shape = values.shape

    flattened = values.reshape(
        -1,
        values.shape[-1]
    )

    inverse = scaler.inverse_transform(
        flattened
    )

    return inverse.reshape(
        original_shape
    )


# ======================================================================
# TRAIN ONE EXPERIMENT
# ======================================================================

def train_experiment(
    config,
    X_train,
    y_train,
    X_val,
    y_val
):

    experiment_id = config["experiment_id"]

    hidden_size = config["hidden_size"]
    num_layers = config["num_layers"]
    dropout = config["dropout"]
    learning_rate = config["learning_rate"]
    batch_size = config["batch_size"]

    print()
    print("=" * 70)
    print(
        f"EXPERIMENT {experiment_id}"
    )
    print("=" * 70)

    print(
        f"[INFO] hidden_size    : {hidden_size}"
    )

    print(
        f"[INFO] num_layers     : {num_layers}"
    )

    print(
        f"[INFO] dropout        : {dropout}"
    )

    print(
        f"[INFO] learning_rate  : {learning_rate}"
    )

    print(
        f"[INFO] batch_size     : {batch_size}"
    )

    # --------------------------------------------------------------
    # Dataset
    # --------------------------------------------------------------

    train_dataset = TrafficDataset(
        X_train,
        y_train
    )

    val_dataset = TrafficDataset(
        X_val,
        y_val
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False
    )

    # --------------------------------------------------------------
    # Model
    # --------------------------------------------------------------

    model = TrafficLSTM(
        input_size=INPUT_SIZE,
        hidden_size=hidden_size,
        num_layers=num_layers,
        output_size=OUTPUT_SIZE,
        dropout=dropout
    ).to(DEVICE)

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=learning_rate
    )

    # --------------------------------------------------------------
    # Training
    # --------------------------------------------------------------

    best_val_loss = float("inf")

    best_epoch = 0

    best_state = None

    patience_counter = 0

    history = []

    for epoch in range(
        1,
        MAX_EPOCHS + 1
    ):

        # ==========================================================
        # TRAIN
        # ==========================================================

        model.train()

        train_losses = []

        for batch_X, batch_y in train_loader:

            batch_X = batch_X.to(DEVICE)
            batch_y = batch_y.to(DEVICE)

            optimizer.zero_grad()

            prediction = model(
                batch_X
            )

            loss = criterion(
                prediction,
                batch_y
            )

            loss.backward()

            optimizer.step()

            train_losses.append(
                loss.item()
            )

        train_loss = np.mean(
            train_losses
        )

        # ==========================================================
        # VALIDATION
        # ==========================================================

        model.eval()

        val_losses = []

        with torch.no_grad():

            for batch_X, batch_y in val_loader:

                batch_X = batch_X.to(DEVICE)
                batch_y = batch_y.to(DEVICE)

                prediction = model(
                    batch_X
                )

                loss = criterion(
                    prediction,
                    batch_y
                )

                val_losses.append(
                    loss.item()
                )

        val_loss = np.mean(
            val_losses
        )

        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss
            }
        )

        print(
            f"Epoch {epoch:02d}/{MAX_EPOCHS} | "
            f"Train Loss: {train_loss:.6f} | "
            f"Val Loss: {val_loss:.6f}"
        )

        # ==========================================================
        # EARLY STOPPING
        # ==========================================================

        if val_loss < best_val_loss:

            best_val_loss = val_loss

            best_epoch = epoch

            best_state = copy.deepcopy(
                model.state_dict()
            )

            patience_counter = 0

        else:

            patience_counter += 1

        if patience_counter >= PATIENCE:

            print(
                f"[EARLY STOP] "
                f"patience={PATIENCE}"
            )

            break

    # --------------------------------------------------------------
    # Restore best model
    # --------------------------------------------------------------

    if best_state is not None:

        model.load_state_dict(
            best_state
        )

    # --------------------------------------------------------------
    # Save history
    # --------------------------------------------------------------

    history_df = pd.DataFrame(
        history
    )

    history_path = (
        EXPERIMENT_DIR
        / f"history_{experiment_id}.csv"
    )

    history_df.to_csv(
        history_path,
        index=False
    )

    print(
        f"[SAVED] {history_path}"
    )

    # --------------------------------------------------------------
    # Save model
    # --------------------------------------------------------------

    model_path = (
        EXPERIMENT_DIR
        / f"lstm_{experiment_id}.pt"
    )

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "input_size": INPUT_SIZE,
            "hidden_size": hidden_size,
            "num_layers": num_layers,
            "output_size": OUTPUT_SIZE,
            "dropout": dropout,
            "sequence_length": SEQUENCE_LENGTH,
            "forecast_horizon": FORECAST_HORIZON,
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "best_epoch": best_epoch,
            "best_val_loss": best_val_loss,
        },
        model_path
    )

    print(
        f"[SAVED] {model_path}"
    )

    # --------------------------------------------------------------
    # Predictions
    # --------------------------------------------------------------

    model.eval()

    val_predictions = []

    test_predictions = []

    val_loader_eval = DataLoader(
        TrafficDataset(
            X_val,
            y_val
        ),
        batch_size=batch_size,
        shuffle=False
    )

    test_loader_eval = DataLoader(
        TrafficDataset(
            X_test,
            np.zeros_like(y_test)
        ),
        batch_size=batch_size,
        shuffle=False
    )

    with torch.no_grad():

        for batch_X, _ in val_loader_eval:

            batch_X = batch_X.to(DEVICE)

            prediction = model(
                batch_X
            )

            val_predictions.append(
                prediction.cpu().numpy()
            )

        for batch_X, _ in test_loader_eval:

            batch_X = batch_X.to(DEVICE)

            prediction = model(
                batch_X
            )

            test_predictions.append(
                prediction.cpu().numpy()
            )

    val_predictions = np.concatenate(
        val_predictions,
        axis=0
    )

    test_predictions = np.concatenate(
        test_predictions,
        axis=0
    )

    # --------------------------------------------------------------
    # Scaled metrics
    # --------------------------------------------------------------

    val_mae_scaled, val_rmse_scaled, val_mse_scaled = (
        calculate_metrics(
            y_val,
            val_predictions
        )
    )

    # --------------------------------------------------------------
    # Original scale
    # --------------------------------------------------------------

    val_pred_original = inverse_transform_targets(
        scaler,
        val_predictions
    )

    y_val_original = inverse_transform_targets(
        scaler,
        y_val
    )

    test_pred_original = inverse_transform_targets(
        scaler,
        test_predictions
    )

    y_test_original = inverse_transform_targets(
        scaler,
        y_test
    )

    val_mae, val_rmse, val_mse = calculate_metrics(
        y_val_original,
        val_pred_original
    )

    test_mae, test_rmse, test_mse = calculate_metrics(
        y_test_original,
        test_pred_original
    )

    # --------------------------------------------------------------
    # Save predictions
    # --------------------------------------------------------------

    np.save(
        EXPERIMENT_DIR
        / f"val_prediction_original_{experiment_id}.npy",
        val_pred_original
    )

    np.save(
        EXPERIMENT_DIR
        / f"test_prediction_original_{experiment_id}.npy",
        test_pred_original
    )

    # --------------------------------------------------------------
    # Print result
    # --------------------------------------------------------------

    print()
    print("[RESULT]")

    print(
        f"Experiment      : "
        f"{experiment_id}"
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
    print("VALIDATION - SCALED")

    print(
        f"MAE  : {val_mae_scaled:.6f}"
    )

    print(
        f"RMSE : {val_rmse_scaled:.6f}"
    )

    print(
        f"MSE  : {val_mse_scaled:.6f}"
    )

    print()
    print("VALIDATION - ORIGINAL SCALE")

    print(
        f"MAE  : {val_mae:.6f}"
    )

    print(
        f"RMSE : {val_rmse:.6f}"
    )

    print(
        f"MSE  : {val_mse:.6f}"
    )

    print()
    print("TEST - ORIGINAL SCALE")

    print(
        f"MAE  : {test_mae:.6f}"
    )

    print(
        f"RMSE : {test_rmse:.6f}"
    )

    print(
        f"MSE  : {test_mse:.6f}"
    )

    # --------------------------------------------------------------
    # Return results
    # --------------------------------------------------------------

    return {
        "experiment_id": experiment_id,

        "hidden_size": hidden_size,
        "num_layers": num_layers,
        "dropout": dropout,
        "learning_rate": learning_rate,
        "batch_size": batch_size,

        "sequence_length": SEQUENCE_LENGTH,
        "forecast_horizon": FORECAST_HORIZON,

        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,

        "val_mae_scaled": val_mae_scaled,
        "val_rmse_scaled": val_rmse_scaled,
        "val_mse_scaled": val_mse_scaled,

        "val_original_mae": val_mae,
        "val_original_rmse": val_rmse,
        "val_original_mse": val_mse,

        "test_original_mae": test_mae,
        "test_original_rmse": test_rmse,
        "test_original_mse": test_mse,

        "parameter_count": sum(
            p.numel()
            for p in model.parameters()
        ),
    }


# ======================================================================
# RUN EXPERIMENTS
# ======================================================================

results = []

for config in EXPERIMENTS:

    result = train_experiment(
        config=config,
        X_train=X_train_exp,
        y_train=y_train,
        X_val=X_val_exp,
        y_val=y_val
    )

    results.append(
        result
    )


# ======================================================================
# SAVE RESULTS
# ======================================================================

print()
print("=" * 70)
print("SAVING HYPERPARAMETER EXPERIMENT RESULTS")
print("=" * 70)

results_df = pd.DataFrame(
    results
)

results_path = (
    EXPERIMENT_DIR
    / "hyperparameter_results.csv"
)

results_df.to_csv(
    results_path,
    index=False
)

print(
    f"[SAVED] {results_path}"
)


# ======================================================================
# FIND BEST CONFIGURATION
# ======================================================================

best_by_val_mae = results_df.loc[
    results_df[
        "val_original_mae"
    ].idxmin()
]

best_by_val_rmse = results_df.loc[
    results_df[
        "val_original_rmse"
    ].idxmin()
]

best_by_val_mse = results_df.loc[
    results_df[
        "val_original_mse"
    ].idxmin()
]


# ======================================================================
# SAVE BEST CONFIGURATION
# ======================================================================

best_config = {
    "selection_rule": "validation_mae",

    "sequence_length": SEQUENCE_LENGTH,

    "forecast_horizon": FORECAST_HORIZON,

    "best_experiment_id": str(
        best_by_val_mae[
            "experiment_id"
        ]
    ),

    "hidden_size": int(
        best_by_val_mae[
            "hidden_size"
        ]
    ),

    "num_layers": int(
        best_by_val_mae[
            "num_layers"
        ]
    ),

    "dropout": float(
        best_by_val_mae[
            "dropout"
        ]
    ),

    "learning_rate": float(
        best_by_val_mae[
            "learning_rate"
        ]
    ),

    "batch_size": int(
        best_by_val_mae[
            "batch_size"
        ]
    ),

    "best_epoch": int(
        best_by_val_mae[
            "best_epoch"
        ]
    ),

    "validation_mae": float(
        best_by_val_mae[
            "val_original_mae"
        ]
    ),

    "validation_rmse": float(
        best_by_val_mae[
            "val_original_rmse"
        ]
    ),

    "validation_mse": float(
        best_by_val_mae[
            "val_original_mse"
        ]
    ),
}

best_config_path = (
    EXPERIMENT_DIR
    / "best_hyperparameters.json"
)

with open(
    best_config_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        best_config,
        f,
        indent=4
    )

print(
    f"[SAVED] {best_config_path}"
)


# ======================================================================
# PLOT VALIDATION MAE
# ======================================================================

print()
print("=" * 70)
print("CREATING RESULT PLOTS")
print("=" * 70)

plt.figure(
    figsize=(10, 6)
)

plt.bar(
    results_df[
        "experiment_id"
    ],
    results_df[
        "val_original_mae"
    ]
)

plt.xlabel(
    "Experiment"
)

plt.ylabel(
    "Validation MAE"
)

plt.title(
    "LSTM Hyperparameter Experiment - Validation MAE"
)

plt.xticks(
    rotation=30
)

plt.tight_layout()

plot_path = (
    PLOTS_DIR
    / "validation_mae_per_configuration.png"
)

plt.savefig(
    plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {plot_path}"
)


# ======================================================================
# PLOT VALIDATION RMSE
# ======================================================================

plt.figure(
    figsize=(10, 6)
)

plt.bar(
    results_df[
        "experiment_id"
    ],
    results_df[
        "val_original_rmse"
    ]
)

plt.xlabel(
    "Experiment"
)

plt.ylabel(
    "Validation RMSE"
)

plt.title(
    "LSTM Hyperparameter Experiment - Validation RMSE"
)

plt.xticks(
    rotation=30
)

plt.tight_layout()

plot_path = (
    PLOTS_DIR
    / "validation_rmse_per_configuration.png"
)

plt.savefig(
    plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {plot_path}"
)


# ======================================================================
# PLOT TEST MAE
# ======================================================================

plt.figure(
    figsize=(10, 6)
)

plt.bar(
    results_df[
        "experiment_id"
    ],
    results_df[
        "test_original_mae"
    ]
)

plt.xlabel(
    "Experiment"
)

plt.ylabel(
    "Test MAE"
)

plt.title(
    "LSTM Hyperparameter Experiment - Test MAE"
)

plt.xticks(
    rotation=30
)

plt.tight_layout()

plot_path = (
    PLOTS_DIR
    / "test_mae_per_configuration.png"
)

plt.savefig(
    plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {plot_path}"
)


# ======================================================================
# SAVE FULL REPORT
# ======================================================================

report = {
    "dataset": "YOLO Traffic Dataset",

    "device": str(DEVICE),

    "sequence_length": SEQUENCE_LENGTH,

    "forecast_horizon": FORECAST_HORIZON,

    "input_size": INPUT_SIZE,

    "output_size": OUTPUT_SIZE,

    "max_epochs": MAX_EPOCHS,

    "early_stopping_patience": PATIENCE,

    "selection_rule": (
        "Best configuration selected "
        "using validation MAE."
    ),

    "experiments": results,

    "best_by_validation_mae": (
        best_by_val_mae.to_dict()
    ),

    "best_by_validation_rmse": (
        best_by_val_rmse.to_dict()
    ),

    "best_by_validation_mse": (
        best_by_val_mse.to_dict()
    ),

    "best_configuration": best_config,
}

report_path = (
    EXPERIMENT_DIR
    / "hyperparameter_experiment_report.json"
)

with open(
    report_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        report,
        f,
        indent=4,
        default=str
    )

print(
    f"[SAVED] {report_path}"
)


# ======================================================================
# SUMMARY
# ======================================================================

print()
print("=" * 70)
print("HYPERPARAMETER EXPERIMENT SUMMARY")
print("=" * 70)

display_columns = [
    "experiment_id",
    "hidden_size",
    "num_layers",
    "dropout",
    "learning_rate",
    "batch_size",
    "best_epoch",
    "val_original_mae",
    "val_original_rmse",
    "test_original_mae",
    "test_original_rmse",
]

print()

print(
    results_df[
        display_columns
    ].to_string(
        index=False
    )
)


# ======================================================================
# BEST VALIDATION MAE
# ======================================================================

print()
print("=" * 70)
print("BEST BY VALIDATION MAE")
print("=" * 70)

print(
    f"Experiment       : "
    f"{best_by_val_mae['experiment_id']}"
)

print(
    f"Hidden size      : "
    f"{int(best_by_val_mae['hidden_size'])}"
)

print(
    f"LSTM layers      : "
    f"{int(best_by_val_mae['num_layers'])}"
)

print(
    f"Dropout          : "
    f"{float(best_by_val_mae['dropout'])}"
)

print(
    f"Learning rate    : "
    f"{float(best_by_val_mae['learning_rate'])}"
)

print(
    f"Batch size       : "
    f"{int(best_by_val_mae['batch_size'])}"
)

print(
    f"Validation MAE   : "
    f"{best_by_val_mae['val_original_mae']:.6f}"
)

print(
    f"Validation RMSE  : "
    f"{best_by_val_mae['val_original_rmse']:.6f}"
)

print(
    f"Validation MSE   : "
    f"{best_by_val_mae['val_original_mse']:.6f}"
)


# ======================================================================
# BEST VALIDATION RMSE
# ======================================================================

print()
print("=" * 70)
print("BEST BY VALIDATION RMSE")
print("=" * 70)

print(
    f"Experiment       : "
    f"{best_by_val_rmse['experiment_id']}"
)

print(
    f"Validation MAE   : "
    f"{best_by_val_rmse['val_original_mae']:.6f}"
)

print(
    f"Validation RMSE  : "
    f"{best_by_val_rmse['val_original_rmse']:.6f}"
)


# ======================================================================
# FINAL NOTICE
# ======================================================================

print()
print("=" * 70)
print("IMPORTANT")
print("=" * 70)

print(
    "[INFO] Sequence length dikunci pada 5."
)

print(
    "[INFO] Forecast horizon dikunci pada 1 second."
)

print(
    "[INFO] Pemilihan hyperparameter berdasarkan validation."
)

print(
    "[INFO] Test tidak digunakan untuk memilih konfigurasi."
)

print(
    "[INFO] Model terbaik belum otomatis menjadi final model."
)

print(
    "[INFO] Setelah tahap ini, konfigurasi terbaik akan "
    "digunakan untuk training model final."
)

print()
print(
    f"[OUTPUT] {EXPERIMENT_DIR}"
)

print("=" * 70)
print(
    "YOLO LSTM HYPERPARAMETER EXPERIMENT COMPLETED"
)
print("=" * 70)