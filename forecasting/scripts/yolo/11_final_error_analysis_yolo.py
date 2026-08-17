from pathlib import Path
import json
import pickle
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")


# ======================================================================
# CONFIGURATION
# ======================================================================

SEED = 42

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "yolo"
)

PROCESSED_DIR = OUTPUT_DIR / "processed"

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

PLOTS_DIR = (
    ERROR_ANALYSIS_DIR
    / "plots"
)

ERROR_ANALYSIS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

PLOTS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ======================================================================
# FILE PATHS
# ======================================================================

ACTUAL_PATH = (
    FINAL_MODEL_DIR
    / "y_test_actual_final_original.npy"
)

PREDICTION_PATH = (
    FINAL_MODEL_DIR
    / "y_test_prediction_final_original.npy"
)

PERSISTENCE_PATH = (
    FINAL_MODEL_DIR
    / "persistence_prediction_final_original.npy"
)

FINAL_METRICS_PATH = (
    FINAL_MODEL_DIR
    / "final_model_metrics.json"
)

FINAL_CONFIG_PATH = (
    FINAL_MODEL_DIR
    / "final_model_config.json"
)

FEATURE_METADATA_PATH = (
    PROCESSED_DIR
    / "feature_metadata.json"
)


# ======================================================================
# REPRODUCIBILITY
# ======================================================================

np.random.seed(SEED)


# ======================================================================
# HELPER FUNCTIONS
# ======================================================================

def print_section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def safe_mae(actual, prediction):
    return float(
        np.mean(
            np.abs(
                actual - prediction
            )
        )
    )


def safe_rmse(actual, prediction):
    return float(
        np.sqrt(
            np.mean(
                (actual - prediction) ** 2
            )
        )
    )


def safe_mse(actual, prediction):
    return float(
        np.mean(
            (actual - prediction) ** 2
        )
    )


def validate_numeric(name, array):
    nan_count = int(np.isnan(array).sum())
    inf_count = int(np.isinf(array).sum())

    print(
        f"[INFO] {name:<15} | "
        f"NaN: {nan_count:<6} | "
        f"Inf: {inf_count:<6}"
    )

    if nan_count > 0 or inf_count > 0:
        raise ValueError(
            f"[ERROR] {name} mengandung NaN/Inf."
        )


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def flatten_feature_metadata(metadata):
    """
    Mengubah berbagai kemungkinan struktur feature_metadata.json
    menjadi list metadata feature.
    """

    if isinstance(metadata, list):
        return metadata

    if isinstance(metadata, dict):

        # Common structure:
        # {
        #   "features": [...]
        # }

        if "features" in metadata:
            features = metadata["features"]

            if isinstance(features, list):
                return features

        # Alternative:
        # {
        #   "feature_names": [...]
        # }

        if "feature_names" in metadata:
            names = metadata["feature_names"]

            if isinstance(names, list):
                return [
                    {
                        "feature_name": str(name)
                    }
                    for name in names
                ]

        # Alternative dictionary keyed by feature index
        numeric_keys = True

        try:
            sorted_items = sorted(
                metadata.items(),
                key=lambda x: int(x[0])
            )
        except Exception:
            numeric_keys = False

        if numeric_keys:
            return [
                value
                for _, value in sorted_items
            ]

    raise ValueError(
        "[ERROR] Struktur feature_metadata.json "
        "tidak dikenali."
    )


def get_feature_name(item, index):
    """
    Mengambil nama feature dari metadata dengan fallback aman.
    """

    if isinstance(item, str):
        return item

    if isinstance(item, dict):

        possible_keys = [
            "feature_name",
            "name",
            "feature",
            "column",
            "full_name"
        ]

        for key in possible_keys:
            if key in item:
                return str(item[key])

    return f"feature_{index}"


def parse_sensor_lane(feature_name):
    """
    Mencoba mengambil informasi sensor/lane dari nama feature.

    Contoh:
        south/lane_2/density_index
        south_lane_2_density_index
        south / lane_2 : density_index

    Fallback:
        sensor = feature_name
    """

    name = str(feature_name)

    normalized = (
        name
        .replace("\\", "/")
        .replace(":", "/")
        .replace(" ", "")
    )

    parts = [
        p
        for p in normalized.split("/")
        if p
    ]

    sensor = None
    lane = None
    feature = name

    for i, part in enumerate(parts):

        lower = part.lower()

        if lower.startswith("lane_"):
            lane = part

            if i > 0:
                sensor = parts[i - 1]

            if i + 1 < len(parts):
                feature = parts[i + 1]

            break

    if sensor is None:
        lower_name = name.lower()

        known_sensors = [
            "north",
            "south",
            "east",
            "west"
        ]

        for s in known_sensors:
            if s in lower_name:
                sensor = s
                break

    if sensor is None:
        sensor = "unknown_sensor"

    if lane is None:
        lane = "unknown_lane"

    return sensor, lane, feature


# ======================================================================
# HEADER
# ======================================================================

print_section(
    "YOLO TRAFFIC LSTM FINAL MODEL ERROR ANALYSIS"
)

print(
    f"[INFO] Project root       : {PROJECT_ROOT}"
)

print(
    f"[INFO] Final model dir    : {FINAL_MODEL_DIR}"
)

print(
    f"[INFO] Error analysis dir : {ERROR_ANALYSIS_DIR}"
)


