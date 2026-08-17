from pathlib import Path
import json
import random
import pickle

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


# ======================================================================
# CONFIGURATION
# ======================================================================

SEED = 42

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

SEQUENCE_LENGTH = 5
FORECAST_HORIZON = 1

INPUT_SIZE = 96
OUTPUT_SIZE = 96

HIDDEN_SIZE = 64
NUM_LAYERS = 1
DROPOUT = 0.0

LEARNING_RATE = 0.001
BATCH_SIZE = 32

# --------------------------------------------------
# IMPORTANT:
# We use the best epoch found in config_02.
# --------------------------------------------------
FINAL_EPOCHS = 8

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


# ======================================================================
# PATHS
# ======================================================================

SCRIPT_DIR = Path(__file__).resolve().parent

# scripts/yolo -> scripts -> forecasting
PROJECT_ROOT = SCRIPT_DIR.parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "yolo"
)

PROCESSED_DIR = OUTPUT_DIR / "processed"

EVALUATION_DIR = OUTPUT_DIR / "evaluation"

FINAL_DIR = (
    EVALUATION_DIR
    / "final_model"
)

PLOTS_DIR = FINAL_DIR / "plots"

FINAL_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PLOTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ======================================================================
# FILE PATHS
# ======================================================================

TIMESTEP_MATRIX_PATH = (
    PROCESSED_DIR
    / "timestep_matrix.npy"
)

SCALER_PATH = (
    PROCESSED_DIR
    / "scaler_X.pkl"
)

FEATURE_METADATA_PATH = (
    PROCESSED_DIR
    / "feature_metadata.json"
)

SENSOR_CONFIG_PATH = (
    PROCESSED_DIR
    / "sensor_config.json"
)

YOLO_CONFIG_PATH = (
    PROCESSED_DIR
    / "yolo_config.json"
)


# ======================================================================
# OUTPUT PATHS
# ======================================================================

MODEL_PATH = (
    FINAL_DIR
    / "lstm_final_model.pt"
)

HISTORY_PATH = (
    FINAL_DIR
    / "final_training_history.csv"
)

METRICS_PATH = (
    FINAL_DIR
    / "final_model_metrics.json"
)

PREDICTION_PATH = (
    FINAL_DIR
    / "y_test_prediction_final_original.npy"
)

ACTUAL_PATH = (
    FINAL_DIR
    / "y_test_actual_final_original.npy"
)

PERSISTENCE_PATH = (
    FINAL_DIR
    / "persistence_prediction_final_original.npy"
)

RESULTS_CSV_PATH = (
    FINAL_DIR
    / "final_prediction_results.csv"
)

CONFIG_PATH = (
    FINAL_DIR
    / "final_model_config.json"
)


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
print("YOLO TRAFFIC LSTM FINAL MODEL TRAINING")
print("=" * 70)

print(f"[INFO] Dataset             : YOLO Traffic Dataset")
print(f"[INFO] Device              : {DEVICE}")
print(f"[INFO] Sequence length     : {SEQUENCE_LENGTH}")
print(f"[INFO] Forecast horizon    : {FORECAST_HORIZON} second")
print(f"[INFO] Input size          : {INPUT_SIZE}")
print(f"[INFO] Output size         : {OUTPUT_SIZE}")
print(f"[INFO] Hidden size         : {HIDDEN_SIZE}")
print(f"[INFO] LSTM layers         : {NUM_LAYERS}")
print(f"[INFO] Dropout             : {DROPOUT}")
print(f"[INFO] Learning rate       : {LEARNING_RATE}")
print(f"[INFO] Batch size          : {BATCH_SIZE}")
print(f"[INFO] Final epochs        : {FINAL_EPOCHS}")
print()
print(f"[INFO] Project root        : {PROJECT_ROOT}")
print(f"[INFO] Processed dir       : {PROCESSED_DIR}")
print(f"[INFO] Final model dir     : {FINAL_DIR}")
print("=" * 70)


# ======================================================================
# VALIDATE FILES
# ======================================================================

print()
print("=" * 70)
print("VALIDATING REQUIRED FILES")
print("=" * 70)


required_files = {
    "timestep_matrix.npy": TIMESTEP_MATRIX_PATH,
    "scaler_X.pkl": SCALER_PATH,
    "feature_metadata.json": FEATURE_METADATA_PATH,
}


