from pathlib import Path
import json
import pickle
import random

import numpy as np
from sklearn.preprocessing import StandardScaler


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

# Dataset mentah yang SAMA dengan eksperimen 10 sensor
DATA_PATH = (
    BASE_DIR
    / "data"
    / "PEMS04.npz"
)

# Output khusus eksperimen 20 sensor
OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "pems04"
    / "sensor_1-20"
)

PROCESSED_DIR = (
    OUTPUT_DIR
    / "processed"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PROCESSED_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================

DATASET_NAME = "PEMS04"

# ------------------------------------------------------------
# Sensor configuration
# ------------------------------------------------------------

SENSOR_START = 1
SENSOR_END = 20

NUM_SENSORS = (
    SENSOR_END
    - SENSOR_START
    + 1
)

# ------------------------------------------------------------
# Feature configuration
# ------------------------------------------------------------

FEATURE_NAMES = [
    "flow",
    "occupancy",
    "speed"
]

NUM_FEATURES = len(
    FEATURE_NAMES
)

# ------------------------------------------------------------
# Sequence configuration
# ------------------------------------------------------------

SEQUENCE_LENGTH = 15

FORECAST_HORIZON = 1

# ------------------------------------------------------------
# Chronological split
# ------------------------------------------------------------

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# ------------------------------------------------------------
# Reproducibility
# ------------------------------------------------------------

RANDOM_SEED = 42


# ============================================================
# REPRODUCIBILITY
# ============================================================

def set_seed(seed=RANDOM_SEED):

    random.seed(seed)

    np.random.seed(seed)


# ============================================================
# LOAD RAW DATA
# ============================================================

def load_raw_data():

    print("=" * 70)
    print("PEMS04 DATA LOADING")
    print("=" * 70)

    print(
        f"[INFO] Dataset:"
    )

    print(
        f"       {DATA_PATH}"
    )

    if not DATA_PATH.exists():

        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n"
            f"{DATA_PATH}"
        )

    data = np.load(
        DATA_PATH
    )

    print()
    print(
        "[INFO] NPZ CONTENTS"
    )

    print(
        f"       {data.files}"
    )

    if "data" not in data.files:

        raise KeyError(
            "Array 'data' tidak ditemukan "
            "di dalam PEMS04.npz."
        )

    raw_data = data["data"]

    print()
    print(
        f"[INFO] Raw data shape : "
        f"{raw_data.shape}"
    )

    print(
        f"[INFO] Raw data dtype : "
        f"{raw_data.dtype}"
    )

    return raw_data


# ============================================================
# VALIDATE RAW DATA
# ============================================================

def validate_raw_data(
    raw_data
):

    print()
    print("=" * 70)
    print("RAW DATA VALIDATION")
    print("=" * 70)

    if raw_data.ndim != 3:

        raise ValueError(
            "Data PEMS04 harus memiliki "
            "3 dimensi: "
            "(time, sensors, features)."
        )

    num_timesteps = raw_data.shape[0]

    total_sensors = raw_data.shape[1]

    total_features = raw_data.shape[2]

    print(
        f"[INFO] Timesteps       : "
        f"{num_timesteps}"
    )

    print(
        f"[INFO] Total sensors   : "
        f"{total_sensors}"
    )

    print(
        f"[INFO] Total features  : "
        f"{total_features}"
    )

    # --------------------------------------------------------
    # Validate sensors
    # --------------------------------------------------------

    if SENSOR_START < 1:

        raise ValueError(
            "SENSOR_START harus >= 1."
        )

    if SENSOR_END > total_sensors:

        raise ValueError(
            f"Sensor {SENSOR_END} tidak tersedia. "
            f"Dataset hanya memiliki "
            f"{total_sensors} sensor."
        )

    # --------------------------------------------------------
    # Validate features
    # --------------------------------------------------------

    if total_features != NUM_FEATURES:

        raise ValueError(
            f"Jumlah feature dataset = "
            f"{total_features}, "
            f"sedangkan konfigurasi "
            f"mengharapkan {NUM_FEATURES}."
        )

    print()
    print(
        "[OK] Raw data shape valid."
    )

    print(
        f"[OK] Sensor range valid: "
        f"{SENSOR_START}-{SENSOR_END}"
    )

    print(
        f"[OK] Feature count valid: "
        f"{NUM_FEATURES}"
    )


# ============================================================
# SELECT SENSORS
# ============================================================