# ======================================================================
# VALIDATING REQUIRED FILES
# ======================================================================

print_section(
    "VALIDATING REQUIRED FILES"
)

required_files = {
    "Actual test target": ACTUAL_PATH,
    "LSTM prediction": PREDICTION_PATH,
    "Persistence prediction": PERSISTENCE_PATH,
    "Final metrics": FINAL_METRICS_PATH,
    "Final config": FINAL_CONFIG_PATH,
    "Feature metadata": FEATURE_METADATA_PATH,
}

for label, path in required_files.items():

    if not path.exists():
        raise FileNotFoundError(
            f"""
[ERROR] Required file tidak ditemukan:
{path}
"""
        )

    print(
        f"[OK] {label:<22}: {path.name}"
    )

print(
    "[OK] Semua required files tersedia."
)


# ======================================================================
# LOADING PREDICTIONS
# ======================================================================

print_section(
    "LOADING FINAL TEST PREDICTIONS"
)

y_actual = np.load(
    ACTUAL_PATH
)

y_lstm = np.load(
    PREDICTION_PATH
)

y_persistence = np.load(
    PERSISTENCE_PATH
)

print(
    f"[INFO] Actual       : {y_actual.shape}"
)

print(
    f"[INFO] LSTM         : {y_lstm.shape}"
)

print(
    f"[INFO] Persistence  : {y_persistence.shape}"
)


# ======================================================================
# SHAPE VALIDATION
# ======================================================================

if y_actual.shape != y_lstm.shape:
    raise ValueError(
        "[ERROR] Shape actual dan LSTM prediction berbeda."
    )

if y_actual.shape != y_persistence.shape:
    raise ValueError(
        "[ERROR] Shape actual dan persistence prediction berbeda."
    )

if y_actual.ndim != 2:
    raise ValueError(
        "[ERROR] Prediction harus berbentuk "
        "(samples, features)."
    )

N_SAMPLES, N_FEATURES = y_actual.shape

print(
    f"[INFO] Samples  : {N_SAMPLES}"
)

print(
    f"[INFO] Features : {N_FEATURES}"
)


# ======================================================================
# NUMERICAL VALIDATION
# ======================================================================

print_section(
    "NUMERICAL DATA VALIDATION"
)

validate_numeric(
    "Actual",
    y_actual
)

validate_numeric(
    "LSTM",
    y_lstm
)

validate_numeric(
    "Persistence",
    y_persistence
)

print(
    "[OK] Semua prediction numerically valid."
)


# ======================================================================
# LOAD METADATA
# ======================================================================

print_section(
    "LOADING FINAL MODEL CONFIGURATION"
)

final_metrics = load_json(
    FINAL_METRICS_PATH
)

final_config = load_json(
    FINAL_CONFIG_PATH
)

print(
    "[INFO] Final model configuration:"
)

for key, value in final_config.items():
    print(
        f"       {key}: {value}"
    )


# ======================================================================
# FEATURE METADATA
# ======================================================================

print_section(
    "BUILDING FEATURE METADATA"
)

feature_metadata_raw = load_json(
    FEATURE_METADATA_PATH
)

feature_metadata = flatten_feature_metadata(
    feature_metadata_raw
)

if len(feature_metadata) != N_FEATURES:
    print(
        "[WARNING] Jumlah metadata feature "
        f"({len(feature_metadata)}) "
        f"berbeda dengan jumlah prediction feature "
        f"({N_FEATURES})."
    )

feature_names = []

for i in range(N_FEATURES):

    if i < len(feature_metadata):
        name = get_feature_name(
            feature_metadata[i],
            i
        )
    else:
        name = f"feature_{i}"

    feature_names.append(name)

print(
    f"[OK] Feature metadata : {len(feature_names)} features"
)


# ======================================================================
# ERROR MATRICES
# ======================================================================

print_section(
    "CALCULATING ERROR MATRICES"
)

lstm_error = (
    y_lstm - y_actual
)

persistence_error = (
    y_persistence - y_actual
)

lstm_abs_error = np.abs(
    lstm_error
)

persistence_abs_error = np.abs(
    persistence_error
)

lstm_squared_error = (
    lstm_error ** 2
)

persistence_squared_error = (
    persistence_error ** 2
)

print(
    f"[INFO] LSTM error matrix        : "
    f"{lstm_error.shape}"
)

print(
    f"[INFO] Persistence error matrix : "
    f"{persistence_error.shape}"
)


# ======================================================================
# GLOBAL METRICS
# ======================================================================

print_section(
    "CALCULATING GLOBAL PERFORMANCE"
)

lstm_mae = safe_mae(
    y_actual,
    y_lstm
)

lstm_rmse = safe_rmse(
    y_actual,
    y_lstm
)

lstm_mse = safe_mse(
    y_actual,
    y_lstm
)

persistence_mae = safe_mae(
    y_actual,
    y_persistence
)

persistence_rmse = safe_rmse(
    y_actual,
    y_persistence
)

persistence_mse = safe_mse(
    y_actual,
    y_persistence
)

mae_improvement = (
    (persistence_mae - lstm_mae)
    / persistence_mae
    * 100
)

rmse_improvement = (
    (persistence_rmse - lstm_rmse)
    / persistence_rmse
    * 100
)