for name, path in required_files.items():

    if not path.exists():

        raise FileNotFoundError(
            f"\n[ERROR] Required file tidak ditemukan:\n{path}"
        )

    print(f"[OK] {name}")


print()
print("[OK] Semua required files tersedia.")


# ======================================================================
# LOAD CONTINUOUS TIMESTEP MATRIX
# ======================================================================

print()
print("=" * 70)
print("LOADING CONTINUOUS TIMESTEP MATRIX")
print("=" * 70)


timestep_matrix = np.load(
    TIMESTEP_MATRIX_PATH
).astype(np.float32)


print(
    f"[INFO] Matrix shape : {timestep_matrix.shape}"
)

TOTAL_TIMESTEPS = timestep_matrix.shape[0]
FEATURE_COUNT = timestep_matrix.shape[1]

print(
    f"[INFO] Timesteps    : {TOTAL_TIMESTEPS}"
)

print(
    f"[INFO] Features     : {FEATURE_COUNT}"
)


# ======================================================================
# VALIDATE MATRIX
# ======================================================================

print()
print("=" * 70)
print("VALIDATING TIMESTEP MATRIX")
print("=" * 70)


nan_count = np.isnan(
    timestep_matrix
).sum()

inf_count = np.isinf(
    timestep_matrix
).sum()


print(f"[INFO] NaN : {nan_count}")
print(f"[INFO] Inf : {inf_count}")


if nan_count > 0:

    raise ValueError(
        "[ERROR] timestep_matrix masih memiliki NaN."
    )


if inf_count > 0:

    raise ValueError(
        "[ERROR] timestep_matrix masih memiliki Inf."
    )


if FEATURE_COUNT != INPUT_SIZE:

    raise ValueError(
        f"[ERROR] Feature count {FEATURE_COUNT} "
        f"tidak sama dengan INPUT_SIZE {INPUT_SIZE}."
    )


print("[OK] Matrix numerically valid.")


# ======================================================================
# LOAD SCALER
# ======================================================================

print()
print("=" * 70)
print("LOADING SCALER")
print("=" * 70)


with open(
    SCALER_PATH,
    "rb"
) as f:

    scaler = pickle.load(f)


print(
    f"[INFO] Scaler type     : {type(scaler).__name__}"
)

print(
    f"[INFO] Scaler features : {scaler.n_features_in_}"
)


if scaler.n_features_in_ != FEATURE_COUNT:

    raise ValueError(
        "[ERROR] Jumlah feature scaler tidak cocok."
    )


print("[OK] Scaler loaded.")


# ======================================================================
# CHRONOLOGICAL SPLIT
# ======================================================================

print()
print("=" * 70)
print("CHRONOLOGICAL SPLIT")
print("=" * 70)


train_end = int(
    TOTAL_TIMESTEPS * TRAIN_RATIO
)

val_end = int(
    TOTAL_TIMESTEPS
    * (TRAIN_RATIO + VAL_RATIO)
)


train_raw = timestep_matrix[
    :train_end
]

val_raw = timestep_matrix[
    train_end:val_end
]

test_raw = timestep_matrix[
    val_end:
]


print(
    f"[TRAIN] {train_raw.shape}"
)

print(
    f"[VAL]   {val_raw.shape}"
)

print(
    f"[TEST]  {test_raw.shape}"
)

print()

print("[INFO] Split ratio:")

print(
    f"       Train : {TRAIN_RATIO * 100:.0f}%"
)

print(
    f"       Val   : {VAL_RATIO * 100:.0f}%"
)

print(
    f"       Test  : {TEST_RATIO * 100:.0f}%"
)


# ======================================================================
# SCALE USING EXISTING TRAIN-FITTED SCALER
# ======================================================================

print()
print("=" * 70)
print("SCALING DATA")
print("=" * 70)


train_scaled = scaler.transform(
    train_raw
).astype(np.float32)


val_scaled = scaler.transform(
    val_raw
).astype(np.float32)


test_scaled = scaler.transform(
    test_raw
).astype(np.float32)


print(
    f"[INFO] Train scaled : {train_scaled.shape}"
)

print(
    f"[INFO] Val scaled   : {val_scaled.shape}"
)

print(
    f"[INFO] Test scaled  : {test_scaled.shape}"
)


# ======================================================================
# CREATE SEQUENCES
# ======================================================================

