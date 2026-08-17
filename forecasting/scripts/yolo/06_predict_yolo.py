import json
import random
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

OUTPUT_DIR = (
    BASE_DIR
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

PREDICTION_DIR = (
    OUTPUT_DIR
    / "predictions"
)

PREDICTION_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# DATASET CONFIGURATION
# ============================================================

DATASET_NAME = "YOLO Traffic Dataset"

INTERSECTION_ID = "simpang4-pingit"

SEQUENCE_LENGTH = 15
FORECAST_HORIZON = 1

NUM_APPROACHES = 4
LANES_PER_APPROACH = 3

NUM_SENSORS = 12

NUM_FEATURES_PER_SENSOR = 8

INPUT_SIZE = (
    NUM_SENSORS
    * NUM_FEATURES_PER_SENSOR
)

OUTPUT_SIZE = INPUT_SIZE


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


# ============================================================
# MODEL CONFIGURATION
# ============================================================

HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2


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
        input_size,
        hidden_size=64,
        num_layers=2,
        output_size=96,
        dropout=0.2
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

        self.dropout = nn.Dropout(
            dropout
        )

        self.output_layer = nn.Linear(
            hidden_size,
            output_size
        )

    def forward(
        self,
        x
    ):

        # ----------------------------------------------------
        # Input:
        #
        # (batch, sequence, 96)
        # ----------------------------------------------------

        lstm_output, _ = self.lstm(
            x
        )

        # ----------------------------------------------------
        # Ambil output timestep terakhir
        #
        # (batch, hidden_size)
        # ----------------------------------------------------

        last_output = (
            lstm_output[:, -1, :]
        )

        last_output = self.dropout(
            last_output
        )

        # ----------------------------------------------------
        # Output:
        #
        # (batch, 96)
        # ----------------------------------------------------

        output = self.output_layer(
            last_output
        )

        return output


# ============================================================
# LOAD YOLO CONFIG
# ============================================================

def load_yolo_config():

    config_path = (
        PROCESSED_DIR
        / "yolo_config.json"
    )

    if not config_path.exists():

        raise FileNotFoundError(
            f"yolo_config.json tidak ditemukan:\n"
            f"{config_path}"
        )

    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(
            file
        )

    print(
        "[OK] yolo_config.json loaded."
    )

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

    print(
        "[OK] Scaler loaded."
    )

    print(
        f"[INFO] Scaler feature count : "
        f"{len(scaler.scale_)}"
    )

    # --------------------------------------------------------
    # Pastikan scaler memang dibuat untuk 96 fitur
    # --------------------------------------------------------

    if len(scaler.scale_) != INPUT_SIZE:

        raise ValueError(
            "Jumlah feature pada scaler tidak sesuai.\n"
            f"Expected : {INPUT_SIZE}\n"
            f"Got      : {len(scaler.scale_)}\n\n"
            "Pastikan scaler_X.pkl berasal dari "
            "preprocessing YOLO terbaru."
        )

    return scaler


# ============================================================
# LOAD MODEL
# ============================================================

def load_model():

    model_path = (
        MODEL_DIR
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

    # --------------------------------------------------------
    # Buat arsitektur yang SAMA dengan training
    # --------------------------------------------------------

    model = TrafficLSTM(
        input_size=INPUT_SIZE,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        output_size=OUTPUT_SIZE,
        dropout=DROPOUT
    )

    checkpoint = torch.load(
        model_path,
        map_location=DEVICE
    )

    # --------------------------------------------------------
    # Support checkpoint training
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
                f"[INFO] Best epoch    : "
                f"{best_epoch}"
            )

        if best_val_loss is not None:

            print(
                f"[INFO] Best val loss : "
                f"{best_val_loss:.6f}"
            )

    else:

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
        parameter.numel()
        for parameter in model.parameters()
    )

    print(
        f"[INFO] Parameters    : "
        f"{parameter_count:,}"
    )

    print(
        "[OK] Model ready."
    )

    return model


# ============================================================
# LOAD LAST TEST SEQUENCE
# ============================================================

