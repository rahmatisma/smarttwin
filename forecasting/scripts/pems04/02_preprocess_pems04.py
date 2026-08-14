# `02_preprocess_pems04.py`

"""
PEMS04 PREPROCESSING
====================

Baseline experiment:
- Sensors       : 1-10
- Features      : Flow, Occupancy, Speed
- Sequence      : 15 timesteps
- Horizon       : 1 timestep
- Split         : 70% train / 15% validation / 15% test
- Scaling       : fitted ONLY on training data

Input:
    forecasting/data/PEMS04.npz

Output:
    forecasting/outputs/pems04/processed/

    X_train.npy
    y_train.npy
    X_val.npy
    y_val.npy
    X_test.npy
    y_test.npy
    scaler_X.pkl
    scaler_y.pkl
    pems04_config.json
"""

from pathlib import Path
import json
import pickle

import numpy as np
from sklearn.preprocessing import StandardScaler


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_PATH = BASE_DIR / "data" / "PEMS04.npz"

OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "pems04"
    / "processed"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================

# PEMS04 memiliki 307 sensor.
# Untuk baseline kita gunakan sensor 1-10.
#
# Python menggunakan index 0-9 untuk sensor 1-10.
SENSOR_START = 0
SENSOR_END = 10

# Nama variabel.
#
# PENTING:
# Urutan ini harus sesuai dengan dokumentasi PEMS04.
# Dataset PEMS04 berbentuk:
#
# (time, sensor, feature)
#
# dengan 3 feature:
# flow, occupancy, speed
#
FEATURE_NAMES = [
    "flow",
    "occupancy",
    "speed"
]

FEATURE_INDICES = {
    "flow": 0,
    "occupancy": 1,
    "speed": 2
}

# Jumlah timestep yang digunakan sebagai input LSTM.
SEQUENCE_LENGTH = 15

# Prediksi 1 timestep ke depan.
FORECAST_HORIZON = 1

# Temporal split.
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


# ============================================================
# HELPER
# ============================================================

def print_header(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# LOAD DATA
# ============================================================

def load_dataset():

    print_header("PEMS04 DATA LOADING")

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n{DATA_PATH}"
        )

    print(
        f"[INFO] Dataset:\n"
        f"       {DATA_PATH}"
    )

    data = np.load(
        DATA_PATH
    )

    print(
        f"[INFO] NPZ contents:\n"
        f"       {data.files}"
    )

    if "data" not in data.files:
        raise KeyError(
            "Array 'data' tidak ditemukan "
            "di dalam PEMS04.npz"
        )

    array = data["data"]

    print()
    print(
        f"[INFO] Raw shape : {array.shape}"
    )

    print(
        f"[INFO] Dtype     : {array.dtype}"
    )

    print(
        f"[INFO] Min       : {array.min()}"
    )

    print(
        f"[INFO] Max       : {array.max()}"
    )

    print(
        f"[INFO] Mean      : {array.mean()}"
    )

    return array


# ============================================================
# VALIDATE DATA
# ============================================================

def validate_dataset(data):

    print_header("DATA VALIDATION")

    if data.ndim != 3:
        raise ValueError(
            "Dataset harus memiliki 3 dimensi "
            "(time, sensor, feature)."
        )

    timesteps = data.shape[0]
    sensors = data.shape[1]
    features = data.shape[2]

    print(
        f"[INFO] Timesteps : {timesteps}"
    )

    print(
        f"[INFO] Sensors   : {sensors}"
    )

    print(
        f"[INFO] Features  : {features}"
    )

    if sensors < SENSOR_END:
        raise ValueError(
            f"Dataset hanya memiliki {sensors} sensor, "
            f"tetapi eksperimen membutuhkan "
            f"{SENSOR_END} sensor."
        )

    if features < len(FEATURE_NAMES):
        raise ValueError(
            "Jumlah feature tidak sesuai."
        )

    if not (
        0 < TRAIN_RATIO < 1
        and 0 < VAL_RATIO < 1
        and 0 < TEST_RATIO < 1
    ):
        raise ValueError(
            "Rasio split harus berada antara 0 dan 1."
        )

    total_ratio = (
        TRAIN_RATIO
        + VAL_RATIO
        + TEST_RATIO
    )

    if not np.isclose(
        total_ratio,
        1.0
    ):
        raise ValueError(
            f"Total ratio harus 1.0, "
            f"sekarang {total_ratio}"
        )

    print(
        "[OK] Dataset memiliki struktur "
        "(time, sensor, feature)."
    )

    print(
        "[OK] Jumlah sensor mencukupi."
    )

    print(
        "[OK] Konfigurasi split valid."
    )


