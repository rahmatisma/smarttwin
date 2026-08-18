# ================================================================
# 12_feature_sensor_diagnostic_yolo.py
# ================================================================
#
# PURPOSE
# -------
# Audit feature -> sensor/lane mapping dan melakukan diagnostic
# terhadap final LSTM model.
#
# TIDAK melakukan training.
# TIDAK melakukan hyperparameter tuning.
#
# Output:
#   outputs/yolo/evaluation/final_model/diagnostic/
#
# ================================================================

from pathlib import Path
import json
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")


# ================================================================
# CONFIGURATION
# ================================================================

SEED = 42

np.random.seed(SEED)

SCRIPT_DIR = Path(__file__).resolve().parent

# forecasting/
PROJECT_ROOT = SCRIPT_DIR.parents[2]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "yolo"
)

PROCESSED_DIR = (
    OUTPUT_DIR
    / "processed"
)

EVALUATION_DIR = (
    OUTPUT_DIR
    / "evaluation"
)

FINAL_MODEL_DIR = (
    EVALUATION_DIR
    / "final_model"
)

ERROR_ANALYSIS_DIR = (
    FINAL_MODEL_DIR
    / "error_analysis"
)

DIAGNOSTIC_DIR = (
    FINAL_MODEL_DIR
    / "diagnostic"
)

PLOTS_DIR = (
    DIAGNOSTIC_DIR
    / "plots"
)

DIAGNOSTIC_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PLOTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ================================================================
# FILE PATHS
# ================================================================

ACTUAL_PATH = (
    FINAL_MODEL_DIR
    / "y_test_actual_final_original.npy"
)

LSTM_PATH = (
    FINAL_MODEL_DIR
    / "y_test_prediction_final_original.npy"
)

PERSISTENCE_PATH = (
    FINAL_MODEL_DIR
    / "persistence_prediction_final_original.npy"
)

METRICS_PATH = (
    FINAL_MODEL_DIR
    / "final_model_metrics.json"
)

CONFIG_PATH = (
    FINAL_MODEL_DIR
    / "final_model_config.json"
)

FEATURE_METADATA_PATH = (
    PROCESSED_DIR
    / "feature_metadata.json"
)

SENSOR_CONFIG_PATH = (
    PROCESSED_DIR
    / "sensor_config.json"
)

YOLO_CONFIG_PATH = (
    PROCESSED_DIR
    / "yolo_config.json"
)

TIMESTEP_MATRIX_PATH = (
    PROCESSED_DIR
    / "timestep_matrix.npy"
)


# ================================================================
# HELPER
# ================================================================

def print_header(title):

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def load_json(path):

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_float(value):

    try:
        return float(value)
    except Exception:
        return np.nan


def normalize_text(value):

    if value is None:
        return ""

    return str(value).strip()


def find_key_recursive(obj, target_keys):

    """
    Mencari key secara recursive di JSON.
    """

    if isinstance(obj, dict):

        for key, value in obj.items():

            if str(key).lower() in target_keys:
                return value

            result = find_key_recursive(
                value,
                target_keys
            )

            if result is not None:
                return result

    elif isinstance(obj, list):

        for item in obj:

            result = find_key_recursive(
                item,
                target_keys
            )

            if result is not None:
                return result

    return None


def flatten_json(obj, prefix=""):

    """
    Flatten JSON menjadi pasangan path -> value.
    """

    result = {}

    if isinstance(obj, dict):

        for key, value in obj.items():

            new_prefix = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            result.update(
                flatten_json(
                    value,
                    new_prefix
                )
            )

    elif isinstance(obj, list):

        for idx, value in enumerate(obj):

            new_prefix = (
                f"{prefix}[{idx}]"
            )

            result.update(
                flatten_json(
                    value,
                    new_prefix
                )
            )

    else:

        result[prefix] = obj

    return result


# ================================================================
# VALIDATE FILES
# ================================================================

print_header(
    "YOLO FEATURE / SENSOR DIAGNOSTIC AUDIT"
)

print(
    f"[INFO] Project root       : {PROJECT_ROOT}"
)

print(
    f"[INFO] Final model dir    : {FINAL_MODEL_DIR}"
)

print(
    f"[INFO] Diagnostic dir     : {DIAGNOSTIC_DIR}"
)


print_header(
    "VALIDATING REQUIRED FILES"
)

required_files = {

    "Actual test target":
        ACTUAL_PATH,

    "LSTM prediction":
        LSTM_PATH,

    "Persistence prediction":
        PERSISTENCE_PATH,

    "Final metrics":
        METRICS_PATH,

    "Final config":
        CONFIG_PATH,

    "Feature metadata":
        FEATURE_METADATA_PATH,

    "Sensor config":
        SENSOR_CONFIG_PATH,

    "YOLO config":
        YOLO_CONFIG_PATH,

}


