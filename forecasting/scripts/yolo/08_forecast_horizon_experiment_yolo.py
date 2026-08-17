import json
import copy
import random
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


# ============================================================
# PATH CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "yolo"
    / "processed"
)

EVALUATION_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "yolo"
    / "evaluation"
)

EXPERIMENT_DIR = (
    EVALUATION_DIR
    / "horizon_experiment"
)

PLOT_DIR = (
    EXPERIMENT_DIR
    / "plots"
)

EXPERIMENT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PLOT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================

DATASET_NAME = "YOLO Traffic Dataset"

SEQUENCE_LENGTH = 5

# Horizon dalam timestep.
#
# Karena preprocessing menggunakan resolusi 1 detik:
#
# 1 timestep  = 1 second
# 3 timestep  = 3 seconds
# 5 timestep  = 5 seconds
# 10 timestep = 10 seconds

FORECAST_HORIZONS = [
    1,
    3,
    5,
    10
]


# ============================================================
# MODEL CONFIGURATION
# ============================================================

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


# ============================================================
# DATA SPLIT
# ============================================================

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


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

def set_seed(seed=42):

    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# FEATURE CONFIGURATION
# ============================================================

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

APPROACHES = [
    "north",
    "east",
    "south",
    "west"
]

LANES = [
    "lane_1",
    "lane_2",
    "lane_3"
]

NUM_SENSORS = (
    len(APPROACHES)
    * len(LANES)
)

NUM_FEATURES = len(
    FEATURE_NAMES
)

FEATURES_PER_TIMESTEP = (
    NUM_SENSORS
    * NUM_FEATURES
)


# ============================================================
# PRINT CONFIGURATION
# ============================================================

def print_configuration():

    print()
    print("=" * 70)
    print("YOLO TRAFFIC LSTM FORECAST HORIZON EXPERIMENT")
    print("=" * 70)

    print(
        f"[INFO] Dataset          : "
        f"{DATASET_NAME}"
    )

    print(
        f"[INFO] Device           : "
        f"{DEVICE}"
    )

    print(
        f"[INFO] Sequence length  : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[INFO] Forecast horizons: "
        f"{FORECAST_HORIZONS}"
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
        f"[INFO] Hidden size      : "
        f"{HIDDEN_SIZE}"
    )

    print(
        f"[INFO] LSTM layers      : "
        f"{NUM_LAYERS}"
    )

    print(
        f"[INFO] Dropout          : "
        f"{DROPOUT}"
    )

    print(
        f"[INFO] Batch size       : "
        f"{BATCH_SIZE}"
    )

    print(
        f"[INFO] Learning rate    : "
        f"{LEARNING_RATE}"
    )

    print(
        f"[INFO] Max epochs       : "
        f"{MAX_EPOCHS}"
    )

    print("=" * 70)


# ============================================================
# VALIDATE FILES
# ============================================================

def validate_required_files():

    print()
    print("=" * 70)
    print("VALIDATING REQUIRED FILES")
    print("=" * 70)

    required_files = [
        "timestep_matrix.npy",
        "scaler_X.pkl",
        "feature_metadata.json",
        "sensor_config.json",
        "yolo_config.json"
    ]

    for filename in required_files:

        path = (
            PROCESSED_DIR
            / filename
        )

        if not path.exists():

            raise FileNotFoundError(
                f"Required file tidak ditemukan:\n"
                f"{path}"
            )

        print(
            f"[OK] {filename}"
        )

    print()
    print(
        "[OK] Semua required files tersedia."
    )


# ============================================================
# LOAD RAW TIMESTEP MATRIX
# ============================================================