def create_sequences(
    data,
    sequence_length,
    forecast_horizon
):
    """
    Creates:

        X[t] = data[t : t + sequence_length]

        y[t] = data[
            t + sequence_length + forecast_horizon - 1
        ]

    For horizon=1:

        X = [t-4, ..., t]
        y = t+1
    """

    X = []

    y = []

    max_start = (
        len(data)
        - sequence_length
        - forecast_horizon
        + 1
    )

    for i in range(max_start):

        x_window = data[
            i:
            i + sequence_length
        ]

        target_index = (
            i
            + sequence_length
            + forecast_horizon
            - 1
        )

        target = data[
            target_index
        ]

        X.append(
            x_window
        )

        y.append(
            target
        )

    X = np.asarray(
        X,
        dtype=np.float32
    )

    y = np.asarray(
        y,
        dtype=np.float32
    )

    return X, y


# ======================================================================
# PREPARE TRAIN + VALIDATION DATA
# ======================================================================

print()
print("=" * 70)
print("PREPARING FINAL TRAINING DATA")
print("=" * 70)


# --------------------------------------------------
# For final training:
#
# Train + validation are combined.
#
# Test remains completely untouched.
#
# We concatenate TRAIN and VAL chronologically.
# --------------------------------------------------

train_val_scaled = np.concatenate(
    [
        train_scaled,
        val_scaled
    ],
    axis=0
)


X_train_final, y_train_final = create_sequences(
    train_val_scaled,
    SEQUENCE_LENGTH,
    FORECAST_HORIZON
)


# --------------------------------------------------
# Test needs historical context.
#
# We use the final SEQUENCE_LENGTH points
# immediately before the test period.
#
# This is valid because they are historical values,
# not future test information.
# --------------------------------------------------

test_context = np.concatenate(
    [
        train_val_scaled[
            -SEQUENCE_LENGTH:
        ],

        test_scaled
    ],
    axis=0
)


X_test_final, y_test_final = create_sequences(
    test_context,
    SEQUENCE_LENGTH,
    FORECAST_HORIZON
)


print(
    f"[INFO] X_train_final : {X_train_final.shape}"
)

print(
    f"[INFO] y_train_final : {y_train_final.shape}"
)

print(
    f"[INFO] X_test_final  : {X_test_final.shape}"
)

print(
    f"[INFO] y_test_final  : {y_test_final.shape}"
)


# ======================================================================
# VALIDATE FINAL DATA
# ======================================================================

print()
print("=" * 70)
print("VALIDATING FINAL DATA")
print("=" * 70)


datasets = {
    "X_train_final": X_train_final,
    "y_train_final": y_train_final,
    "X_test_final": X_test_final,
    "y_test_final": y_test_final,
}


for name, data in datasets.items():

    nan_count = np.isnan(data).sum()

    inf_count = np.isinf(data).sum()

    print(
        f"[INFO] {name:<15} | "
        f"NaN: {nan_count:<6} | "
        f"Inf: {inf_count:<6}"
    )

    if nan_count > 0:

        raise ValueError(
            f"[ERROR] {name} memiliki NaN."
        )

    if inf_count > 0:

        raise ValueError(
            f"[ERROR] {name} memiliki Inf."
        )


print("[OK] Final datasets valid.")


# ======================================================================
# PYTORCH DATASETS
# ======================================================================

train_dataset = TensorDataset(
    torch.from_numpy(X_train_final),
    torch.from_numpy(y_train_final)
)


test_dataset = TensorDataset(
    torch.from_numpy(X_test_final),
    torch.from_numpy(y_test_final)
)


train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True
)


test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False
)


# ======================================================================
# LSTM MODEL
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

        # PyTorch ignores dropout internally when
        # num_layers=1, but we explicitly set it to 0.
        effective_dropout = (
            dropout
            if num_layers > 1
            else 0.0
        )

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=effective_dropout
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


# ======================================================================
# CREATE MODEL
# ======================================================================

print()
print("=" * 70)
print("CREATING FINAL MODEL")
print("=" * 70)


model = TrafficLSTM(
    input_size=INPUT_SIZE,
    hidden_size=HIDDEN_SIZE,
    num_layers=NUM_LAYERS,
    output_size=OUTPUT_SIZE,
    dropout=DROPOUT
).to(DEVICE)


parameter_count = sum(
    p.numel()
    for p in model.parameters()
    if p.requires_grad
)