missing_files = []

for label, path in required_files.items():

    if path.exists():

        print(
            f"[OK] {label:<25} : {path.name}"
        )

    else:

        print(
            f"[MISSING] {label:<25} : {path}"
        )

        missing_files.append(
            str(path)
        )


if missing_files:

    raise FileNotFoundError(
        "\n[ERROR] Required file tidak ditemukan:\n"
        + "\n".join(missing_files)
    )


print(
    "\n[OK] Semua required files tersedia."
)


# ================================================================
# LOAD PREDICTIONS
# ================================================================

print_header(
    "LOADING FINAL PREDICTIONS"
)

actual = np.load(
    ACTUAL_PATH
)

lstm = np.load(
    LSTM_PATH
)

persistence = np.load(
    PERSISTENCE_PATH
)

print(
    f"[INFO] Actual       : {actual.shape}"
)

print(
    f"[INFO] LSTM         : {lstm.shape}"
)

print(
    f"[INFO] Persistence  : {persistence.shape}"
)


if not (
    actual.shape
    == lstm.shape
    == persistence.shape
):

    raise ValueError(
        "[ERROR] Shape prediction tidak sama."
    )


N_SAMPLES, N_FEATURES = actual.shape

print(
    f"[INFO] Samples      : {N_SAMPLES}"
)

print(
    f"[INFO] Features     : {N_FEATURES}"
)


# ================================================================
# NUMERICAL VALIDATION
# ================================================================

print_header(
    "NUMERICAL VALIDATION"
)

arrays = {

    "Actual":
        actual,

    "LSTM":
        lstm,

    "Persistence":
        persistence,

}


for name, arr in arrays.items():

    nan_count = np.isnan(arr).sum()

    inf_count = np.isinf(arr).sum()

    print(
        f"[INFO] {name:<15}"
        f"| NaN: {nan_count:<6}"
        f"| Inf: {inf_count:<6}"
    )

    if nan_count > 0 or inf_count > 0:

        raise ValueError(
            f"[ERROR] {name} memiliki NaN/Inf."
        )


print(
    "[OK] Semua prediction numerically valid."
)


# ================================================================
# LOAD JSON
# ================================================================

print_header(
    "LOADING METADATA"
)

feature_metadata = load_json(
    FEATURE_METADATA_PATH
)

sensor_config = load_json(
    SENSOR_CONFIG_PATH
)

yolo_config = load_json(
    YOLO_CONFIG_PATH
)

final_config = load_json(
    CONFIG_PATH
)

print(
    "[OK] feature_metadata.json loaded"
)

print(
    "[OK] sensor_config.json loaded"
)

print(
    "[OK] yolo_config.json loaded"
)


# ================================================================
# INSPECT METADATA STRUCTURE
# ================================================================

print_header(
    "INSPECTING FEATURE METADATA STRUCTURE"
)

print(
    f"[INFO] Root type : "
    f"{type(feature_metadata).__name__}"
)

if isinstance(feature_metadata, dict):

    print(
        "[INFO] Root keys:"
    )

    for key in feature_metadata.keys():

        print(
            f"       - {key}"
        )

elif isinstance(feature_metadata, list):

    print(
        f"[INFO] Metadata list length : "
        f"{len(feature_metadata)}"
    )


# ================================================================
# FLATTEN METADATA
# ================================================================

flat_metadata = flatten_json(
    feature_metadata
)

flat_sensor_config = flatten_json(
    sensor_config
)

flat_yolo_config = flatten_json(
    yolo_config
)


metadata_text = " ".join(
    str(v)
    for v in flat_metadata.values()
)


sensor_text = " ".join(
    str(v)
    for v in flat_sensor_config.values()
)


# ================================================================
# DETECT SENSOR / LANE CANDIDATES
# ================================================================

print_header(
    "DETECTING SENSOR / LANE CANDIDATES"
)

sensor_lane_pattern = re.compile(
    r"([a-zA-Z]+)\s*[/_-]\s*(lane[_-]?\d+)",
    re.IGNORECASE
)


metadata_matches = (
    sensor_lane_pattern.findall(
        metadata_text
    )
)

sensor_matches = (
    sensor_lane_pattern.findall(
        sensor_text
    )
)


detected_pairs = []


for sensor, lane in (
    metadata_matches
    + sensor_matches
):

    pair = (
        normalize_text(sensor),
        normalize_text(lane)
    )

    if pair not in detected_pairs:

        detected_pairs.append(pair)


print(
    f"[INFO] Detected sensor/lane pairs : "
    f"{len(detected_pairs)}"
)