mse_improvement = (
    (persistence_mse - lstm_mse)
    / persistence_mse
    * 100
)

print()
print("LSTM FINAL MODEL")
print(
    f"  MAE  : {lstm_mae:.6f}"
)
print(
    f"  RMSE : {lstm_rmse:.6f}"
)
print(
    f"  MSE  : {lstm_mse:.6f}"
)

print()
print("PERSISTENCE BASELINE")
print(
    f"  MAE  : {persistence_mae:.6f}"
)
print(
    f"  RMSE : {persistence_rmse:.6f}"
)
print(
    f"  MSE  : {persistence_mse:.6f}"
)

print()
print("LSTM IMPROVEMENT OVER PERSISTENCE")
print(
    f"  MAE  : {mae_improvement:.2f}%"
)
print(
    f"  RMSE : {rmse_improvement:.2f}%"
)
print(
    f"  MSE  : {mse_improvement:.2f}%"
)


# ======================================================================
# FEATURE-LEVEL ANALYSIS
# ======================================================================

print_section(
    "FEATURE-LEVEL ERROR ANALYSIS"
)

feature_rows = []

for i in range(N_FEATURES):

    actual = y_actual[:, i]

    lstm_pred = y_lstm[:, i]

    persistence_pred = y_persistence[:, i]

    lstm_feature_mae = safe_mae(
        actual,
        lstm_pred
    )

    lstm_feature_rmse = safe_rmse(
        actual,
        lstm_pred
    )

    persistence_feature_mae = safe_mae(
        actual,
        persistence_pred
    )

    persistence_feature_rmse = safe_rmse(
        actual,
        persistence_pred
    )

    mae_difference = (
        persistence_feature_mae
        - lstm_feature_mae
    )

    rmse_difference = (
        persistence_feature_rmse
        - lstm_feature_rmse
    )

    feature_rows.append({
        "feature_index": i,
        "feature_name": feature_names[i],
        "lstm_mae": lstm_feature_mae,
        "lstm_rmse": lstm_feature_rmse,
        "persistence_mae": persistence_feature_mae,
        "persistence_rmse": persistence_feature_rmse,
        "mae_improvement": mae_difference,
        "rmse_improvement": rmse_difference,
        "lstm_better_mae": (
            lstm_feature_mae
            < persistence_feature_mae
        ),
        "lstm_better_rmse": (
            lstm_feature_rmse
            < persistence_feature_rmse
        ),
    })


feature_df = pd.DataFrame(
    feature_rows
)

feature_df = feature_df.sort_values(
    "lstm_mae",
    ascending=False
)

feature_path = (
    ERROR_ANALYSIS_DIR
    / "final_error_analysis_per_feature.csv"
)

feature_df.to_csv(
    feature_path,
    index=False
)

print(
    f"[SAVED] {feature_path}"
)


# ======================================================================
# SENSOR-LEVEL ANALYSIS
# ======================================================================

print_section(
    "SENSOR-LEVEL ERROR ANALYSIS"
)

sensor_rows = []

for i, feature_name in enumerate(
    feature_names
):

    sensor, lane, feature = parse_sensor_lane(
        feature_name
    )

    sensor_rows.append({
        "feature_index": i,
        "feature_name": feature_name,
        "sensor": sensor,
        "lane": lane,
        "feature": feature,
    })


sensor_metadata_df = pd.DataFrame(
    sensor_rows
)

sensor_metadata_df[
    "lstm_mae"
] = lstm_abs_error.mean(axis=0)

sensor_metadata_df[
    "lstm_rmse"
] = np.sqrt(
    lstm_squared_error.mean(axis=0)
)

sensor_metadata_df[
    "persistence_mae"
] = persistence_abs_error.mean(axis=0)

sensor_metadata_df[
    "persistence_rmse"
] = np.sqrt(
    persistence_squared_error.mean(axis=0)
)

sensor_metadata_df[
    "mae_improvement"
] = (
    sensor_metadata_df["persistence_mae"]
    - sensor_metadata_df["lstm_mae"]
)

sensor_metadata_df[
    "rmse_improvement"
] = (
    sensor_metadata_df["persistence_rmse"]
    - sensor_metadata_df["lstm_rmse"]
)


sensor_group_df = (
    sensor_metadata_df
    .groupby(
        ["sensor", "lane"],
        dropna=False
    )
    .agg(
        feature_count=(
            "feature_index",
            "count"
        ),
        lstm_mae=(
            "lstm_mae",
            "mean"
        ),
        lstm_rmse=(
            "lstm_rmse",
            "mean"
        ),
        persistence_mae=(
            "persistence_mae",
            "mean"
        ),
        persistence_rmse=(
            "persistence_rmse",
            "mean"
        ),
        mae_improvement=(
            "mae_improvement",
            "mean"
        ),
        rmse_improvement=(
            "rmse_improvement",
            "mean"
        ),
    )
    .reset_index()
)

sensor_group_df[
    "lstm_better_mae"
] = (
    sensor_group_df["lstm_mae"]
    < sensor_group_df["persistence_mae"]
)

sensor_group_df[
    "lstm_better_rmse"
] = (
    sensor_group_df["lstm_rmse"]
    < sensor_group_df["persistence_rmse"]
)

sensor_group_df = sensor_group_df.sort_values(
    "lstm_mae",
    ascending=False
)

