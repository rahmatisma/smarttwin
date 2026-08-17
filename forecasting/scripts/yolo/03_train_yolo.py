from pathlib import Path
import json
import random
import pickle

import numpy as np
import torch
import torch.nn as nn

from torch.utils.data import TensorDataset, DataLoader


# ============================================================
# YOLO TRAFFIC LSTM BASELINE TRAINING
# ============================================================
#
# PIPELINE SETELAH PREPROCESSING
#
# 1. Load hasil preprocessing
#       X_train, y_train
#       X_val,   y_val
#       X_test,  y_test
#
# 2. Validasi bentuk dan numerical data
#
# 3. Konversi NumPy -> PyTorch Tensor
#
# 4. Membuat DataLoader
#
# 5. Membuat model LSTM baseline
#
# 6. Training menggunakan TRAINING SET
#
# 7. Validasi setiap epoch menggunakan VALIDATION SET
#
# 8. Early stopping berdasarkan validation loss
#
# 9. Menyimpan BEST MODEL
#
# 10. Evaluasi akhir pada TEST SET
#
# 11. Menyimpan:
#       - best_model.pt
#       - training_history.json
#       - training_config.json
#       - baseline_test_result.json
#
# ------------------------------------------------------------
#
# MODEL INPUT
#
# 12 sensors
# × 8 traffic features
# = 96 features / timestep
#
# Sequence length = 15 timestep
#
# Input:
#     (batch, 15, 96)
#
# Output:
#     (batch, 96)
#
# Artinya model memprediksi seluruh kondisi traffic
# 1 detik berikutnya untuk seluruh 12 sensor.
#
# ------------------------------------------------------------
#
# CATATAN PENTING
#
# Ini adalah BASELINE.
#
# Belum melakukan:
# - hyperparameter tuning
# - sequence length experiment
# - temporal resolution experiment
# - architecture comparison
#
# Tujuan baseline adalah mendapatkan angka awal
# yang nantinya menjadi pembanding eksperimen.
# ============================================================


# ============================================================
# PATH
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

FORECASTING_DIR = (
    SCRIPT_DIR.parent.parent
)

OUTPUT_ROOT = (
    FORECASTING_DIR
    / "outputs"
    / "yolo"
)

PROCESSED_DIR = (
    OUTPUT_ROOT
    / "processed"
)

MODEL_DIR = (
    OUTPUT_ROOT
    / "models"
)


# ============================================================
# DATA FILES
# ============================================================

X_TRAIN_PATH = (
    PROCESSED_DIR
    / "X_train.npy"
)

Y_TRAIN_PATH = (
    PROCESSED_DIR
    / "y_train.npy"
)

X_VAL_PATH = (
    PROCESSED_DIR
    / "X_val.npy"
)

Y_VAL_PATH = (
    PROCESSED_DIR
    / "y_val.npy"
)

X_TEST_PATH = (
    PROCESSED_DIR
    / "X_test.npy"
)

Y_TEST_PATH = (
    PROCESSED_DIR
    / "y_test.npy"
)

SCALER_PATH = (
    PROCESSED_DIR
    / "scaler_X.pkl"
)


# ============================================================
# TRAINING CONFIGURATION
# ============================================================

RANDOM_SEED = 42

BATCH_SIZE = 32

MAX_EPOCHS = 100

LEARNING_RATE = 0.001

WEIGHT_DECAY = 0.0


# ============================================================
# LSTM CONFIGURATION
# ============================================================

INPUT_SIZE = 96

HIDDEN_SIZE = 128

NUM_LAYERS = 2

DROPOUT = 0.2

OUTPUT_SIZE = 96


# ============================================================
# EARLY STOPPING
# ============================================================

EARLY_STOPPING_PATIENCE = 15

MIN_DELTA = 1e-5


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# RANDOM SEED
# ============================================================

