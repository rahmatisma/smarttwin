import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd

import torch
import torch.nn as nn

from torch.utils.data import (
    DataLoader,
    TensorDataset
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

OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "yolo"
)

MODEL_DIR = (
    OUTPUT_DIR
    / "models"
)

METRICS_DIR = (
    OUTPUT_DIR
    / "metrics"
)

PLOT_DIR = (
    OUTPUT_DIR
    / "plots"
)


MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)

METRICS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PLOT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# DATA CONFIGURATION
# ============================================================

DATASET_NAME = "YOLO Traffic Dataset"

INTERSECTION_ID = "simpang4-pingit"

SEQUENCE_LENGTH = 15

FORECAST_HORIZON = 1

NUM_SENSORS = 12

NUM_FEATURES_PER_SENSOR = 8

INPUT_SIZE = (
    NUM_SENSORS
    * NUM_FEATURES_PER_SENSOR
)

OUTPUT_SIZE = INPUT_SIZE


# ============================================================
# FEATURES
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


# ============================================================
# SENSOR CONFIGURATION
# ============================================================

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

SENSOR_COUNT = (
    len(APPROACHES)
    * len(LANES)
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

HIDDEN_SIZE = 64

NUM_LAYERS = 2

DROPOUT = 0.2

BATCH_SIZE = 64

LEARNING_RATE = 0.001

WEIGHT_DECAY = 1e-5

MAX_EPOCHS = 100

PATIENCE = 15

MIN_DELTA = 1e-6

GRADIENT_CLIP = 1.0


# ============================================================
# RANDOM SEED
# ============================================================

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

    random.seed(
        seed
    )

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

        self.input_size = (
            input_size
        )

        self.hidden_size = (
            hidden_size
        )

        self.num_layers = (
            num_layers
        )

        self.output_size = (
            output_size
        )

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
            )
        )

        # ----------------------------------------------------
        # Dropout
        # ----------------------------------------------------

        self.dropout = nn.Dropout(
            dropout
        )

        # ----------------------------------------------------
        # Output layer
        #
        # 64 hidden units
        # ->
        # 96 predicted features
        # ----------------------------------------------------

        self.output_layer = nn.Linear(
            hidden_size,
            output_size
        )

    def forward(
        self,
        x
    ):

        # ----------------------------------------------------
        # Input shape:
        #
        # (batch, sequence, 96)
        # ----------------------------------------------------

        lstm_output, _ = (
            self.lstm(x)
        )

        # ----------------------------------------------------
        # Take final timestep
        #
        # (batch, sequence, hidden)
        #
        # ->
        #
        # (batch, hidden)
        # ----------------------------------------------------

        last_output = (
            lstm_output[:, -1, :]
        )

        last_output = (
            self.dropout(
                last_output
            )
        )

        # ----------------------------------------------------
        # Prediction
        #
        # (batch, 64)
        #
        # ->
        #
        # (batch, 96)
        # ----------------------------------------------------

        output = (
            self.output_layer(
                last_output
            )
        )

        return output


# ============================================================
# LOAD CONFIGURATION
# ============================================================

def load_yolo_config():

    config_path = (
        PROCESSED_DIR
        / "yolo_config.json"
    )

    if not config_path.exists():

        print(
            "[WARNING] yolo_config.json tidak ditemukan."
        )

        return None

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(
            file
        )

    return config


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print()
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

    # --------------------------------------------------------
    # Check files
    # --------------------------------------------------------

    for name, path in files.items():

        if not path.exists():

            raise FileNotFoundError(
                f"{name} tidak ditemukan:\n"
                f"{path}"
            )

    # --------------------------------------------------------
    # Load arrays
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Print shapes
    # --------------------------------------------------------

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
# VALIDATE DATA
# ============================================================