for sensor, lane in detected_pairs:

    print(
        f"       - {sensor} / {lane}"
    )


# ================================================================
# EXPECTED SENSOR/LANE
# ================================================================

expected_sensor_lanes = [

    ("north", "lane_1"),
    ("north", "lane_2"),

    ("south", "lane_1"),
    ("south", "lane_2"),

    ("east", "lane_1"),
    ("east", "lane_2"),

    ("west", "lane_1"),
    ("west", "lane_2"),

    ("north", "lane_3"),
    ("south", "lane_3"),
    ("east", "lane_3"),
    ("west", "lane_3"),

]


# ================================================================
# BUILD FEATURE MAPPING
# ================================================================

print_header(
    "BUILDING FEATURE MAPPING"
)

feature_rows = []


def extract_sensor_lane_from_text(text):

    if not text:

        return None, None

    match = sensor_lane_pattern.search(
        str(text)
    )

    if match:

        return (
            match.group(1),
            match.group(2)
        )

    return None, None


def extract_feature_name(item):

    if not isinstance(item, dict):

        return ""

    candidate_keys = [

        "feature",
        "feature_name",
        "name",
        "metric",
        "variable",
        "field",
        "column",

    ]

    for key in candidate_keys:

        if key in item:

            return normalize_text(
                item[key]
            )

    return ""


def extract_sensor(item):

    if not isinstance(item, dict):

        return ""

    candidate_keys = [

        "sensor",
        "sensor_name",
        "location",
        "direction",
        "approach",
        "road",

    ]

    for key in candidate_keys:

        if key in item:

            return normalize_text(
                item[key]
            )

    return ""


def extract_lane(item):

    if not isinstance(item, dict):

        return ""

    candidate_keys = [

        "lane",
        "lane_name",
        "lane_id",

    ]

    for key in candidate_keys:

        if key in item:

            return normalize_text(
                item[key]
            )

    return ""


# ---------------------------------------------------------------
# CASE 1: metadata berupa list
# ---------------------------------------------------------------

if isinstance(feature_metadata, list):

    for idx, item in enumerate(
        feature_metadata
    ):

        feature_name = (
            extract_feature_name(item)
        )

        sensor = (
            extract_sensor(item)
        )

        lane = (
            extract_lane(item)
        )

        combined_text = " ".join(
            [
                feature_name,
                sensor,
                lane,
                str(item),
            ]
        )

        parsed_sensor, parsed_lane = (
            extract_sensor_lane_from_text(
                combined_text
            )
        )

        if not sensor:
            sensor = parsed_sensor or ""

        if not lane:
            lane = parsed_lane or ""

        feature_rows.append({

            "feature_index":
                idx,

            "feature_name":
                feature_name,

            "sensor":
                sensor,

            "lane":
                lane,

            "metadata_raw":
                str(item),

        })


# ---------------------------------------------------------------
# CASE 2: metadata berupa dictionary
# ---------------------------------------------------------------

elif isinstance(
    feature_metadata,
    dict
):

    # Search common list containers

    candidate_containers = [

        "features",
        "feature_metadata",
        "feature_names",
        "columns",
        "metadata",

    ]

    metadata_list = None

    for key in candidate_containers:

        if key in feature_metadata:

            value = feature_metadata[key]

            if isinstance(
                value,
                list
            ):

                metadata_list = value

                break

    if metadata_list is not None:

        for idx, item in enumerate(
            metadata_list
        ):

            if isinstance(item, dict):

                feature_name = (
                    extract_feature_name(item)
                )

                sensor = (
                    extract_sensor(item)
                )

                lane = (
                    extract_lane(item)
                )

            else:

                feature_name = (
                    normalize_text(item)
                )

                sensor = ""

                lane = ""

            combined_text = " ".join(
                [
                    feature_name,
                    sensor,
                    lane,
                ]
            )

            parsed_sensor, parsed_lane = (
                extract_sensor_lane_from_text(
                    combined_text
                )
            )

            if not sensor:
                sensor = (
                    parsed_sensor or ""
                )

            if not lane:
                lane = (
                    parsed_lane or ""
                )

            feature_rows.append({

                "feature_index":
                    idx,

                "feature_name":
                    feature_name,

                "sensor":
                    sensor,

                "lane":
                    lane,

                "metadata_raw":
                    str(item),

            })


# ---------------------------------------------------------------
# FALLBACK
# ---------------------------------------------------------------

if len(feature_rows) != N_FEATURES:

    print(
        "[WARNING] Feature metadata tidak "
        "langsung memiliki mapping 96 feature."
    )

    print(
        f"[WARNING] Metadata rows : "
        f"{len(feature_rows)}"
    )

    print(
        f"[WARNING] Expected rows : "
        f"{N_FEATURES}"
    )


