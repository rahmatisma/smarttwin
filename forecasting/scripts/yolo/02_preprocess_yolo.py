from pathlib import Path
import json
import pickle
import random

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler


# ============================================================
# ============================================================
# PREPROCESSING PIPELINE
# ============================================================
#
# Pipeline preprocessing dataset YOLO Traffic:
#
# 1. LOAD DATA
#    Membaca dataset CSV hasil agregasi/deteksi YOLO.
#
# 2. COLUMN VALIDATION
#    Memastikan seluruh kolom yang dibutuhkan tersedia.
#
# 3. BASIC DATA CLEANING
#    - Konversi timestamp
#    - Filter intersection
#    - Konversi fitur ke numeric
#    - Validasi nilai negatif
#    - Sorting data berdasarkan waktu dan sensor
#
# 4. DUPLICATE CHECK
#    Memastikan tidak ada dua record untuk sensor yang sama
#    pada timestamp yang sama.
#
# 5. TIMESTAMP NORMALIZATION
#    Membentuk timeline kontinu berdasarkan resolusi waktu.
#    Baseline menggunakan resolusi 1 detik.
#
# 6. SENSOR MATRIX CONSTRUCTION
#    Mengubah data long-format menjadi wide-format:
#
#        12 sensor × 8 fitur = 96 fitur/timestep
#
#    Sensor:
#        north/lane_1
#        north/lane_2
#        north/lane_3
#        east/lane_1
#        east/lane_2
#        east/lane_3
#        south/lane_1
#        south/lane_2
#        south/lane_3
#        west/lane_1
#        west/lane_2
#        west/lane_3
#
# 7. MISSING DATA ANALYSIS
#    Mengukur jumlah missing timestep secara global
#    dan per sensor.
#
# 8. CHRONOLOGICAL DATA SPLIT
#    Data dibagi berdasarkan urutan waktu:
#
#        TRAIN      = 70%
#        VALIDATION = 15%
#        TEST       = 15%
#
#    Tidak menggunakan random split agar tidak terjadi
#    temporal leakage.
#
# 9. CAUSAL MISSING VALUE IMPUTATION
#    Missing hanya diisi menggunakan data masa lalu.
#
#    Gap pendek:
#        forward fill <= 5 detik
#
#    Gap panjang:
#        tetap NaN
#
#    Tidak menggunakan:
#        - backward fill
#        - interpolasi
#        - future value
#
#    Tujuannya menjaga sifat forecasting agar tidak melihat
#    informasi masa depan.
#
# 10. VALID TIMESTEP FILTERING
#     Timestep yang masih mengandung NaN/Inf setelah
#     forward fill dianggap invalid.
#
#     Timestep invalid tidak digunakan untuk training.
#
# 11. FEATURE SCALING
#     StandardScaler digunakan agar skala antar fitur lebih
#     seimbang.
#
#     Scaler HANYA di-fit menggunakan TRAINING DATA.
#
#     Validation dan test hanya menggunakan scaler yang sama.
#
# 12. SEQUENCE CREATION
#     Membentuk input sequence untuk LSTM:
#
#         X = beberapa timestep sebelumnya
#         y = timestep berikutnya
#
#     Baseline:
#
#         sequence_length = 15 detik
#         forecast_horizon = 1 detik
#
# 13. TEMPORAL CONTINUITY CHECK
#     Sequence hanya dibuat jika timestamp benar-benar
#     kontinu sesuai resolusi waktu.
#
# 14. NUMERICAL VALIDATION
#     Memastikan X dan y tidak mengandung:
#
#         NaN
#         Inf
#
# 15. SAVE ARTIFACTS
#     Menyimpan:
#
#         X_train
#         y_train
#         X_val
#         y_val
#         X_test
#         y_test
#         scaler
#         timestamp
#         sensor configuration
#         feature metadata
#         preprocessing report
#
# ============================================================
# IMPORTANT
# ============================================================
#
# Tahap ini adalah BASELINE PREPROCESSING.
#
# Jangan melakukan tuning LSTM di file ini.
#
# Eksperimen berikutnya dilakukan terpisah:
#
#   Experiment 1:
#       sequence length
#
#   Experiment 2:
#       temporal resolution
#
#   Experiment 3:
#       model architecture
#
#   Experiment 4:
#       hyperparameter tuning
#
# ============================================================
# ============================================================


# ============================================================
# PATH
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
FORECASTING_DIR = SCRIPT_DIR.parent.parent

DATA_DIR = FORECASTING_DIR / "data"
OUTPUT_ROOT = FORECASTING_DIR / "outputs" / "yolo"
PROCESSED_DIR = OUTPUT_ROOT / "processed"


# ============================================================
# DATASET CONFIGURATION
# ============================================================

DATASET_NAME = "YOLO Traffic Dataset"

INPUT_CSV = DATA_DIR / "smarttwin_traffic_data.csv"

INTERSECTION_ID = "simpang4-pingit"


# ============================================================
# SENSOR CONFIGURATION
# ============================================================

APPROACHES = [
    "north",
    "east",
    "south",
    "west",
]

LANES = [
    "lane_1",
    "lane_2",
    "lane_3",
]


# ============================================================
# TRAFFIC FEATURES
# ============================================================
#
# Delapan fitur yang digunakan sebagai input dan target LSTM.
#
# vehicle_count
#     Total kendaraan pada lane.
#
# car_count
#     Jumlah mobil.
#
# motorcycle_count
#     Jumlah sepeda motor.
#
# bus_count
#     Jumlah bus.
#
# truck_count
#     Jumlah truk.
#
# queue_length_veh
#     Panjang antrean dalam jumlah kendaraan.
#
# queue_length_m_est
#     Estimasi panjang antrean dalam meter.
#
# density_index
#     Indeks kepadatan lalu lintas.
#
# ============================================================