def select_sensors(
    raw_data
):

    print()
    print("=" * 70)
    print("SENSOR SELECTION")
    print("=" * 70)

    # Dataset menggunakan zero-based index.
    #
    # Sensor 1  -> index 0
    # Sensor 20 -> index 19
    #
    sensor_start_index = (
        SENSOR_START - 1
    )

    sensor_end_index = SENSOR_END

    selected_data = raw_data[
        :,
        sensor_start_index:
        sensor_end_index,
        :
    ]

    print(
        f"[INFO] Selected sensors : "
        f"{SENSOR_START}-{SENSOR_END}"
    )

    print(
        f"[INFO] Number of sensors: "
        f"{selected_data.shape[1]}"
    )

    print(
        f"[INFO] Selected data shape: "
        f"{selected_data.shape}"
    )

    return selected_data


# ============================================================
# HANDLE NUMERICAL VALUES
# ============================================================

def validate_numeric_values(
    data
):

    print()
    print("=" * 70)
    print("NUMERICAL DATA VALIDATION")
    print("=" * 70)

    nan_count = np.isnan(
        data
    ).sum()

    inf_count = np.isinf(
        data
    ).sum()

    print(
        f"[INFO] NaN count : "
        f"{nan_count}"
    )

    print(
        f"[INFO] Inf count : "
        f"{inf_count}"
    )

    if nan_count > 0:

        raise ValueError(
            "Dataset mengandung NaN. "
            "Lakukan cleaning terlebih dahulu."
        )

    if inf_count > 0:

        raise ValueError(
            "Dataset mengandung infinite value."
        )

    print(
        "[OK] Tidak ditemukan NaN atau Inf."
    )


# ============================================================
# CHRONOLOGICAL SPLIT
# ============================================================

def chronological_split(
    data
):

    print()
    print("=" * 70)
    print("CHRONOLOGICAL SPLIT")
    print("=" * 70)

    total_timesteps = data.shape[0]

    train_end = int(
        total_timesteps
        * TRAIN_RATIO
    )

    val_end = (
        train_end
        + int(
            total_timesteps
            * VAL_RATIO
        )
    )

    train_data = data[
        :train_end
    ]

    val_data = data[
        train_end:val_end
    ]

    test_data = data[
        val_end:
    ]

    print(
        f"[INFO] Total timesteps : "
        f"{total_timesteps}"
    )

    print()
    print(
        "[TRAIN]"
    )

    print(
        f"       Shape : "
        f"{train_data.shape}"
    )

    print()
    print(
        "[VALIDATION]"
    )

    print(
        f"       Shape : "
        f"{val_data.shape}"
    )

    print()
    print(
        "[TEST]"
    )

    print(
        f"       Shape : "
        f"{test_data.shape}"
    )

    print()
    print(
        "[INFO] Split ratio:"
    )

    print(
        f"       Train : {TRAIN_RATIO:.0%}"
    )

    print(
        f"       Val   : {VAL_RATIO:.0%}"
    )

    print(
        f"       Test  : {TEST_RATIO:.0%}"
    )

    return (
        train_data,
        val_data,
        test_data
    )


# ============================================================
# FIT SCALER
# ============================================================

def fit_scaler(
    train_data
):

    print()
    print("=" * 70)
    print("SCALER")
    print("=" * 70)

    print(
        "[INFO] Fitting scaler "
        "menggunakan TRAINING DATA saja."
    )

    # --------------------------------------------------------
    # Shape:
    #
    # train_data
    # (time, sensors, features)
    #
    # scaler membutuhkan:
    # (samples, features)
    #
    # Kita flatten sensor dimension sehingga setiap
    # sensor-feature menjadi satu kolom.
    # --------------------------------------------------------

    train_flat = train_data.reshape(
        train_data.shape[0],
        -1
    )

    scaler = StandardScaler()

    scaler.fit(
        train_flat
    )

    print(
        "[OK] Scaler fitted "
        "menggunakan training data."
    )

    return scaler


# ============================================================
# APPLY SCALER
# ============================================================