# ================================================================
# FORCE FEATURE COUNT
# ================================================================

if len(feature_rows) < N_FEATURES:

    existing = len(feature_rows)

    for idx in range(
        existing,
        N_FEATURES
    ):

        feature_rows.append({

            "feature_index":
                idx,

            "feature_name":
                f"feature_{idx}",

            "sensor":
                "",

            "lane":
                "",

            "metadata_raw":
                "",

        })


elif len(feature_rows) > N_FEATURES:

    feature_rows = feature_rows[
        :N_FEATURES
    ]


feature_mapping = pd.DataFrame(
    feature_rows
)


# ================================================================
# SECOND PASS: PARSE FEATURE NAME
# ================================================================

for idx in range(
    len(feature_mapping)
):

    feature_name = normalize_text(
        feature_mapping.loc[
            idx,
            "feature_name"
        ]
    )

    sensor = normalize_text(
        feature_mapping.loc[
            idx,
            "sensor"
        ]
    )

    lane = normalize_text(
        feature_mapping.loc[
            idx,
            "lane"
        ]
    )

    combined_text = " ".join(
        [
            feature_name,
            sensor,
            lane,
            feature_mapping.loc[
                idx,
                "metadata_raw"
            ],
        ]
    )

    parsed_sensor, parsed_lane = (
        extract_sensor_lane_from_text(
            combined_text
        )
    )

    if not sensor and parsed_sensor:

        feature_mapping.loc[
            idx,
            "sensor"
        ] = parsed_sensor

    if not lane and parsed_lane:

        feature_mapping.loc[
            idx,
            "lane"
        ] = parsed_lane


# ================================================================
# NORMALIZE SENSOR/LANE
# ================================================================

feature_mapping["sensor"] = (
    feature_mapping["sensor"]
    .astype(str)
    .str.strip()
    .str.lower()
)

feature_mapping["lane"] = (
    feature_mapping["lane"]
    .astype(str)
    .str.strip()
    .str.lower()
)


# ================================================================
# DISPLAY FEATURE MAPPING
# ================================================================

print_header(
    "FEATURE MAPPING PREVIEW"
)

print(
    feature_mapping[
        [
            "feature_index",
            "feature_name",
            "sensor",
            "lane",
        ]
    ].head(20).to_string(
        index=False
    )
)


# ================================================================
# COUNT MAPPING
# ================================================================

mapped_features = feature_mapping[
    (
        feature_mapping["sensor"] != ""
    )
    &
    (
        feature_mapping["lane"] != ""
    )
]


unknown_features = feature_mapping[
    (
        feature_mapping["sensor"] == ""
    )
    |
    (
        feature_mapping["lane"] == ""
    )
]


print_header(
    "MAPPING QUALITY"
)

print(
    f"[INFO] Total features       : "
    f"{len(feature_mapping)}"
)

print(
    f"[INFO] Mapped features      : "
    f"{len(mapped_features)}"
)

print(
    f"[INFO] Unknown features     : "
    f"{len(unknown_features)}"
)

mapping_percentage = (
    len(mapped_features)
    / len(feature_mapping)
    * 100
)

print(
    f"[INFO] Mapping coverage     : "
    f"{mapping_percentage:.2f}%"
)


# ================================================================
# SAVE FEATURE MAPPING
# ================================================================

feature_mapping_path = (
    DIAGNOSTIC_DIR
    / "feature_sensor_lane_mapping.csv"
)

feature_mapping.to_csv(
    feature_mapping_path,
    index=False
)

print(
    f"[SAVED] {feature_mapping_path}"
)


# ================================================================
# ERROR MATRICES
# ================================================================

print_header(
    "CALCULATING ERROR MATRICES"
)

lstm_abs_error = np.abs(
    actual - lstm
)

persistence_abs_error = np.abs(
    actual - persistence
)

lstm_squared_error = (
    actual - lstm
) ** 2

persistence_squared_error = (
    actual - persistence
) ** 2


# ================================================================
# FEATURE LEVEL ANALYSIS
# ================================================================

print_header(
    "FEATURE LEVEL DIAGNOSTIC"
)

feature_results = []

