import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import joblib


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

PROCESSED_DIR = (
    BASE_DIR
    / "outputs"
    / "pems04"
    / "processed"
)

OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "pems04"
)

PREDICTION_DIR = (
    OUTPUT_DIR
    / "prediction"
)

PREDICTION_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================

DATASET_NAME = "PEMS04"

SEQUENCE_LENGTH = 15
FORECAST_HORIZON = 1

HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2

NUM_SENSORS = 10
NUM_FEATURES = 3

FEATURE_NAMES = [
    "flow",
    "occupancy",
    "speed"
]

SENSOR_START = 1
SENSOR_END = 10

BATCH_SIZE = 64

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

        # IMPORTANT:
        # Sama dengan model training.
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
        # LSTM:
        # (batch, sequence, sensors * features)
        # ----------------------------------------------------

        x = x.reshape(
            batch_size,
            x.size(1),
            -1
        )

        lstm_output, _ = self.lstm(x)

        # Ambil output timestep terakhir
        last_output = (
            lstm_output[:, -1, :]
        )

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
# LOAD CONFIG
# ============================================================

def load_preprocess_config():

    config_path = (
        PROCESSED_DIR
        / "pems04_config.json"
    )

    if not config_path.exists():

        raise FileNotFoundError(
            f"Config tidak ditemukan:\n"
            f"{config_path}"
        )

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(file)

    return config


# ============================================================
# LOAD SCALER
# ============================================================

def load_scaler():

    scaler_path = (
        PROCESSED_DIR
        / "scaler_X.pkl"
    )

    if not scaler_path.exists():

        raise FileNotFoundError(
            f"Scaler tidak ditemukan:\n"
            f"{scaler_path}"
        )

    scaler = joblib.load(
        scaler_path
    )

    return scaler


# ============================================================
# LOAD MODEL
# ============================================================

def load_model():

    model_path = (
        OUTPUT_DIR
        / "best_model.pth"
    )

    if not model_path.exists():

        raise FileNotFoundError(
            f"Best model tidak ditemukan:\n"
            f"{model_path}"
        )

    print("=" * 70)
    print("MODEL LOADING")
    print("=" * 70)

    print(
        f"[INFO] Model path:\n"
        f"       {model_path}"
    )

    model = TrafficLSTM(
        num_sensors=NUM_SENSORS,
        num_features=NUM_FEATURES,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        dropout=DROPOUT
    )

    checkpoint = torch.load(
        model_path,
        map_location=DEVICE
    )

    # --------------------------------------------------------
    # Support checkpoint dari training
    # --------------------------------------------------------

    if (
        isinstance(checkpoint, dict)
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
                f"[INFO] Best epoch     : "
                f"{best_epoch}"
            )

        if best_val_loss is not None:

            print(
                f"[INFO] Best val loss  : "
                f"{best_val_loss:.6f}"
            )

    else:

        # Fallback jika checkpoint hanya
        # berisi state_dict
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
        f"[INFO] Parameters      : "
        f"{parameter_count:,}"
    )

    return model


# ============================================================
# LOAD LAST SEQUENCE
# ============================================================

def load_last_sequence():

    X_test_path = (
        PROCESSED_DIR
        / "X_test.npy"
    )

    if not X_test_path.exists():

        raise FileNotFoundError(
            f"X_test tidak ditemukan:\n"
            f"{X_test_path}"
        )

    X_test = np.load(
        X_test_path
    ).astype(
        np.float32
    )

    print("=" * 70)
    print("INPUT SEQUENCE")
    print("=" * 70)

    print(
        f"[INFO] X_test shape : "
        f"{X_test.shape}"
    )

    # --------------------------------------------------------
    # Ambil sequence terakhir
    #
    # Shape:
    # (15, 10, 3)
    # --------------------------------------------------------

    last_sequence = X_test[-1]

    if last_sequence.shape != (
        SEQUENCE_LENGTH,
        NUM_SENSORS,
        NUM_FEATURES
    ):

        raise ValueError(
            "Shape sequence tidak sesuai.\n"
            f"Expected: "
            f"({SEQUENCE_LENGTH}, "
            f"{NUM_SENSORS}, "
            f"{NUM_FEATURES})\n"
            f"Got: "
            f"{last_sequence.shape}"
        )

    print(
        f"[INFO] Sequence length : "
        f"{last_sequence.shape[0]}"
    )

    print(
        f"[INFO] Sensors         : "
        f"{last_sequence.shape[1]}"
    )

    print(
        f"[INFO] Features        : "
        f"{last_sequence.shape[2]}"
    )

    print(
        "[OK] Last test sequence loaded."
    )

    return last_sequence