print(
    f"[INFO] Trainable parameters : {parameter_count:,}"
)

print(
    f"[INFO] Model device         : {DEVICE}"
)


# ======================================================================
# OPTIMIZER / LOSS
# ======================================================================

criterion = nn.MSELoss()

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=LEARNING_RATE
)


# ======================================================================
# TRAIN FINAL MODEL
# ======================================================================

print()
print("=" * 70)
print("TRAINING FINAL MODEL")
print("=" * 70)

print()
print(
    "[INFO] Train + validation data digunakan "
    "untuk final training."
)

print(
    "[INFO] Test data TIDAK digunakan selama training."
)

print(
    f"[INFO] Training epochs : {FINAL_EPOCHS}"
)

print()


history = []


for epoch in range(
    1,
    FINAL_EPOCHS + 1
):

    model.train()

    running_loss = 0.0

    total_samples = 0


    for X_batch, y_batch in train_loader:

        X_batch = X_batch.to(
            DEVICE
        )

        y_batch = y_batch.to(
            DEVICE
        )


        optimizer.zero_grad()


        prediction = model(
            X_batch
        )


        loss = criterion(
            prediction,
            y_batch
        )


        loss.backward()


        optimizer.step()


        batch_size_current = (
            X_batch.size(0)
        )


        running_loss += (
            loss.item()
            * batch_size_current
        )


        total_samples += (
            batch_size_current
        )


    epoch_loss = (
        running_loss
        / total_samples
    )


    history.append(
        {
            "epoch": epoch,
            "train_loss": epoch_loss
        }
    )


    print(
        f"Epoch {epoch:02d}/{FINAL_EPOCHS} "
        f"| Train Loss: {epoch_loss:.6f}"
    )


# ======================================================================
# SAVE TRAINING HISTORY
# ======================================================================

history_df = pd.DataFrame(
    history
)


history_df.to_csv(
    HISTORY_PATH,
    index=False
)


print()
print(
    f"[SAVED] {HISTORY_PATH}"
)


# ======================================================================
# SAVE MODEL
# ======================================================================

torch.save(
    {
        "model_state_dict": model.state_dict(),

        "input_size": INPUT_SIZE,

        "hidden_size": HIDDEN_SIZE,

        "num_layers": NUM_LAYERS,

        "output_size": OUTPUT_SIZE,

        "dropout": DROPOUT,

        "sequence_length": SEQUENCE_LENGTH,

        "forecast_horizon": FORECAST_HORIZON,

        "learning_rate": LEARNING_RATE,

        "batch_size": BATCH_SIZE,

        "final_epochs": FINAL_EPOCHS,

        "seed": SEED,

        "parameter_count": parameter_count
    },
    MODEL_PATH
)


print(
    f"[SAVED] {MODEL_PATH}"
)


# ======================================================================
# PREDICTION
# ======================================================================

print()
print("=" * 70)
print("GENERATING FINAL TEST PREDICTIONS")
print("=" * 70)


model.eval()

predictions_scaled = []


with torch.no_grad():

    for X_batch, _ in test_loader:

        X_batch = X_batch.to(
            DEVICE
        )

        prediction = model(
            X_batch
        )

        predictions_scaled.append(
            prediction.cpu().numpy()
        )


predictions_scaled = np.concatenate(
    predictions_scaled,
    axis=0
)


print(
    f"[INFO] Prediction scaled : "
    f"{predictions_scaled.shape}"
)


# ======================================================================
# INVERSE TRANSFORM
# ======================================================================

print()
print("=" * 70)
print("CONVERTING PREDICTIONS TO ORIGINAL SCALE")
print("=" * 70)


predictions_original = (
    scaler.inverse_transform(
        predictions_scaled
    )
)


actual_original = (
    scaler.inverse_transform(
        y_test_final
    )
)


print(
    f"[INFO] Actual       : "
    f"{actual_original.shape}"
)

print(
    f"[INFO] Prediction   : "
    f"{predictions_original.shape}"
)


# ======================================================================
# PERSISTENCE BASELINE
# ======================================================================

print()
print("=" * 70)
print("CREATING PERSISTENCE BASELINE")
print("=" * 70)


# --------------------------------------------------
# Persistence:
#
# prediction(t+1) = latest observed value
#
# Since X_test_final contains the historical
# sequence, the last timestep is the persistence
# prediction.
# --------------------------------------------------