for i in range(
    N_FEATURES
):

    lstm_mae = (
        np.mean(
            lstm_abs_error[:, i]
        )
    )

    persistence_mae = (
        np.mean(
            persistence_abs_error[:, i]
        )
    )

    lstm_rmse = np.sqrt(
        np.mean(
            lstm_squared_error[:, i]
        )
    )

    persistence_rmse = np.sqrt(
        np.mean(
            persistence_squared_error[:, i]
        )
    )

    mae_advantage = (
        persistence_mae
        - lstm_mae
    )

    rmse_advantage = (
        persistence_rmse
        - lstm_rmse
    )

    if mae_advantage > 0:

        mae_winner = "LSTM"

    elif mae_advantage < 0:

        mae_winner = "Persistence"

    else:

        mae_winner = "Tie"

    if rmse_advantage > 0:

        rmse_winner = "LSTM"

    elif rmse_advantage < 0:

        rmse_winner = "Persistence"

    else:

        rmse_winner = "Tie"

    row = (
        feature_mapping.iloc[i]
        .to_dict()
    )

    row.update({

        "lstm_mae":
            lstm_mae,

        "persistence_mae":
            persistence_mae,

        "lstm_rmse":
            lstm_rmse,

        "persistence_rmse":
            persistence_rmse,

        "mae_advantage_lstm":
            mae_advantage,

        "rmse_advantage_lstm":
            rmse_advantage,

        "mae_winner":
            mae_winner,

        "rmse_winner":
            rmse_winner,

    })

    feature_results.append(
        row
    )


feature_df = pd.DataFrame(
    feature_results
)


feature_df = feature_df.sort_values(
    "lstm_mae",
    ascending=False
)


feature_output = (
    DIAGNOSTIC_DIR
    / "diagnostic_per_feature.csv"
)

feature_df.to_csv(
    feature_output,
    index=False
)

print(
    f"[SAVED] {feature_output}"
)


# ================================================================
# SENSOR / LANE ANALYSIS
# ================================================================

print_header(
    "SENSOR / LANE ERROR ANALYSIS"
)

sensor_results = []


for (
    sensor,
    lane
), group in feature_df.groupby(
    ["sensor", "lane"],
    dropna=False
):

    indices = (
        group[
            "feature_index"
        ]
        .astype(int)
        .tolist()
    )

    if not indices:

        continue

    lstm_errors = (
        lstm_abs_error[
            :,
            indices
        ]
    )

    persistence_errors = (
        persistence_abs_error[
            :,
            indices
        ]
    )

    lstm_sq = (
        lstm_squared_error[
            :,
            indices
        ]
    )

    persistence_sq = (
        persistence_squared_error[
            :,
            indices
        ]
    )

    lstm_mae = np.mean(
        lstm_errors
    )

    persistence_mae = np.mean(
        persistence_errors
    )

    lstm_rmse = np.sqrt(
        np.mean(
            lstm_sq
        )
    )

    persistence_rmse = np.sqrt(
        np.mean(
            persistence_sq
        )
    )

    sensor_results.append({

        "sensor":
            sensor,

        "lane":
            lane,

        "feature_count":
            len(indices),

        "lstm_mae":
            lstm_mae,

        "persistence_mae":
            persistence_mae,

        "lstm_rmse":
            lstm_rmse,

        "persistence_rmse":
            persistence_rmse,

        "mae_advantage_lstm":
            persistence_mae
            - lstm_mae,

        "rmse_advantage_lstm":
            persistence_rmse
            - lstm_rmse,

    })


sensor_df = pd.DataFrame(
    sensor_results
)


if not sensor_df.empty:

    sensor_df = sensor_df.sort_values(
        "lstm_mae",
        ascending=False
    )


sensor_output = (
    DIAGNOSTIC_DIR
    / "diagnostic_per_sensor_lane.csv"
)

sensor_df.to_csv(
    sensor_output,
    index=False
)

print(
    f"[SAVED] {sensor_output}"
)


# ================================================================
# WIN RATE PER FEATURE
# ================================================================

print_header(
    "FEATURE WIN RATE"
)

feature_mae_wins = (
    feature_df[
        "mae_winner"
    ]
    == "LSTM"
).sum()

feature_rmse_wins = (
    feature_df[
        "rmse_winner"
    ]
    == "LSTM"
).sum()

print(
    f"[INFO] LSTM better MAE  : "
    f"{feature_mae_wins}/{N_FEATURES}"
)

print(
    f"[INFO] LSTM better RMSE : "
    f"{feature_rmse_wins}/{N_FEATURES}"
)


# ================================================================
# TOP / BEST FEATURES
# ================================================================

print_header(
    "TOP WORST FEATURES"
)

worst_features = (
    feature_df
    .sort_values(
        "lstm_mae",
        ascending=False
    )
    .head(15)
)

print(
    worst_features[
        [
            "feature_index",
            "feature_name",
            "sensor",
            "lane",
            "lstm_mae",
            "persistence_mae",
            "mae_winner",
        ]
    ].to_string(
        index=False
    )
)


print_header(
    "TOP LSTM ADVANTAGE FEATURES"
)

best_features = (
    feature_df
    .sort_values(
        "mae_advantage_lstm",
        ascending=False
    )
    .head(15)
)