# ============================================================
# GENERATE PREDICTION
# ============================================================

def generate_prediction(
    model,
    sequence
):

    print("=" * 70)
    print("GENERATING PREDICTION")
    print("=" * 70)

    # --------------------------------------------------------
    # Convert:
    #
    # (15, 10, 3)
    #
    # menjadi:
    #
    # (1, 15, 10, 3)
    # --------------------------------------------------------

    input_tensor = torch.from_numpy(
        sequence
    ).float()

    input_tensor = input_tensor.unsqueeze(
        0
    )

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

    # --------------------------------------------------------
    # Shape:
    #
    # (1, 10, 3)
    #
    # menjadi:
    #
    # (10, 3)
    # --------------------------------------------------------

    prediction = prediction[0]

    print(
        f"[INFO] Prediction shape : "
        f"{prediction.shape}"
    )

    print(
        f"[INFO] Inference time   : "
        f"{inference_time:.4f} seconds"
    )

    return (
        prediction,
        inference_time
    )


# ============================================================
# INVERSE SCALING
# ============================================================

def inverse_transform_prediction(
    prediction,
    scaler
):

    print("=" * 70)
    print("INVERSE SCALING")
    print("=" * 70)

    original_shape = prediction.shape

    # --------------------------------------------------------
    # StandardScaler bekerja pada:
    #
    # (samples, features)
    #
    # Prediction:
    #
    # (10, 3)
    #
    # --------------------------------------------------------

    prediction_2d = prediction.reshape(
        -1,
        NUM_FEATURES
    )

    try:

        prediction_original = (
            scaler.inverse_transform(
                prediction_2d
            )
        )

    except ValueError as error:

        raise ValueError(
            "Gagal melakukan inverse scaling.\n"
            "Pastikan scaler_X.pkl dibuat dari "
            "3 feature PEMS04 "
            "(flow, occupancy, speed).\n\n"
            f"Original error: {error}"
        )

    prediction_original = (
        prediction_original.reshape(
            original_shape
        )
    )

    print(
        "[OK] Prediction berhasil "
        "dikembalikan ke skala asli."
    )

    return prediction_original


# ============================================================
# CLEAN PHYSICAL VALUES
# ============================================================

def clean_prediction(
    prediction
):

    prediction = prediction.copy()

    # Flow tidak boleh negatif
    prediction[:, 0] = np.maximum(
        prediction[:, 0],
        0
    )

    # Occupancy tidak boleh negatif
    prediction[:, 1] = np.maximum(
        prediction[:, 1],
        0
    )

    # Speed tidak boleh negatif
    prediction[:, 2] = np.maximum(
        prediction[:, 2],
        0
    )

    return prediction


# ============================================================
# CREATE RESULT DATAFRAME
# ============================================================

def create_prediction_dataframe(
    prediction
):

    rows = []

    for sensor_index in range(
        NUM_SENSORS
    ):

        sensor_id = (
            SENSOR_START
            + sensor_index
        )

        rows.append(
            {
                "sensor":
                    sensor_id,

                "predicted_flow":
                    float(
                        prediction[
                            sensor_index,
                            0
                        ]
                    ),

                "predicted_occupancy":
                    float(
                        prediction[
                            sensor_index,
                            1
                        ]
                    ),

                "predicted_speed":
                    float(
                        prediction[
                            sensor_index,
                            2
                        ]
                    )
            }
        )

    dataframe = pd.DataFrame(
        rows
    )

    return dataframe


# ============================================================
# SAVE PREDICTION
# ============================================================