def transform_data(
    data,
    scaler
):

    original_shape = data.shape

    flat_data = data.reshape(
        data.shape[0],
        -1
    )

    scaled_data = scaler.transform(
        flat_data
    )

    scaled_data = scaled_data.reshape(
        original_shape
    )

    return scaled_data.astype(
        np.float32
    )


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    data
):

    print()
    print("=" * 70)
    print("SEQUENCE CREATION")
    print("=" * 70)

    X = []
    y = []

    total_timesteps = data.shape[0]

    required_length = (
        SEQUENCE_LENGTH
        + FORECAST_HORIZON
    )

    if total_timesteps < required_length:

        raise ValueError(
            "Jumlah timestep tidak cukup "
            "untuk membuat sequence."
        )

    # --------------------------------------------------------
    # Example:
    #
    # sequence length = 15
    # horizon = 1
    #
    # X:
    # t-14 ... t
    #
    # y:
    # t+1
    # --------------------------------------------------------

    max_start = (
        total_timesteps
        - SEQUENCE_LENGTH
        - FORECAST_HORIZON
        + 1
    )

    for start_idx in range(
        max_start
    ):

        end_idx = (
            start_idx
            + SEQUENCE_LENGTH
        )

        target_idx = (
            end_idx
            + FORECAST_HORIZON
            - 1
        )

        X.append(
            data[
                start_idx:end_idx
            ]
        )

        y.append(
            data[
                target_idx
            ]
        )

    X = np.asarray(
        X,
        dtype=np.float32
    )

    y = np.asarray(
        y,
        dtype=np.float32
    )

    print(
        f"[INFO] X shape: "
        f"{X.shape}"
    )

    print(
        f"[INFO] y shape: "
        f"{y.shape}"
    )

    return X, y


# ============================================================
# SAVE SCALER
# ============================================================

def save_scaler(
    scaler
):

    scaler_path = (
        PROCESSED_DIR
        / "scaler_X.pkl"
    )

    with open(
        scaler_path,
        "wb"
    ) as file:

        pickle.dump(
            scaler,
            file
        )

    print(
        f"[SAVED] {scaler_path}"
    )


# ============================================================
# SAVE CONFIGURATION
# ============================================================

def save_config(
    raw_shape,
    selected_shape,
    train_data,
    val_data,
    test_data,
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test
):

    config_path = (
        PROCESSED_DIR
        / "pems04_20_config.json"
    )

    config = {

        "dataset": DATASET_NAME,

        "source_file": (
            "data/PEMS04.npz"
        ),

        "experiment": {
            "name": "PEMS04_20_SENSORS",
            "sensor_start": SENSOR_START,
            "sensor_end": SENSOR_END,
            "num_sensors": NUM_SENSORS,
            "features": FEATURE_NAMES,
            "num_features": NUM_FEATURES
        },

        "raw_data": {
            "shape": [
                int(value)
                for value in raw_shape
            ]
        },

        "selected_data": {
            "shape": [
                int(value)
                for value in selected_shape
            ]
        },

        "split": {
            "method": "chronological",
            "train_ratio": TRAIN_RATIO,
            "validation_ratio": VAL_RATIO,
            "test_ratio": TEST_RATIO
        },

        "timesteps": {
            "train": int(
                train_data.shape[0]
            ),
            "validation": int(
                val_data.shape[0]
            ),
            "test": int(
                test_data.shape[0]
            )
        },

        "sequence": {
            "sequence_length":
                SEQUENCE_LENGTH,
            "forecast_horizon":
                FORECAST_HORIZON
        },

        "samples": {
            "X_train": int(
                X_train.shape[0]
            ),
            "y_train": int(
                y_train.shape[0]
            ),
            "X_val": int(
                X_val.shape[0]
            ),
            "y_val": int(
                y_val.shape[0]
            ),
            "X_test": int(
                X_test.shape[0]
            ),
            "y_test": int(
                y_test.shape[0]
            )
        },

        "shapes": {
            "X_train": [
                int(value)
                for value in X_train.shape
            ],
            "y_train": [
                int(value)
                for value in y_train.shape
            ],
            "X_val": [
                int(value)
                for value in X_val.shape
            ],
            "y_val": [
                int(value)
                for value in y_val.shape
            ],
            "X_test": [
                int(value)
                for value in X_test.shape
            ],
            "y_test": [
                int(value)
                for value in y_test.shape
            ]
        },

        "scaling": {
            "method": "StandardScaler",
            "fit_on": "training_data_only",
            "data_leakage_prevention": True
        }
    }

    with open(
        config_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            config,
            file,
            indent=4
        )

    print(
        f"[SAVED] {config_path}"
    )


# ============================================================
# SAVE ARRAYS
# ============================================================