def validate_data(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test
):

    print()
    print("=" * 70)
    print("DATA VALIDATION")
    print("=" * 70)

    datasets = {

        "X_train":
            X_train,

        "y_train":
            y_train,

        "X_val":
            X_val,

        "y_val":
            y_val,

        "X_test":
            X_test,

        "y_test":
            y_test
    }

    # --------------------------------------------------------
    # NaN / Inf check
    # --------------------------------------------------------

    for name, data in datasets.items():

        nan_count = np.isnan(
            data
        ).sum()

        inf_count = np.isinf(
            data
        ).sum()

        if nan_count > 0:

            raise ValueError(
                f"{name} memiliki "
                f"{nan_count} NaN."
            )

        if inf_count > 0:

            raise ValueError(
                f"{name} memiliki "
                f"{inf_count} Inf."
            )

    # --------------------------------------------------------
    # X shape
    # --------------------------------------------------------

    expected_x_shape = (
        SEQUENCE_LENGTH,
        INPUT_SIZE
    )

    expected_y_shape = (
        OUTPUT_SIZE,
    )

    for name in [
        "X_train",
        "X_val",
        "X_test"
    ]:

        data = datasets[name]

        if data.ndim != 3:

            raise ValueError(
                f"{name} harus 3D "
                f"(samples, sequence, features). "
                f"Got: {data.shape}"
            )

        if tuple(
            data.shape[1:]
        ) != expected_x_shape:

            raise ValueError(
                f"{name} shape tidak sesuai.\n"
                f"Expected: "
                f"(samples, "
                f"{SEQUENCE_LENGTH}, "
                f"{INPUT_SIZE})\n"
                f"Got: {data.shape}"
            )

    # --------------------------------------------------------
    # Y shape
    # --------------------------------------------------------

    for name in [
        "y_train",
        "y_val",
        "y_test"
    ]:

        data = datasets[name]

        if data.ndim != 2:

            raise ValueError(
                f"{name} harus 2D "
                f"(samples, features). "
                f"Got: {data.shape}"
            )

        if data.shape[1] != (
            OUTPUT_SIZE
        ):

            raise ValueError(
                f"{name} memiliki "
                f"{data.shape[1]} output features.\n"
                f"Expected: "
                f"{OUTPUT_SIZE}"
            )

    # --------------------------------------------------------
    # Sample count consistency
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
        "[OK] Semua shape data valid."
    )

    print(
        "[OK] Tidak ditemukan NaN."
    )

    print(
        "[OK] Tidak ditemukan Inf."
    )

    print(
        f"[INFO] Sequence length : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[INFO] Input features  : "
        f"{INPUT_SIZE}"
    )

    print(
        f"[INFO] Output features : "
        f"{OUTPUT_SIZE}"
    )

    print(
        f"[INFO] Sensors         : "
        f"{NUM_SENSORS}"
    )

    print(
        f"[INFO] Features/sensor : "
        f"{NUM_FEATURES_PER_SENSOR}"
    )


# ============================================================
# CREATE DATALOADERS
# ============================================================

def create_dataloaders(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test
):

    print()
    print("=" * 70)
    print("DATALOADER")
    print("=" * 70)

    train_dataset = TensorDataset(
        torch.from_numpy(X_train),
        torch.from_numpy(y_train)
    )

    val_dataset = TensorDataset(
        torch.from_numpy(X_val),
        torch.from_numpy(y_val)
    )

    test_dataset = TensorDataset(
        torch.from_numpy(X_test),
        torch.from_numpy(y_test)
    )

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
        f"[INFO] Train samples : "
        f"{len(train_loader.dataset)}"
    )

    print(
        f"[INFO] Train batches : "
        f"{len(train_loader)}"
    )

    print(
        f"[INFO] Val samples   : "
        f"{len(val_loader.dataset)}"
    )

    print(
        f"[INFO] Val batches   : "
        f"{len(val_loader)}"
    )

    print(
        f"[INFO] Test samples  : "
        f"{len(test_loader.dataset)}"
    )

    print(
        f"[INFO] Test batches  : "
        f"{len(test_loader)}"
    )

    return (
        train_loader,
        val_loader,
        test_loader
    )


# ============================================================
# CREATE MODEL
# ============================================================