def set_seed():
    """
    Membuat eksperimen reproducible.
    """

    random.seed(
        RANDOM_SEED
    )

    np.random.seed(
        RANDOM_SEED
    )

    torch.manual_seed(
        RANDOM_SEED
    )

    if torch.cuda.is_available():

        torch.cuda.manual_seed(
            RANDOM_SEED
        )

        torch.cuda.manual_seed_all(
            RANDOM_SEED
        )


# ============================================================
# DIRECTORY
# ============================================================

def ensure_directories():

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# LOAD DATA
# ============================================================

def load_numpy_data():

    print_header(
        "LOADING PREPROCESSED DATA"
    )

    required_files = [
        X_TRAIN_PATH,
        Y_TRAIN_PATH,
        X_VAL_PATH,
        Y_VAL_PATH,
        X_TEST_PATH,
        Y_TEST_PATH,
    ]

    for path in required_files:

        if not path.exists():

            raise FileNotFoundError(
                f"File tidak ditemukan:\n{path}"
            )

    X_train = np.load(
        X_TRAIN_PATH
    )

    y_train = np.load(
        Y_TRAIN_PATH
    )

    X_val = np.load(
        X_VAL_PATH
    )

    y_val = np.load(
        Y_VAL_PATH
    )

    X_test = np.load(
        X_TEST_PATH
    )

    y_test = np.load(
        Y_TEST_PATH
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

    return (
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test,
    )


# ============================================================
# DATA VALIDATION
# ============================================================

def validate_numpy_data(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test,
):

    print_header(
        "NUMERICAL DATA VALIDATION"
    )

    datasets = {
        "X_train": X_train,
        "y_train": y_train,
        "X_val": X_val,
        "y_val": y_val,
        "X_test": X_test,
        "y_test": y_test,
    }

    for name, data in datasets.items():

        nan_count = np.isnan(
            data
        ).sum()

        inf_count = np.isinf(
            data
        ).sum()

        print(
            f"[INFO] {name:8s} | "
            f"NaN: {nan_count:,} | "
            f"Inf: {inf_count:,}"
        )

        if (
            nan_count > 0
            or inf_count > 0
        ):

            raise ValueError(
                f"{name} mengandung "
                "NaN atau Inf."
            )

    print(
        "[OK] Semua dataset "
        "numerically valid."
    )


# ============================================================
# SHAPE VALIDATION
# ============================================================

def validate_shapes(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test,
):

    print_header(
        "SHAPE VALIDATION"
    )

    expected_train_input = (
        INPUT_SIZE
    )

    expected_output = (
        OUTPUT_SIZE
    )

    # --------------------------------------------------------
    # TRAIN
    # --------------------------------------------------------

    if X_train.ndim != 3:

        raise ValueError(
            "X_train harus memiliki "
            "3 dimensi: "
            "(samples, timesteps, features)."
        )

    if X_train.shape[2] != (
        expected_train_input
    ):

        raise ValueError(
            f"X_train feature size salah. "
            f"Expected {expected_train_input}, "
            f"got {X_train.shape[2]}"
        )

    if y_train.ndim != 2:

        raise ValueError(
            "y_train harus memiliki "
            "2 dimensi: "
            "(samples, features)."
        )

    if y_train.shape[1] != (
        expected_output
    ):

        raise ValueError(
            f"y_train output size salah. "
            f"Expected {expected_output}, "
            f"got {y_train.shape[1]}"
        )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if X_val.shape[2] != (
        expected_train_input
    ):

        raise ValueError(
            "X_val feature size tidak sesuai."
        )

    if y_val.shape[1] != (
        expected_output
    ):

        raise ValueError(
            "y_val output size tidak sesuai."
        )

    # --------------------------------------------------------
    # TEST
    # --------------------------------------------------------

    if X_test.shape[2] != (
        expected_train_input
    ):

        raise ValueError(
            "X_test feature size tidak sesuai."
        )

    if y_test.shape[1] != (
        expected_output
    ):

        raise ValueError(
            "y_test output size tidak sesuai."
        )

    # --------------------------------------------------------
    # SAMPLE COUNT
    # --------------------------------------------------------

    if len(X_train) != len(y_train):

        raise ValueError(
            "Jumlah X_train dan y_train "
            "tidak sama."
        )

    if len(X_val) != len(y_val):

        raise ValueError(
            "Jumlah X_val dan y_val "
            "tidak sama."
        )

    if len(X_test) != len(y_test):

        raise ValueError(
            "Jumlah X_test dan y_test "
            "tidak sama."
        )

    print(
        "[OK] Shape validation passed."
    )


# ============================================================
# PYTORCH DATASET
# ============================================================

def create_dataloaders(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test,
):

    print_header(
        "CREATING DATALOADERS"
    )

    # --------------------------------------------------------
    # NumPy -> Tensor
    # --------------------------------------------------------

    X_train_tensor = torch.tensor(
        X_train,
        dtype=torch.float32
    )

    y_train_tensor = torch.tensor(
        y_train,
        dtype=torch.float32
    )

    X_val_tensor = torch.tensor(
        X_val,
        dtype=torch.float32
    )

    y_val_tensor = torch.tensor(
        y_val,
        dtype=torch.float32
    )

    X_test_tensor = torch.tensor(
        X_test,
        dtype=torch.float32
    )

    y_test_tensor = torch.tensor(
        y_test,
        dtype=torch.float32
    )

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    train_dataset = TensorDataset(
        X_train_tensor,
        y_train_tensor
    )

    val_dataset = TensorDataset(
        X_val_tensor,
        y_val_tensor
    )

    test_dataset = TensorDataset(
        X_test_tensor,
        y_test_tensor
    )

    # --------------------------------------------------------
    # DataLoader
    # --------------------------------------------------------

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        drop_last=False
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        drop_last=False
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        drop_last=False
    )

    print(
        f"[INFO] Batch size : "
        f"{BATCH_SIZE}"
    )

    print(
        f"[INFO] Train batches : "
        f"{len(train_loader)}"
    )

    print(
        f"[INFO] Val batches   : "
        f"{len(val_loader)}"
    )

    print(
        f"[INFO] Test batches  : "
        f"{len(test_loader)}"
    )

    return (
        train_loader,
        val_loader,
        test_loader,
    )