sensor_path = (
    ERROR_ANALYSIS_DIR
    / "final_error_analysis_per_sensor.csv"
)

sensor_group_df.to_csv(
    sensor_path,
    index=False
)

print(
    f"[SAVED] {sensor_path}"
)


# ======================================================================
# SAMPLE-LEVEL ANALYSIS
# ======================================================================

print_section(
    "SAMPLE-LEVEL ERROR ANALYSIS"
)

sample_lstm_mae = (
    lstm_abs_error.mean(axis=1)
)

sample_persistence_mae = (
    persistence_abs_error.mean(axis=1)
)

sample_lstm_rmse = np.sqrt(
    lstm_squared_error.mean(axis=1)
)

sample_persistence_rmse = np.sqrt(
    persistence_squared_error.mean(axis=1)
)

sample_df = pd.DataFrame({
    "sample_index": np.arange(N_SAMPLES),

    "lstm_mae": sample_lstm_mae,

    "persistence_mae":
        sample_persistence_mae,

    "lstm_rmse": sample_lstm_rmse,

    "persistence_rmse":
        sample_persistence_rmse,

    "lstm_mae_better":
        sample_lstm_mae
        < sample_persistence_mae,

    "lstm_rmse_better":
        sample_lstm_rmse
        < sample_persistence_rmse,
})

sample_df[
    "mae_difference"
] = (
    sample_df["persistence_mae"]
    - sample_df["lstm_mae"]
)

sample_df[
    "rmse_difference"
] = (
    sample_df["persistence_rmse"]
    - sample_df["lstm_rmse"]
)

sample_path = (
    ERROR_ANALYSIS_DIR
    / "final_sample_level_error_analysis.csv"
)

sample_df.to_csv(
    sample_path,
    index=False
)

print(
    f"[SAVED] {sample_path}"
)

mae_win_rate = (
    sample_df["lstm_mae_better"]
    .mean()
    * 100
)

rmse_win_rate = (
    sample_df["lstm_rmse_better"]
    .mean()
    * 100
)

print()
print(
    f"[INFO] LSTM MAE win rate  : "
    f"{mae_win_rate:.2f}%"
)

print(
    f"[INFO] LSTM RMSE win rate : "
    f"{rmse_win_rate:.2f}%"
)


# ======================================================================
# TRAFFIC CHANGE ANALYSIS
# ======================================================================

print_section(
    "ANALYZING TRAFFIC CHANGE"
)

"""
Traffic change didefinisikan sebagai perubahan absolut
antara input terakhir dan target.

Karena input sequence tidak tersedia di final model output,
kita menggunakan persistence prediction sebagai proxy kondisi
sebelumnya:

    traffic_change =
        |actual - persistence|

Ini konsisten dengan konsep persistence:
prediction persistence = kondisi terakhir yang diketahui.
"""

traffic_change = np.mean(
    np.abs(
        y_actual - y_persistence
    ),
    axis=1
)

sample_df[
    "traffic_change"
] = traffic_change

# Quantile-based grouping
low_threshold = np.quantile(
    traffic_change,
    0.33
)

high_threshold = np.quantile(
    traffic_change,
    0.67
)

def classify_change(value):

    if value <= low_threshold:
        return "low"

    if value >= high_threshold:
        return "high"

    return "medium"


sample_df[
    "traffic_change_group"
] = [
    classify_change(x)
    for x in traffic_change
]


traffic_group_df = (
    sample_df
    .groupby(
        "traffic_change_group"
    )
    .agg(
        sample_count=(
            "sample_index",
            "count"
        ),
        mean_traffic_change=(
            "traffic_change",
            "mean"
        ),
        lstm_mae=(
            "lstm_mae",
            "mean"
        ),
        persistence_mae=(
            "persistence_mae",
            "mean"
        ),
        lstm_rmse=(
            "lstm_rmse",
            "mean"
        ),
        persistence_rmse=(
            "persistence_rmse",
            "mean"
        ),
        lstm_mae_win_rate=(
            "lstm_mae_better",
            "mean"
        ),
        lstm_rmse_win_rate=(
            "lstm_rmse_better",
            "mean"
        ),
    )
    .reset_index()
)

traffic_group_df[
    "lstm_mae_win_rate"
] *= 100

traffic_group_df[
    "lstm_rmse_win_rate"
] *= 100

traffic_path = (
    ERROR_ANALYSIS_DIR
    / "traffic_change_final_analysis.csv"
)

traffic_group_df.to_csv(
    traffic_path,
    index=False
)

print(
    f"[SAVED] {traffic_path}"
)


# ======================================================================
# PREDICTION BIAS
# ======================================================================

print_section(
    "ANALYZING PREDICTION BIAS"
)

bias_rows = []

for i in range(N_FEATURES):

    error = lstm_error[:, i]

    bias = float(
        np.mean(error)
    )

    mean_actual = float(
        np.mean(y_actual[:, i])
    )

    mean_prediction = float(
        np.mean(y_lstm[:, i])
    )

    bias_percentage = (
        bias
        / (abs(mean_actual) + 1e-8)
        * 100
    )

    if bias > 0:
        direction = "overprediction"

    elif bias < 0:
        direction = "underprediction"

    else:
        direction = "neutral"

    bias_rows.append({
        "feature_index": i,
        "feature_name": feature_names[i],
        "mean_actual": mean_actual,
        "mean_prediction": mean_prediction,
        "bias": bias,
        "bias_percentage": bias_percentage,
        "bias_direction": direction,
    })