def create_model():

    print()
    print("=" * 70)
    print("MODEL CONFIGURATION")
    print("=" * 70)

    model = TrafficLSTM(
        input_size=INPUT_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        output_size=OUTPUT_SIZE,
        dropout=DROPOUT
    )

    model = model.to(
        DEVICE
    )

    parameter_count = sum(
        parameter.numel()
        for parameter in model.parameters()
    )

    trainable_count = sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )

    print(
        f"[INFO] Architecture : LSTM"
    )

    print(
        f"[INFO] Input size    : "
        f"{INPUT_SIZE}"
    )

    print(
        f"[INFO] Hidden size   : "
        f"{HIDDEN_SIZE}"
    )

    print(
        f"[INFO] LSTM layers   : "
        f"{NUM_LAYERS}"
    )

    print(
        f"[INFO] Dropout       : "
        f"{DROPOUT}"
    )

    print(
        f"[INFO] Output size   : "
        f"{OUTPUT_SIZE}"
    )

    print(
        f"[INFO] Parameters    : "
        f"{parameter_count:,}"
    )

    print(
        f"[INFO] Trainable     : "
        f"{trainable_count:,}"
    )

    print(
        "[OK] Model created."
    )

    return model


# ============================================================
# TRAIN ONE EPOCH
# ============================================================

def train_one_epoch(
    model,
    loader,
    criterion,
    optimizer
):

    model.train()

    total_loss = 0.0

    total_samples = 0

    for X_batch, y_batch in loader:

        X_batch = X_batch.to(
            DEVICE,
            non_blocking=True
        )

        y_batch = y_batch.to(
            DEVICE,
            non_blocking=True
        )

        # ----------------------------------------------------
        # Clear gradients
        # ----------------------------------------------------

        optimizer.zero_grad(
            set_to_none=True
        )

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
        # Gradient clipping
        # ----------------------------------------------------

        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            max_norm=GRADIENT_CLIP
        )

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
# VALIDATION
# ============================================================