# ============================================================
# LSTM MODEL
# ============================================================

class TrafficLSTM(nn.Module):

    def __init__(
        self,
        input_size,
        hidden_size,
        num_layers,
        output_size,
        dropout,
    ):

        super().__init__()

        # ----------------------------------------------------
        # LSTM
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Output layer
        # ----------------------------------------------------

        self.fc = nn.Linear(
            hidden_size,
            output_size
        )

    def forward(
        self,
        x
    ):

        # x:
        # (batch, sequence_length, input_size)

        lstm_output, _ = (
            self.lstm(x)
        )

        # Ambil hidden state pada
        # timestep terakhir.

        last_output = (
            lstm_output[:, -1, :]
        )

        # Prediksi seluruh 96 features.

        output = self.fc(
            last_output
        )

        return output


# ============================================================
# MODEL SUMMARY
# ============================================================

def print_model_information(
    model
):

    print_header(
        "MODEL INFORMATION"
    )

    print(model)

    total_parameters = sum(
        parameter.numel()
        for parameter in model.parameters()
    )

    trainable_parameters = sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )

    print()

    print(
        f"[INFO] Total parameters     : "
        f"{total_parameters:,}"
    )

    print(
        f"[INFO] Trainable parameters : "
        f"{trainable_parameters:,}"
    )

    print(
        f"[INFO] Device               : "
        f"{DEVICE}"
    )


# ============================================================
# TRAIN ONE EPOCH
# ============================================================