FEATURE_NAMES = [
    "vehicle_count",
    "car_count",
    "motorcycle_count",
    "bus_count",
    "truck_count",
    "queue_length_veh",
    "queue_length_m_est",
    "density_index",
]


NUM_SENSORS = len(APPROACHES) * len(LANES)
NUM_FEATURES = len(FEATURE_NAMES)

INPUT_FEATURES_PER_TIMESTEP = (
    NUM_SENSORS * NUM_FEATURES
)


# ============================================================
# TEMPORAL CONFIGURATION
# ============================================================
#
# BASELINE:
#
# Resolusi data      : 1 detik
# Sequence length    : 15 timestep
# Forecast horizon   : 1 timestep
#
# Artinya:
#
# 15 detik data sebelumnya
#             ↓
#           LSTM
#             ↓
# prediksi 1 detik berikutnya
#
# ============================================================

TIME_RESOLUTION_SECONDS = 1

SEQUENCE_LENGTH = 15

FORECAST_HORIZON = 1


# ============================================================
# MISSING DATA CONFIGURATION
# ============================================================
#
# Missing value TIDAK langsung diganti dengan 0.
#
# Karena:
#
# missing != tidak ada kendaraan
#
# Contoh:
#
# timestamp:
# 10:01:01 -> 5 kendaraan
# 10:01:02 -> missing
# 10:01:03 -> missing
# 10:01:04 -> 6 kendaraan
#
# Untuk gap pendek <= 5 detik:
#
# 5 -> 5 -> 5 -> 6
#
# Untuk gap panjang:
#
# 5 -> NaN -> NaN -> ... -> 6
#
# Sequence yang mengandung NaN akan dibuang.
#
# ============================================================

MAX_FORWARD_FILL_SECONDS = 5


# ============================================================
# CHRONOLOGICAL SPLIT
# ============================================================

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


# ============================================================
# RANDOM SEED
# ============================================================

RANDOM_SEED = 42


# ============================================================
# HELPERS
# ============================================================

def set_seed():

    random.seed(RANDOM_SEED)

    np.random.seed(RANDOM_SEED)


def print_header(title):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def ensure_directories():

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


def save_json(path, data):

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
# LOAD DATA
# ============================================================

def load_dataset():

    print_header("DATA LOADING")

    print(
        f"[INFO] Dataset     : {DATASET_NAME}"
    )

    print(
        f"[INFO] Source CSV  : {INPUT_CSV}"
    )

    if not INPUT_CSV.exists():

        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n{INPUT_CSV}"
        )

    df = pd.read_csv(INPUT_CSV)

    print(
        f"[INFO] Rows        : {len(df):,}"
    )

    print(
        f"[INFO] Columns     : {len(df.columns)}"
    )

    print()
    print("[INFO] Columns:")

    for column in df.columns:

        print(
            f"       - {column}"
        )

    return df


# ============================================================
# COLUMN VALIDATION
# ============================================================