def save_prediction(
    prediction,
    dataframe,
    inference_time
):

    npz_path = (
        PREDICTION_DIR
        / "prediction.npz"
    )

    csv_path = (
        PREDICTION_DIR
        / "prediction.csv"
    )

    summary_path = (
        PREDICTION_DIR
        / "prediction_summary.json"
    )

    # --------------------------------------------------------
    # Save NPZ
    # --------------------------------------------------------

    np.savez(
        npz_path,
        prediction=prediction
    )

    print(
        f"[SAVED] {npz_path}"
    )

    # --------------------------------------------------------
    # Save CSV
    # --------------------------------------------------------

    dataframe.to_csv(
        csv_path,
        index=False
    )

    print(
        f"[SAVED] {csv_path}"
    )

    # --------------------------------------------------------
    # Save JSON summary
    # --------------------------------------------------------

    summary = {

        "dataset":
            DATASET_NAME,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

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

        "inference_time_seconds":
            float(
                inference_time
            ),

        "prediction_file":
            "prediction.npz",

        "prediction_csv":
            "prediction.csv"
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
# DISPLAY RESULTS
# ============================================================

def display_results(
    dataframe
):

    print()
    print("=" * 70)
    print("PREDICTION RESULTS")
    print("=" * 70)

    print()

    print(
        dataframe.to_string(
            index=False,
            float_format=lambda value:
                f"{value:.4f}"
        )
    )

    print()

    print("=" * 70)
    print("PREDICTION SUMMARY")
    print("=" * 70)

    print(
        f"[INFO] Average predicted flow      : "
        f"{dataframe['predicted_flow'].mean():.4f}"
    )

    print(
        f"[INFO] Average predicted occupancy : "
        f"{dataframe['predicted_occupancy'].mean():.4f}"
    )

    print(
        f"[INFO] Average predicted speed     : "
        f"{dataframe['predicted_speed'].mean():.4f}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    set_seed()

    print("=" * 70)
    print("PEMS04 LSTM TRAFFIC PREDICTION")
    print("=" * 70)

    print(
        f"[INFO] Device: {DEVICE}"
    )

    print("=" * 70)
    print("PREDICTION CONFIGURATION")
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
        f"[INFO] Sensors         : "
        f"{SENSOR_START}-{SENSOR_END}"
    )

    print(
        "[INFO] Features        : "
        "Flow + Occupancy + Speed"
    )

    # --------------------------------------------------------
    # Load preprocess config
    # --------------------------------------------------------

    try:

        preprocess_config = (
            load_preprocess_config()
        )

        print(
            "[OK] Preprocessing config loaded."
        )

    except Exception as error:

        print(
            f"[WARNING] Config tidak dapat "
            f"dibaca: {error}"
        )

        preprocess_config = None

    # --------------------------------------------------------
    # Load scaler
    # --------------------------------------------------------

    scaler = load_scaler()

    print(
        "[OK] Scaler loaded."
    )

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    model = load_model()

    # --------------------------------------------------------
    # Load last sequence
    # --------------------------------------------------------

    sequence = load_last_sequence()

    # --------------------------------------------------------
    # Generate prediction
    # --------------------------------------------------------

    (
        prediction_scaled,
        inference_time
    ) = generate_prediction(
        model=model,
        sequence=sequence
    )

    # --------------------------------------------------------
    # Inverse scaling
    # --------------------------------------------------------

    prediction_original = (
        inverse_transform_prediction(
            prediction_scaled,
            scaler
        )
    )

    # --------------------------------------------------------
    # Physical value cleaning
    # --------------------------------------------------------

    prediction_original = (
        clean_prediction(
            prediction_original
        )
    )

    # --------------------------------------------------------
    # Create dataframe
    # --------------------------------------------------------

    dataframe = (
        create_prediction_dataframe(
            prediction_original
        )
    )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    display_results(
        dataframe
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING PREDICTION")
    print("=" * 70)

    save_prediction(
        prediction=prediction_original,
        dataframe=dataframe,
        inference_time=inference_time
    )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PREDICTION PIPELINE COMPLETED")
    print("=" * 70)

    print(
        "[OK] Model              : best_model.pth"
    )

    print(
        "[OK] Input               : "
        f"{SEQUENCE_LENGTH} timestep terakhir"
    )

    print(
        "[OK] Forecast horizon    : "
        f"{FORECAST_HORIZON} timestep"
    )

    print(
        "[OK] Sensors             : "
        f"{SENSOR_START}-{SENSOR_END}"
    )

    print(
        "[OK] Features            : "
        "Flow + Occupancy + Speed"
    )

    print()
    print("[OUTPUT]")

    print(
        f"[SAVED] "
        f"{PREDICTION_DIR / 'prediction.npz'}"
    )

    print(
        f"[SAVED] "
        f"{PREDICTION_DIR / 'prediction.csv'}"
    )

    print(
        f"[SAVED] "
        f"{PREDICTION_DIR / 'prediction_summary.json'}"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