def train_one_epoch(
    model,
    loader,
    criterion,
    optimizer,
):

    model.train()

    total_loss = 0.0

    total_samples = 0

    for X_batch, y_batch in loader:

        X_batch = X_batch.to(
            DEVICE
        )

        y_batch = y_batch.to(
            DEVICE
        )

        # ----------------------------------------------------
        # Clear gradients
        # ----------------------------------------------------

        optimizer.zero_grad()

        # ----------------------------------------------------
        # Forward
        # ----------------------------------------------------

        prediction = model(
            X_batch
        )

        # ----------------------------------------------------
        # Loss
        # ----------------------------------------------------

        loss = criterion(
            prediction,
            y_batch
        )

        # ----------------------------------------------------
        # Backpropagation
        # ----------------------------------------------------

        loss.backward()

        # ----------------------------------------------------
        # Update weights
        # ----------------------------------------------------

        optimizer.step()

        batch_size = (
            X_batch.size(0)
        )

        total_loss += (
            loss.item()
            * batch_size
        )

        total_samples += (
            batch_size
        )

    epoch_loss = (
        total_loss
        / total_samples
    )

    return epoch_loss


# ============================================================
# VALIDATE ONE EPOCH
# ============================================================

def validate_one_epoch(
    model,
    loader,
    criterion,
):

    model.eval()

    total_loss = 0.0

    total_samples = 0

    with torch.no_grad():

        for X_batch, y_batch in loader:

            X_batch = X_batch.to(
                DEVICE
            )

            y_batch = y_batch.to(
                DEVICE
            )

            prediction = model(
                X_batch
            )

            loss = criterion(
                prediction,
                y_batch
            )

            batch_size = (
                X_batch.size(0)
            )

            total_loss += (
                loss.item()
                * batch_size
            )

            total_samples += (
                batch_size
            )

    epoch_loss = (
        total_loss
        / total_samples
    )

    return epoch_loss


# ============================================================
# TRAINING
# ============================================================

def train_model(
    model,
    train_loader,
    val_loader,
):

    print_header(
        "MODEL TRAINING"
    )

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    best_val_loss = float(
        "inf"
    )

    patience_counter = 0

    history = {
        "epoch": [],
        "train_loss": [],
        "val_loss": [],
    }

    best_model_path = (
        MODEL_DIR
        / "best_model.pt"
    )

    for epoch in range(
        1,
        MAX_EPOCHS + 1
    ):

        train_loss = (
            train_one_epoch(
                model,
                train_loader,
                criterion,
                optimizer,
            )
        )

        val_loss = (
            validate_one_epoch(
                model,
                val_loader,
                criterion,
            )
        )

        history["epoch"].append(
            epoch
        )

        history["train_loss"].append(
            float(train_loss)
        )

        history["val_loss"].append(
            float(val_loss)
        )

        print(
            f"Epoch "
            f"{epoch:03d}/{MAX_EPOCHS} | "
            f"Train Loss: "
            f"{train_loss:.6f} | "
            f"Val Loss: "
            f"{val_loss:.6f}"
        )

        # ----------------------------------------------------
        # Best model
        # ----------------------------------------------------

        improvement = (
            best_val_loss
            - val_loss
        )

        if improvement > MIN_DELTA:

            best_val_loss = (
                val_loss
            )

            patience_counter = 0

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

                    "epoch":
                        epoch,

                    "best_val_loss":
                        best_val_loss,

                    "random_seed":
                        RANDOM_SEED,
                },
                best_model_path
            )

            print(
                "       [BEST MODEL SAVED]"
            )

        else:

            patience_counter += 1

            print(
                f"       "
                f"Early stopping counter: "
                f"{patience_counter}/"
                f"{EARLY_STOPPING_PATIENCE}"
            )

        # ----------------------------------------------------
        # Early stopping
        # ----------------------------------------------------

        if (
            patience_counter
            >= EARLY_STOPPING_PATIENCE
        ):

            print()

            print(
                "[INFO] Early stopping triggered."
            )

            break

    print()

    print(
        f"[INFO] Best validation loss : "
        f"{best_val_loss:.6f}"
    )

    print(
        f"[SAVED] {best_model_path}"
    )

    return (
        history,
        best_model_path,
    )


# ============================================================
# LOAD BEST MODEL
# ============================================================