persistence_scaled = (
    X_test_final[:, -1, :]
)


persistence_original = (
    scaler.inverse_transform(
        persistence_scaled
    )
)


print(
    f"[INFO] Persistence : "
    f"{persistence_original.shape}"
)


# ======================================================================
# METRICS
# ======================================================================

def calculate_metrics(
    actual,
    prediction
):

    error = (
        prediction
        - actual
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

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "mse": float(mse)
    }


lstm_metrics = calculate_metrics(
    actual_original,
    predictions_original
)


persistence_metrics = calculate_metrics(
    actual_original,
    persistence_original
)


# ======================================================================
# IMPROVEMENT
# ======================================================================

def calculate_improvement(
    baseline,
    model_value
):

    if baseline == 0:

        return None

    return float(
        (
            baseline
            - model_value
        )
        / baseline
        * 100.0
    )


improvement = {

    "mae_percent": calculate_improvement(
        persistence_metrics["mae"],
        lstm_metrics["mae"]
    ),

    "rmse_percent": calculate_improvement(
        persistence_metrics["rmse"],
        lstm_metrics["rmse"]
    ),

    "mse_percent": calculate_improvement(
        persistence_metrics["mse"],
        lstm_metrics["mse"]
    )
}


# ======================================================================
# SAMPLE-LEVEL METRICS
# ======================================================================

lstm_sample_mae = np.mean(
    np.abs(
        predictions_original
        - actual_original
    ),
    axis=1
)


persistence_sample_mae = np.mean(
    np.abs(
        persistence_original
        - actual_original
    ),
    axis=1
)


lstm_wins = (
    lstm_sample_mae
    < persistence_sample_mae
)


lstm_win_rate = (
    np.mean(lstm_wins)
    * 100
)


# ======================================================================
# PRINT FINAL RESULTS
# ======================================================================

print()
print("=" * 70)
print("FINAL TEST PERFORMANCE")
print("=" * 70)

print()
print("LSTM FINAL MODEL")

print(
    f"  MAE  : {lstm_metrics['mae']:.6f}"
)

print(
    f"  RMSE : {lstm_metrics['rmse']:.6f}"
)

print(
    f"  MSE  : {lstm_metrics['mse']:.6f}"
)


print()
print("PERSISTENCE BASELINE")

print(
    f"  MAE  : {persistence_metrics['mae']:.6f}"
)

print(
    f"  RMSE : {persistence_metrics['rmse']:.6f}"
)

print(
    f"  MSE  : {persistence_metrics['mse']:.6f}"
)


print()
print("LSTM IMPROVEMENT OVER PERSISTENCE")

print(
    f"  MAE  : "
    f"{improvement['mae_percent']:.2f}%"
)

print(
    f"  RMSE : "
    f"{improvement['rmse_percent']:.2f}%"
)

print(
    f"  MSE  : "
    f"{improvement['mse_percent']:.2f}%"
)


print()
print("SAMPLE-LEVEL")

print(
    f"  LSTM MAE win rate : "
    f"{lstm_win_rate:.2f}%"
)


# ======================================================================
# SAVE PREDICTIONS
# ======================================================================

np.save(
    PREDICTION_PATH,
    predictions_original
)


np.save(
    ACTUAL_PATH,
    actual_original
)


np.save(
    PERSISTENCE_PATH,
    persistence_original
)


print()
print("=" * 70)
print("SAVING FINAL PREDICTIONS")
print("=" * 70)

print(
    f"[SAVED] {PREDICTION_PATH}"
)

print(
    f"[SAVED] {ACTUAL_PATH}"
)

print(
    f"[SAVED] {PERSISTENCE_PATH}"
)


# ======================================================================
# SAVE PREDICTION CSV
# ======================================================================

prediction_rows = []


for i in range(
    len(actual_original)
):

    actual_mae = np.mean(
        np.abs(
            actual_original[i]
            - predictions_original[i]
        )
    )

    persistence_mae = np.mean(
        np.abs(
            actual_original[i]
            - persistence_original[i]
        )
    )


    prediction_rows.append(
        {
            "sample_index": i,

            "lstm_mae": float(
                actual_mae
            ),

            "persistence_mae": float(
                persistence_mae
            ),

            "lstm_better": bool(
                actual_mae
                < persistence_mae
            )
        }
    )


prediction_results_df = pd.DataFrame(
    prediction_rows
)