def load_timestep_matrix():

    print()
    print("=" * 70)
    print("LOADING CONTINUOUS TIMESTEP MATRIX")
    print("=" * 70)

    path = (
        PROCESSED_DIR
        / "timestep_matrix.npy"
    )

    matrix = np.load(
        path
    )

    print(
        f"[INFO] Matrix shape : "
        f"{matrix.shape}"
    )

    if matrix.ndim != 2:

        raise ValueError(
            "timestep_matrix harus "
            "berdimensi 2."
        )

    if matrix.shape[1] != FEATURES_PER_TIMESTEP:

        raise ValueError(
            "Jumlah feature tidak sesuai.\n"
            f"Expected : {FEATURES_PER_TIMESTEP}\n"
            f"Got      : {matrix.shape[1]}"
        )

    print(
        f"[INFO] Timesteps    : "
        f"{matrix.shape[0]:,}"
    )

    print(
        f"[INFO] Features     : "
        f"{matrix.shape[1]}"
    )

    return matrix.astype(
        np.float32
    )


# ============================================================
# VALIDATE MATRIX
# ============================================================

def validate_matrix(matrix):

    print()
    print("=" * 70)
    print("VALIDATING TIMESTEP MATRIX")
    print("=" * 70)

    nan_count = np.isnan(
        matrix
    ).sum()

    inf_count = np.isinf(
        matrix
    ).sum()

    print(
        f"[INFO] NaN : "
        f"{nan_count:,}"
    )

    print(
        f"[INFO] Inf : "
        f"{inf_count:,}"
    )

    if nan_count > 0:

        raise ValueError(
            "Matrix mengandung NaN."
        )

    if inf_count > 0:

        raise ValueError(
            "Matrix mengandung Inf."
        )

    print(
        "[OK] Matrix numerically valid."
    )


# ============================================================
# LOAD SCALER
# ============================================================

def load_scaler():

    print()
    print("=" * 70)
    print("LOADING SCALER")
    print("=" * 70)

    path = (
        PROCESSED_DIR
        / "scaler_X.pkl"
    )

    scaler = joblib.load(
        path
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

        if scaler.n_features_in_ != FEATURES_PER_TIMESTEP:

            raise ValueError(
                "Scaler feature count "
                "tidak sesuai."
            )

    print(
        "[OK] Scaler loaded."
    )

    return scaler


# ============================================================
# CHRONOLOGICAL SPLIT
# ============================================================

def chronological_split(
    matrix
):

    print()
    print("=" * 70)
    print("CHRONOLOGICAL SPLIT")
    print("=" * 70)

    total_timesteps = len(
        matrix
    )

    train_end = int(
        total_timesteps
        * TRAIN_RATIO
    )

    val_end = int(
        total_timesteps
        * (TRAIN_RATIO + VAL_RATIO)
    )

    train = matrix[
        :train_end
    ]

    val = matrix[
        train_end:val_end
    ]

    test = matrix[
        val_end:
    ]

    print(
        f"[INFO] Total timesteps : "
        f"{total_timesteps:,}"
    )

    print()

    print(
        f"[TRAIN] "
        f"{train.shape}"
    )

    print(
        f"[VAL]   "
        f"{val.shape}"
    )

    print(
        f"[TEST]  "
        f"{test.shape}"
    )

    print()

    print(
        "[INFO] Split ratio:"
    )

    print(
        "       Train : 70%"
    )

    print(
        "       Val   : 15%"
    )

    print(
        "       Test  : 15%"
    )

    return (
        train,
        val,
        test
    )


# ============================================================
# SCALE DATA
# ============================================================

def scale_data(
    train,
    val,
    test,
    scaler
):

    print()
    print("=" * 70)
    print("SCALING DATA")
    print("=" * 70)

    # IMPORTANT:
    #
    # scaler sudah dilatih pada training data
    # dari preprocessing asli.
    #
    # Kita TIDAK fit ulang scaler.
    #
    # Ini menjaga konsistensi dengan model
    # dan menghindari leakage.

    train_scaled = scaler.transform(
        train
    )

    val_scaled = scaler.transform(
        val
    )

    test_scaled = scaler.transform(
        test
    )

    train_scaled = train_scaled.astype(
        np.float32
    )

    val_scaled = val_scaled.astype(
        np.float32
    )

    test_scaled = test_scaled.astype(
        np.float32
    )

    print(
        f"[INFO] Train scaled : "
        f"{train_scaled.shape}"
    )

    print(
        f"[INFO] Val scaled   : "
        f"{val_scaled.shape}"
    )

    print(
        f"[INFO] Test scaled  : "
        f"{test_scaled.shape}"
    )

    print(
        "[OK] Scaling completed."
    )

    return (
        train_scaled,
        val_scaled,
        test_scaled
    )


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    data,
    sequence_length,
    forecast_horizon
):

    X = []
    y = []

    total_samples = (
        len(data)
        - sequence_length
        - forecast_horizon
        + 1
    )

    if total_samples <= 0:

        raise ValueError(
            "Data terlalu sedikit "
            "untuk membuat sequence."
        )

    for index in range(
        total_samples
    ):

        start = index

        input_end = (
            index
            + sequence_length
        )

        target_end = (
            input_end
            + forecast_horizon
        )

        input_sequence = (
            data[
                start:input_end
            ]
        )

        target_sequence = (
            data[
                input_end:target_end
            ]
        )

        # ----------------------------------------------------
        # Untuk eksperimen ini model tetap menghasilkan
        # satu kondisi traffic 96 feature.
        #
        # Horizon menentukan:
        #
        # sequence:
        # t-4 ... t
        #
        # horizon 1:
        # target = t+1
        #
        # horizon 3:
        # target = t+3
        #
        # horizon 5:
        # target = t+5
        #
        # horizon 10:
        # target = t+10
        #
        # Jadi kita tidak mengubah output size model.
        # ----------------------------------------------------

        target = (
            target_sequence[-1]
        )

        X.append(
            input_sequence
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

    return (
        X,
        y
    )


# ============================================================
# TRAFFIC LSTM
# ============================================================

class TrafficLSTM(
    nn.Module
):

    def __init__(
        self,
        input_size,
        hidden_size,
        num_layers,
        output_size,
        dropout
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
            )
        )

        self.fc = nn.Linear(
            hidden_size,
            output_size
        )

    def forward(
        self,
        x
    ):

        output, _ = self.lstm(
            x
        )

        last_output = (
            output[:, -1, :]
        )

        prediction = self.fc(
            last_output
        )

        return prediction