def load_best_model(
    model,
    model_path
):

    print_header(
        "LOADING BEST MODEL"
    )

    checkpoint = torch.load(
        model_path,
        map_location=DEVICE
    )

    model.load_state_dict(
        checkpoint[
            "model_state_dict"
        ]
    )

    model.to(
        DEVICE
    )

    print(
        f"[INFO] Best epoch : "
        f"{checkpoint['epoch']}"
    )

    print(
        f"[INFO] Best val loss : "
        f"{checkpoint['best_val_loss']:.6f}"
    )

    print(
        "[OK] Best model loaded."
    )

    return checkpoint


# ============================================================
# TEST EVALUATION
# ============================================================

def evaluate_test(
    model,
    test_loader,
):

    print_header(
        "TEST EVALUATION"
    )

    criterion = nn.MSELoss()

    model.eval()

    total_squared_error = 0.0

    total_absolute_error = 0.0

    total_elements = 0

    with torch.no_grad():

        for X_batch, y_batch in test_loader:

            X_batch = X_batch.to(
                DEVICE
            )

            y_batch = y_batch.to(
                DEVICE
            )

            prediction = model(
                X_batch
            )

            # ------------------------------------------------
            # MSE
            # ------------------------------------------------

            squared_error = (
                (
                    prediction
                    - y_batch
                ) ** 2
            )

            # ------------------------------------------------
            # MAE
            # ------------------------------------------------

            absolute_error = (
                torch.abs(
                    prediction
                    - y_batch
                )
            )

            total_squared_error += (
                squared_error.sum()
                .item()
            )

            total_absolute_error += (
                absolute_error.sum()
                .item()
            )

            total_elements += (
                y_batch.numel()
            )

    mse = (
        total_squared_error
        / total_elements
    )

    mae = (
        total_absolute_error
        / total_elements
    )

    rmse = np.sqrt(
        mse
    )

    print(
        f"[TEST] MSE  : "
        f"{mse:.6f}"
    )

    print(
        f"[TEST] RMSE : "
        f"{rmse:.6f}"
    )

    print(
        f"[TEST] MAE  : "
        f"{mae:.6f}"
    )

    return {
        "mse": float(mse),
        "rmse": float(rmse),
        "mae": float(mae),
    }


# ============================================================
# SAVE JSON
# ============================================================

def save_json(
    path,
    data
):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# SAVE TRAINING CONFIG
# ============================================================