prediction_results_df.to_csv(
    RESULTS_CSV_PATH,
    index=False
)


print(
    f"[SAVED] {RESULTS_CSV_PATH}"
)


# ======================================================================
# SAVE CONFIGURATION
# ======================================================================

final_config = {

    "dataset": "YOLO Traffic Dataset",

    "device": str(DEVICE),

    "sequence_length": SEQUENCE_LENGTH,

    "forecast_horizon": FORECAST_HORIZON,

    "input_size": INPUT_SIZE,

    "output_size": OUTPUT_SIZE,

    "hidden_size": HIDDEN_SIZE,

    "num_layers": NUM_LAYERS,

    "dropout": DROPOUT,

    "learning_rate": LEARNING_RATE,

    "batch_size": BATCH_SIZE,

    "final_epochs": FINAL_EPOCHS,

    "seed": SEED,

    "train_ratio": TRAIN_RATIO,

    "val_ratio": VAL_RATIO,

    "test_ratio": TEST_RATIO,

    "parameter_count": parameter_count,

    "training_data": "train + validation",

    "test_usage": "final evaluation only",

    "selection_source":
        "hyperparameter config_02",

    "selection_reason":
        "best validation MAE and RMSE"
}


with open(
    CONFIG_PATH,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        final_config,
        f,
        indent=4
    )


print(
    f"[SAVED] {CONFIG_PATH}"
)


# ======================================================================
# SAVE METRICS REPORT
# ======================================================================

metrics_report = {

    "model": {

        "mae": lstm_metrics["mae"],

        "rmse": lstm_metrics["rmse"],

        "mse": lstm_metrics["mse"]
    },

    "persistence": {

        "mae": persistence_metrics["mae"],

        "rmse": persistence_metrics["rmse"],

        "mse": persistence_metrics["mse"]
    },

    "improvement_over_persistence_percent":
        improvement,

    "sample_level": {

        "lstm_mae_win_rate_percent":
            float(lstm_win_rate),

        "total_test_samples":
            int(len(actual_original)),

        "lstm_mae_wins":
            int(np.sum(lstm_wins))
    },

    "dataset": {

        "total_timesteps":
            int(TOTAL_TIMESTEPS),

        "train_timesteps":
            int(len(train_raw)),

        "validation_timesteps":
            int(len(val_raw)),

        "test_timesteps":
            int(len(test_raw))
    },

    "model_configuration":
        final_config
}


with open(
    METRICS_PATH,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        metrics_report,
        f,
        indent=4
    )


print(
    f"[SAVED] {METRICS_PATH}"
)


# ======================================================================
# PLOT TRAINING LOSS
# ======================================================================

print()
print("=" * 70)
print("CREATING FINAL MODEL PLOTS")
print("=" * 70)


plt.figure(
    figsize=(10, 6)
)

plt.plot(
    history_df["epoch"],
    history_df["train_loss"],
    marker="o"
)

plt.title(
    "Final LSTM Training Loss"
)

plt.xlabel(
    "Epoch"
)

plt.ylabel(
    "MSE Loss"
)

plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


training_plot_path = (
    PLOTS_DIR
    / "final_training_loss.png"
)


plt.savefig(
    training_plot_path,
    dpi=150
)

plt.close()


print(
    f"[SAVED] {training_plot_path}"
)


# ======================================================================
# PLOT TEST MAE COMPARISON
# ======================================================================

plt.figure(
    figsize=(10, 6)
)

plt.plot(
    lstm_sample_mae,
    label="LSTM",
    linewidth=1.5
)

plt.plot(
    persistence_sample_mae,
    label="Persistence",
    linewidth=1.5
)

plt.title(
    "Test Sample MAE: LSTM vs Persistence"
)

plt.xlabel(
    "Test Sample"
)

plt.ylabel(
    "MAE"
)

plt.legend()

plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


sample_mae_plot_path = (
    PLOTS_DIR
    / "test_sample_mae_lstm_vs_persistence.png"
)


plt.savefig(
    sample_mae_plot_path,
    dpi=150
)

plt.close()


print(
    f"[SAVED] {sample_mae_plot_path}"
)


# ======================================================================
# PLOT ACTUAL VS PREDICTION
# ======================================================================

# --------------------------------------------------
# Use the first feature only for visualization.
# Feature name will be loaded from metadata when
# available.
# --------------------------------------------------