# ============================================================
# CREATE MODEL
# ============================================================

def create_model():

    model = TrafficLSTM(
        input_size=INPUT_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        output_size=OUTPUT_SIZE,
        dropout=DROPOUT
    )

    return model.to(
        DEVICE
    )


# ============================================================
# TRAIN ONE HORIZON
# ============================================================

def train_one_horizon(
    horizon,
    X_train,
    y_train,
    X_val,
    y_val
):

    print()
    print("-" * 70)
    print(
        f"TRAINING FORECAST HORIZON = "
        f"{horizon} SECOND"
    )
    print("-" * 70)

    train_dataset = TensorDataset(
        torch.from_numpy(
            X_train
        ),
        torch.from_numpy(
            y_train
        )
    )

    val_dataset = TensorDataset(
        torch.from_numpy(
            X_val
        ),
        torch.from_numpy(
            y_val
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

    model = create_model()

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE
    )

    best_val_loss = float(
        "inf"
    )

    best_epoch = 0

    best_state = None

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

        train_losses = []

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

            train_losses.append(
                loss.item()
            )

        train_loss = float(
            np.mean(
                train_losses
            )
        )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        model.eval()

        val_losses = []

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

                val_losses.append(
                    loss.item()
                )

        val_loss = float(
            np.mean(
                val_losses
            )
        )

        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss
            }
        )

        print(
            f"Epoch {epoch:02d}/{MAX_EPOCHS} "
            f"| Train Loss: {train_loss:.6f} "
            f"| Val Loss: {val_loss:.6f}"
        )

        # ----------------------------------------------------
        # BEST MODEL
        # ----------------------------------------------------

        if val_loss < best_val_loss:

            best_val_loss = val_loss

            best_epoch = epoch

            best_state = copy.deepcopy(
                model.state_dict()
            )

            patience_counter = 0

        else:

            patience_counter += 1

        # ----------------------------------------------------
        # EARLY STOPPING
        # ----------------------------------------------------

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

    print()

    print(
        f"[RESULT] Horizon      : "
        f"{horizon} second"
    )

    print(
        f"[RESULT] Best epoch   : "
        f"{best_epoch}"
    )

    print(
        f"[RESULT] Best val loss: "
        f"{best_val_loss:.6f}"
    )

    history_df = pd.DataFrame(
        history
    )

    history_path = (
        EXPERIMENT_DIR
        / f"history_horizon_{horizon}.csv"
    )

    history_df.to_csv(
        history_path,
        index=False
    )

    print(
        f"[SAVED] {history_path}"
    )

    model_path = (
        EXPERIMENT_DIR
        / f"lstm_horizon_{horizon}.pt"
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
                SEQUENCE_LENGTH,

            "forecast_horizon":
                horizon,

            "best_epoch":
                best_epoch,

            "best_val_loss":
                best_val_loss
        },
        model_path
    )

    print(
        f"[SAVED] {model_path}"
    )

    return (
        model,
        history_df,
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
        torch.from_numpy(
            X
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

    predictions = np.concatenate(
        predictions,
        axis=0
    )

    return predictions.astype(
        np.float32
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    actual,
    prediction
):

    error = (
        prediction
        - actual
    )

    mae = float(
        np.mean(
            np.abs(error)
        )
    )

    mse = float(
        np.mean(
            np.square(error)
        )
    )

    rmse = float(
        np.sqrt(mse)
    )

    return {
        "mae": mae,
        "rmse": rmse,
        "mse": mse
    }


# ============================================================
# INVERSE TRANSFORM
# ============================================================

def inverse_transform(
    scaler,
    data
):

    return scaler.inverse_transform(
        data
    )


# ============================================================
# PLOT TRAINING HISTORY
# ============================================================

def plot_history(
    history,
    horizon
):

    import matplotlib.pyplot as plt

    plt.figure(
        figsize=(9, 5)
    )

    plt.plot(
        history["epoch"],
        history["train_loss"],
        label="Train Loss"
    )

    plt.plot(
        history["epoch"],
        history["val_loss"],
        label="Validation Loss"
    )

    plt.xlabel(
        "Epoch"
    )

    plt.ylabel(
        "MSE Loss"
    )

    plt.title(
        f"Training History - "
        f"Forecast Horizon {horizon}s"
    )

    plt.legend()

    plt.grid(
        alpha=0.3
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / f"training_history_horizon_{horizon}.png"
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
# PLOT HORIZON COMPARISON
# ============================================================

def plot_horizon_comparison(
    results_df
):

    import matplotlib.pyplot as plt

    # --------------------------------------------------------
    # MAE
    # --------------------------------------------------------

    plt.figure(
        figsize=(9, 5)
    )

    plt.plot(
        results_df[
            "forecast_horizon"
        ],
        results_df[
            "val_original_mae"
        ],
        marker="o",
        label="Validation MAE"
    )

    plt.plot(
        results_df[
            "forecast_horizon"
        ],
        results_df[
            "test_original_mae"
        ],
        marker="o",
        label="Test MAE"
    )

    plt.xlabel(
        "Forecast Horizon (seconds)"
    )

    plt.ylabel(
        "MAE"
    )

    plt.title(
        "MAE vs Forecast Horizon"
    )

    plt.xticks(
        FORECAST_HORIZONS
    )

    plt.legend()

    plt.grid(
        alpha=0.3
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / "mae_vs_forecast_horizon.png"
    )

    plt.savefig(
        output_path,
        dpi=150
    )

    plt.close()

    print(
        f"[SAVED] {output_path}"
    )

    # --------------------------------------------------------
    # RMSE
    # --------------------------------------------------------

    plt.figure(
        figsize=(9, 5)
    )

    plt.plot(
        results_df[
            "forecast_horizon"
        ],
        results_df[
            "val_original_rmse"
        ],
        marker="o",
        label="Validation RMSE"
    )

    plt.plot(
        results_df[
            "forecast_horizon"
        ],
        results_df[
            "test_original_rmse"
        ],
        marker="o",
        label="Test RMSE"
    )

    plt.xlabel(
        "Forecast Horizon (seconds)"
    )

    plt.ylabel(
        "RMSE"
    )

    plt.title(
        "RMSE vs Forecast Horizon"
    )

    plt.xticks(
        FORECAST_HORIZONS
    )

    plt.legend()

    plt.grid(
        alpha=0.3
    )

    plt.tight_layout()

    output_path = (
        PLOT_DIR
        / "rmse_vs_forecast_horizon.png"
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
# SAVE EXPERIMENT REPORT
# ============================================================

def save_report(
    results_df
):

    report = {

        "dataset":
            DATASET_NAME,

        "experiment":
            "forecast_horizon",

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizons":
            FORECAST_HORIZONS,

        "timestamp_resolution":
            "1 second",

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

        "results":
            results_df.to_dict(
                orient="records"
            )
    }

    report_path = (
        EXPERIMENT_DIR
        / "forecast_horizon_experiment_report.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4
        )

    print(
        f"[SAVED] {report_path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    set_seed(
        RANDOM_SEED
    )

    print_configuration()

    # --------------------------------------------------------
    # 1. Validate files
    # --------------------------------------------------------

    validate_required_files()

    # --------------------------------------------------------
    # 2. Load continuous matrix
    # --------------------------------------------------------

    matrix = load_timestep_matrix()

    # --------------------------------------------------------
    # 3. Validate matrix
    # --------------------------------------------------------

    validate_matrix(
        matrix
    )

    # --------------------------------------------------------
    # 4. Load scaler
    # --------------------------------------------------------

    scaler = load_scaler()

    # --------------------------------------------------------
    # 5. Chronological split
    # --------------------------------------------------------

    (
        train,
        val,
        test
    ) = chronological_split(
        matrix
    )

    # --------------------------------------------------------
    # 6. Scale
    # --------------------------------------------------------

    (
        train_scaled,
        val_scaled,
        test_scaled
    ) = scale_data(
        train,
        val,
        test,
        scaler
    )

    # --------------------------------------------------------
    # 7. Experiment
    # --------------------------------------------------------

    results = []

    for horizon in FORECAST_HORIZONS:

        print()
        print("=" * 70)

        print(
            f"EXPERIMENT "
            f"FORECAST HORIZON = "
            f"{horizon} SECOND"
        )

        print("=" * 70)

        # ----------------------------------------------------
        # Create sequences
        # ----------------------------------------------------

        print()

        print(
            "[INFO] Creating sequences..."
        )

        (
            X_train,
            y_train
        ) = create_sequences(
            train_scaled,
            SEQUENCE_LENGTH,
            horizon
        )

        (
            X_val,
            y_val
        ) = create_sequences(
            val_scaled,
            SEQUENCE_LENGTH,
            horizon
        )

        (
            X_test,
            y_test
        ) = create_sequences(
            test_scaled,
            SEQUENCE_LENGTH,
            horizon
        )

        print(
            f"[INFO] X_train : "
            f"{X_train.shape}"
        )

        print(
            f"[INFO] y_train : "
            f"{y_train.shape}"
        )

        print(
            f"[INFO] X_val   : "
            f"{X_val.shape}"
        )

        print(
            f"[INFO] y_val   : "
            f"{y_val.shape}"
        )

        print(
            f"[INFO] X_test  : "
            f"{X_test.shape}"
        )

        print(
            f"[INFO] y_test  : "
            f"{y_test.shape}"
        )

        # ----------------------------------------------------
        # Train
        # ----------------------------------------------------

        (
            model,
            history,
            best_epoch,
            best_val_loss
        ) = train_one_horizon(
            horizon,
            X_train,
            y_train,
            X_val,
            y_val
        )

        # ----------------------------------------------------
        # Plot training history
        # ----------------------------------------------------

        plot_history(
            history,
            horizon
        )

        # ----------------------------------------------------
        # Predict
        # ----------------------------------------------------

        print()

        print(
            "[INFO] Generating predictions..."
        )

        val_prediction = predict(
            model,
            X_val
        )

        test_prediction = predict(
            model,
            X_test
        )

        # ----------------------------------------------------
        # Scaled metrics
        # ----------------------------------------------------

        val_scaled_metrics = (
            calculate_metrics(
                y_val,
                val_prediction
            )
        )

        test_scaled_metrics = (
            calculate_metrics(
                y_test,
                test_prediction
            )
        )

        # ----------------------------------------------------
        # Original scale
        # ----------------------------------------------------

        val_actual_original = (
            inverse_transform(
                scaler,
                y_val
            )
        )

        val_prediction_original = (
            inverse_transform(
                scaler,
                val_prediction
            )
        )

        test_actual_original = (
            inverse_transform(
                scaler,
                y_test
            )
        )

        test_prediction_original = (
            inverse_transform(
                scaler,
                test_prediction
            )
        )

        val_original_metrics = (
            calculate_metrics(
                val_actual_original,
                val_prediction_original
            )
        )

        test_original_metrics = (
            calculate_metrics(
                test_actual_original,
                test_prediction_original
            )
        )

        # ----------------------------------------------------
        # Print result
        # ----------------------------------------------------

        print()

        print(
            "VALIDATION - SCALED"
        )

        print(
            f"MAE  : "
            f"{val_scaled_metrics['mae']:.6f}"
        )

        print(
            f"RMSE : "
            f"{val_scaled_metrics['rmse']:.6f}"
        )

        print(
            f"MSE  : "
            f"{val_scaled_metrics['mse']:.6f}"
        )

        print()

        print(
            "VALIDATION - ORIGINAL SCALE"
        )

        print(
            f"MAE  : "
            f"{val_original_metrics['mae']:.6f}"
        )

        print(
            f"RMSE : "
            f"{val_original_metrics['rmse']:.6f}"
        )

        print(
            f"MSE  : "
            f"{val_original_metrics['mse']:.6f}"
        )

        print()

        print(
            "TEST - ORIGINAL SCALE"
        )

        print(
            f"MAE  : "
            f"{test_original_metrics['mae']:.6f}"
        )

        print(
            f"RMSE : "
            f"{test_original_metrics['rmse']:.6f}"
        )

        print(
            f"MSE  : "
            f"{test_original_metrics['mse']:.6f}"
        )

        # ----------------------------------------------------
        # Save predictions
        # ----------------------------------------------------

        np.save(
            EXPERIMENT_DIR
            / f"val_prediction_horizon_{horizon}.npy",
            val_prediction_original
        )

        np.save(
            EXPERIMENT_DIR
            / f"test_prediction_horizon_{horizon}.npy",
            test_prediction_original
        )

        np.save(
            EXPERIMENT_DIR
            / f"test_actual_horizon_{horizon}.npy",
            test_actual_original
        )

        # ----------------------------------------------------
        # Store result
        # ----------------------------------------------------

        results.append(
            {
                "forecast_horizon":
                    horizon,

                "sequence_length":
                    SEQUENCE_LENGTH,

                "best_epoch":
                    best_epoch,

                "best_val_loss_scaled":
                    best_val_loss,

                "val_scaled_mae":
                    val_scaled_metrics[
                        "mae"
                    ],

                "val_scaled_rmse":
                    val_scaled_metrics[
                        "rmse"
                    ],

                "val_scaled_mse":
                    val_scaled_metrics[
                        "mse"
                    ],

                "val_original_mae":
                    val_original_metrics[
                        "mae"
                    ],

                "val_original_rmse":
                    val_original_metrics[
                        "rmse"
                    ],

                "val_original_mse":
                    val_original_metrics[
                        "mse"
                    ],

                "test_scaled_mae":
                    test_scaled_metrics[
                        "mae"
                    ],

                "test_scaled_rmse":
                    test_scaled_metrics[
                        "rmse"
                    ],

                "test_scaled_mse":
                    test_scaled_metrics[
                        "mse"
                    ],

                "test_original_mae":
                    test_original_metrics[
                        "mae"
                    ],

                "test_original_rmse":
                    test_original_metrics[
                        "rmse"
                    ],

                "test_original_mse":
                    test_original_metrics[
                        "mse"
                    ]
            }
        )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    print()
    print("=" * 70)
    print("SAVING EXPERIMENT RESULTS")
    print("=" * 70)

    results_df = pd.DataFrame(
        results
    )

    results_path = (
        EXPERIMENT_DIR
        / "forecast_horizon_results.csv"
    )

    results_df.to_csv(
        results_path,
        index=False
    )

    print(
        f"[SAVED] {results_path}"
    )

    # ========================================================
    # PLOTS
    # ========================================================

    print()
    print("=" * 70)
    print("CREATING RESULT PLOTS")
    print("=" * 70)

    plot_horizon_comparison(
        results_df
    )

    # ========================================================
    # BEST HORIZON
    # ========================================================

    best_by_val_mae = (
        results_df
        .sort_values(
            "val_original_mae"
        )
        .iloc[0]
    )

    best_by_val_rmse = (
        results_df
        .sort_values(
            "val_original_rmse"
        )
        .iloc[0]
    )

    # ========================================================
    # SAVE REPORT
    # ========================================================

    save_report(
        results_df
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print(
        "FORECAST HORIZON EXPERIMENT SUMMARY"
    )
    print("=" * 70)

    print()

    print(
        results_df[
            [
                "forecast_horizon",
                "best_epoch",
                "val_original_mae",
                "val_original_rmse",
                "test_original_mae",
                "test_original_rmse"
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
        f"Forecast horizon : "
        f"{int(best_by_val_mae['forecast_horizon'])} second"
    )

    print(
        f"Validation MAE   : "
        f"{best_by_val_mae['val_original_mae']:.6f}"
    )

    print()

    print(
        "[BEST BY VALIDATION RMSE]"
    )

    print(
        f"Forecast horizon : "
        f"{int(best_by_val_rmse['forecast_horizon'])} second"
    )

    print(
        f"Validation RMSE  : "
        f"{best_by_val_rmse['val_original_rmse']:.6f}"
    )

    print()
    print("=" * 70)

    print(
        "IMPORTANT"
    )

    print(
        "1. Horizon dipilih berdasarkan validation."
    )

    print(
        "2. Test digunakan hanya untuk evaluasi akhir."
    )

    print(
        "3. Sequence length tetap 5."
    )

    print(
        "4. Timestamp resolution = 1 second."
    )

    print(
        "5. Horizon 1 = prediksi t+1."
    )

    print(
        "6. Horizon 3 = prediksi t+3."
    )

    print(
        "7. Horizon 5 = prediksi t+5."
    )

    print(
        "8. Horizon 10 = prediksi t+10."
    )

    print()
    print(
        "Jangan memilih horizon berdasarkan "
        "test MAE saja."
    )

    print()
    print(
        "Setelah horizon dipilih, "
        "barulah kita lanjut ke eksperimen berikutnya."
    )

    print()
    print(
        f"[OUTPUT] "
        f"{EXPERIMENT_DIR}"
    )

    print("=" * 70)

    print()
    print(
        "YOLO LSTM FORECAST HORIZON "
        "EXPERIMENT COMPLETED"
    )
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()