def save_training_config():

    path = (
        MODEL_DIR
        / "training_config.json"
    )

    config = {

        "dataset":
            "YOLO Traffic Dataset",

        "input_size":
            INPUT_SIZE,

        "output_size":
            OUTPUT_SIZE,

        "sequence_length":
            15,

        "forecast_horizon":
            1,

        "model":
            "LSTM",

        "hidden_size":
            HIDDEN_SIZE,

        "num_layers":
            NUM_LAYERS,

        "dropout":
            DROPOUT,

        "batch_size":
            BATCH_SIZE,

        "max_epochs":
            MAX_EPOCHS,

        "learning_rate":
            LEARNING_RATE,

        "weight_decay":
            WEIGHT_DECAY,

        "loss":
            "MSELoss",

        "optimizer":
            "Adam",

        "early_stopping":
            {
                "patience":
                    EARLY_STOPPING_PATIENCE,

                "min_delta":
                    MIN_DELTA,
            },

        "random_seed":
            RANDOM_SEED,

        "device":
            str(DEVICE),

        "note":
            "Baseline model. "
            "Belum dilakukan hyperparameter tuning.",
    }

    save_json(
        path,
        config
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE HISTORY
# ============================================================

def save_training_history(
    history
):

    path = (
        MODEL_DIR
        / "training_history.json"
    )

    save_json(
        path,
        history
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE TEST RESULT
# ============================================================

def save_test_result(
    result
):

    path = (
        MODEL_DIR
        / "baseline_test_result.json"
    )

    save_json(
        path,
        result
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# PRINT HEADER
# ============================================================

def print_header(
    title
):

    print()

    print(
        "=" * 70
    )

    print(
        title
    )

    print(
        "=" * 70
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "YOLO TRAFFIC LSTM BASELINE TRAINING"
    )

    print(
        "=" * 70
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
        f"15"
    )

    print(
        f"[INFO] Forecast horizon : "
        f"1 second"
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
        f"[INFO] Device           : "
        f"{DEVICE}"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # SETUP
    # --------------------------------------------------------

    set_seed()

    ensure_directories()

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    (
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test,
    ) = load_numpy_data()

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    validate_numpy_data(
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test,
    )

    validate_shapes(
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test,
    )

    # --------------------------------------------------------
    # DATALOADER
    # --------------------------------------------------------

    (
        train_loader,
        val_loader,
        test_loader,
    ) = create_dataloaders(
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test,
    )

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    model = TrafficLSTM(
        input_size=INPUT_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        output_size=OUTPUT_SIZE,
        dropout=DROPOUT,
    )

    model = model.to(
        DEVICE
    )

    print_model_information(
        model
    )

    # --------------------------------------------------------
    # SAVE CONFIG
    # --------------------------------------------------------

    save_training_config()

    # --------------------------------------------------------
    # TRAIN
    # --------------------------------------------------------

    (
        history,
        best_model_path,
    ) = train_model(
        model,
        train_loader,
        val_loader,
    )

    # --------------------------------------------------------
    # SAVE HISTORY
    # --------------------------------------------------------

    save_training_history(
        history
    )

    # --------------------------------------------------------
    # LOAD BEST MODEL
    # --------------------------------------------------------

    load_best_model(
        model,
        best_model_path
    )

    # --------------------------------------------------------
    # TEST
    # --------------------------------------------------------

    test_result = evaluate_test(
        model,
        test_loader
    )

    # --------------------------------------------------------
    # SAVE TEST RESULT
    # --------------------------------------------------------

    save_test_result(
        test_result
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print_header(
        "BASELINE TRAINING SUMMARY"
    )

    print()

    print(
        "[DATA]"
    )

    print(
        f"Train samples : "
        f"{len(X_train):,}"
    )

    print(
        f"Val samples   : "
        f"{len(X_val):,}"
    )

    print(
        f"Test samples  : "
        f"{len(X_test):,}"
    )

    print()

    print(
        "[MODEL]"
    )

    print(
        "Architecture : LSTM"
    )

    print(
        f"Input size   : "
        f"{INPUT_SIZE}"
    )

    print(
        f"Hidden size  : "
        f"{HIDDEN_SIZE}"
    )

    print(
        f"Layers       : "
        f"{NUM_LAYERS}"
    )

    print(
        f"Dropout      : "
        f"{DROPOUT}"
    )

    print(
        f"Output size  : "
        f"{OUTPUT_SIZE}"
    )

    print()

    print(
        "[TEST RESULT]"
    )

    print(
        f"MSE  : "
        f"{test_result['mse']:.6f}"
    )

    print(
        f"RMSE : "
        f"{test_result['rmse']:.6f}"
    )

    print(
        f"MAE  : "
        f"{test_result['mae']:.6f}"
    )

    print()

    print(
        "[OUTPUT]"
    )

    print(
        f"Model directory:"
    )

    print(
        f"{MODEL_DIR}"
    )

    print()

    print(
        "[NEXT]"
    )

    print(
        "1. Plot training loss vs validation loss"
    )

    print(
        "2. Evaluate prediction vs actual"
    )

    print(
        "3. Evaluate MAE/RMSE per traffic feature"
    )

    print(
        "4. Evaluate MAE/RMSE per sensor"
    )

    print(
        "5. Establish baseline"
    )

    print(
        "6. Baru lakukan eksperimen "
        "sequence length dan temporal resolution"
    )

    print()

    print(
        "=" * 70
    )

    print(
        "YOLO LSTM BASELINE TRAINING COMPLETED"
    )

    print(
        "=" * 70
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()