feature_name = "feature_0"


try:

    with open(
        FEATURE_METADATA_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        feature_metadata = json.load(f)


    if isinstance(
        feature_metadata,
        list
    ):

        if len(feature_metadata) > 0:

            first_item = (
                feature_metadata[0]
            )

            if isinstance(
                first_item,
                dict
            ):

                feature_name = (
                    first_item.get(
                        "feature_name",
                        first_item.get(
                            "name",
                            "feature_0"
                        )
                    )
                )


    elif isinstance(
        feature_metadata,
        dict
    ):

        features = (
            feature_metadata.get(
                "features",
                []
            )
        )

        if (
            isinstance(features, list)
            and len(features) > 0
        ):

            first_item = features[0]

            if isinstance(
                first_item,
                dict
            ):

                feature_name = (
                    first_item.get(
                        "feature_name",
                        first_item.get(
                            "name",
                            "feature_0"
                        )
                    )
                )

except Exception:

    feature_name = "feature_0"


plot_count = min(
    100,
    len(actual_original)
)


plt.figure(
    figsize=(14, 6)
)

plt.plot(
    range(plot_count),
    actual_original[
        :plot_count,
        0
    ],
    label="Actual",
    linewidth=1.5
)

plt.plot(
    range(plot_count),
    predictions_original[
        :plot_count,
        0
    ],
    label="LSTM",
    linewidth=1.5
)

plt.plot(
    range(plot_count),
    persistence_original[
        :plot_count,
        0
    ],
    label="Persistence",
    linewidth=1.2,
    linestyle="--"
)

plt.title(
    f"Final Model Prediction vs Actual - {feature_name}"
)

plt.xlabel(
    "Test Sample"
)

plt.ylabel(
    "Traffic Value"
)

plt.legend()

plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


prediction_plot_path = (
    PLOTS_DIR
    / "actual_vs_prediction_feature_0.png"
)


plt.savefig(
    prediction_plot_path,
    dpi=150
)

plt.close()


print(
    f"[SAVED] {prediction_plot_path}"
)


# ======================================================================
# FINAL SUMMARY
# ======================================================================

print()
print("=" * 70)
print("FINAL MODEL SUMMARY")
print("=" * 70)

print()

print("[FINAL CONFIGURATION]")

print(
    f"Sequence length : "
    f"{SEQUENCE_LENGTH}"
)

print(
    f"Forecast horizon: "
    f"{FORECAST_HORIZON} second"
)

print(
    f"Hidden size     : "
    f"{HIDDEN_SIZE}"
)

print(
    f"LSTM layers     : "
    f"{NUM_LAYERS}"
)

print(
    f"Dropout         : "
    f"{DROPOUT}"
)

print(
    f"Learning rate   : "
    f"{LEARNING_RATE}"
)

print(
    f"Batch size      : "
    f"{BATCH_SIZE}"
)

print(
    f"Final epochs    : "
    f"{FINAL_EPOCHS}"
)


print()

print("[FINAL TEST PERFORMANCE]")

print(
    f"LSTM MAE        : "
    f"{lstm_metrics['mae']:.6f}"
)

print(
    f"LSTM RMSE       : "
    f"{lstm_metrics['rmse']:.6f}"
)

print(
    f"LSTM MSE        : "
    f"{lstm_metrics['mse']:.6f}"
)


print()

print("[PERSISTENCE BASELINE]")

print(
    f"Persistence MAE : "
    f"{persistence_metrics['mae']:.6f}"
)

print(
    f"Persistence RMSE: "
    f"{persistence_metrics['rmse']:.6f}"
)

print(
    f"Persistence MSE : "
    f"{persistence_metrics['mse']:.6f}"
)


print()

print("[LSTM vs PERSISTENCE]")

print(
    f"MAE improvement : "
    f"{improvement['mae_percent']:.2f}%"
)

print(
    f"RMSE improvement: "
    f"{improvement['rmse_percent']:.2f}%"
)

print(
    f"MSE improvement : "
    f"{improvement['mse_percent']:.2f}%"
)

print(
    f"MAE win rate    : "
    f"{lstm_win_rate:.2f}%"
)


print()

print("[OUTPUT DIRECTORY]")

print(
    FINAL_DIR
)


print()
print("=" * 70)
print("YOLO LSTM FINAL MODEL TRAINING COMPLETED")
print("=" * 70)