print(
    best_features[
        [
            "feature_index",
            "feature_name",
            "sensor",
            "lane",
            "lstm_mae",
            "persistence_mae",
            "mae_advantage_lstm",
        ]
    ].to_string(
        index=False
    )
)


# ================================================================
# SENSOR SUMMARY
# ================================================================

print_header(
    "SENSOR / LANE SUMMARY"
)

if sensor_df.empty:

    print(
        "[WARNING] Tidak ada mapping "
        "sensor/lane yang berhasil."
    )

else:

    print(
        sensor_df.to_string(
            index=False
        )
    )


# ================================================================
# TRAFFIC CHANGE ANALYSIS
# ================================================================

print_header(
    "TRAFFIC CHANGE ANALYSIS"
)

# Per sample:
#
# Mean absolute change antara input terakhir
# dan target aktual.
#
# Karena final model menggunakan horizon 1,
# perubahan traffic dihitung sebagai:
#
# |y(t+1) - x(t)|
#
# Persistence menggunakan x(t).

if TIMESTEP_MATRIX_PATH.exists():

    timestep_matrix = np.load(
        TIMESTEP_MATRIX_PATH
    )

    if timestep_matrix.ndim == 2:

        print(
            f"[INFO] Timestep matrix : "
            f"{timestep_matrix.shape}"
        )

        # Test segment sesuai final model:
        total_timesteps = (
            len(timestep_matrix)
        )

        train_end = int(
            total_timesteps * 0.70
        )

        val_end = (
            train_end
            + int(
                total_timesteps * 0.15
            )
        )

        test_raw = (
            timestep_matrix[
                val_end:
            ]
        )

        # Final test memiliki 442 samples.
        #
        # Input terakhir untuk setiap sample
        # berada tepat sebelum target.

        if len(test_raw) >= N_SAMPLES + 1:

            last_input = (
                test_raw[
                    :N_SAMPLES
                ]
            )

            traffic_change = np.mean(
                np.abs(
                    actual
                    - last_input
                ),
                axis=1
            )

        else:

            print(
                "[WARNING] Timestep matrix "
                "tidak cukup untuk alignment."
            )

            traffic_change = np.mean(
                np.abs(
                    actual
                    - persistence
                ),
                axis=1
            )

    else:

        traffic_change = np.mean(
            np.abs(
                actual
                - persistence
            ),
            axis=1
        )

else:

    print(
        "[WARNING] timestep_matrix.npy "
        "tidak ditemukan."
    )

    traffic_change = np.mean(
        np.abs(
            actual
            - persistence
        ),
        axis=1
    )


sample_lstm_mae = np.mean(
    lstm_abs_error,
    axis=1
)

sample_persistence_mae = np.mean(
    persistence_abs_error,
    axis=1
)

sample_lstm_rmse = np.sqrt(
    np.mean(
        lstm_squared_error,
        axis=1
    )
)

sample_persistence_rmse = np.sqrt(
    np.mean(
        persistence_squared_error,
        axis=1
    )
)


traffic_df = pd.DataFrame({

    "sample_index":
        np.arange(N_SAMPLES),

    "traffic_change":
        traffic_change,

    "lstm_mae":
        sample_lstm_mae,

    "persistence_mae":
        sample_persistence_mae,

    "lstm_rmse":
        sample_lstm_rmse,

    "persistence_rmse":
        sample_persistence_rmse,

})


traffic_df["lstm_mae_advantage"] = (
    traffic_df["persistence_mae"]
    - traffic_df["lstm_mae"]
)


traffic_df["lstm_rmse_advantage"] = (
    traffic_df["persistence_rmse"]
    - traffic_df["lstm_rmse"]
)


# ================================================================
# TRAFFIC CHANGE GROUPS
# ================================================================

q1 = traffic_df[
    "traffic_change"
].quantile(0.33)

q2 = traffic_df[
    "traffic_change"
].quantile(0.66)


def classify_change(value):

    if value <= q1:

        return "low"

    elif value <= q2:

        return "medium"

    return "high"


traffic_df["traffic_change_group"] = (
    traffic_df[
        "traffic_change"
    ]
    .apply(
        classify_change
    )
)


traffic_output = (
    DIAGNOSTIC_DIR
    / "traffic_change_diagnostic.csv"
)

traffic_df.to_csv(
    traffic_output,
    index=False
)

print(
    f"[SAVED] {traffic_output}"
)


# ================================================================
# TRAFFIC GROUP SUMMARY
# ================================================================

traffic_summary = []

