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
    / "pems04_20"
    / "processed"
)

OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "pems04"
    / "sensor_1_20"
)

PLOT_DIR = OUTPUT_DIR / "plots"

OUTPUT_DIR.mkdir(
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

SEQUENCE_LENGTH = 15
FORECAST_HORIZON = 1

HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2

LEARNING_RATE = 0.001
BATCH_SIZE = 64

MAX_EPOCHS = 100
EARLY_STOPPING_PATIENCE = 10

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

def set_seed(seed=RANDOM_SEED):

    random.seed(seed)

    np.random.seed(seed)

    torch.manual_seed(seed)

    if torch.cuda.is_available():

        torch.cuda.manual_seed_all(seed)

    # Deterministic behavior
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ============================================================
# LSTM MODEL
# ============================================================

class TrafficLSTM(nn.Module):

    def __init__(
        self,
        num_sensors,
        num_features,
        hidden_size=64,
        num_layers=2,
        dropout=0.2
    ):

        super().__init__()

        self.num_sensors = num_sensors
        self.num_features = num_features

        self.input_size = (
            num_sensors * num_features
        )

        self.hidden_size = hidden_size
        self.num_layers = num_layers

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

        self.output_layer = nn.Linear(
            hidden_size,
            num_sensors * num_features
        )

    def forward(self, x):

        batch_size = x.size(0)

        # ----------------------------------------------------
        # Input:
        # (batch, sequence, sensors, features)
        #
        # LSTM requires:
        # (batch, sequence, sensors * features)
        # ----------------------------------------------------

        x = x.reshape(
            batch_size,
            x.size(1),
            -1
        )

        lstm_output, _ = self.lstm(x)

        # Last timestep
        last_output = lstm_output[:, -1, :]

        last_output = self.dropout(
            last_output
        )

        output = self.output_layer(
            last_output
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
        "X_train": PROCESSED_DIR / "X_train.npy",
        "y_train": PROCESSED_DIR / "y_train.npy",
        "X_val": PROCESSED_DIR / "X_val.npy",
        "y_val": PROCESSED_DIR / "y_val.npy",
        "X_test": PROCESSED_DIR / "X_test.npy",
        "y_test": PROCESSED_DIR / "y_test.npy",
    }

    for name, path in files.items():

        if not path.exists():

            raise FileNotFoundError(
                f"File tidak ditemukan: {path}"
            )

    X_train = np.load(
        files["X_train"]
    ).astype(np.float32)

    y_train = np.load(
        files["y_train"]
    ).astype(np.float32)

    X_val = np.load(
        files["X_val"]
    ).astype(np.float32)

    y_val = np.load(
        files["y_val"]
    ).astype(np.float32)

    X_test = np.load(
        files["X_test"]
    ).astype(np.float32)

    y_test = np.load(
        files["y_test"]
    ).astype(np.float32)

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

    return (
        train_loader,
        val_loader,
        test_loader
    )


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
            DEVICE
        )

        y_batch = y_batch.to(
            DEVICE
        )

        optimizer.zero_grad()

        predictions = model(
            X_batch
        )

        loss = criterion(
            predictions,
            y_batch
        )

        loss.backward()

        # Prevent exploding gradients
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            max_norm=1.0
        )

        optimizer.step()

        batch_size = X_batch.size(0)

        total_loss += (
            loss.item()
            * batch_size
        )

        total_samples += batch_size

    return (
        total_loss
        / total_samples
    )


# ============================================================
# VALIDATION
# ============================================================

def validate(
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
                DEVICE
            )

            y_batch = y_batch.to(
                DEVICE
            )

            predictions = model(
                X_batch
            )

            loss = criterion(
                predictions,
                y_batch
            )

            batch_size = X_batch.size(0)

            total_loss += (
                loss.item()
                * batch_size
            )

            total_samples += batch_size

    return (
        total_loss
        / total_samples
    )


# ============================================================
# SAVE MODEL CHECKPOINT
# ============================================================