def validate_one_epoch(
    model,
    loader,
    criterion
):

    model.eval()

    total_loss = 0.0

    total_samples = 0

    with torch.no_grad():

        for X_batch, y_batch in loader:

            X_batch = X_batch.to(
                DEVICE,
                non_blocking=True
            )

            y_batch = y_batch.to(
                DEVICE,
                non_blocking=True
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
# SAVE CHECKPOINT
# ============================================================

def save_checkpoint(
    model,
    optimizer,
    epoch,
    train_loss,
    val_loss,
    path
):

    checkpoint = {

        "epoch":
            epoch,

        "model_state_dict":
            model.state_dict(),

        "optimizer_state_dict":
            optimizer.state_dict(),

        "train_loss":
            float(train_loss),

        "val_loss":
            float(val_loss),

        "dataset":
            DATASET_NAME,

        "intersection_id":
            INTERSECTION_ID,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "num_sensors":
            NUM_SENSORS,

        "num_features_per_sensor":
            NUM_FEATURES_PER_SENSOR,

        "input_size":
            INPUT_SIZE,

        "output_size":
            OUTPUT_SIZE,

        "feature_names":
            FEATURE_NAMES,

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

        "weight_decay":
            WEIGHT_DECAY,

        "random_seed":
            RANDOM_SEED
    }

    torch.save(
        checkpoint,
        path
    )


# ============================================================
# TRAINING LOOP
# ============================================================

def train_model(
    model,
    train_loader,
    val_loader
):

    print()
    print("=" * 70)
    print("TRAINING")
    print("=" * 70)

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY
    )

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=5
    )

    best_model_path = (
        MODEL_DIR
        / "best_model.pth"
    )

    history = []

    best_val_loss = float(
        "inf"
    )

    best_epoch = 0

    patience_counter = 0

    training_start = time.time()

    print(
        f"[INFO] Maximum epochs : "
        f"{MAX_EPOCHS}"
    )

    print(
        f"[INFO] Early stopping : "
        f"{PATIENCE} epochs"
    )

    print(
        f"[INFO] Learning rate   : "
        f"{LEARNING_RATE}"
    )

    print(
        f"[INFO] Weight decay    : "
        f"{WEIGHT_DECAY}"
    )

    print(
        f"[INFO] Loss function   : MSELoss"
    )

    print()

    for epoch in range(
        1,
        MAX_EPOCHS + 1
    ):

        epoch_start = time.time()

        train_loss = train_one_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion,
            optimizer=optimizer
        )

        val_loss = validate_one_epoch(
            model=model,
            loader=val_loader,
            criterion=criterion
        )

        scheduler.step(
            val_loss
        )

        current_lr = (
            optimizer.param_groups[0]["lr"]
        )

        epoch_time = (
            time.time()
            - epoch_start
        )

        history.append(
            {
                "epoch":
                    epoch,

                "train_loss":
                    float(train_loss),

                "val_loss":
                    float(val_loss),

                "learning_rate":
                    float(current_lr),

                "epoch_time_seconds":
                    float(epoch_time)
            }
        )

        print(
            f"Epoch "
            f"{epoch:03d}/{MAX_EPOCHS} | "
            f"Train Loss: "
            f"{train_loss:.6f} | "
            f"Val Loss: "
            f"{val_loss:.6f} | "
            f"LR: "
            f"{current_lr:.7f} | "
            f"Time: "
            f"{epoch_time:.2f}s"
        )

        # ----------------------------------------------------
        # Check improvement
        # ----------------------------------------------------

        improvement = (
            best_val_loss
            - val_loss
        )

        if improvement > MIN_DELTA:

            best_val_loss = (
                val_loss
            )

            best_epoch = (
                epoch
            )

            patience_counter = 0

            save_checkpoint(
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                train_loss=train_loss,
                val_loss=val_loss,
                path=best_model_path
            )

            print(
                f"       [BEST] "
                f"Validation loss improved: "
                f"{val_loss:.6f}"
            )

        else:

            patience_counter += 1

            print(
                f"       [NO IMPROVEMENT] "
                f"{patience_counter}/{PATIENCE}"
            )

        # ----------------------------------------------------
        # Early stopping
        # ----------------------------------------------------

        if (
            patience_counter
            >= PATIENCE
        ):

            print()

            print(
                f"[EARLY STOPPING] "
                f"Training berhenti pada "
                f"epoch {epoch}."
            )

            break

    total_training_time = (
        time.time()
        - training_start
    )

    history_df = pd.DataFrame(
        history
    )

    history_path = (
        METRICS_DIR
        / "training_history.csv"
    )

    history_df.to_csv(
        history_path,
        index=False
    )

    print()
    print(
        f"[SAVED] "
        f"{history_path}"
    )

    print(
        f"[SAVED] "
        f"{best_model_path}"
    )

    print()
    print(
        f"[INFO] Best epoch       : "
        f"{best_epoch}"
    )

    print(
        f"[INFO] Best val loss    : "
        f"{best_val_loss:.6f}"
    )

    print(
        f"[INFO] Training time    : "
        f"{total_training_time:.2f} seconds"
    )

    return (
        best_model_path,
        history_df,
        best_epoch,
        best_val_loss,
        total_training_time
    )


# ============================================================
# LOAD BEST MODEL
# ============================================================