# ============================================================
# SELECT SENSORS AND FEATURES
# ============================================================

def select_data(data):

    print_header(
        "SENSOR AND FEATURE SELECTION"
    )

    selected = data[
        :,
        SENSOR_START:SENSOR_END,
        :
    ]

    # Pilih feature sesuai konfigurasi.
    feature_indices = [
        FEATURE_INDICES[name]
        for name in FEATURE_NAMES
    ]

    selected = selected[
        :,
        :,
        feature_indices
    ]

    print(
        f"[INFO] Sensor range : "
        f"{SENSOR_START + 1}-{SENSOR_END}"
    )

    print(
        f"[INFO] Sensor count : "
        f"{SENSOR_END - SENSOR_START}"
    )

    print(
        "[INFO] Features:"
    )

    for index, name in enumerate(
        FEATURE_NAMES,
        start=1
    ):
        print(
            f"       {index}. {name}"
        )

    print(
        f"[INFO] Selected shape: "
        f"{selected.shape}"
    )

    return selected


# ============================================================
# TEMPORAL SPLIT
# ============================================================

def temporal_split(data):

    print_header(
        "TEMPORAL TRAIN / VALIDATION / TEST SPLIT"
    )

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

    print(
        f"[INFO] Train timesteps : "
        f"{len(train_data)}"
    )

    print(
        f"[INFO] Validation      : "
        f"{len(val_data)}"
    )

    print(
        f"[INFO] Test            : "
        f"{len(test_data)}"
    )

    print()
    print(
        "[OK] Split dilakukan berdasarkan "
        "urutan waktu."
    )

    return (
        train_data,
        val_data,
        test_data
    )


# ============================================================
# SCALING
# ============================================================

def fit_scalers(
    train_data,
    val_data,
    test_data
):

    print_header(
        "FEATURE SCALING"
    )

    """
    Data shape:
        (time, sensor, feature)

    StandardScaler membutuhkan bentuk:
        (sample, feature)

    Kita flatten:
        time × sensor
    """

    num_sensors = train_data.shape[1]
    num_features = train_data.shape[2]

    train_flat = train_data.reshape(
        -1,
        num_features
    )

    val_flat = val_data.reshape(
        -1,
        num_features
    )

    test_flat = test_data.reshape(
        -1,
        num_features
    )

    scaler_X = StandardScaler()

    # FIT HANYA PADA TRAIN
    scaler_X.fit(
        train_flat
    )

    train_scaled = scaler_X.transform(
        train_flat
    )

    val_scaled = scaler_X.transform(
        val_flat
    )

    test_scaled = scaler_X.transform(
        test_flat
    )

    train_scaled = train_scaled.reshape(
        train_data.shape
    )

    val_scaled = val_scaled.reshape(
        val_data.shape
    )

    test_scaled = test_scaled.reshape(
        test_data.shape
    )

    print(
        "[OK] StandardScaler fitted "
        "menggunakan TRAIN saja."
    )

    print(
        "[OK] Validation dan test "
        "hanya menggunakan transform."
    )

    return (
        train_scaled,
        val_scaled,
        test_scaled,
        scaler_X
    )


# ============================================================
# CREATE SEQUENCES
# ============================================================