bias_df = pd.DataFrame(
    bias_rows
)

bias_path = (
    ERROR_ANALYSIS_DIR
    / "final_prediction_bias_per_feature.csv"
)

bias_df.to_csv(
    bias_path,
    index=False
)

print(
    f"[SAVED] {bias_path}"
)


# ======================================================================
# WORST FEATURES
# ======================================================================

print_section(
    "IDENTIFYING WORST FEATURES"
)

worst_mae = (
    feature_df
    .sort_values(
        "lstm_mae",
        ascending=False
    )
    .head(20)
)

worst_rmse = (
    feature_df
    .sort_values(
        "lstm_rmse",
        ascending=False
    )
    .head(20)
)

worst_mae_path = (
    ERROR_ANALYSIS_DIR
    / "final_worst_features_mae.csv"
)

worst_rmse_path = (
    ERROR_ANALYSIS_DIR
    / "final_worst_features_rmse.csv"
)

worst_mae.to_csv(
    worst_mae_path,
    index=False
)

worst_rmse.to_csv(
    worst_rmse_path,
    index=False
)

print(
    f"[SAVED] {worst_mae_path}"
)

print(
    f"[SAVED] {worst_rmse_path}"
)


# ======================================================================
# WORST SENSORS
# ======================================================================

worst_sensor_mae = (
    sensor_group_df
    .sort_values(
        "lstm_mae",
        ascending=False
    )
    .head(20)
)

worst_sensor_rmse = (
    sensor_group_df
    .sort_values(
        "lstm_rmse",
        ascending=False
    )
    .head(20)
)

worst_sensor_mae_path = (
    ERROR_ANALYSIS_DIR
    / "final_worst_sensors_mae.csv"
)

worst_sensor_rmse_path = (
    ERROR_ANALYSIS_DIR
    / "final_worst_sensors_rmse.csv"
)

worst_sensor_mae.to_csv(
    worst_sensor_mae_path,
    index=False
)

worst_sensor_rmse.to_csv(
    worst_sensor_rmse_path,
    index=False
)

print(
    f"[SAVED] {worst_sensor_mae_path}"
)

print(
    f"[SAVED] {worst_sensor_rmse_path}"
)


# ======================================================================
# FEATURE WIN / LOSS
# ======================================================================

feature_mae_win_count = int(
    (
        feature_df["lstm_better_mae"]
    ).sum()
)

feature_rmse_win_count = int(
    (
        feature_df["lstm_better_rmse"]
    ).sum()
)

feature_mae_win_rate = (
    feature_mae_win_count
    / N_FEATURES
    * 100
)

feature_rmse_win_rate = (
    feature_rmse_win_count
    / N_FEATURES
    * 100
)

sensor_mae_win_count = int(
    (
        sensor_group_df["lstm_better_mae"]
    ).sum()
)

sensor_rmse_win_count = int(
    (
        sensor_group_df["lstm_better_rmse"]
    ).sum()
)

sensor_count = len(
    sensor_group_df
)

sensor_mae_win_rate = (
    sensor_mae_win_count
    / sensor_count
    * 100
    if sensor_count > 0
    else 0
)

sensor_rmse_win_rate = (
    sensor_rmse_win_count
    / sensor_count
    * 100
    if sensor_count > 0
    else 0
)


# ======================================================================
# PLOTS
# ======================================================================

print_section(
    "CREATING FINAL ERROR ANALYSIS PLOTS"
)


# ----------------------------------------------------------------------
# PLOT 1: FEATURE MAE
# ----------------------------------------------------------------------

print(
    "\n----------------------------------------------------------------------"
)

print(
    "PLOTTING FEATURE ERROR COMPARISON"
)