def load_best_model(
    model,
    model_path
):

    print()
    print("=" * 70)
    print("LOADING BEST MODEL")
    print("=" * 70)

    checkpoint = torch.load(
        model_path,
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

    else:

        model.load_state_dict(
            checkpoint
        )

    model = model.to(
        DEVICE
    )

    model.eval()

    print(
        "[OK] Best model loaded."
    )

    return model


# ============================================================
# TEST EVALUATION
# ============================================================

def evaluate_test(
    model,
    test_loader
):

    print()
    print("=" * 70)
    print("TEST EVALUATION")
    print("=" * 70)

    criterion = nn.MSELoss()

    model.eval()

    predictions = []

    actuals = []

    total_loss = 0.0

    total_samples = 0

    start_time = time.time()

    with torch.no_grad():

        for X_batch, y_batch in test_loader:

            X_batch = X_batch.to(
                DEVICE,
                non_blocking=True
            )

            y_batch = y_batch.to(
                DEVICE,
                non_blocking=True
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

            predictions.append(
                prediction
                .cpu()
                .numpy()
            )

            actuals.append(
                y_batch
                .cpu()
                .numpy()
            )

    test_loss = (
        total_loss
        / total_samples
    )

    inference_time = (
        time.time()
        - start_time
    )

    y_pred = np.concatenate(
        predictions,
        axis=0
    )

    y_true = np.concatenate(
        actuals,
        axis=0
    )

    print(
        f"[INFO] Test MSE : "
        f"{test_loss:.6f}"
    )

    print(
        f"[INFO] Prediction shape : "
        f"{y_pred.shape}"
    )

    print(
        f"[INFO] Actual shape     : "
        f"{y_true.shape}"
    )

    print(
        f"[INFO] Inference time   : "
        f"{inference_time:.4f} seconds"
    )

    return (
        y_true,
        y_pred,
        test_loss,
        inference_time
    )


# ============================================================
# CALCULATE METRICS
# ============================================================

def calculate_metrics(
    y_true,
    y_pred
):

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

    # --------------------------------------------------------
    # R2
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MAPE
    # --------------------------------------------------------

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
                /
                true_flat[
                    non_zero_mask
                ]
            )
        ) * 100

    else:

        mape = np.nan

    return {

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


# ============================================================
# FEATURE METRICS
# ============================================================

def calculate_feature_metrics(
    y_true,
    y_pred
):

    rows = []

    for sensor_index in range(
        NUM_SENSORS
    ):

        sensor_start = (
            sensor_index
            * NUM_FEATURES_PER_SENSOR
        )

        sensor_end = (
            sensor_start
            + NUM_FEATURES_PER_SENSOR
        )

        for feature_index, feature_name in enumerate(
            FEATURE_NAMES
        ):

            feature_position = (
                sensor_start
                + feature_index
            )

            true_values = (
                y_true[
                    :,
                    feature_position
                ]
            )

            pred_values = (
                y_pred[
                    :,
                    feature_position
                ]
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
                    - np.mean(
                        true_values
                    )
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

                    "feature":
                        feature_name,

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
# SAVE TEST RESULTS
# ============================================================

def save_test_results(
    y_true,
    y_pred,
    test_loss,
    inference_time,
    metrics
):

    prediction_path = (
        OUTPUT_DIR
        / "test_predictions.npz"
    )

    np.savez_compressed(
        prediction_path,
        y_true=y_true,
        y_pred=y_pred
    )

    print(
        f"[SAVED] "
        f"{prediction_path}"
    )

    # --------------------------------------------------------
    # Overall metrics
    # --------------------------------------------------------

    metrics_path = (
        METRICS_DIR
        / "test_metrics.json"
    )

    with open(
        metrics_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            {
                "dataset":
                    DATASET_NAME,

                "intersection_id":
                    INTERSECTION_ID,

                "test_mse":
                    float(test_loss),

                "inference_time_seconds":
                    float(
                        inference_time
                    ),

                "metrics":
                    metrics,

                "sequence_length":
                    SEQUENCE_LENGTH,

                "forecast_horizon":
                    FORECAST_HORIZON,

                "num_sensors":
                    NUM_SENSORS,

                "features_per_sensor":
                    NUM_FEATURES_PER_SENSOR,

                "input_size":
                    INPUT_SIZE,

                "output_size":
                    OUTPUT_SIZE,

                "feature_names":
                    FEATURE_NAMES
            },
            file,
            indent=4
        )

    print(
        f"[SAVED] "
        f"{metrics_path}"
    )


# ============================================================
# SAVE TRAINING SUMMARY
# ============================================================

def save_training_summary(
    best_epoch,
    best_val_loss,
    total_training_time,
    test_loss,
    metrics
):

    summary_path = (
        METRICS_DIR
        / "training_summary.json"
    )

    summary = {

        "dataset":
            DATASET_NAME,

        "intersection_id":
            INTERSECTION_ID,

        "model": {

            "type":
                "LSTM",

            "input_size":
                INPUT_SIZE,

            "hidden_size":
                HIDDEN_SIZE,

            "num_layers":
                NUM_LAYERS,

            "dropout":
                DROPOUT,

            "output_size":
                OUTPUT_SIZE
        },

        "data": {

            "num_sensors":
                NUM_SENSORS,

            "features_per_sensor":
                NUM_FEATURES_PER_SENSOR,

            "features":
                FEATURE_NAMES,

            "sequence_length":
                SEQUENCE_LENGTH,

            "forecast_horizon":
                FORECAST_HORIZON
        },

        "training": {

            "batch_size":
                BATCH_SIZE,

            "learning_rate":
                LEARNING_RATE,

            "weight_decay":
                WEIGHT_DECAY,

            "max_epochs":
                MAX_EPOCHS,

            "early_stopping_patience":
                PATIENCE,

            "best_epoch":
                best_epoch,

            "best_validation_loss":
                float(
                    best_val_loss
                ),

            "training_time_seconds":
                float(
                    total_training_time
                )
        },

        "test": {

            "mse":
                float(
                    test_loss
                ),

            "metrics":
                metrics
        },

        "device":
            str(DEVICE),

        "random_seed":
            RANDOM_SEED
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
        f"[SAVED] "
        f"{summary_path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Seed
    # --------------------------------------------------------

    set_seed()

    print("=" * 70)
    print(
        "YOLO TRAFFIC LSTM TRAINING"
    )
    print("=" * 70)

    print(
        f"[INFO] Device : "
        f"{DEVICE}"
    )

    # --------------------------------------------------------
    # Configuration
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TRAINING CONFIGURATION")
    print("=" * 70)

    print(
        f"[INFO] Dataset           : "
        f"{DATASET_NAME}"
    )

    print(
        f"[INFO] Intersection      : "
        f"{INTERSECTION_ID}"
    )

    print(
        f"[INFO] Sensors           : "
        f"{NUM_SENSORS}"
    )

    print(
        f"[INFO] Features/sensor  : "
        f"{NUM_FEATURES_PER_SENSOR}"
    )

    print(
        f"[INFO] Input size        : "
        f"{INPUT_SIZE}"
    )

    print(
        f"[INFO] Output size       : "
        f"{OUTPUT_SIZE}"
    )

    print(
        f"[INFO] Sequence length   : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[INFO] Forecast horizon  : "
        f"{FORECAST_HORIZON}"
    )

    print(
        f"[INFO] Hidden size       : "
        f"{HIDDEN_SIZE}"
    )

    print(
        f"[INFO] LSTM layers       : "
        f"{NUM_LAYERS}"
    )

    print(
        f"[INFO] Dropout           : "
        f"{DROPOUT}"
    )

    print(
        f"[INFO] Batch size        : "
        f"{BATCH_SIZE}"
    )

    print(
        f"[INFO] Learning rate     : "
        f"{LEARNING_RATE}"
    )

    print(
        f"[INFO] Max epochs        : "
        f"{MAX_EPOCHS}"
    )

    print(
        f"[INFO] Early stopping    : "
        f"{PATIENCE}"
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
    # Load YOLO config
    # --------------------------------------------------------

    yolo_config = (
        load_yolo_config()
    )

    if yolo_config is not None:

        print()
        print(
            "[OK] yolo_config.json loaded."
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
    # Validate data
    # --------------------------------------------------------

    validate_data(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test
    )

    # --------------------------------------------------------
    # Create loaders
    # --------------------------------------------------------

    (
        train_loader,
        val_loader,
        test_loader
    ) = create_dataloaders(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test
    )

    # --------------------------------------------------------
    # Create model
    # --------------------------------------------------------

    model = create_model()

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    (
        best_model_path,
        history_df,
        best_epoch,
        best_val_loss,
        total_training_time
    ) = train_model(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader
    )

    # --------------------------------------------------------
    # Load best model
    # --------------------------------------------------------

    model = load_best_model(
        model=model,
        model_path=best_model_path
    )

    # --------------------------------------------------------
    # Test evaluation
    # --------------------------------------------------------

    (
        y_true,
        y_pred,
        test_loss,
        inference_time
    ) = evaluate_test(
        model=model,
        test_loader=test_loader
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CALCULATING TEST METRICS")
    print("=" * 70)

    metrics = calculate_metrics(
        y_true=y_true,
        y_pred=y_pred
    )

    feature_metrics = (
        calculate_feature_metrics(
            y_true=y_true,
            y_pred=y_pred
        )
    )

    print()
    print(
        "[OVERALL TEST METRICS]"
    )

    print(
        f"MAE  : "
        f"{metrics['MAE']:.6f}"
    )

    print(
        f"MSE  : "
        f"{metrics['MSE']:.6f}"
    )

    print(
        f"RMSE : "
        f"{metrics['RMSE']:.6f}"
    )

    print(
        f"MAPE : "
        f"{metrics['MAPE_percent']:.4f}%"
    )

    print(
        f"R2   : "
        f"{metrics['R2']:.6f}"
    )

    # --------------------------------------------------------
    # Feature metrics
    # --------------------------------------------------------

    feature_metrics_path = (
        METRICS_DIR
        / "feature_metrics.csv"
    )

    feature_metrics.to_csv(
        feature_metrics_path,
        index=False
    )

    print()
    print(
        f"[SAVED] "
        f"{feature_metrics_path}"
    )

    # --------------------------------------------------------
    # Test results
    # --------------------------------------------------------

    save_test_results(
        y_true=y_true,
        y_pred=y_pred,
        test_loss=test_loss,
        inference_time=inference_time,
        metrics=metrics
    )

    # --------------------------------------------------------
    # Training summary
    # --------------------------------------------------------

    save_training_summary(
        best_epoch=best_epoch,
        best_val_loss=best_val_loss,
        total_training_time=total_training_time,
        test_loss=test_loss,
        metrics=metrics
    )

    # --------------------------------------------------------
    # Final output
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "YOLO LSTM TRAINING COMPLETED"
    )
    print("=" * 70)

    print()
    print(
        "[MODEL]"
    )

    print(
        f"[OK] Best model : "
        f"{best_model_path}"
    )

    print(
        f"[OK] Best epoch : "
        f"{best_epoch}"
    )

    print(
        f"[OK] Best val loss : "
        f"{best_val_loss:.6f}"
    )

    print()
    print(
        "[DATA INTERFACE]"
    )

    print(
        f"[OK] Sensors : "
        f"{NUM_SENSORS}"
    )

    print(
        f"[OK] Features/sensor : "
        f"{NUM_FEATURES_PER_SENSOR}"
    )

    print(
        f"[OK] Input size : "
        f"{INPUT_SIZE}"
    )

    print(
        f"[OK] Output size : "
        f"{OUTPUT_SIZE}"
    )

    print(
        f"[OK] Sequence : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[OK] Horizon : "
        f"{FORECAST_HORIZON}"
    )

    print()
    print(
        "[TEST RESULT]"
    )

    print(
        f"MAE  : "
        f"{metrics['MAE']:.6f}"
    )

    print(
        f"RMSE : "
        f"{metrics['RMSE']:.6f}"
    )

    print(
        f"MAPE : "
        f"{metrics['MAPE_percent']:.4f}%"
    )

    print(
        f"R2   : "
        f"{metrics['R2']:.6f}"
    )

    print()
    print(
        "[OUTPUT DIRECTORY]"
    )

    print(
        f"{OUTPUT_DIR}"
    )

    print()
    print(
        "[NEXT]"
    )

    print(
        "Gunakan best_model.pth "
        "untuk prediction."
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()