def create_sequences(
    data,
    sequence_length,
    forecast_horizon
):

    """
    Input:
        data shape =
        (time, sensor, feature)

    Output:
        X shape =
        (samples, sequence, sensor, feature)

        y shape =
        (samples, sensor, feature)

    Contoh sequence_length = 15:

        X:
        t0 ... t14

        y:
        t15

    Kemudian:

        X:
        t1 ... t15

        y:
        t16

    dst.
    """

    X = []
    y = []

    total_timesteps = data.shape[0]

    max_start = (
        total_timesteps
        - sequence_length
        - forecast_horizon
        + 1
    )

    for start in range(
        max_start
    ):

        end = (
            start
            + sequence_length
        )

        target_index = (
            end
            + forecast_horizon
            - 1
        )

        X.append(
            data[
                start:end
            ]
        )

        y.append(
            data[
                target_index
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

    return X, y


# ============================================================
# CREATE ALL SEQUENCES
# ============================================================

def build_sequences(
    train_data,
    val_data,
    test_data
):

    print_header(
        "SEQUENCE GENERATION"
    )

    print(
        f"[INFO] Sequence length : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[INFO] Forecast horizon: "
        f"{FORECAST_HORIZON}"
    )

    X_train, y_train = create_sequences(
        train_data,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    X_val, y_val = create_sequences(
        val_data,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    X_test, y_test = create_sequences(
        test_data,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    print()
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

    if len(X_train) == 0:
        raise ValueError(
            "Sequence TRAIN kosong."
        )

    if len(X_val) == 0:
        raise ValueError(
            "Sequence VALIDATION kosong."
        )

    if len(X_test) == 0:
        raise ValueError(
            "Sequence TEST kosong."
        )

    print()
    print(
        "[OK] Sequence berhasil dibuat."
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
# SAVE
# ============================================================

def save_numpy(
    name,
    array
):

    path = OUTPUT_DIR / name

    np.save(
        path,
        array
    )

    print(
        f"[SAVED] {path}"
    )


def save_scaler(
    name,
    scaler
):

    path = OUTPUT_DIR / name

    with open(
        path,
        "wb"
    ) as file:

        pickle.dump(
            scaler,
            file
        )

    print(
        f"[SAVED] {path}"
    )


def save_config(
    data_shape,
    selected_shape
):

    config = {

        "dataset": "PEMS04",

        "input_file":
            str(DATA_PATH),

        "raw_shape":
            list(data_shape),

        "selected_shape":
            list(selected_shape),

        "sensor_start":
            SENSOR_START + 1,

        "sensor_end":
            SENSOR_END,

        "num_sensors":
            SENSOR_END - SENSOR_START,

        "features":
            FEATURE_NAMES,

        "feature_indices":
            FEATURE_INDICES,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "split": {

            "train":
                TRAIN_RATIO,

            "validation":
                VAL_RATIO,

            "test":
                TEST_RATIO
        },

        "scaler":
            "StandardScaler",

        "scaler_fit_on":
            "training_data_only"
    }

    path = (
        OUTPUT_DIR
        / "pems04_config.json"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            config,
            file,
            indent=4
        )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "PEMS04 TRAFFIC DATA PREPROCESSING"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # 1. LOAD
    # --------------------------------------------------------

    raw_data = load_dataset()

    # --------------------------------------------------------
    # 2. VALIDATE
    # --------------------------------------------------------

    validate_dataset(
        raw_data
    )

    # --------------------------------------------------------
    # 3. SELECT SENSOR + FEATURE
    # --------------------------------------------------------

    selected_data = select_data(
        raw_data
    )

    # --------------------------------------------------------
    # 4. TEMPORAL SPLIT
    # --------------------------------------------------------

    (
        train_data,
        val_data,
        test_data
    ) = temporal_split(
        selected_data
    )

    # --------------------------------------------------------
    # 5. SCALE
    # --------------------------------------------------------

    (
        train_scaled,
        val_scaled,
        test_scaled,
        scaler_X
    ) = fit_scalers(
        train_data,
        val_data,
        test_data
    )

    # --------------------------------------------------------
    # 6. CREATE SEQUENCES
    # --------------------------------------------------------

    (
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test
    ) = build_sequences(
        train_scaled,
        val_scaled,
        test_scaled
    )

    # --------------------------------------------------------
    # 7. SAVE ARRAYS
    # --------------------------------------------------------

    print_header(
        "SAVING PREPROCESSED DATA"
    )

    save_numpy(
        "X_train.npy",
        X_train
    )

    save_numpy(
        "y_train.npy",
        y_train
    )

    save_numpy(
        "X_val.npy",
        X_val
    )

    save_numpy(
        "y_val.npy",
        y_val
    )

    save_numpy(
        "X_test.npy",
        X_test
    )

    save_numpy(
        "y_test.npy",
        y_test
    )

    # --------------------------------------------------------
    # 8. SAVE SCALER
    # --------------------------------------------------------

    save_scaler(
        "scaler_X.pkl",
        scaler_X
    )

    # --------------------------------------------------------
    # 9. SAVE CONFIG
    # --------------------------------------------------------

    save_config(
        raw_data.shape,
        selected_data.shape
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print_header(
        "PREPROCESSING COMPLETED"
    )

    print(
        "[OK] Dataset       : PEMS04"
    )

    print(
        f"[OK] Sensors       : "
        f"{SENSOR_START + 1}-"
        f"{SENSOR_END}"
    )

    print(
        "[OK] Features      : "
        "Flow + Occupancy + Speed"
    )

    print(
        f"[OK] Sequence      : "
        f"{SEQUENCE_LENGTH} timestep"
    )

    print(
        f"[OK] Horizon       : "
        f"{FORECAST_HORIZON} timestep"
    )

    print(
        f"[OK] Train samples : "
        f"{len(X_train)}"
    )

    print(
        f"[OK] Val samples   : "
        f"{len(X_val)}"
    )

    print(
        f"[OK] Test samples  : "
        f"{len(X_test)}"
    )

    print()
    print(
        f"[OK] Output folder:"
    )

    print(
        f"    {OUTPUT_DIR}"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