top_features = (
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

y_pos = np.arange(
    len(top_features)
)

plt.barh(
    y_pos - 0.2,
    top_features["lstm_mae"],
    height=0.4,
    label="LSTM"
)

plt.barh(
    y_pos + 0.2,
    top_features["persistence_mae"],
    height=0.4,
    label="Persistence"
)

plt.yticks(
    y_pos,
    top_features["feature_name"]
)

plt.xlabel(
    "MAE"
)

plt.ylabel(
    "Feature"
)

plt.title(
    "Final Model: LSTM vs Persistence MAE - Worst 20 Features"
)

plt.legend()

plt.tight_layout()

feature_plot_path = (
    PLOTS_DIR
    / "final_lstm_vs_persistence_mae_per_feature.png"
)

plt.savefig(
    feature_plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {feature_plot_path}"
)


# ----------------------------------------------------------------------
# PLOT 2: SENSOR MAE
# ----------------------------------------------------------------------

print(
    "\n----------------------------------------------------------------------"
)

print(
    "PLOTTING SENSOR ERROR COMPARISON"
)

top_sensors = (
    sensor_group_df
    .sort_values(
        "lstm_mae",
        ascending=False
    )
    .head(20)
    .sort_values(
        "lstm_mae"
    )
)

sensor_labels = (
    top_sensors["sensor"]
    + " / "
    + top_sensors["lane"]
)

plt.figure(
    figsize=(11, 7)
)

y_pos = np.arange(
    len(top_sensors)
)

plt.barh(
    y_pos - 0.2,
    top_sensors["lstm_mae"],
    height=0.4,
    label="LSTM"
)

plt.barh(
    y_pos + 0.2,
    top_sensors["persistence_mae"],
    height=0.4,
    label="Persistence"
)

plt.yticks(
    y_pos,
    sensor_labels
)

plt.xlabel(
    "MAE"
)

plt.ylabel(
    "Sensor / Lane"
)

plt.title(
    "Final Model: LSTM vs Persistence MAE by Sensor/Lane"
)

plt.legend()

plt.tight_layout()

sensor_plot_path = (
    PLOTS_DIR
    / "final_lstm_vs_persistence_mae_per_sensor.png"
)

plt.savefig(
    sensor_plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {sensor_plot_path}"
)


# ----------------------------------------------------------------------
# PLOT 3: ERROR DISTRIBUTION
# ----------------------------------------------------------------------

print(
    "\n----------------------------------------------------------------------"
)

print(
    "PLOTTING ERROR DISTRIBUTION"
)

plt.figure(
    figsize=(11, 7)
)

plt.hist(
    lstm_error.flatten(),
    bins=100,
    alpha=0.6,
    label="LSTM"
)

plt.hist(
    persistence_error.flatten(),
    bins=100,
    alpha=0.6,
    label="Persistence"
)

plt.axvline(
    0,
    linestyle="--"
)

plt.xlabel(
    "Prediction Error"
)

plt.ylabel(
    "Frequency"
)

plt.title(
    "Final Model Prediction Error Distribution"
)

plt.legend()

plt.tight_layout()

error_distribution_path = (
    PLOTS_DIR
    / "final_prediction_error_distribution.png"
)

plt.savefig(
    error_distribution_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {error_distribution_path}"
)


# ----------------------------------------------------------------------
# PLOT 4: SAMPLE MAE
# ----------------------------------------------------------------------

print(
    "\n----------------------------------------------------------------------"
)

print(
    "PLOTTING SAMPLE-LEVEL MAE"
)

plt.figure(
    figsize=(13, 6)
)

plt.plot(
    sample_df["sample_index"],
    sample_df["lstm_mae"],
    label="LSTM",
    alpha=0.8
)

plt.plot(
    sample_df["sample_index"],
    sample_df["persistence_mae"],
    label="Persistence",
    alpha=0.8
)

plt.xlabel(
    "Test Sample"
)

plt.ylabel(
    "MAE"
)

plt.title(
    "Final Model Sample-Level MAE"
)

plt.legend()

plt.tight_layout()

sample_plot_path = (
    PLOTS_DIR
    / "final_sample_level_mae_lstm_vs_persistence.png"
)

plt.savefig(
    sample_plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {sample_plot_path}"
)


# ----------------------------------------------------------------------
# PLOT 5: TRAFFIC CHANGE VS LSTM ADVANTAGE
# ----------------------------------------------------------------------

print(
    "\n----------------------------------------------------------------------"
)

print(
    "PLOTTING TRAFFIC CHANGE VS LSTM ADVANTAGE"
)

plt.figure(
    figsize=(10, 7)
)

plt.scatter(
    sample_df["traffic_change"],
    sample_df["mae_difference"],
    alpha=0.6
)

plt.axhline(
    0,
    linestyle="--"
)

plt.xlabel(
    "Traffic Change"
)

plt.ylabel(
    "Persistence MAE - LSTM MAE"
)

plt.title(
    "Traffic Change vs LSTM MAE Advantage"
)

plt.tight_layout()

traffic_plot_path = (
    PLOTS_DIR
    / "traffic_change_vs_lstm_advantage.png"
)

plt.savefig(
    traffic_plot_path,
    dpi=200
)

plt.close()

print(
    f"[SAVED] {traffic_plot_path}"
)


# ----------------------------------------------------------------------
# PLOT 6: ACTUAL VS PREDICTION
# ----------------------------------------------------------------------

print(
    "\n----------------------------------------------------------------------"
)

print(
    "PLOTTING ACTUAL VS PREDICTION"
)

feature_candidates = [
    0,
    min(1, N_FEATURES - 1),
    min(10, N_FEATURES - 1),
    min(20, N_FEATURES - 1),
]

for feature_index in feature_candidates:

    feature_name = feature_names[
        feature_index
    ]

    plt.figure(
        figsize=(13, 6)
    )

    plt.plot(
        y_actual[:, feature_index],
        label="Actual",
        linewidth=1.5
    )

    plt.plot(
        y_lstm[:, feature_index],
        label="LSTM",
        linewidth=1.2
    )

    plt.plot(
        y_persistence[:, feature_index],
        label="Persistence",
        linewidth=1.0,
        alpha=0.8
    )

    plt.xlabel(
        "Test Sample"
    )

    plt.ylabel(
        "Value"
    )

    plt.title(
        f"Actual vs Prediction - "
        f"Feature {feature_index}: "
        f"{feature_name}"
    )

    plt.legend()

    plt.tight_layout()

    actual_prediction_path = (
        PLOTS_DIR
        / f"actual_vs_prediction_feature_{feature_index}.png"
    )

    plt.savefig(
        actual_prediction_path,
        dpi=200
    )

    plt.close()

    print(
        f"[SAVED] {actual_prediction_path}"
    )


# ======================================================================
# WORST FEATURE PRINT
# ======================================================================

print_section(
    "TOP WORST FEATURES"
)

for _, row in worst_mae.head(10).iterrows():

    print(
        f"{int(row['feature_index']):>3} | "
        f"{row['feature_name']:<40} | "
        f"LSTM MAE: {row['lstm_mae']:.6f} | "
        f"Persistence MAE: "
        f"{row['persistence_mae']:.6f}"
    )


# ======================================================================
# WORST SENSOR PRINT
# ======================================================================

print_section(
    "TOP WORST SENSOR / LANE"
)

for _, row in worst_sensor_mae.head(10).iterrows():

    print(
        f"{str(row['sensor']):<10} / "
        f"{str(row['lane']):<10} | "
        f"LSTM MAE: {row['lstm_mae']:.6f} | "
        f"Persistence MAE: "
        f"{row['persistence_mae']:.6f}"
    )


# ======================================================================
# TRAFFIC CHANGE SUMMARY
# ======================================================================

print_section(
    "TRAFFIC CHANGE SUMMARY"
)

for _, row in traffic_group_df.iterrows():

    print(
        f"{row['traffic_change_group']:<8} | "
        f"Samples: {int(row['sample_count']):>4} | "
        f"Change: {row['mean_traffic_change']:.6f} | "
        f"LSTM MAE: {row['lstm_mae']:.6f} | "
        f"Persistence MAE: "
        f"{row['persistence_mae']:.6f} | "
        f"LSTM MAE Win: "
        f"{row['lstm_mae_win_rate']:.2f}%"
    )


# ======================================================================
# BUILD REPORT
# ======================================================================

print_section(
    "BUILDING FINAL ERROR ANALYSIS REPORT"
)

best_feature_mae_row = (
    feature_df
    .sort_values(
        "lstm_mae"
    )
    .iloc[0]
)

worst_feature_mae_row = (
    feature_df
    .sort_values(
        "lstm_mae",
        ascending=False
    )
    .iloc[0]
)

best_sensor_mae_row = (
    sensor_group_df
    .sort_values(
        "lstm_mae"
    )
    .iloc[0]
)

worst_sensor_mae_row = (
    sensor_group_df
    .sort_values(
        "lstm_mae",
        ascending=False
    )
    .iloc[0]
)

report = {

    "model": {
        "sequence_length": final_config.get(
            "sequence_length"
        ),
        "forecast_horizon": final_config.get(
            "forecast_horizon"
        ),
        "hidden_size": final_config.get(
            "hidden_size"
        ),
        "num_layers": final_config.get(
            "num_layers"
        ),
        "dropout": final_config.get(
            "dropout"
        ),
        "learning_rate": final_config.get(
            "learning_rate"
        ),
        "batch_size": final_config.get(
            "batch_size"
        ),
    },

    "dataset": {
        "test_samples": N_SAMPLES,
        "features": N_FEATURES,
    },

    "global_performance": {

        "lstm": {
            "mae": lstm_mae,
            "rmse": lstm_rmse,
            "mse": lstm_mse,
        },

        "persistence": {
            "mae": persistence_mae,
            "rmse": persistence_rmse,
            "mse": persistence_mse,
        },

        "improvement_percent": {
            "mae": mae_improvement,
            "rmse": rmse_improvement,
            "mse": mse_improvement,
        },
    },

    "feature_level": {
        "lstm_better_mae_count":
            feature_mae_win_count,

        "lstm_better_mae_rate_percent":
            feature_mae_win_rate,

        "lstm_better_rmse_count":
            feature_rmse_win_count,

        "lstm_better_rmse_rate_percent":
            feature_rmse_win_rate,

        "worst_feature_by_mae": {
            "index": int(
                worst_feature_mae_row[
                    "feature_index"
                ]
            ),
            "name": str(
                worst_feature_mae_row[
                    "feature_name"
                ]
            ),
            "mae": float(
                worst_feature_mae_row[
                    "lstm_mae"
                ]
            ),
        },

        "best_feature_by_mae": {
            "index": int(
                best_feature_mae_row[
                    "feature_index"
                ]
            ),
            "name": str(
                best_feature_mae_row[
                    "feature_name"
                ]
            ),
            "mae": float(
                best_feature_mae_row[
                    "lstm_mae"
                ]
            ),
        },
    },

    "sensor_level": {
        "lstm_better_mae_count":
            sensor_mae_win_count,

        "lstm_better_mae_rate_percent":
            sensor_mae_win_rate,

        "lstm_better_rmse_count":
            sensor_rmse_win_count,

        "lstm_better_rmse_rate_percent":
            sensor_rmse_win_rate,

        "worst_sensor_by_mae": {
            "sensor": str(
                worst_sensor_mae_row[
                    "sensor"
                ]
            ),
            "lane": str(
                worst_sensor_mae_row[
                    "lane"
                ]
            ),
            "mae": float(
                worst_sensor_mae_row[
                    "lstm_mae"
                ]
            ),
        },

        "best_sensor_by_mae": {
            "sensor": str(
                best_sensor_mae_row[
                    "sensor"
                ]
            ),
            "lane": str(
                best_sensor_mae_row[
                    "lane"
                ]
            ),
            "mae": float(
                best_sensor_mae_row[
                    "lstm_mae"
                ]
            ),
        },
    },

    "sample_level": {
        "lstm_mae_win_rate_percent":
            mae_win_rate,

        "lstm_rmse_win_rate_percent":
            rmse_win_rate,
    },

    "traffic_change": {
        "low_threshold":
            float(low_threshold),

        "high_threshold":
            float(high_threshold),

        "groups":
            traffic_group_df.to_dict(
                orient="records"
            ),
    },

    "interpretation": {
        "mae": (
            "LSTM belum mengungguli persistence "
            "secara global jika MAE menjadi metrik utama."
        ),

        "rmse": (
            "LSTM mengungguli persistence "
            "jika RMSE lebih rendah."
        ),

        "mse": (
            "LSTM mengungguli persistence "
            "jika MSE lebih rendah."
        ),

        "next_step": (
            "Gunakan hasil error analysis untuk "
            "menentukan apakah perlu feature engineering, "
            "penanganan sensor tertentu, atau evaluasi "
            "model tambahan."
        ),
    },
}

report_path = (
    ERROR_ANALYSIS_DIR
    / "final_error_analysis_report.json"
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


# ======================================================================
# FINAL SUMMARY
# ======================================================================

print_section(
    "FINAL MODEL ERROR ANALYSIS SUMMARY"
)

print()
print(
    "[GLOBAL TEST PERFORMANCE]"
)

print(
    f"LSTM"
)

print(
    f"  MAE  : {lstm_mae:.6f}"
)

print(
    f"  RMSE : {lstm_rmse:.6f}"
)

print(
    f"  MSE  : {lstm_mse:.6f}"
)

print()

print(
    f"Persistence"
)

print(
    f"  MAE  : {persistence_mae:.6f}"
)

print(
    f"  RMSE : {persistence_rmse:.6f}"
)

print(
    f"  MSE  : {persistence_mse:.6f}"
)

print()

print(
    "[LSTM VS PERSISTENCE]"
)

print(
    f"  MAE improvement  : "
    f"{mae_improvement:.2f}%"
)

print(
    f"  RMSE improvement : "
    f"{rmse_improvement:.2f}%"
)

print(
    f"  MSE improvement  : "
    f"{mse_improvement:.2f}%"
)

print()

print(
    "[FEATURE LEVEL]"
)

print(
    f"  Better MAE  : "
    f"{feature_mae_win_count}/{N_FEATURES} "
    f"({feature_mae_win_rate:.2f}%)"
)

print(
    f"  Better RMSE : "
    f"{feature_rmse_win_count}/{N_FEATURES} "
    f"({feature_rmse_win_rate:.2f}%)"
)

print()

print(
    "[SENSOR LEVEL]"
)

print(
    f"  Better MAE  : "
    f"{sensor_mae_win_count}/{sensor_count} "
    f"({sensor_mae_win_rate:.2f}%)"
)

print(
    f"  Better RMSE : "
    f"{sensor_rmse_win_count}/{sensor_count} "
    f"({sensor_rmse_win_rate:.2f}%)"
)

print()

print(
    "[SAMPLE LEVEL]"
)

print(
    f"  MAE win rate  : "
    f"{mae_win_rate:.2f}%"
)

print(
    f"  RMSE win rate : "
    f"{rmse_win_rate:.2f}%"
)

print()

print(
    "[WORST FEATURE]"
)

print(
    f"  {worst_feature_mae_row['feature_name']}"
)

print(
    f"  MAE : "
    f"{worst_feature_mae_row['lstm_mae']:.6f}"
)

print()

print(
    "[WORST SENSOR / LANE]"
)

print(
    f"  {worst_sensor_mae_row['sensor']} / "
    f"{worst_sensor_mae_row['lane']}"
)

print(
    f"  MAE : "
    f"{worst_sensor_mae_row['lstm_mae']:.6f}"
)

print()

print(
    "[KEY FINDINGS]"
)

if lstm_mae < persistence_mae:

    print(
        "1. LSTM mengungguli persistence berdasarkan MAE."
    )

else:

    print(
        "1. Persistence masih mengungguli LSTM berdasarkan MAE."
    )

if lstm_rmse < persistence_rmse:

    print(
        "2. LSTM mengungguli persistence berdasarkan RMSE."
    )

else:

    print(
        "2. Persistence masih mengungguli LSTM berdasarkan RMSE."
    )

if lstm_mse < persistence_mse:

    print(
        "3. LSTM mengungguli persistence berdasarkan MSE."
    )

else:

    print(
        "3. Persistence masih mengungguli LSTM berdasarkan MSE."
    )

print(
    "4. Error analysis digunakan untuk menemukan "
    "sensor/lane/feature yang paling bermasalah."
)

print(
    "5. Traffic-change analysis digunakan untuk melihat "
    "kapan LSTM memberikan keuntungan dibanding persistence."
)

print(
    "6. Jangan melakukan tuning tambahan sebelum hasil "
    "error analysis final diperiksa."
)

print()

print(
    "[OUTPUT DIRECTORY]"
)

print(
    ERROR_ANALYSIS_DIR
)

print_section(
    "YOLO LSTM FINAL ERROR ANALYSIS COMPLETED"
)