def save_arrays(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test
):

    print()
    print("=" * 70)
    print("SAVING PROCESSED DATA")
    print("=" * 70)

    files = {

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

    for name, array in files.items():

        path = (
            PROCESSED_DIR
            / f"{name}.npy"
        )

        np.save(
            path,
            array
        )

        print(
            f"[SAVED] {path}"
        )


# ============================================================
# PRINT DATA SUMMARY
# ============================================================

def print_summary(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test
):

    print()
    print("=" * 70)
    print("PREPROCESSING SUMMARY")
    print("=" * 70)

    print(
        "[EXPERIMENT]"
    )

    print(
        f"Sensor range : "
        f"{SENSOR_START}-{SENSOR_END}"
    )

    print(
        f"Sensor count : "
        f"{NUM_SENSORS}"
    )

    print(
        f"Features     : "
        f"{', '.join(FEATURE_NAMES)}"
    )

    print()
    print(
        "[SEQUENCE]"
    )

    print(
        f"Sequence length : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"Forecast horizon: "
        f"{FORECAST_HORIZON}"
    )

    print()
    print(
        "[OUTPUT SHAPES]"
    )

    print(
        f"X_train : "
        f"{X_train.shape}"
    )

    print(
        f"y_train : "
        f"{y_train.shape}"
    )

    print(
        f"X_val   : "
        f"{X_val.shape}"
    )

    print(
        f"y_val   : "
        f"{y_val.shape}"
    )

    print(
        f"X_test  : "
        f"{X_test.shape}"
    )

    print(
        f"y_test  : "
        f"{y_test.shape}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    set_seed()

    print("=" * 70)
    print("PEMS04 PREPROCESSING — 20 SENSORS")
    print("=" * 70)

    print(
        f"[INFO] Device-independent preprocessing"
    )

    print(
        f"[INFO] Source dataset: "
        f"{DATA_PATH}"
    )

    print(
        f"[INFO] Sensor range: "
        f"{SENSOR_START}-{SENSOR_END}"
    )

    print(
        f"[INFO] Number of sensors: "
        f"{NUM_SENSORS}"
    )

    print(
        f"[INFO] Features: "
        f"{', '.join(FEATURE_NAMES)}"
    )

    print(
        f"[INFO] Sequence length: "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[INFO] Forecast horizon: "
        f"{FORECAST_HORIZON}"
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    raw_data = load_raw_data()

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    validate_raw_data(
        raw_data
    )

    # --------------------------------------------------------
    # Select sensors
    # --------------------------------------------------------

    selected_data = select_sensors(
        raw_data
    )

    # --------------------------------------------------------
    # Numerical validation
    # --------------------------------------------------------

    validate_numeric_values(
        selected_data
    )

    # --------------------------------------------------------
    # Chronological split
    # --------------------------------------------------------

    (
        train_data,
        val_data,
        test_data
    ) = chronological_split(
        selected_data
    )

    # --------------------------------------------------------
    # Fit scaler on TRAIN ONLY
    # --------------------------------------------------------

    scaler = fit_scaler(
        train_data
    )

    # --------------------------------------------------------
    # Transform
    # --------------------------------------------------------

    train_scaled = transform_data(
        train_data,
        scaler
    )

    val_scaled = transform_data(
        val_data,
        scaler
    )

    test_scaled = transform_data(
        test_data,
        scaler
    )

    print()
    print(
        "[OK] Scaling completed."
    )

    # --------------------------------------------------------
    # Create sequences
    # --------------------------------------------------------

    X_train, y_train = create_sequences(
        train_scaled
    )

    X_val, y_val = create_sequences(
        val_scaled
    )

    X_test, y_test = create_sequences(
        test_scaled
    )

    # --------------------------------------------------------
    # Save arrays
    # --------------------------------------------------------

    save_arrays(
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test
    )

    # --------------------------------------------------------
    # Save scaler
    # --------------------------------------------------------

    save_scaler(
        scaler
    )

    # --------------------------------------------------------
    # Save configuration
    # --------------------------------------------------------

    save_config(
        raw_shape=raw_data.shape,
        selected_shape=selected_data.shape,
        train_data=train_data,
        val_data=val_data,
        test_data=test_data,
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print_summary(
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test
    )

    print()
    print("=" * 70)
    print("PREPROCESSING PIPELINE COMPLETED")
    print("=" * 70)

    print()
    print("[OUTPUT DIRECTORY]")

    print(
        f"{PROCESSED_DIR}"
    )

    print()
    print(
        "[NEXT]"
    )

    print(
        "Jalankan training menggunakan "
        "script training khusus PEMS04 20 sensor."
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