for group_name, group in (
    traffic_df.groupby(
        "traffic_change_group"
    )
):

    sample_count = len(group)

    mae_win_rate = (
        np.mean(
            group[
                "lstm_mae"
            ]
            <
            group[
                "persistence_mae"
            ]
        )
        * 100
    )

    rmse_win_rate = (
        np.mean(
            group[
                "lstm_rmse"
            ]
            <
            group[
                "persistence_rmse"
            ]
        )
        * 100
    )

    traffic_summary.append({

        "traffic_group":
            group_name,

        "samples":
            sample_count,

        "mean_traffic_change":
            group[
                "traffic_change"
            ].mean(),

        "lstm_mae":
            group[
                "lstm_mae"
            ].mean(),

        "persistence_mae":
            group[
                "persistence_mae"
            ].mean(),

        "lstm_mae_win_rate":
            mae_win_rate,

        "lstm_rmse_win_rate":
            rmse_win_rate,

    })


traffic_summary_df = pd.DataFrame(
    traffic_summary
)

traffic_summary_path = (
    DIAGNOSTIC_DIR
    / "traffic_change_summary.csv"
)

traffic_summary_df.to_csv(
    traffic_summary_path,
    index=False
)

print(
    f"[SAVED] {traffic_summary_path}"
)


print_header(
    "TRAFFIC CHANGE SUMMARY"
)

print(
    traffic_summary_df.to_string(
        index=False
    )
)


# ================================================================
# UNKNOWN MAPPING DIAGNOSTIC
# ================================================================

print_header(
    "UNKNOWN MAPPING DIAGNOSTIC"
)

if len(unknown_features) > 0:

    print(
        f"[WARNING] "
        f"{len(unknown_features)} feature "
        f"belum memiliki sensor/lane."
    )

    print(
        "\n[UNKNOWN FEATURES]"
    )

    print(
        unknown_features[
            [
                "feature_index",
                "feature_name",
                "sensor",
                "lane",
            ]
        ].to_string(
            index=False
        )
    )

else:

    print(
        "[OK] Semua feature berhasil "
        "dipetakan ke sensor/lane."
    )


# ================================================================
# SAVE UNKNOWN FEATURES
# ================================================================

unknown_output = (
    DIAGNOSTIC_DIR
    / "unknown_feature_mapping.csv"
)

unknown_features.to_csv(
    unknown_output,
    index=False
)

print(
    f"[SAVED] {unknown_output}"
)


# ================================================================
# PLOT 1: FEATURE MAE
# ================================================================

print_header(
    "CREATING DIAGNOSTIC PLOTS"
)

plot_df = (
    feature_df
    .sort_values(
        "lstm_mae",
        ascending=False
    )
    .head(20)
    .sort_values(
        "lstm_mae"
    )
)

plt.figure(
    figsize=(12, 8)
)

plt.barh(
    plot_df[
        "feature_index"
    ].astype(str),
    plot_df[
        "lstm_mae"
    ],
    label="LSTM"
)

plt.barh(
    plot_df[
        "feature_index"
    ].astype(str),
    plot_df[
        "persistence_mae"
    ],
    alpha=0.6,
    label="Persistence"
)

plt.xlabel(
    "MAE"
)

plt.ylabel(
    "Feature Index"
)

plt.title(
    "Top 20 Worst Features: LSTM vs Persistence"
)

plt.legend()

plt.tight_layout()

plot_path = (
    PLOTS_DIR
    / "top20_worst_features_mae.png"
)

plt.savefig(
    plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {plot_path}"
)


# ================================================================
# PLOT 2: SENSOR / LANE
# ================================================================

if not sensor_df.empty:

    sensor_plot = (
        sensor_df
        .sort_values(
            "lstm_mae",
            ascending=True
        )
    )

    labels = (
        sensor_plot[
            "sensor"
        ]
        + " / "
        + sensor_plot[
            "lane"
        ]
    )

    x = np.arange(
        len(sensor_plot)
    )

    width = 0.35

    plt.figure(
        figsize=(12, 8)
    )

    plt.bar(
        x - width / 2,
        sensor_plot[
            "lstm_mae"
        ],
        width,
        label="LSTM"
    )

    plt.bar(
        x + width / 2,
        sensor_plot[
            "persistence_mae"
        ],
        width,
        label="Persistence"
    )

    plt.xticks(
        x,
        labels,
        rotation=45,
        ha="right"
    )

    plt.ylabel(
        "MAE"
    )

    plt.title(
        "MAE by Sensor / Lane"
    )

    plt.legend()

    plt.tight_layout()

    plot_path = (
        PLOTS_DIR
        / "mae_per_sensor_lane.png"
    )

    plt.savefig(
        plot_path,
        dpi=200
    )

    plt.close()

    print(
        f"[SAVED] {plot_path}"
    )