def load_last_sequence():

    X_test_path = (
        PROCESSED_DIR
        / "X_test.npy"
    )

    if not X_test_path.exists():

        raise FileNotFoundError(
            f"X_test.npy tidak ditemukan:\n"
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
    # Expected:
    #
    # (samples, 15, 96)
    # --------------------------------------------------------

    if X_test.ndim != 3:

        raise ValueError(
            "X_test harus memiliki 3 dimensi:\n"
            "(samples, sequence_length, input_size)"
        )

    if X_test.shape[1] != SEQUENCE_LENGTH:

        raise ValueError(
            "Sequence length tidak sesuai.\n"
            f"Expected : {SEQUENCE_LENGTH}\n"
            f"Got      : {X_test.shape[1]}"
        )

    if X_test.shape[2] != INPUT_SIZE:

        raise ValueError(
            "Input size tidak sesuai.\n"
            f"Expected : {INPUT_SIZE}\n"
            f"Got      : {X_test.shape[2]}"
        )

    # --------------------------------------------------------
    # Ambil sequence terakhir
    #
    # (15, 96)
    # --------------------------------------------------------

    last_sequence = X_test[-1]

    print(
        f"[INFO] Sequence length : "
        f"{last_sequence.shape[0]}"
    )

    print(
        f"[INFO] Input features  : "
        f"{last_sequence.shape[1]}"
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
    # Sequence:
    #
    # (15, 96)
    #
    # menjadi:
    #
    # (1, 15, 96)
    # --------------------------------------------------------

    input_tensor = torch.from_numpy(
        sequence
    ).float()

    input_tensor = (
        input_tensor
        .unsqueeze(0)
    )

    input_tensor = input_tensor.to(
        DEVICE
    )

    print(
        f"[INFO] Input tensor shape : "
        f"{tuple(input_tensor.shape)}"
    )

    # --------------------------------------------------------
    # Inference
    # --------------------------------------------------------

    start_time = time.time()

    with torch.no_grad():

        prediction = model(
            input_tensor
        )

    inference_time = (
        time.time()
        - start_time
    )

    # --------------------------------------------------------
    # CPU + NumPy
    #
    # (1, 96)
    # menjadi
    # (96,)
    # --------------------------------------------------------

    prediction = (
        prediction
        .detach()
        .cpu()
        .numpy()
    )

    prediction = prediction[0]

    print(
        f"[INFO] Prediction shape : "
        f"{prediction.shape}"
    )

    print(
        f"[INFO] Inference time   : "
        f"{inference_time:.4f} seconds"
    )

    if prediction.shape != (
        INPUT_SIZE,
    ):

        raise ValueError(
            "Shape prediction tidak sesuai.\n"
            f"Expected : ({INPUT_SIZE},)\n"
            f"Got      : {prediction.shape}"
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

    # --------------------------------------------------------
    # IMPORTANT
    #
    # YOLO menggunakan:
    #
    # 12 sensor × 8 feature = 96 feature
    #
    # Jadi scaler juga memiliki 96 feature.
    #
    # Jangan reshape menjadi (sensor, 8)
    # lalu inverse_transform.
    #
    # StandardScaler bekerja pada:
    #
    # (samples, 96)
    # --------------------------------------------------------

    prediction_2d = (
        prediction
        .reshape(
            1,
            INPUT_SIZE
        )
    )

    print(
        f"[INFO] Input to scaler : "
        f"{prediction_2d.shape}"
    )

    if prediction_2d.shape[1] != len(
        scaler.scale_
    ):

        raise ValueError(
            "Jumlah feature prediction "
            "tidak sama dengan scaler.\n"
            f"Prediction : {prediction_2d.shape[1]}\n"
            f"Scaler     : {len(scaler.scale_)}"
        )

    try:

        prediction_original = (
            scaler.inverse_transform(
                prediction_2d
            )
        )

    except Exception as error:

        raise ValueError(
            "Gagal melakukan inverse scaling.\n"
            f"Prediction shape : "
            f"{prediction_2d.shape}\n"
            f"Scaler features  : "
            f"{len(scaler.scale_)}\n\n"
            f"Original error: {error}"
        )

    prediction_original = (
        prediction_original
        .reshape(INPUT_SIZE)
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

    prediction = (
        prediction
        .copy()
    )

    # --------------------------------------------------------
    # Reshape:
    #
    # (96,)
    #
    # menjadi:
    #
    # (12, 8)
    #
    # supaya setiap sensor memiliki 8 feature.
    # --------------------------------------------------------

    prediction_matrix = (
        prediction
        .reshape(
            NUM_SENSORS,
            NUM_FEATURES_PER_SENSOR
        )
    )

    # --------------------------------------------------------
    # Semua feature traffic yang digunakan
    # tidak boleh negatif.
    #
    # Index:
    #
    # 0 vehicle_count
    # 1 car_count
    # 2 motorcycle_count
    # 3 bus_count
    # 4 truck_count
    # 5 queue_length_veh
    # 6 queue_length_m_est
    # 7 density_index
    # --------------------------------------------------------

    prediction_matrix = np.maximum(
        prediction_matrix,
        0
    )

    # --------------------------------------------------------
    # Kembalikan menjadi:
    #
    # (96,)
    # --------------------------------------------------------

    prediction = (
        prediction_matrix
        .reshape(INPUT_SIZE)
    )

    return prediction


# ============================================================
# SENSOR MAPPING
# ============================================================

def build_sensor_mapping():

    sensors = []

    sensor_id = 1

    for approach in APPROACHES:

        for lane in LANES:

            sensors.append(
                {
                    "sensor": sensor_id,
                    "approach": approach,
                    "lane_id": lane
                }
            )

            sensor_id += 1

    return sensors


# ============================================================
# CREATE PREDICTION DATAFRAME
# ============================================================

def create_prediction_dataframe(
    prediction
):

    prediction_matrix = (
        prediction
        .reshape(
            NUM_SENSORS,
            NUM_FEATURES_PER_SENSOR
        )
    )

    sensors = (
        build_sensor_mapping()
    )

    rows = []

    for sensor_index in range(
        NUM_SENSORS
    ):

        sensor_info = (
            sensors[sensor_index]
        )

        row = {

            "sensor":
                sensor_info[
                    "sensor"
                ],

            "approach":
                sensor_info[
                    "approach"
                ],

            "lane_id":
                sensor_info[
                    "lane_id"
                ]
        }

        for feature_index, feature_name in enumerate(
            FEATURE_NAMES
        ):

            row[
                f"predicted_{feature_name}"
            ] = float(
                prediction_matrix[
                    sensor_index,
                    feature_index
                ]
            )

        rows.append(
            row
        )

    dataframe = pd.DataFrame(
        rows
    )

    return dataframe


# ============================================================
# CREATE FLAT PREDICTION DATAFRAME
# ============================================================

def create_flat_prediction_dataframe(
    prediction
):

    prediction_matrix = (
        prediction
        .reshape(
            NUM_SENSORS,
            NUM_FEATURES_PER_SENSOR
        )
    )

    sensors = (
        build_sensor_mapping()
    )

    row = {}

    for sensor_index in range(
        NUM_SENSORS
    ):

        sensor_info = (
            sensors[sensor_index]
        )

        sensor_id = (
            sensor_info[
                "sensor"
            ]
        )

        approach = (
            sensor_info[
                "approach"
            ]
        )

        lane_id = (
            sensor_info[
                "lane_id"
            ]
        )

        for feature_index, feature_name in enumerate(
            FEATURE_NAMES
        ):

            column_name = (
                f"{approach}_"
                f"{lane_id}_"
                f"{feature_name}"
            )

            row[
                column_name
            ] = float(
                prediction_matrix[
                    sensor_index,
                    feature_index
                ]
            )

    dataframe = pd.DataFrame(
        [row]
    )

    return dataframe


# ============================================================
# SAVE PREDICTION
# ============================================================

def save_prediction(
    prediction,
    dataframe,
    flat_dataframe,
    inference_time
):

    # --------------------------------------------------------
    # NPZ
    # --------------------------------------------------------

    npz_path = (
        PREDICTION_DIR
        / "prediction.npz"
    )

    np.savez(
        npz_path,
        prediction=prediction
    )

    print(
        f"[SAVED] {npz_path}"
    )

    # --------------------------------------------------------
    # CSV - format per sensor
    # --------------------------------------------------------

    csv_path = (
        PREDICTION_DIR
        / "prediction.csv"
    )

    dataframe.to_csv(
        csv_path,
        index=False
    )

    print(
        f"[SAVED] {csv_path}"
    )

    # --------------------------------------------------------
    # CSV - flat format
    # --------------------------------------------------------

    flat_csv_path = (
        PREDICTION_DIR
        / "prediction_flat.csv"
    )

    flat_dataframe.to_csv(
        flat_csv_path,
        index=False
    )

    print(
        f"[SAVED] {flat_csv_path}"
    )

    # --------------------------------------------------------
    # JSON summary
    # --------------------------------------------------------

    summary_path = (
        PREDICTION_DIR
        / "prediction_summary.json"
    )

    summary = {

        "dataset":
            DATASET_NAME,

        "intersection_id":
            INTERSECTION_ID,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "sensors": {

            "count":
                NUM_SENSORS,

            "approaches":
                APPROACHES,

            "lanes_per_approach":
                LANES_PER_APPROACH
        },

        "features": {

            "count":
                NUM_FEATURES_PER_SENSOR,

            "names":
                FEATURE_NAMES
        },

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

        "inference_time_seconds":
            float(
                inference_time
            ),

        "prediction_shape":
            list(
                prediction.shape
            ),

        "prediction_file":
            "prediction.npz",

        "prediction_csv":
            "prediction.csv",

        "prediction_flat_csv":
            "prediction_flat.csv"
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

    # --------------------------------------------------------
    # Print average setiap feature
    # --------------------------------------------------------

    for feature_name in FEATURE_NAMES:

        column_name = (
            f"predicted_{feature_name}"
        )

        average_value = (
            dataframe[
                column_name
            ].mean()
        )

        print(
            f"[INFO] Average predicted "
            f"{feature_name:<20}: "
            f"{average_value:.4f}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    set_seed()

    print("=" * 70)
    print("YOLO TRAFFIC LSTM PREDICTION")
    print("=" * 70)

    print(
        f"[INFO] Device : {DEVICE}"
    )

    print("=" * 70)
    print("PREDICTION CONFIGURATION")
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

    print()

    print(
        "[INFO] Features:"
    )

    for feature_name in FEATURE_NAMES:

        print(
            f"       - {feature_name}"
        )

    # --------------------------------------------------------
    # Load config
    # --------------------------------------------------------

    try:

        config = (
            load_yolo_config()
        )

    except Exception as error:

        print(
            f"[WARNING] Config tidak dapat "
            f"dibaca: {error}"
        )

        config = None

    # --------------------------------------------------------
    # Load scaler
    # --------------------------------------------------------

    scaler = (
        load_scaler()
    )

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    model = (
        load_model()
    )

    # --------------------------------------------------------
    # Load last sequence
    # --------------------------------------------------------

    sequence = (
        load_last_sequence()
    )

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
            prediction=prediction_scaled,
            scaler=scaler
        )
    )

    # --------------------------------------------------------
    # Clean physical values
    # --------------------------------------------------------

    prediction_original = (
        clean_prediction(
            prediction_original
        )
    )

    # --------------------------------------------------------
    # Create sensor dataframe
    # --------------------------------------------------------

    dataframe = (
        create_prediction_dataframe(
            prediction_original
        )
    )

    # --------------------------------------------------------
    # Create flat dataframe
    # --------------------------------------------------------

    flat_dataframe = (
        create_flat_prediction_dataframe(
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
        flat_dataframe=flat_dataframe,
        inference_time=inference_time
    )

    # --------------------------------------------------------
    # Final
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("YOLO PREDICTION PIPELINE COMPLETED")
    print("=" * 70)

    print(
        "[OK] Model             : "
        "best_model.pth"
    )

    print(
        "[OK] Input              : "
        f"{SEQUENCE_LENGTH} timestep terakhir"
    )

    print(
        "[OK] Forecast horizon   : "
        f"{FORECAST_HORIZON} timestep"
    )

    print(
        "[OK] Sensors            : "
        f"{NUM_SENSORS}"
    )

    print(
        "[OK] Features/sensor   : "
        f"{NUM_FEATURES_PER_SENSOR}"
    )

    print(
        "[OK] Input size         : "
        f"{INPUT_SIZE}"
    )

    print(
        "[OK] Features           : "
        "Semua 8 feature YOLO"
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
        f"{PREDICTION_DIR / 'prediction_flat.csv'}"
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