def validate_columns(df):

    print_header("COLUMN VALIDATION")

    required_columns = [
        "timestamp",
        "intersection_id",
        "approach",
        "lane_id",
        *FEATURE_NAMES,
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:

        raise ValueError(
            "Kolom berikut tidak ditemukan:\n"
            + "\n".join(
                f"- {column}"
                for column in missing
            )
        )

    print(
        "[OK] Semua kolom yang dibutuhkan tersedia."
    )


# ============================================================
# BASIC DATA CLEANING
# ============================================================

def basic_cleaning(df):

    print_header("BASIC DATA CLEANING")

    df = df.copy()

    # --------------------------------------------------------
    # Timestamp conversion
    # --------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    invalid_timestamp = (
        df["timestamp"]
        .isna()
        .sum()
    )

    print(
        f"[INFO] Invalid timestamp : "
        f"{invalid_timestamp:,}"
    )

    if invalid_timestamp > 0:

        df = df.dropna(
            subset=["timestamp"]
        )

    # --------------------------------------------------------
    # Filter intersection
    # --------------------------------------------------------

    df = df[
        df["intersection_id"]
        == INTERSECTION_ID
    ].copy()

    print(
        f"[INFO] Intersection rows : "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    for feature in FEATURE_NAMES:

        df[feature] = pd.to_numeric(
            df[feature],
            errors="coerce"
        )

    invalid_numeric = (
        df[FEATURE_NAMES]
        .isna()
        .sum()
        .sum()
    )

    print(
        f"[INFO] Invalid numeric values : "
        f"{invalid_numeric:,}"
    )

    if invalid_numeric > 0:

        raise ValueError(
            "Ditemukan nilai numerik invalid."
        )

    # --------------------------------------------------------
    # Negative values
    # --------------------------------------------------------

    negative_count = (
        df[FEATURE_NAMES]
        .lt(0)
        .sum()
        .sum()
    )

    print(
        f"[INFO] Negative feature values : "
        f"{negative_count:,}"
    )

    if negative_count > 0:

        raise ValueError(
            "Ditemukan nilai negatif "
            "pada traffic features."
        )

    # --------------------------------------------------------
    # Sort chronologically
    # --------------------------------------------------------

    df = df.sort_values(
        [
            "timestamp",
            "approach",
            "lane_id",
        ]
    ).reset_index(drop=True)

    print(
        "[OK] Basic cleaning completed."
    )

    return df


# ============================================================
# DUPLICATE SENSOR RECORD CHECK
# ============================================================

def check_duplicates(df):

    print_header(
        "DUPLICATE SENSOR RECORD CHECK"
    )

    key_columns = [
        "timestamp",
        "intersection_id",
        "approach",
        "lane_id",
    ]

    duplicates = df.duplicated(
        subset=key_columns,
        keep=False
    )

    duplicate_count = duplicates.sum()

    print(
        f"[INFO] Duplicate sensor records : "
        f"{duplicate_count:,}"
    )

    if duplicate_count > 0:

        duplicate_rows = df.loc[
            duplicates,
            key_columns
        ]

        print()
        print(
            duplicate_rows.head(20)
        )

        raise ValueError(
            "Ditemukan duplicate sensor record."
        )

    print(
        "[OK] Tidak ditemukan duplicate "
        "sensor record."
    )


# ============================================================
# DATASET INFORMATION
# ============================================================

def print_dataset_information(df):

    print_header(
        "DATASET INFORMATION"
    )

    print(
        f"[INFO] Timestamp count : "
        f"{df['timestamp'].nunique():,}"
    )

    print(
        f"[INFO] Start : "
        f"{df['timestamp'].min()}"
    )

    print(
        f"[INFO] End   : "
        f"{df['timestamp'].max()}"
    )

    duration = (
        df["timestamp"].max()
        - df["timestamp"].min()
    )

    print(
        f"[INFO] Duration : "
        f"{duration}"
    )

    print()
    print("[INFO] Approaches:")

    print(
        df["approach"]
        .value_counts()
        .sort_index()
    )

    print()
    print("[INFO] Lanes:")

    print(
        df["lane_id"]
        .value_counts()
        .sort_index()
    )


# ============================================================
# FEATURE STATISTICS
# ============================================================

def print_feature_statistics(df):

    print_header(
        "FEATURE STATISTICS"
    )

    for feature in FEATURE_NAMES:

        values = df[feature]

        print()
        print(
            f"[INFO] {feature}"
        )

        print(
            f"       Min  : "
            f"{values.min():.6f}"
        )

        print(
            f"       Max  : "
            f"{values.max():.6f}"
        )

        print(
            f"       Mean : "
            f"{values.mean():.6f}"
        )

        zero_percentage = (
            (values == 0).mean()
            * 100
        )

        print(
            f"       Zero : "
            f"{zero_percentage:.2f}%"
        )


# ============================================================
# TIMESTAMP ANALYSIS
# ============================================================

def analyze_timestamps(df):

    print_header(
        "TIMESTAMP ANALYSIS"
    )

    timestamps = (
        df["timestamp"]
        .drop_duplicates()
        .sort_values()
    )

    start = timestamps.min()
    end = timestamps.max()

    expected_index = pd.date_range(
        start=start,
        end=end,
        freq=f"{TIME_RESOLUTION_SECONDS}s"
    )

    actual_index = pd.DatetimeIndex(
        timestamps
    )

    missing_timestamps = (
        expected_index
        .difference(actual_index)
    )

    print(
        f"[INFO] Original timestamps : "
        f"{len(actual_index):,}"
    )

    print(
        f"[INFO] Expected timestamps : "
        f"{len(expected_index):,}"
    )

    print(
        f"[INFO] Missing timestamp slots : "
        f"{len(missing_timestamps):,}"
    )

    if len(missing_timestamps) > 0:

        print()
        print(
            "[INFO] Contoh missing timestamp:"
        )

        for timestamp in missing_timestamps[:20]:

            print(
                f"       {timestamp}"
            )

    # --------------------------------------------------------
    # Gap distribution
    # --------------------------------------------------------

    differences = (
        actual_index
        .to_series()
        .diff()
        .dropna()
    )

    print()
    print(
        "[INFO] Timestamp gap distribution:"
    )

    print(
        differences
        .value_counts()
        .head(15)
    )

    return expected_index


# ============================================================
# BUILD SENSOR MATRIX
# ============================================================

def build_raw_matrix(
    df,
    expected_index
):

    print_header(
        "BUILDING RAW TIMESTEP MATRIX"
    )

    indexed = df.set_index(
        [
            "timestamp",
            "approach",
            "lane_id",
        ]
    )

    wide = indexed[
        FEATURE_NAMES
    ].unstack(
        [
            "approach",
            "lane_id",
        ]
    )

    # --------------------------------------------------------
    # Force deterministic sensor/feature ordering.
    #
    # Setiap timestep selalu memiliki struktur:
    #
    # north lane_1 -> 8 feature
    # north lane_2 -> 8 feature
    # north lane_3 -> 8 feature
    # east  lane_1 -> 8 feature
    # ...
    #
    # Total:
    #
    # 12 sensor × 8 feature = 96 feature
    # --------------------------------------------------------

    desired_columns = []

    for approach in APPROACHES:

        for lane in LANES:

            for feature in FEATURE_NAMES:

                desired_columns.append(
                    (
                        feature,
                        approach,
                        lane,
                    )
                )

    desired_index = pd.MultiIndex.from_tuples(
        desired_columns,
        names=[
            "feature",
            "approach",
            "lane_id",
        ]
    )

    wide = wide.reindex(
        columns=desired_index
    )

    # --------------------------------------------------------
    # Reindex complete timeline.
    # --------------------------------------------------------

    wide = wide.reindex(
        expected_index
    )

    wide.index.name = "timestamp"

    print(
        f"[INFO] Matrix shape : "
        f"{wide.shape}"
    )

    expected_features = (
        NUM_SENSORS
        * NUM_FEATURES
    )

    if wide.shape[1] != expected_features:

        raise ValueError(
            "Jumlah feature tidak sesuai.\n"
            f"Expected : {expected_features}\n"
            f"Actual   : {wide.shape[1]}"
        )

    raw_path = (
        PROCESSED_DIR
        / "timestep_matrix_raw.csv"
    )

    wide.to_csv(
        raw_path
    )

    print(
        f"[SAVED] {raw_path}"
    )

    return wide


# ============================================================
# MISSING SENSOR ANALYSIS
# ============================================================

def analyze_missing_sensors(wide):

    print_header(
        "MISSING SENSOR ANALYSIS"
    )

    total_cells = (
        wide.shape[0]
        * wide.shape[1]
    )

    missing_cells = (
        wide.isna()
        .sum()
        .sum()
    )

    print(
        f"[INFO] Total matrix cells : "
        f"{total_cells:,}"
    )

    print(
        f"[INFO] Missing cells      : "
        f"{missing_cells:,}"
    )

    print(
        f"[INFO] Missing percentage : "
        f"{missing_cells / total_cells * 100:.2f}%"
    )

    print()
    print(
        "[INFO] Missing per sensor:"
    )

    sensor_report = []

    for approach in APPROACHES:

        for lane in LANES:

            sensor_columns = [
                (
                    feature,
                    approach,
                    lane,
                )
                for feature in FEATURE_NAMES
            ]

            sensor_data = wide[
                sensor_columns
            ]

            # Sensor dianggap missing pada timestep
            # jika seluruh feature sensor tersebut NaN.

            missing = (
                sensor_data
                .isna()
                .all(axis=1)
                .sum()
            )

            total = len(sensor_data)

            percentage = (
                missing / total * 100
            )

            print(
                f"       {approach:5s} / "
                f"{lane:6s} : "
                f"{missing:4d} missing "
                f"({percentage:6.2f}%)"
            )

            sensor_report.append(
                {
                    "approach": approach,
                    "lane_id": lane,
                    "missing_timesteps": int(
                        missing
                    ),
                    "missing_percentage": float(
                        percentage
                    ),
                }
            )

    return sensor_report


# ============================================================
# CHRONOLOGICAL SPLIT
# ============================================================

def split_timeline(wide):

    print_header(
        "CHRONOLOGICAL TIMELINE SPLIT"
    )

    total = len(wide)

    train_end = int(
        total * TRAIN_RATIO
    )

    val_end = (
        train_end
        + int(total * VAL_RATIO)
    )

    train = wide.iloc[
        :train_end
    ].copy()

    val = wide.iloc[
        train_end:val_end
    ].copy()

    test = wide.iloc[
        val_end:
    ].copy()

    print(
        f"[INFO] Total timesteps : "
        f"{total:,}"
    )

    print()
    print("[TRAIN]")

    print(
        f"       Timesteps : "
        f"{len(train):,}"
    )

    print(
        f"       Start    : "
        f"{train.index.min()}"
    )

    print(
        f"       End      : "
        f"{train.index.max()}"
    )

    print()
    print("[VALIDATION]")

    print(
        f"       Timesteps : "
        f"{len(val):,}"
    )

    print(
        f"       Start    : "
        f"{val.index.min()}"
    )

    print(
        f"       End      : "
        f"{val.index.max()}"
    )

    print()
    print("[TEST]")

    print(
        f"       Timesteps : "
        f"{len(test):,}"
    )

    print(
        f"       Start    : "
        f"{test.index.min()}"
    )

    print(
        f"       End      : "
        f"{test.index.max()}"
    )

    return train, val, test


# ============================================================
# CAUSAL MISSING VALUE HANDLING
# ============================================================

def causal_fill_split(
    split_df,
    max_fill_seconds
):

    """
    Forward-fill hanya menggunakan nilai masa lalu.

    Tidak menggunakan:
        - backward fill
        - interpolation
        - future value

    Gap <= max_fill_seconds:
        di-forward-fill.

    Gap > max_fill_seconds:
        tetap NaN.

    Penting:
    Forward fill dilakukan per kolom sensor-feature.
    """

    filled = split_df.copy()

    filled = filled.ffill(
        limit=max_fill_seconds
    )

    return filled


def impute_splits(
    train,
    val,
    test
):

    print_header(
        "CAUSAL MISSING VALUE HANDLING"
    )

    print(
        "[INFO] Strategy:"
    )

    print(
        f"       Forward fill <= "
        f"{MAX_FORWARD_FILL_SECONDS} seconds"
    )

    print(
        "       Gap lebih panjang "
        "tetap NaN."
    )

    print(
        "       Sequence yang melewati "
        "gap panjang akan dibuang."
    )

    train_filled = causal_fill_split(
        train,
        MAX_FORWARD_FILL_SECONDS
    )

    val_filled = causal_fill_split(
        val,
        MAX_FORWARD_FILL_SECONDS
    )

    test_filled = causal_fill_split(
        test,
        MAX_FORWARD_FILL_SECONDS
    )

    print()

    print(
        f"[INFO] TRAIN unresolved NaN : "
        f"{train_filled.isna().sum().sum():,}"
    )

    print(
        f"[INFO] VAL unresolved NaN   : "
        f"{val_filled.isna().sum().sum():,}"
    )

    print(
        f"[INFO] TEST unresolved NaN  : "
        f"{test_filled.isna().sum().sum():,}"
    )

    return (
        train_filled,
        val_filled,
        test_filled,
    )


# ============================================================
# MATRIX TO NUMPY
# ============================================================

def matrix_to_numpy(df):

    return df.to_numpy(
        dtype=np.float32
    )


# ============================================================
# VALID TIMESTEP CHECK
# ============================================================

def get_valid_rows(matrix):

    return np.isfinite(
        matrix
    ).all(axis=1)


# ============================================================
# SCALER
# ============================================================

def fit_scaler(
    train_matrix
):

    print_header(
        "SCALER"
    )

    scaler = StandardScaler()

    print(
        "[INFO] Fitting scaler "
        "menggunakan TRAINING DATA saja."
    )

    scaler.fit(
        train_matrix
    )

    print(
        "[OK] Scaler fitted."
    )

    return scaler


def transform_matrix(
    matrix,
    scaler
):

    return scaler.transform(
        matrix
    ).astype(
        np.float32
    )


# ============================================================
# SEQUENCE CREATION
# ============================================================

def create_sequences(
    matrix,
    timestamps,
    sequence_length,
    forecast_horizon
):

    print_header(
        "SEQUENCE CREATION"
    )

    X = []
    y = []

    X_timestamps = []
    y_timestamps = []

    total = len(matrix)

    # --------------------------------------------------------
    # Contoh baseline:
    #
    # sequence_length = 15
    # forecast_horizon = 1
    #
    # t1 ... t15 -> prediksi t16
    #
    # --------------------------------------------------------

    for end_idx in range(
        sequence_length,
        total - forecast_horizon + 1
    ):

        start_idx = (
            end_idx
            - sequence_length
        )

        target_idx = (
            end_idx
            + forecast_horizon
            - 1
        )

        # ----------------------------------------------------
        # TIMESTAMP CONTINUITY
        # ----------------------------------------------------

        expected_seconds = (
            (
                sequence_length
                + forecast_horizon
                - 1
            )
            * TIME_RESOLUTION_SECONDS
        )

        actual_seconds = (
            timestamps[target_idx]
            - timestamps[start_idx]
        ).total_seconds()

        if actual_seconds != expected_seconds:

            continue

        # ----------------------------------------------------
        # INPUT WINDOW
        # ----------------------------------------------------

        input_window = matrix[
            start_idx:end_idx
        ]

        # ----------------------------------------------------
        # TARGET
        # ----------------------------------------------------

        target = matrix[
            target_idx
        ]

        # ----------------------------------------------------
        # NUMERICAL VALIDATION
        # ----------------------------------------------------

        if not np.isfinite(
            input_window
        ).all():

            continue

        if not np.isfinite(
            target
        ).all():

            continue

        X.append(
            input_window
        )

        y.append(
            target
        )

        X_timestamps.append(
            timestamps[start_idx]
        )

        y_timestamps.append(
            timestamps[target_idx]
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
        f"[INFO] X shape : "
        f"{X.shape}"
    )

    print(
        f"[INFO] y shape : "
        f"{y.shape}"
    )

    print(
        f"[INFO] Valid sequences : "
        f"{len(X):,}"
    )

    return (
        X,
        y,
        np.asarray(
            X_timestamps,
            dtype="datetime64[ns]"
        ),
        np.asarray(
            y_timestamps,
            dtype="datetime64[ns]"
        ),
    )


# ============================================================
# SEQUENCE VALIDATION
# ============================================================

def validate_sequences(
    name,
    X,
    y
):

    print()
    print(
        f"[VALIDATION] {name}"
    )

    nan_X = np.isnan(X).sum()
    nan_y = np.isnan(y).sum()

    inf_X = np.isinf(X).sum()
    inf_y = np.isinf(y).sum()

    print(
        f"       NaN X : {nan_X:,}"
    )

    print(
        f"       NaN y : {nan_y:,}"
    )

    print(
        f"       Inf X : {inf_X:,}"
    )

    print(
        f"       Inf y : {inf_y:,}"
    )

    if (
        nan_X > 0
        or nan_y > 0
        or inf_X > 0
        or inf_y > 0
    ):

        raise ValueError(
            f"{name} masih mengandung "
            "NaN atau Inf."
        )

    print(
        "       [OK] Numerical validation passed."
    )


# ============================================================
# SAVE SENSOR CONFIG
# ============================================================

def save_sensor_config():

    path = (
        PROCESSED_DIR
        / "sensor_config.json"
    )

    sensors = []

    sensor_id = 1

    for approach in APPROACHES:

        for lane in LANES:

            sensors.append(
                {
                    "sensor_id": sensor_id,
                    "approach": approach,
                    "lane_id": lane,
                }
            )

            sensor_id += 1

    config = {

        "dataset":
            DATASET_NAME,

        "intersection_id":
            INTERSECTION_ID,

        "num_sensors":
            NUM_SENSORS,

        "approaches":
            APPROACHES,

        "lanes":
            LANES,

        "sensors":
            sensors,

        "features":
            FEATURE_NAMES,

        "num_features":
            NUM_FEATURES,

        "features_per_timestep":
            INPUT_FEATURES_PER_TIMESTEP,

        "sensor_order":
            [
                f"{approach}/{lane}"
                for approach in APPROACHES
                for lane in LANES
            ],
    }

    save_json(
        path,
        config
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE FEATURE METADATA
# ============================================================

def save_feature_metadata():

    path = (
        PROCESSED_DIR
        / "feature_metadata.json"
    )

    metadata = []

    index = 0

    for approach in APPROACHES:

        for lane in LANES:

            sensor_id = (
                APPROACHES.index(approach)
                * len(LANES)
                + LANES.index(lane)
                + 1
            )

            for feature in FEATURE_NAMES:

                metadata.append(
                    {
                        "index":
                            index,

                        "sensor_id":
                            sensor_id,

                        "approach":
                            approach,

                        "lane_id":
                            lane,

                        "feature":
                            feature,
                    }
                )

                index += 1

    save_json(
        path,
        {
            "feature_count":
                len(metadata),

            "features":
                metadata,
        }
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE PREPROCESS CONFIG
# ============================================================

def save_preprocess_config():

    path = (
        PROCESSED_DIR
        / "yolo_config.json"
    )

    config = {

        "dataset":
            DATASET_NAME,

        "intersection_id":
            INTERSECTION_ID,

        "timestamp_resolution_seconds":
            TIME_RESOLUTION_SECONDS,

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "split":
            {
                "train":
                    TRAIN_RATIO,

                "validation":
                    VAL_RATIO,

                "test":
                    TEST_RATIO,
            },

        "sensors":
            {
                "count":
                    NUM_SENSORS,

                "approaches":
                    APPROACHES,

                "lanes":
                    LANES,
            },

        "features":
            {
                "names":
                    FEATURE_NAMES,

                "count":
                    NUM_FEATURES,

                "per_timestep":
                    INPUT_FEATURES_PER_TIMESTEP,
            },

        "model_input":
            {
                "sequence_length":
                    SEQUENCE_LENGTH,

                "input_size":
                    INPUT_FEATURES_PER_TIMESTEP,

                "output_size":
                    INPUT_FEATURES_PER_TIMESTEP,
            },

        "missing_data":
            {
                "strategy":
                    "causal_forward_fill",

                "max_forward_fill_seconds":
                    MAX_FORWARD_FILL_SECONDS,

                "unresolved_gap_strategy":
                    "drop_sequence",
            },

        "scaler":
            {
                "type":
                    "StandardScaler",

                "fit":
                    "training_data_only",
            },

        "random_seed":
            RANDOM_SEED,
    }

    save_json(
        path,
        config
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE SCALER
# ============================================================

def save_scaler(scaler):

    path = (
        PROCESSED_DIR
        / "scaler_X.pkl"
    )

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


# ============================================================
# SAVE ARRAY
# ============================================================

def save_array(
    name,
    array
):

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
# SAVE TIMESTAMPS
# ============================================================

def save_timestamps(
    timestamps
):

    path = (
        PROCESSED_DIR
        / "timestamps.npy"
    )

    np.save(
        path,
        np.asarray(
            timestamps,
            dtype="datetime64[ns]"
        )
    )

    print(
        f"[SAVED] {path}"
    )


def save_sequence_timestamps(
    name,
    timestamps
):

    path = (
        PROCESSED_DIR
        / f"{name}.npy"
    )

    np.save(
        path,
        timestamps
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE PREPROCESS REPORT
# ============================================================

def save_preprocess_report(
    df,
    raw_matrix,
    train_filled,
    val_filled,
    test_filled,
    X_train,
    X_val,
    X_test,
):

    path = (
        PROCESSED_DIR
        / "preprocessing_report.json"
    )

    report = {

        "dataset":
            DATASET_NAME,

        "source_csv":
            str(INPUT_CSV),

        "intersection_id":
            INTERSECTION_ID,

        "raw":
            {
                "rows":
                    int(len(df)),

                "columns":
                    int(len(df.columns)),

                "timestamp_count":
                    int(
                        df.timestamp.nunique()
                    ),

                "start":
                    str(
                        df.timestamp.min()
                    ),

                "end":
                    str(
                        df.timestamp.max()
                    ),

                "duration_seconds":
                    int(
                        (
                            df.timestamp.max()
                            - df.timestamp.min()
                        ).total_seconds()
                    ),
            },

        "matrix":
            {
                "rows":
                    int(raw_matrix.shape[0]),

                "features":
                    int(raw_matrix.shape[1]),
            },

        "missing":
            {
                "raw_missing_cells":
                    int(
                        raw_matrix
                        .isna()
                        .sum()
                        .sum()
                    ),

                "train_unresolved_nan":
                    int(
                        train_filled
                        .isna()
                        .sum()
                        .sum()
                    ),

                "val_unresolved_nan":
                    int(
                        val_filled
                        .isna()
                        .sum()
                        .sum()
                    ),

                "test_unresolved_nan":
                    int(
                        test_filled
                        .isna()
                        .sum()
                        .sum()
                    ),
            },

        "sequences":
            {
                "train":
                    int(len(X_train)),

                "validation":
                    int(len(X_val)),

                "test":
                    int(len(X_test)),
            },

        "configuration":
            {
                "resolution_seconds":
                    TIME_RESOLUTION_SECONDS,

                "sequence_length":
                    SEQUENCE_LENGTH,

                "forecast_horizon":
                    FORECAST_HORIZON,

                "max_forward_fill_seconds":
                    MAX_FORWARD_FILL_SECONDS,
            },
    }

    save_json(
        path,
        report
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "YOLO TRAFFIC DATA PREPROCESSING V3"
    )
    print("=" * 70)

    print(
        f"[INFO] Dataset           : "
        f"{DATASET_NAME}"
    )

    print(
        f"[INFO] Source CSV        : "
        f"{INPUT_CSV}"
    )

    print(
        f"[INFO] Intersection      : "
        f"{INTERSECTION_ID}"
    )

    print(
        f"[INFO] Timestamp         : "
        f"{TIME_RESOLUTION_SECONDS} second"
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
        f"[INFO] Sensors           : "
        f"{NUM_SENSORS}"
    )

    print(
        f"[INFO] Features/sensor   : "
        f"{NUM_FEATURES}"
    )

    print(
        f"[INFO] Features/timestep : "
        f"{INPUT_FEATURES_PER_TIMESTEP}"
    )

    print(
        f"[INFO] Missing strategy  : "
        f"forward fill <= "
        f"{MAX_FORWARD_FILL_SECONDS}s"
    )

    print("=" * 70)

    set_seed()

    ensure_directories()

    # ========================================================
    # 1. LOAD DATA
    # ========================================================

    df = load_dataset()

    # ========================================================
    # 2. COLUMN VALIDATION
    # ========================================================

    validate_columns(df)

    # ========================================================
    # 3. BASIC CLEANING
    # ========================================================

    df = basic_cleaning(df)

    # ========================================================
    # 4. DUPLICATE CHECK
    # ========================================================

    check_duplicates(df)

    # ========================================================
    # 5. DATASET INFORMATION
    # ========================================================

    print_dataset_information(df)

    # ========================================================
    # 6. FEATURE STATISTICS
    # ========================================================

    print_feature_statistics(df)

    # ========================================================
    # 7. TIMESTAMP ANALYSIS
    # ========================================================

    expected_index = analyze_timestamps(
        df
    )

    # ========================================================
    # 8. BUILD SENSOR MATRIX
    # ========================================================

    raw_matrix = build_raw_matrix(
        df,
        expected_index
    )

    # ========================================================
    # 9. MISSING DATA ANALYSIS
    # ========================================================

    sensor_report = (
        analyze_missing_sensors(
            raw_matrix
        )
    )

    # ========================================================
    # 10. CHRONOLOGICAL SPLIT
    # ========================================================

    (
        train_raw,
        val_raw,
        test_raw,
    ) = split_timeline(
        raw_matrix
    )

    # ========================================================
    # 11. CAUSAL MISSING DATA HANDLING
    # ========================================================

    (
        train_filled,
        val_filled,
        test_filled,
    ) = impute_splits(
        train_raw,
        val_raw,
        test_raw
    )

    # ========================================================
    # 12. CONVERT TO NUMPY
    # ========================================================

    train_matrix_raw = (
        matrix_to_numpy(
            train_filled
        )
    )

    val_matrix_raw = (
        matrix_to_numpy(
            val_filled
        )
    )

    test_matrix_raw = (
        matrix_to_numpy(
            test_filled
        )
    )

    # ========================================================
    # 13. VALID TIMESTEP FILTERING
    # ========================================================

    train_valid_rows = (
        get_valid_rows(
            train_matrix_raw
        )
    )

    val_valid_rows = (
        get_valid_rows(
            val_matrix_raw
        )
    )

    test_valid_rows = (
        get_valid_rows(
            test_matrix_raw
        )
    )

    print_header(
        "VALID TIMESTEP CHECK"
    )

    print(
        f"[INFO] Train valid rows : "
        f"{train_valid_rows.sum():,} / "
        f"{len(train_valid_rows):,}"
    )

    print(
        f"[INFO] Val valid rows   : "
        f"{val_valid_rows.sum():,} / "
        f"{len(val_valid_rows):,}"
    )

    print(
        f"[INFO] Test valid rows  : "
        f"{test_valid_rows.sum():,} / "
        f"{len(test_valid_rows):,}"
    )

    # ========================================================
    # 14. FIT SCALER USING TRAINING DATA ONLY
    # ========================================================

    scaler_input = (
        train_matrix_raw[
            train_valid_rows
        ]
    )

    if len(scaler_input) == 0:

        raise ValueError(
            "Tidak ada training timestep "
            "yang valid."
        )

    scaler = fit_scaler(
        scaler_input
    )

    # ========================================================
    # 15. SCALE DATA
    # ========================================================

    print_header(
        "SCALING"
    )

    train_scaled = np.full_like(
        train_matrix_raw,
        np.nan,
        dtype=np.float32
    )

    val_scaled = np.full_like(
        val_matrix_raw,
        np.nan,
        dtype=np.float32
    )

    test_scaled = np.full_like(
        test_matrix_raw,
        np.nan,
        dtype=np.float32
    )

    train_scaled[
        train_valid_rows
    ] = transform_matrix(
        train_matrix_raw[
            train_valid_rows
        ],
        scaler
    )

    val_scaled[
        val_valid_rows
    ] = transform_matrix(
        val_matrix_raw[
            val_valid_rows
        ],
        scaler
    )

    test_scaled[
        test_valid_rows
    ] = transform_matrix(
        test_matrix_raw[
            test_valid_rows
        ],
        scaler
    )

    print(
        "[OK] Scaling completed."
    )

    # ========================================================
    # 16. CREATE TRAINING SEQUENCES
    # ========================================================

    (
        X_train,
        y_train,
        X_train_ts,
        y_train_ts,
    ) = create_sequences(
        train_scaled,
        train_filled.index,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    # ========================================================
    # 17. CREATE VALIDATION SEQUENCES
    # ========================================================

    (
        X_val,
        y_val,
        X_val_ts,
        y_val_ts,
    ) = create_sequences(
        val_scaled,
        val_filled.index,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    # ========================================================
    # 18. CREATE TEST SEQUENCES
    # ========================================================

    (
        X_test,
        y_test,
        X_test_ts,
        y_test_ts,
    ) = create_sequences(
        test_scaled,
        test_filled.index,
        SEQUENCE_LENGTH,
        FORECAST_HORIZON
    )

    # ========================================================
    # 19. VALIDATE SEQUENCES
    # ========================================================

    print_header(
        "SEQUENCE VALIDATION"
    )

    validate_sequences(
        "TRAIN",
        X_train,
        y_train
    )

    validate_sequences(
        "VALIDATION",
        X_val,
        y_val
    )

    validate_sequences(
        "TEST",
        X_test,
        y_test
    )

    # ========================================================
    # 20. SAVE PROCESSED ARRAYS
    # ========================================================

    print_header(
        "SAVING PROCESSED DATA"
    )

    save_array(
        "X_train",
        X_train
    )

    save_array(
        "y_train",
        y_train
    )

    save_array(
        "X_val",
        X_val
    )

    save_array(
        "y_val",
        y_val
    )

    save_array(
        "X_test",
        X_test
    )

    save_array(
        "y_test",
        y_test
    )

    # ========================================================
    # 21. SAVE SCALER
    # ========================================================

    save_scaler(
        scaler
    )

    # ========================================================
    # 22. SAVE TIMESTAMPS
    # ========================================================

    save_timestamps(
        expected_index
    )

    save_sequence_timestamps(
        "train_input_timestamps",
        X_train_ts
    )

    save_sequence_timestamps(
        "train_target_timestamps",
        y_train_ts
    )

    save_sequence_timestamps(
        "val_input_timestamps",
        X_val_ts
    )

    save_sequence_timestamps(
        "val_target_timestamps",
        y_val_ts
    )

    save_sequence_timestamps(
        "test_input_timestamps",
        X_test_ts
    )

    save_sequence_timestamps(
        "test_target_timestamps",
        y_test_ts
    )

    # ========================================================
    # 23. SAVE CLEAN MATRIX
    # ========================================================

    clean_matrix_path = (
        PROCESSED_DIR
        / "timestep_matrix_clean.csv"
    )

    clean_columns = []

    for approach in APPROACHES:

        for lane in LANES:

            for feature in FEATURE_NAMES:

                clean_columns.append(
                    f"{approach}_{lane}_{feature}"
                )

    clean_matrix = pd.concat(
        [
            train_filled,
            val_filled,
            test_filled,
        ]
    )

    clean_matrix.columns = (
        clean_columns
    )

    clean_matrix.to_csv(
        clean_matrix_path,
        index_label="timestamp"
    )

    print(
        f"[SAVED] {clean_matrix_path}"
    )

    # ========================================================
    # 24. SAVE MISSING SENSOR REPORT
    # ========================================================

    save_json(
        PROCESSED_DIR
        / "missing_sensor_report.json",
        {
            "max_forward_fill_seconds":
                MAX_FORWARD_FILL_SECONDS,

            "sensors":
                sensor_report,
        }
    )

    print(
        "[SAVED] "
        f"{PROCESSED_DIR / 'missing_sensor_report.json'}"
    )

    # ========================================================
    # 25. SAVE SENSOR CONFIGURATION
    # ========================================================

    save_sensor_config()

    # ========================================================
    # 26. SAVE FEATURE METADATA
    # ========================================================

    save_feature_metadata()

    # ========================================================
    # 27. SAVE PREPROCESSING CONFIG
    # ========================================================

    save_preprocess_config()

    # ========================================================
    # 28. SAVE PREPROCESSING REPORT
    # ========================================================

    save_preprocess_report(
        df,
        raw_matrix,
        train_filled,
        val_filled,
        test_filled,
        X_train,
        X_val,
        X_test,
    )

    # ========================================================
    # 29. SUMMARY
    # ========================================================

    print_header(
        "PREPROCESSING SUMMARY"
    )

    print()

    print("[DATA]")

    print(
        f"Dataset             : "
        f"{DATASET_NAME}"
    )

    print(
        f"Intersection        : "
        f"{INTERSECTION_ID}"
    )

    print(
        f"Timestamp resolution: "
        f"{TIME_RESOLUTION_SECONDS} second"
    )

    print(
        f"Total timesteps     : "
        f"{len(expected_index):,}"
    )

    print(
        f"Sensors             : "
        f"{NUM_SENSORS}"
    )

    print(
        f"Features/sensor     : "
        f"{NUM_FEATURES}"
    )

    print(
        f"Features/timestep   : "
        f"{INPUT_FEATURES_PER_TIMESTEP}"
    )

    print()

    print("[MISSING DATA]")

    print(
        f"Forward fill limit  : "
        f"{MAX_FORWARD_FILL_SECONDS} sec"
    )

    print(
        "Long unresolved gaps: "
        "sequence dibuang"
    )

    print()

    print("[SEQUENCE]")

    print(
        f"Sequence length     : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"Forecast horizon    : "
        f"{FORECAST_HORIZON}"
    )

    print()

    print("[OUTPUT SHAPES]")

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

    print()

    print("[MODEL INTERFACE]")

    print(
        f"LSTM input_size  : "
        f"{INPUT_FEATURES_PER_TIMESTEP}"
    )

    print(
        f"LSTM output_size : "
        f"{INPUT_FEATURES_PER_TIMESTEP}"
    )

    print()

    print("[OUTPUT DIRECTORY]")

    print(
        f"{PROCESSED_DIR}"
    )

    print()

    print("=" * 70)

    print(
        "YOLO PREPROCESSING V3 COMPLETED"
    )

    print("=" * 70)

    print()

    print(
        "[OK] Data cleaning completed."
    )

    print(
        "[OK] Timestamp continuity checked."
    )

    print(
        "[OK] 12 lane sensors preserved."
    )

    print(
        "[OK] 8 traffic features preserved."
    )

    print(
        "[OK] Missing values handled causally."
    )

    print(
        "[OK] Long missing gaps are not fabricated."
    )

    print(
        "[OK] StandardScaler fitted on training data only."
    )

    print(
        "[OK] Temporal sequence continuity validated."
    )

    print(
        "[OK] NaN/Inf sequence validation passed."
    )

    print()

    print("[NEXT]")

    print(
        "Jangan langsung melakukan hyperparameter tuning."
    )

    print(
        "Tahap eksperimen berikutnya:"
    )

    print(
        "1. Eksperimen sequence length"
    )

    print(
        "2. Eksperimen temporal resolution"
    )

    print(
        "3. Training baseline"
    )

    print(
        "4. Evaluasi per-feature"
    )

    print(
        "5. Hyperparameter tuning"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()