# ================================================================
# PLOT 3: TRAFFIC CHANGE VS ADVANTAGE
# ================================================================

plt.figure(
    figsize=(10, 7)
)

plt.scatter(
    traffic_df[
        "traffic_change"
    ],
    traffic_df[
        "lstm_mae_advantage"
    ],
    alpha=0.65
)

plt.axhline(
    0,
    linestyle="--"
)

plt.xlabel(
    "Traffic Change"
)

plt.ylabel(
    "LSTM MAE Advantage"
)

plt.title(
    "Traffic Change vs LSTM MAE Advantage"
)

plt.tight_layout()

plot_path = (
    PLOTS_DIR
    / "traffic_change_vs_lstm_advantage.png"
)

plt.savefig(
    plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {plot_path}"
)


# ================================================================
# PLOT 4: LSTM ADVANTAGE DISTRIBUTION
# ================================================================

plt.figure(
    figsize=(10, 7)
)

plt.hist(
    feature_df[
        "mae_advantage_lstm"
    ],
    bins=20,
    alpha=0.8
)

plt.axvline(
    0,
    linestyle="--"
)

plt.xlabel(
    "MAE Advantage of LSTM"
)

plt.ylabel(
    "Number of Features"
)

plt.title(
    "Distribution of LSTM MAE Advantage"
)

plt.tight_layout()

plot_path = (
    PLOTS_DIR
    / "lstm_mae_advantage_distribution.png"
)

plt.savefig(
    plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {plot_path}"
)


# ================================================================
# FINAL REPORT
# ================================================================

print_header(
    "BUILDING DIAGNOSTIC REPORT"
)

report = {

    "dataset":
        "YOLO Traffic Dataset",

    "samples":
        int(N_SAMPLES),

    "features":
        int(N_FEATURES),

    "final_configuration":
        final_config,

    "mapping": {

        "total_features":
            int(len(feature_mapping)),

        "mapped_features":
            int(len(mapped_features)),

        "unknown_features":
            int(len(unknown_features)),

        "mapping_coverage_percent":
            float(mapping_percentage),

        "detected_sensor_lane_pairs":
            [
                {
                    "sensor": sensor,
                    "lane": lane,
                }
                for sensor, lane
                in detected_pairs
            ],

    },

    "feature_results": {

        "lstm_better_mae":
            int(feature_mae_wins),

        "lstm_better_rmse":
            int(feature_rmse_wins),

        "total_features":
            int(N_FEATURES),

    },

    "traffic_change": {

        "q33":
            float(q1),

        "q66":
            float(q2),

    },

    "files": {

        "feature_mapping":
            str(feature_mapping_path),

        "feature_diagnostic":
            str(feature_output),

        "sensor_lane_diagnostic":
            str(sensor_output),

        "traffic_change":
            str(traffic_output),

        "traffic_summary":
            str(traffic_summary_path),

        "unknown_mapping":
            str(unknown_output),

    },

}


report_path = (
    DIAGNOSTIC_DIR
    / "feature_sensor_diagnostic_report.json"
)


with open(
    report_path,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        report,
        f,
        indent=4
    )


print(
    f"[SAVED] {report_path}"
)


# ================================================================
# FINAL SUMMARY
# ================================================================

print_header(
    "FEATURE / SENSOR DIAGNOSTIC SUMMARY"
)

print(
    f"Total features       : {N_FEATURES}"
)

print(
    f"Mapped features      : {len(mapped_features)}"
)

print(
    f"Unknown features     : {len(unknown_features)}"
)

print(
    f"Mapping coverage     : "
    f"{mapping_percentage:.2f}%"
)

print()

print(
    f"LSTM better MAE      : "
    f"{feature_mae_wins}/{N_FEATURES}"
)

print(
    f"LSTM better RMSE     : "
    f"{feature_rmse_wins}/{N_FEATURES}"
)

print()

if not sensor_df.empty:

    worst_sensor = (
        sensor_df
        .sort_values(
            "lstm_mae",
            ascending=False
        )
        .iloc[0]
    )

    print(
        "Worst sensor/lane:"
    )

    print(
        f"  {worst_sensor['sensor']} / "
        f"{worst_sensor['lane']}"
    )

    print(
        f"  LSTM MAE : "
        f"{worst_sensor['lstm_mae']:.6f}"
    )

    print(
        f"  Persistence MAE : "
        f"{worst_sensor['persistence_mae']:.6f}"
    )

else:

    print(
        "[WARNING] Sensor/lane mapping "
        "belum berhasil."
    )


print()

print(
    "[OUTPUT DIRECTORY]"
)

print(
    DIAGNOSTIC_DIR
)

print_header(
    "FEATURE / SENSOR DIAGNOSTIC COMPLETED"
)