def save_best_model(
    model,
    optimizer,
    epoch,
    train_loss,
    val_loss,
    path
):

    checkpoint = {

        "epoch": epoch,

        "model_state_dict":
            model.state_dict(),

        "optimizer_state_dict":
            optimizer.state_dict(),

        "train_loss":
            float(train_loss),

        "val_loss":
            float(val_loss),

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "hidden_size":
            HIDDEN_SIZE,

        "num_layers":
            NUM_LAYERS,

        "dropout":
            DROPOUT,

        "learning_rate":
            LEARNING_RATE,

        "batch_size":
            BATCH_SIZE
    }

    torch.save(
        checkpoint,
        path
    )


# ============================================================
# TRAINING
# ============================================================

def train_model(
    model,
    train_loader,
    val_loader
):

    criterion = nn.MSELoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE
    )

    best_val_loss = float("inf")

    best_epoch = 0

    patience_counter = 0

    history = {
        "epoch": [],
        "train_loss": [],
        "val_loss": []
    }

    best_model_path = (
        OUTPUT_DIR
        / "best_model.pth"
    )

    print("=" * 70)
    print("TRAINING")
    print("=" * 70)

    start_time = time.time()

    for epoch in range(
        1,
        MAX_EPOCHS + 1
    ):

        train_loss = train_one_epoch(
            model,
            train_loader,
            criterion,
            optimizer
        )

        val_loss = validate(
            model,
            val_loader,
            criterion
        )

        # ----------------------------------------------------
        # Store history
        # ----------------------------------------------------

        history["epoch"].append(
            epoch
        )

        history["train_loss"].append(
            train_loss
        )

        history["val_loss"].append(
            val_loss
        )

        # ----------------------------------------------------
        # Check best model
        # ----------------------------------------------------

        if val_loss < best_val_loss:

            best_val_loss = val_loss

            best_epoch = epoch

            patience_counter = 0

            save_best_model(
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                train_loss=train_loss,
                val_loss=val_loss,
                path=best_model_path
            )

            print(
                f"[BEST] Epoch {epoch:03d} | "
                f"Train Loss: {train_loss:.6f} | "
                f"Val Loss: {val_loss:.6f}"
            )

        else:

            patience_counter += 1

            print(
                f"[INFO] Epoch {epoch:03d} | "
                f"Train Loss: {train_loss:.6f} | "
                f"Val Loss: {val_loss:.6f} | "
                f"Patience: "
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

    training_time = (
        time.time()
        - start_time
    )

    print()
    print("=" * 70)
    print("TRAINING COMPLETED")
    print("=" * 70)

    print(
        f"[INFO] Best epoch     : "
        f"{best_epoch}"
    )

    print(
        f"[INFO] Best val loss  : "
        f"{best_val_loss:.6f}"
    )

    print(
        f"[INFO] Training time  : "
        f"{training_time:.2f} seconds"
    )

    print(
        f"[SAVED] Best model: "
        f"{best_model_path}"
    )

    return (
        history,
        best_val_loss,
        best_epoch,
        training_time,
        best_model_path
    )


# ============================================================
# SAVE TRAINING HISTORY
# ============================================================

def save_training_history(
    history
):

    history_path = (
        OUTPUT_DIR
        / "training_history.csv"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # history is a dictionary.
    # Convert it to DataFrame before saving.
    # --------------------------------------------------------

    history_df = pd.DataFrame(
        history
    )

    history_df.to_csv(
        history_path,
        index=False
    )

    print(
        f"[SAVED] {history_path}"
    )

    return history_df


# ============================================================
# SAVE LOSS PLOT
# ============================================================

def save_loss_plot(
    history_df
):

    plot_path = (
        PLOT_DIR
        / "training_loss.png"
    )

    plt.figure(
        figsize=(10, 6)
    )

    plt.plot(
        history_df["epoch"],
        history_df["train_loss"],
        label="Train Loss"
    )

    plt.plot(
        history_df["epoch"],
        history_df["val_loss"],
        label="Validation Loss"
    )

    plt.xlabel(
        "Epoch"
    )

    plt.ylabel(
        "MSE Loss"
    )

    plt.title(
        "PEMS04 LSTM Training and Validation Loss"
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
# SAVE TRAINING SUMMARY
# ============================================================

def save_training_summary(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test,
    history_df,
    best_val_loss,
    best_epoch,
    training_time,
    model
):

    summary_path = (
        OUTPUT_DIR
        / "training_summary.json"
    )

    summary = {

        "dataset": "PEMS04",

        "device": str(
            DEVICE
        ),

        "sensors": {
            "start": 1,
            "end": 20,
            "count": 20   
        },

        "features": [
            "flow",
            "occupancy",
            "speed"
        ],

        "num_features": 3,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "model": {
            "type": "LSTM",
            "hidden_size":
                HIDDEN_SIZE,
            "num_layers":
                NUM_LAYERS,
            "dropout":
                DROPOUT
        },

        "training": {
            "learning_rate":
                LEARNING_RATE,
            "batch_size":
                BATCH_SIZE,
            "max_epochs":
                MAX_EPOCHS,
            "early_stopping_patience":
                EARLY_STOPPING_PATIENCE,
            "epochs_trained":
                int(
                    len(history_df)
                )
        },

        "samples": {
            "train":
                int(
                    len(X_train)
                ),
            "validation":
                int(
                    len(X_val)
                ),
            "test":
                int(
                    len(X_test)
                )
        },

        "best_epoch":
            int(best_epoch),

        "best_validation_loss":
            float(best_val_loss),

        "final_train_loss":
            float(
                history_df[
                    "train_loss"
                ].iloc[-1]
            ),

        "final_validation_loss":
            float(
                history_df[
                    "val_loss"
                ].iloc[-1]
            ),

        "training_time_seconds":
            float(training_time),

        "model_parameters":
            int(
                sum(
                    p.numel()
                    for p
                    in model.parameters()
                )
            ),

        "best_model_file":
            "best_model.pth",

        "training_history_file":
            "training_history.csv",

        "training_plot_file":
            "plots/training_loss.png"
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
# MAIN
# ============================================================

def main():

    set_seed()

    print("=" * 70)
    print("PEMS04 LSTM TRAFFIC FORECASTING TRAINING")
    print("=" * 70)

    print(
        f"[INFO] Device: {DEVICE}"
    )

    # --------------------------------------------------------
    # Experiment configuration
    # --------------------------------------------------------

    print("=" * 70)
    print("EXPERIMENT CONFIGURATION")
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
        f"[INFO] Learning rate   : "
        f"{LEARNING_RATE}"
    )

    print(
        f"[INFO] Batch size      : "
        f"{BATCH_SIZE}"
    )

    print(
        f"[INFO] Max epochs      : "
        f"{MAX_EPOCHS}"
    )

    print(
        f"[INFO] Early stopping  : "
        f"{EARLY_STOPPING_PATIENCE} epochs"
    )

    # --------------------------------------------------------
    # Feature configuration
    # --------------------------------------------------------

    print("=" * 70)
    print("FEATURE CONFIGURATION")
    print("=" * 70)

    print(
        "[INFO] Sensors : 1-20"
    )

    print(
        "[INFO] Number of sensors : 20"
    )

    print(
        "[INFO] Features:"
    )

    print(
        "       1. flow"
    )

    print(
        "       2. occupancy"
    )

    print(
        "       3. speed"
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
    # Validate dimensions
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DATA VALIDATION")
    print("=" * 70)

    if X_train.ndim != 4:

        raise ValueError(
            "X_train harus memiliki "
            "shape (samples, timestep, sensors, features)."
        )

    if y_train.ndim != 3:

        raise ValueError(
            "y_train harus memiliki "
            "shape (samples, sensors, features)."
        )

    num_sensors = X_train.shape[2]

    num_features = X_train.shape[3]

    sequence_length = X_train.shape[1]

    if (
        sequence_length
        != SEQUENCE_LENGTH
    ):

        raise ValueError(
            f"Sequence length tidak sesuai. "
            f"Expected {SEQUENCE_LENGTH}, "
            f"got {sequence_length}."
        )

    if num_sensors != 20:

        raise ValueError(
            f"Jumlah sensor tidak sesuai. "
            f"Expected 20, got {num_sensors}."
        )

    if num_features != 3:

        raise ValueError(
            f"Jumlah fitur tidak sesuai. "
            f"Expected 3, got {num_features}."
        )

    print(
        "[OK] Input shape valid."
    )

    print(
        f"[INFO] Sensors : "
        f"{num_sensors}"
    )

    print(
        f"[INFO] Features: "
        f"{num_features}"
    )

    # --------------------------------------------------------
    # Create DataLoaders
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DATALOADER")
    print("=" * 70)

    (
        train_loader,
        val_loader,
        test_loader
    ) = create_dataloaders(
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test
    )

    print(
        f"[INFO] Train batches: "
        f"{len(train_loader)}"
    )

    print(
        f"[INFO] Val batches  : "
        f"{len(val_loader)}"
    )

    print(
        f"[INFO] Test batches : "
        f"{len(test_loader)}"
    )

    # --------------------------------------------------------
    # Build model
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("MODEL")
    print("=" * 70)

    model = TrafficLSTM(
        num_sensors=num_sensors,
        num_features=num_features,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        dropout=DROPOUT
    )

    model = model.to(
        DEVICE
    )

    parameter_count = sum(
        p.numel()
        for p in model.parameters()
    )

    trainable_parameters = sum(
        p.numel()
        for p in model.parameters()
        if p.requires_grad
    )

    print(
        f"[INFO] Model parameters: "
        f"{parameter_count:,}"
    )

    print(
        f"[INFO] Trainable parameters: "
        f"{trainable_parameters:,}"
    )

    # --------------------------------------------------------
    # Training
    # --------------------------------------------------------

    (
        history,
        best_val_loss,
        best_epoch,
        training_time,
        best_model_path
    ) = train_model(
        model,
        train_loader,
        val_loader
    )

    # --------------------------------------------------------
    # Save history
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING TRAINING HISTORY")
    print("=" * 70)

    history_df = save_training_history(
        history
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Model is already saved BEFORE plotting.
    # Therefore plotting failure will not destroy
    # the trained model.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # Save plot
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING TRAINING PLOT")
    print("=" * 70)

    try:

        save_loss_plot(
            history_df
        )

    except Exception as error:

        print(
            f"[WARNING] Gagal membuat "
            f"loss plot: {error}"
        )

        print(
            "[WARNING] Training tetap "
            "dianggap berhasil karena "
            "best_model.pth sudah tersimpan."
        )

    # --------------------------------------------------------
    # Save summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING TRAINING SUMMARY")
    print("=" * 70)

    try:

        save_training_summary(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            X_test=X_test,
            y_test=y_test,
            history_df=history_df,
            best_val_loss=best_val_loss,
            best_epoch=best_epoch,
            training_time=training_time,
            model=model
        )

    except Exception as error:

        print(
            f"[WARNING] Gagal membuat "
            f"training summary: {error}"
        )

    # --------------------------------------------------------
    # Final output
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TRAINING PIPELINE COMPLETED")
    print("=" * 70)

    print(
        f"[OK] Best epoch      : "
        f"{best_epoch}"
    )

    print(
        f"[OK] Best val loss   : "
        f"{best_val_loss:.6f}"
    )

    print(
        f"[OK] Training time   : "
        f"{training_time:.2f} seconds"
    )

    print()
    print("[OUTPUT]")

    print(
        f"[SAVED] {best_model_path}"
    )

    print(
        f"[SAVED] "
        f"{OUTPUT_DIR / 'training_history.csv'}"
    )

    print(
        f"[SAVED] "
        f"{OUTPUT_DIR / 'training_summary.json'}"
    )

    print(
        f"[SAVED] "
        f"{PLOT_DIR / 'training_loss.png'}"
    )

    print()
    print(
        "[NEXT] Jalankan evaluation "
        "menggunakan best_model.pth."
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()

