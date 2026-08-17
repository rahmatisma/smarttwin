import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_PATH = (
    BASE_DIR
    / "data"
    / "smarttwin_traffic_data_copy.csv"
)

OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "yolo"
)

PROCESSED_DIR = (
    OUTPUT_DIR
    / "processed"
)

PROCESSED_DIR.mkdir(
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
# FEATURES
# ============================================================

# IMPORTANT:
# Semua fitur lalu lintas numerik dari dataset YOLO digunakan.
#
# Jangan dikurangi menjadi hanya 3 fitur seperti PEMS04.
#
# Total:
#
# 8 features
# ×
# 12 lane sensors
# =
# 96 input features per timestep
#
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


NUM_FEATURES = len(
    FEATURE_NAMES
)

NUM_SENSORS = (
    len(APPROACHES)
    * len(LANES)
)

INPUT_FEATURES_PER_TIMESTEP = (
    NUM_SENSORS
    * NUM_FEATURES
)


# ============================================================
# SENSOR ORDER
# ============================================================

# Urutan sensor dibuat tetap.
#
# north/lane_1
# north/lane_2
# north/lane_3
# east/lane_1
# east/lane_2
# east/lane_3
# south/lane_1
# south/lane_2
# south/lane_3
# west/lane_1
# west/lane_2
# west/lane_3

SENSOR_COLUMNS = []

for approach in APPROACHES:

    for lane in LANES:

        SENSOR_COLUMNS.append(
            (
                approach,
                lane
            )
        )


# ============================================================
# RANDOM SEED
# ============================================================

RANDOM_SEED = 42

np.random.seed(
    RANDOM_SEED
)


# ============================================================
# PRINT CONFIGURATION
# ============================================================

def print_configuration():

    print("=" * 70)
    print("YOLO TRAFFIC DATA PREPROCESSING")
    print("=" * 70)

    print(
        f"[INFO] Dataset          : "
        f"{DATASET_NAME}"
    )

    print(
        f"[INFO] Source CSV       : "
        f"{DATA_PATH}"
    )

    print(
        f"[INFO] Intersection     : "
        f"{INTERSECTION_ID}"
    )

    print(
        f"[INFO] Sequence length  : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"[INFO] Forecast horizon : "
        f"{FORECAST_HORIZON}"
    )

    print(
        f"[INFO] Approaches       : "
        f"{len(APPROACHES)}"
    )

    print(
        f"[INFO] Lanes/approach   : "
        f"{len(LANES)}"
    )

    print(
        f"[INFO] Sensors          : "
        f"{NUM_SENSORS}"
    )

    print(
        f"[INFO] Features/sensor : "
        f"{NUM_FEATURES}"
    )

    print(
        f"[INFO] Features/timestep: "
        f"{INPUT_FEATURES_PER_TIMESTEP}"
    )

    print("=" * 70)


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print()
    print("=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    if not DATA_PATH.exists():

        raise FileNotFoundError(
            "Dataset tidak ditemukan:\n"
            f"{DATA_PATH}"
        )

    dataframe = pd.read_csv(
        DATA_PATH
    )

    print(
        f"[INFO] Rows    : "
        f"{len(dataframe):,}"
    )

    print(
        f"[INFO] Columns : "
        f"{len(dataframe.columns)}"
    )

    print()
    print(
        "[INFO] Columns:"
    )

    for column in dataframe.columns:

        print(
            f"       - {column}"
        )

    return dataframe


# ============================================================
# VALIDATE REQUIRED COLUMNS
# ============================================================

def validate_columns(
    dataframe
):

    print()
    print("=" * 70)
    print("COLUMN VALIDATION")
    print("=" * 70)

    required_columns = [
        "timestamp",
        "intersection_id",
        "approach",
        "lane_id"
    ]

    required_columns.extend(
        FEATURE_NAMES
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:

        raise ValueError(
            "Kolom berikut tidak ditemukan:\n"
            + "\n".join(
                f"- {column}"
                for column in missing_columns
            )
        )

    print(
        "[OK] Semua kolom yang dibutuhkan "
        "tersedia."
    )


# ============================================================
# CLEAN BASIC DATA
# ============================================================

def clean_basic_data(
    dataframe
):

    print()
    print("=" * 70)
    print("BASIC DATA CLEANING")
    print("=" * 70)

    dataframe = dataframe.copy()

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce"
    )

    invalid_timestamp = (
        dataframe["timestamp"]
        .isna()
        .sum()
    )

    print(
        f"[INFO] Invalid timestamp : "
        f"{invalid_timestamp}"
    )

    if invalid_timestamp > 0:

        dataframe = dataframe.dropna(
            subset=["timestamp"]
        )

    # --------------------------------------------------------
    # Intersection
    # --------------------------------------------------------

    dataframe = dataframe[
        dataframe["intersection_id"]
        == INTERSECTION_ID
    ].copy()

    print(
        f"[INFO] Intersection rows : "
        f"{len(dataframe):,}"
    )

    # --------------------------------------------------------
    # Approach
    # --------------------------------------------------------

    dataframe["approach"] = (
        dataframe["approach"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    # --------------------------------------------------------
    # Lane
    # --------------------------------------------------------

    dataframe["lane_id"] = (
        dataframe["lane_id"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    dataframe = dataframe[
        dataframe["approach"]
        .isin(APPROACHES)
    ].copy()

    dataframe = dataframe[
        dataframe["lane_id"]
        .isin(LANES)
    ].copy()

    # --------------------------------------------------------
    # Numeric features
    # --------------------------------------------------------

    for feature in FEATURE_NAMES:

        dataframe[feature] = pd.to_numeric(
            dataframe[feature],
            errors="coerce"
        )

    invalid_numeric = (
        dataframe[
            FEATURE_NAMES
        ]
        .isna()
        .sum()
        .sum()
    )

    print(
        f"[INFO] Invalid numeric values : "
        f"{invalid_numeric}"
    )

    if invalid_numeric > 0:

        dataframe[
            FEATURE_NAMES
        ] = (
            dataframe[
                FEATURE_NAMES
            ]
            .fillna(0)
        )

    # --------------------------------------------------------
    # Negative physical values
    # --------------------------------------------------------

    negative_count = (
        dataframe[
            FEATURE_NAMES
        ]
        .lt(0)
        .sum()
        .sum()
    )

    print(
        f"[INFO] Negative feature values : "
        f"{negative_count}"
    )

    # Traffic counts and queue/density
    # should not be negative.

    for feature in FEATURE_NAMES:

        dataframe[feature] = (
            dataframe[feature]
            .clip(lower=0)
        )

    # --------------------------------------------------------
    # Sort chronologically
    # --------------------------------------------------------

    dataframe = dataframe.sort_values(
        [
            "timestamp",
            "approach",
            "lane_id"
        ]
    ).reset_index(
        drop=True
    )

    print(
        "[OK] Basic cleaning completed."
    )

    return dataframe


# ============================================================
# REMOVE DUPLICATE SENSOR RECORDS
# ============================================================

def remove_duplicates(
    dataframe
):

    print()
    print("=" * 70)
    print("DUPLICATE SENSOR RECORD CHECK")
    print("=" * 70)

    duplicate_mask = (
        dataframe.duplicated(
            subset=[
                "timestamp",
                "approach",
                "lane_id"
            ],
            keep=False
        )
    )

    duplicate_count = (
        duplicate_mask.sum()
    )

    print(
        f"[INFO] Duplicate rows : "
        f"{duplicate_count:,}"
    )

    if duplicate_count > 0:

        print(
            "[INFO] Duplicate sensor "
            "records akan diagregasi."
        )

        dataframe = (
            dataframe
            .groupby(
                [
                    "timestamp",
                    "approach",
                    "lane_id"
                ],
                as_index=False
            )[FEATURE_NAMES]
            .mean()
        )

    else:

        print(
            "[OK] Tidak ditemukan "
            "duplicate sensor record."
        )

    return dataframe


# ============================================================
# TIMESTAMP NORMALIZATION
# ============================================================

def normalize_timestamp(
    dataframe
):

    print()
    print("=" * 70)
    print("TIMESTAMP NORMALIZATION")
    print("=" * 70)

    dataframe = dataframe.copy()

    # --------------------------------------------------------
    # Dataset mayoritas memiliki interval 1 detik.
    #
    # Kita normalkan timestamp ke resolusi 1 detik.
    #
    # Contoh:
    #
    # 16:30:12.000
    # 16:30:13.000
    # 16:30:14.000
    #
    # --------------------------------------------------------

    dataframe["timestamp"] = (
        dataframe["timestamp"]
        .dt.floor("1s")
    )

    # Jika setelah flooring muncul duplicate,
    # agregasi kembali.

    dataframe = (
        dataframe
        .groupby(
            [
                "timestamp",
                "approach",
                "lane_id"
            ],
            as_index=False
        )[FEATURE_NAMES]
        .mean()
    )

    dataframe = dataframe.sort_values(
        [
            "timestamp",
            "approach",
            "lane_id"
        ]
    ).reset_index(
        drop=True
    )

    print(
        f"[INFO] Timestamp count : "
        f"{dataframe['timestamp'].nunique():,}"
    )

    print(
        f"[INFO] Start : "
        f"{dataframe['timestamp'].min()}"
    )

    print(
        f"[INFO] End   : "
        f"{dataframe['timestamp'].max()}"
    )

    print(
        "[OK] Timestamp normalized."
    )

    return dataframe


# ============================================================
# CREATE COMPLETE TIMESTAMP INDEX
# ============================================================

def create_timestamp_index(
    dataframe
):

    print()
    print("=" * 70)
    print("TIMESTAMP INDEX")
    print("=" * 70)

    start_time = (
        dataframe["timestamp"]
        .min()
    )

    end_time = (
        dataframe["timestamp"]
        .max()
    )

    timestamps = pd.date_range(
        start=start_time,
        end=end_time,
        freq="1s"
    )

    print(
        f"[INFO] Original timestamps : "
        f"{dataframe['timestamp'].nunique():,}"
    )

    print(
        f"[INFO] Expected 1-second "
        f"timestamps : "
        f"{len(timestamps):,}"
    )

    print(
        f"[INFO] Missing timestamp "
        f"slots : "
        f"{len(timestamps) - dataframe['timestamp'].nunique():,}"
    )

    return timestamps


# ============================================================
# BUILD COMPLETE LANE TABLE
# ============================================================

def build_lane_table(
    dataframe,
    timestamps
):

    print()
    print("=" * 70)
    print("BUILDING COMPLETE LANE TABLE")
    print("=" * 70)

    # --------------------------------------------------------
    # IMPORTANT
    #
    # Tidak menggunakan MultiIndex.reindex().
    #
    # Kita membangun tabel secara eksplisit supaya:
    #
    # timestamp × approach × lane
    #
    # selalu memiliki struktur yang konsisten.
    # --------------------------------------------------------

    complete_rows = []

    for timestamp in timestamps:

        timestamp_data = dataframe[
            dataframe["timestamp"]
            == timestamp
        ]

        # Membuat lookup:
        #
        # (approach, lane) -> values

        lookup = {}

        for row in timestamp_data.itertuples(
            index=False
        ):

            key = (
                row.approach,
                row.lane_id
            )

            values = [
                getattr(
                    row,
                    feature
                )
                for feature in FEATURE_NAMES
            ]

            lookup[key] = values

        # ----------------------------------------------------
        # Selalu buat 12 sensor.
        # ----------------------------------------------------

        for approach in APPROACHES:

            for lane in LANES:

                key = (
                    approach,
                    lane
                )

                if key in lookup:

                    values = lookup[key]

                else:

                    # Tidak ada data pada timestamp
                    # tersebut.
                    #
                    # Diisi 0 karena:
                    #
                    # tidak ada kendaraan
                    # /
                    # tidak ada queue
                    # /
                    # tidak ada density.
                    #
                    # Ini juga menjaga dimensi
                    # input LSTM tetap konsisten.

                    values = [
                        0.0
                        for _ in FEATURE_NAMES
                    ]

                row_data = {
                    "timestamp":
                        timestamp,

                    "approach":
                        approach,

                    "lane_id":
                        lane
                }

                for feature, value in zip(
                    FEATURE_NAMES,
                    values
                ):

                    row_data[feature] = (
                        float(value)
                    )

                complete_rows.append(
                    row_data
                )

    table = pd.DataFrame(
        complete_rows
    )

    table = table.sort_values(
        [
            "timestamp",
            "approach",
            "lane_id"
        ]
    ).reset_index(
        drop=True
    )

    expected_rows = (
        len(timestamps)
        * NUM_SENSORS
    )

    print(
        f"[INFO] Expected rows : "
        f"{expected_rows:,}"
    )

    print(
        f"[INFO] Actual rows   : "
        f"{len(table):,}"
    )

    if len(table) != expected_rows:

        raise ValueError(
            "Jumlah baris complete lane table "
            "tidak sesuai."
        )

    print(
        "[OK] Complete lane table created."
    )

    return table


# ============================================================
# BUILD TIMESTEP MATRIX
# ============================================================

def build_timestep_matrix(
    lane_table
):

    print()
    print("=" * 70)
    print("BUILDING TIMESTEP MATRIX")
    print("=" * 70)

    timestamps = (
        lane_table[
            "timestamp"
        ]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    matrix = []

    for timestamp in timestamps:

        timestamp_data = (
            lane_table[
                lane_table[
                    "timestamp"
                ]
                == timestamp
            ]
        )

        # ----------------------------------------------------
        # Pastikan jumlah sensor = 12
        # ----------------------------------------------------

        if len(timestamp_data) != NUM_SENSORS:

            raise ValueError(
                f"Timestamp {timestamp} "
                f"tidak memiliki "
                f"{NUM_SENSORS} sensor."
            )

        # ----------------------------------------------------
        # Ambil sensor berdasarkan urutan tetap
        # ----------------------------------------------------

        timestep_values = []

        for approach, lane in (
            SENSOR_COLUMNS
        ):

            sensor_data = (
                timestamp_data[
                    (
                        timestamp_data[
                            "approach"
                        ]
                        == approach
                    )
                    &
                    (
                        timestamp_data[
                            "lane_id"
                        ]
                        == lane
                    )
                ]
            )

            if len(sensor_data) != 1:

                raise ValueError(
                    f"Sensor duplicate/missing:\n"
                    f"timestamp={timestamp}\n"
                    f"approach={approach}\n"
                    f"lane={lane}"
                )

            row = sensor_data.iloc[0]

            for feature in FEATURE_NAMES:

                timestep_values.append(
                    float(
                        row[feature]
                    )
                )

        matrix.append(
            timestep_values
        )

    matrix = np.asarray(
        matrix,
        dtype=np.float32
    )

    print(
        f"[INFO] Timestep count : "
        f"{matrix.shape[0]:,}"
    )

    print(
        f"[INFO] Features/timestep : "
        f"{matrix.shape[1]}"
    )

    expected_features = (
        NUM_SENSORS
        * NUM_FEATURES
    )

    if matrix.shape[1] != (
        expected_features
    ):

        raise ValueError(
            "Jumlah feature timestep "
            "tidak sesuai.\n"
            f"Expected: {expected_features}\n"
            f"Got: {matrix.shape[1]}"
        )

    print(
        f"[OK] Matrix shape: "
        f"{matrix.shape}"
    )

    return (
        matrix,
        timestamps
    )


# ============================================================
# DATA VALIDATION
# ============================================================

def validate_matrix(
    matrix
):

    print()
    print("=" * 70)
    print("NUMERICAL DATA VALIDATION")
    print("=" * 70)

    nan_count = (
        np.isnan(matrix)
        .sum()
    )

    inf_count = (
        np.isinf(matrix)
        .sum()
    )

    print(
        f"[INFO] NaN count : "
        f"{nan_count:,}"
    )

    print(
        f"[INFO] Inf count : "
        f"{inf_count:,}"
    )

    if nan_count > 0:

        raise ValueError(
            "Dataset masih mengandung NaN."
        )

    if inf_count > 0:

        raise ValueError(
            "Dataset masih mengandung Inf."
        )

    print(
        "[OK] Tidak ditemukan NaN atau Inf."
    )

    print()
    print(
        "[FEATURE STATISTICS]"
    )

    for feature_index, feature_name in enumerate(
        FEATURE_NAMES
    ):

        # Feature berada pada posisi yang sama
        # untuk setiap sensor.
        #
        # Contoh:
        # sensor 0:
        # index 0-7
        #
        # sensor 1:
        # index 8-15
        #
        # dst.

        values = matrix[
            :,
            feature_index::NUM_FEATURES
        ]

        print(
            f"\n[INFO] {feature_name}"
        )

        print(
            f"       Min  : "
            f"{np.min(values):.6f}"
        )

        print(
            f"       Max  : "
            f"{np.max(values):.6f}"
        )

        print(
            f"       Mean : "
            f"{np.mean(values):.6f}"
        )


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

    total_timesteps = (
        len(matrix)
    )

    train_end = int(
        total_timesteps
        * 0.70
    )

    val_end = int(
        total_timesteps
        * 0.85
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
        "[TRAIN]"
    )

    print(
        f"       Shape : "
        f"{train.shape}"
    )

    print()
    print(
        "[VALIDATION]"
    )

    print(
        f"       Shape : "
        f"{val.shape}"
    )

    print()
    print(
        "[TEST]"
    )

    print(
        f"       Shape : "
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
# SCALING
# ============================================================

def scale_data(
    train,
    val,
    test
):

    print()
    print("=" * 70)
    print("SCALER")
    print("=" * 70)

    print(
        "[INFO] Fitting scaler menggunakan "
        "TRAINING DATA saja."
    )

    scaler = StandardScaler()

    # --------------------------------------------------------
    # Fit hanya training data
    # --------------------------------------------------------

    scaler.fit(
        train
    )

    train_scaled = (
        scaler.transform(
            train
        )
    )

    val_scaled = (
        scaler.transform(
            val
        )
    )

    test_scaled = (
        scaler.transform(
            test
        )
    )

    print(
        "[OK] Scaler fitted menggunakan "
        "training data."
    )

    print(
        "[OK] Scaling completed."
    )

    return (
        train_scaled.astype(
            np.float32
        ),
        val_scaled.astype(
            np.float32
        ),
        test_scaled.astype(
            np.float32
        ),
        scaler
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

    total_samples = (
        len(data)
        - SEQUENCE_LENGTH
        - FORECAST_HORIZON
        + 1
    )

    if total_samples <= 0:

        raise ValueError(
            "Data terlalu sedikit untuk "
            "membuat sequence."
        )

    for index in range(
        total_samples
    ):

        start = index

        end = (
            index
            + SEQUENCE_LENGTH
        )

        target_end = (
            end
            + FORECAST_HORIZON
        )

        input_sequence = (
            data[
                start:end
            ]
        )

        target_sequence = (
            data[
                end:target_end
            ]
        )

        # ----------------------------------------------------
        # Forecast horizon = 1
        #
        # X:
        # (15, 96)
        #
        # y:
        # (96)
        # ----------------------------------------------------

        if FORECAST_HORIZON == 1:

            target_sequence = (
                target_sequence[0]
            )

        X.append(
            input_sequence
        )

        y.append(
            target_sequence
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

    return (
        X,
        y
    )


# ============================================================
# RESHAPE FOR LSTM
# ============================================================

def reshape_for_lstm(
    X,
    y
):

    print()
    print("=" * 70)
    print("LSTM SHAPE PREPARATION")
    print("=" * 70)

    # --------------------------------------------------------
    # Saat ini:
    #
    # X = (samples, 15, 96)
    # y = (samples, 96)
    #
    # Ini sudah merupakan format yang dibutuhkan
    # LSTM dengan input_size = 96.
    # --------------------------------------------------------

    expected_x_features = (
        NUM_SENSORS
        * NUM_FEATURES
    )

    if X.shape[2] != (
        expected_x_features
    ):

        raise ValueError(
            "X feature dimension tidak sesuai."
        )

    if y.shape[1] != (
        expected_x_features
    ):

        raise ValueError(
            "y feature dimension tidak sesuai."
        )

    print(
        f"[INFO] LSTM input size : "
        f"{X.shape[2]}"
    )

    print(
        f"[INFO] LSTM output size: "
        f"{y.shape[1]}"
    )

    print(
        "[OK] LSTM shapes valid."
    )

    return (
        X,
        y
    )


# ============================================================
# SAVE NUMPY DATA
# ============================================================

def save_numpy(
    name,
    array
):

    path = (
        PROCESSED_DIR
        / name
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

    timestamp_array = np.asarray(
        timestamps,
        dtype="datetime64[ns]"
    )

    np.save(
        path,
        timestamp_array
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE SENSOR CONFIGURATION
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
                    "sensor_id":
                        sensor_id,

                    "approach":
                        approach,

                    "lane_id":
                        lane
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
                for approach, lane
                in SENSOR_COLUMNS
            ]
    }

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

        "sequence_length":
            SEQUENCE_LENGTH,

        "forecast_horizon":
            FORECAST_HORIZON,

        "split": {

            "train":
                0.70,

            "validation":
                0.15,

            "test":
                0.15
        },

        "sensors": {

            "count":
                NUM_SENSORS,

            "approaches":
                APPROACHES,

            "lanes":
                LANES
        },

        "features": {

            "names":
                FEATURE_NAMES,

            "count":
                NUM_FEATURES,

            "per_timestep":
                INPUT_FEATURES_PER_TIMESTEP
        },

        "model_input": {

            "shape":
                [
                    SEQUENCE_LENGTH,
                    INPUT_FEATURES_PER_TIMESTEP
                ],

            "input_size":
                INPUT_FEATURES_PER_TIMESTEP,

            "output_size":
                INPUT_FEATURES_PER_TIMESTEP
        },

        "missing_sensor_strategy":
            "fill_zero",

        "timestamp_resolution":
            "1 second",

        "scaler":
            "StandardScaler",

        "scaler_fit":
            "training_data_only",

        "random_seed":
            RANDOM_SEED
    }

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
# SAVE SCALER
# ============================================================

def save_scaler(
    scaler
):

    path = (
        PROCESSED_DIR
        / "scaler_X.pkl"
    )

    joblib.dump(
        scaler,
        path
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE COMPLETE LANE TABLE
# ============================================================

def save_lane_table(
    lane_table
):

    path = (
        PROCESSED_DIR
        / "complete_lane_table.csv"
    )

    lane_table.to_csv(
        path,
        index=False
    )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SAVE RAW TIMESTEP MATRIX
# ============================================================

def save_raw_matrix(
    matrix
):

    path = (
        PROCESSED_DIR
        / "timestep_matrix.npy"
    )

    np.save(
        path,
        matrix
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

    metadata = {

        "features":
            FEATURE_NAMES,

        "num_features":
            NUM_FEATURES,

        "num_sensors":
            NUM_SENSORS,

        "features_per_timestep":
            INPUT_FEATURES_PER_TIMESTEP,

        "feature_layout":
            "sensor-major",

        "layout_example": {

            "sensor_1":
                FEATURE_NAMES,

            "sensor_2":
                FEATURE_NAMES,

            "sensor_12":
                FEATURE_NAMES
        }
    }

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4
        )

    print(
        f"[SAVED] {path}"
    )


# ============================================================
# SUMMARY
# ============================================================

def print_summary(
    X_train,
    y_train,
    X_val,
    y_val,
    X_test,
    y_test,
    matrix
):

    print()
    print("=" * 70)
    print("PREPROCESSING SUMMARY")
    print("=" * 70)

    print()
    print(
        "[DATA]"
    )

    print(
        f"Dataset             : "
        f"{DATASET_NAME}"
    )

    print(
        f"Intersection        : "
        f"{INTERSECTION_ID}"
    )

    print(
        f"Timesteps           : "
        f"{len(matrix):,}"
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
    print(
        "[FEATURES]"
    )

    for feature in FEATURE_NAMES:

        print(
            f"       - {feature}"
        )

    print()
    print(
        "[SEQUENCE]"
    )

    print(
        f"Sequence length     : "
        f"{SEQUENCE_LENGTH}"
    )

    print(
        f"Forecast horizon    : "
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

    print()
    print(
        "[MODEL INTERFACE]"
    )

    print(
        f"LSTM input_size     : "
        f"{INPUT_FEATURES_PER_TIMESTEP}"
    )

    print(
        f"LSTM output_size    : "
        f"{INPUT_FEATURES_PER_TIMESTEP}"
    )

    print()
    print(
        "[OUTPUT DIRECTORY]"
    )

    print(
        f"{PROCESSED_DIR}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print_configuration()

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    dataframe = load_data()

    # --------------------------------------------------------
    # Validate columns
    # --------------------------------------------------------

    validate_columns(
        dataframe
    )

    # --------------------------------------------------------
    # Basic cleaning
    # --------------------------------------------------------

    dataframe = clean_basic_data(
        dataframe
    )

    # --------------------------------------------------------
    # Remove duplicate sensor records
    # --------------------------------------------------------

    dataframe = remove_duplicates(
        dataframe
    )

    # --------------------------------------------------------
    # Normalize timestamp
    # --------------------------------------------------------

    dataframe = normalize_timestamp(
        dataframe
    )

    # --------------------------------------------------------
    # Create complete timestamp index
    # --------------------------------------------------------

    timestamps = (
        create_timestamp_index(
            dataframe
        )
    )

    # --------------------------------------------------------
    # Build complete lane table
    # --------------------------------------------------------

    lane_table = (
        build_lane_table(
            dataframe,
            timestamps
        )
    )

    # --------------------------------------------------------
    # Save lane table
    # --------------------------------------------------------

    save_lane_table(
        lane_table
    )

    # --------------------------------------------------------
    # Build timestep matrix
    # --------------------------------------------------------

    (
        matrix,
        timestamps
    ) = build_timestep_matrix(
        lane_table
    )

    # --------------------------------------------------------
    # Validate numerical matrix
    # --------------------------------------------------------

    validate_matrix(
        matrix
    )

    # --------------------------------------------------------
    # Save raw matrix
    # --------------------------------------------------------

    save_raw_matrix(
        matrix
    )

    # --------------------------------------------------------
    # Chronological split
    # --------------------------------------------------------

    (
        train,
        val,
        test
    ) = chronological_split(
        matrix
    )

    # --------------------------------------------------------
    # Scale
    # --------------------------------------------------------

    (
        train_scaled,
        val_scaled,
        test_scaled,
        scaler
    ) = scale_data(
        train,
        val,
        test
    )

    # --------------------------------------------------------
    # Create sequences
    # --------------------------------------------------------

    (
        X_train,
        y_train
    ) = create_sequences(
        train_scaled
    )

    (
        X_val,
        y_val
    ) = create_sequences(
        val_scaled
    )

    (
        X_test,
        y_test
    ) = create_sequences(
        test_scaled
    )

    # --------------------------------------------------------
    # Validate LSTM shape
    # --------------------------------------------------------

    (
        X_train,
        y_train
    ) = reshape_for_lstm(
        X_train,
        y_train
    )

    (
        X_val,
        y_val
    ) = reshape_for_lstm(
        X_val,
        y_val
    )

    (
        X_test,
        y_test
    ) = reshape_for_lstm(
        X_test,
        y_test
    )

    # --------------------------------------------------------
    # Save processed arrays
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING PROCESSED DATA")
    print("=" * 70)

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
    # Save scaler
    # --------------------------------------------------------

    save_scaler(
        scaler
    )

    # --------------------------------------------------------
    # Save timestamps
    # --------------------------------------------------------

    save_timestamps(
        timestamps
    )

    # --------------------------------------------------------
    # Save metadata
    # --------------------------------------------------------

    save_sensor_config()

    save_feature_metadata()

    save_preprocess_config()

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print_summary(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test,
        matrix=matrix
    )

    print()
    print("=" * 70)
    print(
        "YOLO PREPROCESSING PIPELINE COMPLETED"
    )
    print("=" * 70)

    print()
    print(
        "[OK] Dataset berhasil diproses."
    )

    print(
        "[OK] Semua 8 traffic features digunakan."
    )

    print(
        "[OK] Semua 12 lane sensors digunakan."
    )

    print(
        "[OK] Input LSTM = 96 features/timestep."
    )

    print(
        "[OK] Sequence = 15 timestep."
    )

    print(
        "[OK] Forecast horizon = 1 timestep."
    )

    print()
    print(
        "[NEXT]"
    )

    print(
        "Jalankan training:"
    )

    print(
        "python scripts/yolo/03_train_yolo.py"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()