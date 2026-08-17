"""
06_error_analysis_yolo.py

YOLO Traffic LSTM - Error Analysis

Tujuan:
1. Menganalisis error LSTM pada test set.
2. Membandingkan LSTM dengan persistence baseline.
3. Menganalisis error berdasarkan:
   - traffic feature
   - sensor
   - perubahan traffic
   - stabilitas traffic
4. Mengidentifikasi kondisi ketika LSTM lebih baik / lebih buruk
   daripada persistence.
5. Menghasilkan CSV, PNG, dan JSON report.

Script ini TIDAK melakukan training ulang.

Input utama:
    outputs/yolo/evaluation/y_test_actual_original.npy
    outputs/yolo/evaluation/y_test_prediction_original.npy
    outputs/yolo/evaluation/baseline/persistence_prediction_original.npy

Output:
    outputs/yolo/evaluation/error_analysis/
"""

from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "yolo"
EVALUATION_DIR = OUTPUT_ROOT / "evaluation"
BASELINE_DIR = EVALUATION_DIR / "baseline"
ERROR_DIR = EVALUATION_DIR / "error_analysis"
PLOTS_DIR = ERROR_DIR / "plots"

ERROR_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


# Existing evaluation artifacts
ACTUAL_PATH = EVALUATION_DIR / "y_test_actual_original.npy"
LSTM_PATH = EVALUATION_DIR / "y_test_prediction_original.npy"
PERSISTENCE_PATH = BASELINE_DIR / "persistence_prediction_original.npy"

FEATURE_METADATA_PATH = (
    OUTPUT_ROOT / "processed" / "feature_metadata.json"
)

# Existing metrics if available
METRICS_FEATURE_PATH = (
    EVALUATION_DIR / "metrics_per_feature.csv"
)

METRICS_SENSOR_PATH = (
    EVALUATION_DIR / "metrics_per_sensor.csv"
)

METRICS_SENSOR_FEATURE_PATH = (
    EVALUATION_DIR / "metrics_per_sensor_feature.csv"
)

BASELINE_FEATURE_PATH = (
    BASELINE_DIR / "comparison_per_feature.csv"
)

BASELINE_SENSOR_PATH = (
    BASELINE_DIR / "comparison_per_sensor.csv"
)


# ============================================================
# CONSTANTS
# ============================================================

EXPECTED_FEATURES = 96
EXPECTED_SENSORS = 12

FEATURES_PER_SENSOR = 8

TRAFFIC_FEATURES = [
    "vehicle_count",
    "car_count",
    "motorcycle_count",
    "bus_count",
    "truck_count",
    "queue_length_veh",
    "queue_length_m_est",
    "density_index",
]

APPROACHES = {
    1: "north",
    2: "north",
    3: "north",
    4: "east",
    5: "east",
    6: "east",
    7: "south",
    8: "south",
    9: "south",
    10: "west",
    11: "west",
    12: "west",
}

LANES = {
    1: "lane_1",
    2: "lane_2",
    3: "lane_3",
}


# ============================================================
# PRINT HELPERS
# ============================================================

def print_header(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_subheader(title):
    print()
    print("-" * 70)
    print(title)
    print("-" * 70)


def info(message):
    print(f"[INFO] {message}")


def ok(message):
    print(f"[OK] {message}")


def warn(message):
    print(f"[WARN] {message}")


def saved(path):
    print(f"[SAVED] {path}")


# ============================================================
# FILE VALIDATION
# ============================================================

def validate_required_files():
    print_header("VALIDATING REQUIRED FILES")

    required_files = {
        "Actual test target": ACTUAL_PATH,
        "LSTM prediction": LSTM_PATH,
        "Persistence prediction": PERSISTENCE_PATH,
    }

    all_exist = True

    for name, path in required_files.items():
        if path.exists():
            info(f"{name:<25}: {path}")
        else:
            print(f"[ERROR] {name} tidak ditemukan:")
            print(f"        {path}")
            all_exist = False

    if not all_exist:
        raise FileNotFoundError(
            "Required evaluation artifacts tidak lengkap. "
            "Jalankan 04_evaluate_yolo.py dan 05_baseline_yolo.py terlebih dahulu."
        )

    ok("Required files tersedia.")


# ============================================================
# LOAD DATA
# ============================================================

def load_predictions():
    print_header("LOADING TEST PREDICTIONS")

    actual = np.load(ACTUAL_PATH)
    lstm = np.load(LSTM_PATH)
    persistence = np.load(PERSISTENCE_PATH)

    info(f"Actual       : {actual.shape}")
    info(f"LSTM         : {lstm.shape}")
    info(f"Persistence  : {persistence.shape}")

    if actual.ndim != 2:
        raise ValueError(
            f"Actual harus 2D, tetapi shape = {actual.shape}"
        )

    if lstm.ndim != 2:
        raise ValueError(
            f"LSTM prediction harus 2D, tetapi shape = {lstm.shape}"
        )

    if persistence.ndim != 2:
        raise ValueError(
            f"Persistence prediction harus 2D, tetapi shape = {persistence.shape}"
        )

    if actual.shape != lstm.shape:
        raise ValueError(
            f"Actual dan LSTM berbeda shape: "
            f"{actual.shape} vs {lstm.shape}"
        )

    if actual.shape != persistence.shape:
        raise ValueError(
            f"Actual dan persistence berbeda shape: "
            f"{actual.shape} vs {persistence.shape}"
        )

    if actual.shape[1] != EXPECTED_FEATURES:
        warn(
            f"Expected {EXPECTED_FEATURES} features, "
            f"tetapi ditemukan {actual.shape[1]}."
        )

    ok("Prediction arrays berhasil dimuat.")

    return actual, lstm, persistence


# ============================================================
# NUMERICAL VALIDATION
# ============================================================

def validate_numeric_data(actual, lstm, persistence):
    print_header("NUMERICAL DATA VALIDATION")

    datasets = {
        "Actual": actual,
        "LSTM": lstm,
        "Persistence": persistence,
    }

    for name, data in datasets.items():
        nan_count = np.isnan(data).sum()
        inf_count = np.isinf(data).sum()

        info(
            f"{name:<12} | "
            f"NaN: {nan_count:,} | "
            f"Inf: {inf_count:,}"
        )

        if nan_count > 0 or inf_count > 0:
            raise ValueError(
                f"{name} mengandung NaN atau Inf."
            )

    ok("Semua prediction numerically valid.")


# ============================================================
# FEATURE METADATA
# ============================================================

def build_feature_metadata():
    """
    Membuat metadata 96 feature berdasarkan struktur:
        12 sensor x 8 feature

    Urutan mengikuti hasil evaluasi sebelumnya:
        sensor 1:
            vehicle_count
            car_count
            motorcycle_count
            bus_count
            truck_count
            queue_length_veh
            queue_length_m_est
            density_index

        sensor 2:
            ...
    """

    print_header("BUILDING FEATURE METADATA")

    metadata = []

    for sensor_id in range(1, EXPECTED_SENSORS + 1):

        approach = APPROACHES.get(
            sensor_id,
            f"sensor_{sensor_id}"
        )

        lane_number = ((sensor_id - 1) % 3) + 1

        lane_id = f"lane_{lane_number}"

        for feature in TRAFFIC_FEATURES:

            metadata.append(
                {
                    "sensor_id": sensor_id,
                    "approach": approach,
                    "lane_id": lane_id,
                    "sensor": f"{approach}/{lane_id}",
                    "feature": feature,
                }
            )

    metadata_df = pd.DataFrame(metadata)

    if len(metadata_df) != EXPECTED_FEATURES:
        raise ValueError(
            f"Metadata feature count salah: "
            f"{len(metadata_df)} != {EXPECTED_FEATURES}"
        )

    metadata_df.insert(
        0,
        "index",
        np.arange(len(metadata_df))
    )

    ok(
        f"Feature metadata dibuat: "
        f"{len(metadata_df)} features"
    )

    return metadata_df


# ============================================================
# BASIC ERROR CALCULATION
# ============================================================

def calculate_error_tables(
    actual,
    lstm,
    persistence,
    metadata_df,
):
    print_header("CALCULATING ERROR MATRICES")

    lstm_error = lstm - actual
    persistence_error = persistence - actual

    lstm_abs_error = np.abs(lstm_error)
    persistence_abs_error = np.abs(persistence_error)

    lstm_squared_error = lstm_error ** 2
    persistence_squared_error = persistence_error ** 2

    info(
        f"LSTM error matrix        : {lstm_error.shape}"
    )

    info(
        f"Persistence error matrix : "
        f"{persistence_error.shape}"
    )

    # --------------------------------------------------------
    # Per observation
    # --------------------------------------------------------

    observation_rows = []

    for i in range(actual.shape[0]):

        actual_row = actual[i]
        lstm_row = lstm[i]
        persistence_row = persistence[i]

        lstm_abs = np.abs(lstm_row - actual_row)
        persistence_abs = np.abs(
            persistence_row - actual_row
        )

        lstm_sq = (lstm_row - actual_row) ** 2
        persistence_sq = (
            persistence_row - actual_row
        ) ** 2

        observation_rows.append(
            {
                "sample_index": i,

                "actual_mean": np.mean(actual_row),
                "actual_std": np.std(actual_row),

                "lstm_mae": np.mean(lstm_abs),
                "lstm_rmse": np.sqrt(np.mean(lstm_sq)),

                "persistence_mae": np.mean(
                    persistence_abs
                ),
                "persistence_rmse": np.sqrt(
                    np.mean(persistence_sq)
                ),

                "lstm_better_mae": (
                    np.mean(lstm_abs)
                    <
                    np.mean(persistence_abs)
                ),

                "lstm_better_rmse": (
                    np.sqrt(np.mean(lstm_sq))
                    <
                    np.sqrt(np.mean(persistence_sq))
                ),
            }
        )

    observation_df = pd.DataFrame(
        observation_rows
    )

    # --------------------------------------------------------
    # Per feature
    # --------------------------------------------------------

    feature_rows = []

    for feature_idx in range(actual.shape[1]):

        meta = metadata_df.iloc[feature_idx]

        y_true = actual[:, feature_idx]
        y_lstm = lstm[:, feature_idx]
        y_persistence = persistence[:, feature_idx]

        lstm_err = y_lstm - y_true
        persistence_err = (
            y_persistence - y_true
        )

        lstm_abs = np.abs(lstm_err)
        persistence_abs = np.abs(
            persistence_err
        )

        lstm_sq = lstm_err ** 2
        persistence_sq = persistence_err ** 2

        lstm_mae = np.mean(lstm_abs)
        persistence_mae = np.mean(
            persistence_abs
        )

        lstm_rmse = np.sqrt(
            np.mean(lstm_sq)
        )

        persistence_rmse = np.sqrt(
            np.mean(persistence_sq)
        )

        feature_rows.append(
            {
                "index": feature_idx,
                "sensor_id": meta["sensor_id"],
                "approach": meta["approach"],
                "lane_id": meta["lane_id"],
                "sensor": meta["sensor"],
                "feature": meta["feature"],

                "lstm_mae": lstm_mae,
                "lstm_rmse": lstm_rmse,

                "persistence_mae": persistence_mae,
                "persistence_rmse": persistence_rmse,

                "mae_difference": (
                    persistence_mae
                    - lstm_mae
                ),

                "rmse_difference": (
                    persistence_rmse
                    - lstm_rmse
                ),

                "mae_improvement_percent": (
                    (
                        persistence_mae
                        - lstm_mae
                    )
                    /
                    persistence_mae
                    * 100
                    if persistence_mae != 0
                    else np.nan
                ),

                "rmse_improvement_percent": (
                    (
                        persistence_rmse
                        - lstm_rmse
                    )
                    /
                    persistence_rmse
                    * 100
                    if persistence_rmse != 0
                    else np.nan
                ),

                "lstm_better_mae": (
                    lstm_mae < persistence_mae
                ),

                "lstm_better_rmse": (
                    lstm_rmse < persistence_rmse
                ),
            }
        )

    feature_df = pd.DataFrame(feature_rows)

    # --------------------------------------------------------
    # Per sensor
    # --------------------------------------------------------

    sensor_rows = []

    for sensor_id in range(
        1,
        EXPECTED_SENSORS + 1
    ):

        sensor_indices = metadata_df[
            metadata_df["sensor_id"] == sensor_id
        ]["index"].values

        y_true = actual[:, sensor_indices]

        y_lstm = lstm[:, sensor_indices]

        y_persistence = (
            persistence[:, sensor_indices]
        )

        lstm_error_sensor = (
            y_lstm - y_true
        )

        persistence_error_sensor = (
            y_persistence - y_true
        )

        lstm_mae = np.mean(
            np.abs(lstm_error_sensor)
        )

        persistence_mae = np.mean(
            np.abs(persistence_error_sensor)
        )

        lstm_rmse = np.sqrt(
            np.mean(lstm_error_sensor ** 2)
        )

        persistence_rmse = np.sqrt(
            np.mean(
                persistence_error_sensor ** 2
            )
        )

        approach = APPROACHES.get(
            sensor_id,
            f"sensor_{sensor_id}"
        )

        lane_number = (
            (sensor_id - 1) % 3
        ) + 1

        lane_id = f"lane_{lane_number}"

        sensor_rows.append(
            {
                "sensor_id": sensor_id,
                "approach": approach,
                "lane_id": lane_id,
                "sensor": f"{approach}/{lane_id}",

                "lstm_mae": lstm_mae,
                "lstm_rmse": lstm_rmse,

                "persistence_mae": persistence_mae,
                "persistence_rmse": persistence_rmse,

                "mae_difference": (
                    persistence_mae
                    - lstm_mae
                ),

                "rmse_difference": (
                    persistence_rmse
                    - lstm_rmse
                ),

                "mae_improvement_percent": (
                    (
                        persistence_mae
                        - lstm_mae
                    )
                    /
                    persistence_mae
                    * 100
                    if persistence_mae != 0
                    else np.nan
                ),

                "rmse_improvement_percent": (
                    (
                        persistence_rmse
                        - lstm_rmse
                    )
                    /
                    persistence_rmse
                    * 100
                    if persistence_rmse != 0
                    else np.nan
                ),

                "lstm_better_mae": (
                    lstm_mae < persistence_mae
                ),

                "lstm_better_rmse": (
                    lstm_rmse < persistence_rmse
                ),
            }
        )

    sensor_df = pd.DataFrame(sensor_rows)

    ok("Error matrices berhasil dihitung.")

    return (
        lstm_error,
        persistence_error,
        observation_df,
        feature_df,
        sensor_df,
    )


# ============================================================
# TRAFFIC CHANGE ANALYSIS
# ============================================================

def analyze_traffic_change(
    actual,
    lstm,
    persistence,
    metadata_df,
):
    """
    Menganalisis hubungan antara perubahan aktual traffic
    dan performa LSTM vs persistence.

    Karena y_test adalah target t+1 dan X_test tidak dibaca
    oleh script ini, perubahan dihitung antar target test:
        |y_true[i] - y_true[i-1]|

    Ini adalah proxy perubahan traffic antar sampel test.

    Jangan dianggap sebagai perubahan t -> t+1 secara mutlak
    apabila test samples bukan timestep berurutan.
    """

    print_header("ANALYZING TRAFFIC CHANGE")

    rows = []

    for i in range(actual.shape[0]):

        if i == 0:
            change = np.nan
            change_percent = np.nan
        else:
            previous = actual[i - 1]
            current = actual[i]

            change = np.mean(
                np.abs(current - previous)
            )

            denominator = np.mean(
                np.abs(previous)
            )

            if denominator > 1e-12:
                change_percent = (
                    change
                    /
                    denominator
                    * 100
                )
            else:
                change_percent = np.nan

        lstm_mae = np.mean(
            np.abs(lstm[i] - actual[i])
        )

        persistence_mae = np.mean(
            np.abs(
                persistence[i] - actual[i]
            )
        )

        rows.append(
            {
                "sample_index": i,
                "traffic_change_mean_abs": change,
                "traffic_change_percent": change_percent,
                "lstm_mae": lstm_mae,
                "persistence_mae": persistence_mae,
                "lstm_minus_persistence_mae": (
                    lstm_mae
                    -
                    persistence_mae
                ),
                "lstm_better": (
                    lstm_mae
                    <
                    persistence_mae
                ),
            }
        )

    change_df = pd.DataFrame(rows)

    valid_change = change_df[
        change_df["traffic_change_mean_abs"]
        .notna()
    ].copy()

    if len(valid_change) > 0:

        median_change = (
            valid_change[
                "traffic_change_mean_abs"
            ].median()
        )

        valid_change["change_group"] = np.where(
            valid_change[
                "traffic_change_mean_abs"
            ]
            <= median_change,
            "Low change",
            "High change",
        )

        group_summary = (
            valid_change
            .groupby("change_group")
            .agg(
                samples=("sample_index", "count"),
                mean_change=(
                    "traffic_change_mean_abs",
                    "mean",
                ),
                lstm_mae=("lstm_mae", "mean"),
                persistence_mae=(
                    "persistence_mae",
                    "mean",
                ),
                lstm_win_rate=(
                    "lstm_better",
                    "mean",
                ),
            )
            .reset_index()
        )

        group_summary[
            "lstm_win_rate"
        ] *= 100

    else:
        group_summary = pd.DataFrame()

    change_path = (
        ERROR_DIR
        / "traffic_change_analysis.csv"
    )

    change_df.to_csv(
        change_path,
        index=False,
    )

    saved(change_path)

    summary_path = (
        ERROR_DIR
        / "traffic_change_summary.csv"
    )

    group_summary.to_csv(
        summary_path,
        index=False,
    )

    saved(summary_path)

    return change_df, group_summary


# ============================================================
# ERROR BIAS ANALYSIS
# ============================================================

def analyze_bias(
    actual,
    lstm,
    persistence,
    metadata_df,
):
    print_header("ANALYZING PREDICTION BIAS")

    rows = []

    for feature_idx in range(
        actual.shape[1]
    ):

        meta = metadata_df.iloc[feature_idx]

        y_true = actual[:, feature_idx]

        lstm_error = (
            lstm[:, feature_idx]
            -
            y_true
        )

        persistence_error = (
            persistence[:, feature_idx]
            -
            y_true
        )

        rows.append(
            {
                "index": feature_idx,
                "sensor_id": meta["sensor_id"],
                "approach": meta["approach"],
                "lane_id": meta["lane_id"],
                "sensor": meta["sensor"],
                "feature": meta["feature"],

                "lstm_mean_error": np.mean(
                    lstm_error
                ),

                "lstm_median_error": np.median(
                    lstm_error
                ),

                "lstm_mean_abs_error": np.mean(
                    np.abs(lstm_error)
                ),

                "persistence_mean_error": (
                    np.mean(
                        persistence_error
                    )
                ),

                "persistence_median_error": (
                    np.median(
                        persistence_error
                    )
                ),

                "persistence_mean_abs_error": (
                    np.mean(
                        np.abs(
                            persistence_error
                        )
                    )
                ),
            }
        )

    bias_df = pd.DataFrame(rows)

    path = (
        ERROR_DIR
        / "prediction_bias_per_feature.csv"
    )

    bias_df.to_csv(
        path,
        index=False,
    )

    saved(path)

    return bias_df


# ============================================================
# WIN / LOSS ANALYSIS
# ============================================================

def analyze_sample_wins(
    observation_df,
):
    print_header("ANALYZING SAMPLE-LEVEL WINS")

    total = len(observation_df)

    lstm_better_mae_count = int(
        observation_df[
            "lstm_better_mae"
        ].sum()
    )

    persistence_better_mae_count = (
        total
        -
        lstm_better_mae_count
    )

    lstm_better_rmse_count = int(
        observation_df[
            "lstm_better_rmse"
        ].sum()
    )

    persistence_better_rmse_count = (
        total
        -
        lstm_better_rmse_count
    )

    summary = {
        "total_test_samples": total,

        "lstm_better_mae_samples":
            lstm_better_mae_count,

        "persistence_better_mae_samples":
            persistence_better_mae_count,

        "lstm_mae_win_rate_percent": (
            lstm_better_mae_count
            /
            total
            * 100
            if total > 0
            else 0
        ),

        "lstm_better_rmse_samples":
            lstm_better_rmse_count,

        "persistence_better_rmse_samples":
            persistence_better_rmse_count,

        "lstm_rmse_win_rate_percent": (
            lstm_better_rmse_count
            /
            total
            * 100
            if total > 0
            else 0
        ),
    }

    summary_df = pd.DataFrame(
        [summary]
    )

    path = (
        ERROR_DIR
        / "sample_win_loss_summary.csv"
    )

    summary_df.to_csv(
        path,
        index=False,
    )

    saved(path)

    return summary


# ============================================================
# TOP WORST FEATURES
# ============================================================

def create_top_error_tables(
    feature_df,
    sensor_df,
):
    print_header("IDENTIFYING WORST ERROR AREAS")

    worst_features_mae = (
        feature_df
        .sort_values(
            "lstm_mae",
            ascending=False,
        )
        .head(10)
        .copy()
    )

    worst_features_rmse = (
        feature_df
        .sort_values(
            "lstm_rmse",
            ascending=False,
        )
        .head(10)
        .copy()
    )

    worst_sensors_mae = (
        sensor_df
        .sort_values(
            "lstm_mae",
            ascending=False,
        )
        .copy()
    )

    worst_sensors_rmse = (
        sensor_df
        .sort_values(
            "lstm_rmse",
            ascending=False,
        )
        .copy()
    )

    paths = {
        "worst_features_mae.csv":
            worst_features_mae,

        "worst_features_rmse.csv":
            worst_features_rmse,

        "worst_sensors_mae.csv":
            worst_sensors_mae,

        "worst_sensors_rmse.csv":
            worst_sensors_rmse,
    }

    for filename, dataframe in paths.items():

        path = ERROR_DIR / filename

        dataframe.to_csv(
            path,
            index=False,
        )

        saved(path)

    return (
        worst_features_mae,
        worst_features_rmse,
        worst_sensors_mae,
        worst_sensors_rmse,
    )


# ============================================================
# PLOT 1 - LSTM VS PERSISTENCE PER FEATURE
# ============================================================

def plot_feature_error_comparison(
    feature_df,
):
    print_subheader(
        "PLOTTING FEATURE ERROR COMPARISON"
    )

    plot_df = feature_df.copy()

    # Aggregate across sensors
    grouped = (
        plot_df
        .groupby("feature")
        .agg(
            lstm_mae=("lstm_mae", "mean"),
            persistence_mae=(
                "persistence_mae",
                "mean",
            ),
        )
        .reindex(TRAFFIC_FEATURES)
        .reset_index()
    )

    x = np.arange(
        len(grouped)
    )

    width = 0.36

    fig, ax = plt.subplots(
        figsize=(14, 7)
    )

    ax.bar(
        x - width / 2,
        grouped["lstm_mae"],
        width,
        label="LSTM",
    )

    ax.bar(
        x + width / 2,
        grouped["persistence_mae"],
        width,
        label="Persistence",
    )

    ax.set_title(
        "LSTM vs Persistence MAE per Traffic Feature"
    )

    ax.set_ylabel("MAE")

    ax.set_xticks(x)

    ax.set_xticklabels(
        grouped["feature"],
        rotation=35,
        ha="right",
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.3,
    )

    plt.tight_layout()

    path = (
        PLOTS_DIR
        / "lstm_vs_persistence_mae_per_feature_error_analysis.png"
    )

    plt.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    saved(path)


# ============================================================
# PLOT 2 - SENSOR ERROR
# ============================================================

def plot_sensor_error_comparison(
    sensor_df,
):
    print_subheader(
        "PLOTTING SENSOR ERROR COMPARISON"
    )

    plot_df = sensor_df.copy()

    x = np.arange(
        len(plot_df)
    )

    width = 0.36

    fig, ax = plt.subplots(
        figsize=(15, 7)
    )

    ax.bar(
        x - width / 2,
        plot_df["lstm_mae"],
        width,
        label="LSTM",
    )

    ax.bar(
        x + width / 2,
        plot_df["persistence_mae"],
        width,
        label="Persistence",
    )

    ax.set_title(
        "LSTM vs Persistence MAE per Sensor"
    )

    ax.set_ylabel("MAE")

    ax.set_xticks(x)

    ax.set_xticklabels(
        plot_df["sensor"],
        rotation=45,
        ha="right",
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.3,
    )

    plt.tight_layout()

    path = (
        PLOTS_DIR
        / "lstm_vs_persistence_mae_per_sensor_error_analysis.png"
    )

    plt.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    saved(path)


# ============================================================
# PLOT 3 - ERROR DISTRIBUTION
# ============================================================

def plot_error_distribution(
    actual,
    lstm,
    persistence,
):
    print_subheader(
        "PLOTTING ERROR DISTRIBUTION"
    )

    lstm_error = (
        lstm - actual
    ).flatten()

    persistence_error = (
        persistence - actual
    ).flatten()

    # Limit extreme values only for visualization.
    # Original values are NOT modified.
    combined = np.concatenate(
        [
            lstm_error,
            persistence_error,
        ]
    )

    lower = np.percentile(
        combined,
        1,
    )

    upper = np.percentile(
        combined,
        99,
    )

    fig, ax = plt.subplots(
        figsize=(12, 7)
    )

    ax.hist(
        lstm_error,
        bins=80,
        range=(lower, upper),
        alpha=0.55,
        label="LSTM",
    )

    ax.hist(
        persistence_error,
        bins=80,
        range=(lower, upper),
        alpha=0.55,
        label="Persistence",
    )

    ax.axvline(
        0,
        linestyle="--",
        linewidth=1.5,
    )

    ax.set_title(
        "Prediction Error Distribution"
    )

    ax.set_xlabel(
        "Prediction Error (Prediction - Actual)"
    )

    ax.set_ylabel(
        "Frequency"
    )

    ax.legend()

    ax.grid(
        axis="y",
        alpha=0.3,
    )

    plt.tight_layout()

    path = (
        PLOTS_DIR
        / "prediction_error_distribution_lstm_vs_persistence.png"
    )

    plt.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    saved(path)


# ============================================================
# PLOT 4 - TRAFFIC CHANGE VS ERROR
# ============================================================

def plot_change_vs_error(
    change_df,
):
    print_subheader(
        "PLOTTING TRAFFIC CHANGE VS ERROR"
    )

    df = change_df.dropna(
        subset=[
            "traffic_change_mean_abs",
            "lstm_minus_persistence_mae",
        ]
    ).copy()

    if len(df) == 0:
        warn(
            "Tidak ada data valid untuk "
            "traffic change plot."
        )
        return

    fig, ax = plt.subplots(
        figsize=(11, 7)
    )

    ax.scatter(
        df["traffic_change_mean_abs"],
        df[
            "lstm_minus_persistence_mae"
        ],
        alpha=0.65,
    )

    ax.axhline(
        0,
        linestyle="--",
        linewidth=1.5,
    )

    ax.set_title(
        "Traffic Change vs LSTM Error Advantage"
    )

    ax.set_xlabel(
        "Mean Absolute Traffic Change"
    )

    ax.set_ylabel(
        "LSTM MAE - Persistence MAE"
    )

    ax.grid(
        alpha=0.3,
    )

    plt.tight_layout()

    path = (
        PLOTS_DIR
        / "traffic_change_vs_lstm_advantage.png"
    )

    plt.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    saved(path)


# ============================================================
# PLOT 5 - SAMPLE MAE
# ============================================================

def plot_sample_mae(
    observation_df,
):
    print_subheader(
        "PLOTTING SAMPLE-LEVEL MAE"
    )

    fig, ax = plt.subplots(
        figsize=(14, 7)
    )

    ax.plot(
        observation_df["sample_index"],
        observation_df["lstm_mae"],
        label="LSTM",
        linewidth=1.5,
    )

    ax.plot(
        observation_df["sample_index"],
        observation_df[
            "persistence_mae"
        ],
        label="Persistence",
        linewidth=1.5,
    )

    ax.set_title(
        "Sample-Level MAE: LSTM vs Persistence"
    )

    ax.set_xlabel(
        "Test Sample Index"
    )

    ax.set_ylabel(
        "MAE"
    )

    ax.legend()

    ax.grid(
        alpha=0.3,
    )

    plt.tight_layout()

    path = (
        PLOTS_DIR
        / "sample_level_mae_lstm_vs_persistence.png"
    )

    plt.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close()

    saved(path)


# ============================================================
# FEATURE CHANGE ANALYSIS
# ============================================================

def analyze_feature_change(
    actual,
    lstm,
    persistence,
    metadata_df,
):
    """
    Analisis perubahan actual per feature dan hubungan
    dengan keunggulan LSTM terhadap persistence.
    """

    print_header(
        "ANALYZING FEATURE-LEVEL TRAFFIC CHANGE"
    )

    rows = []

    for feature_idx in range(
        actual.shape[1]
    ):

        meta = metadata_df.iloc[
            feature_idx
        ]

        y_true = actual[
            :,
            feature_idx,
        ]

        y_lstm = lstm[
            :,
            feature_idx,
        ]

        y_persistence = persistence[
            :,
            feature_idx,
        ]

        if len(y_true) > 1:

            actual_change = np.abs(
                np.diff(y_true)
            )

            lstm_error = np.abs(
                y_lstm[1:]
                -
                y_true[1:]
            )

            persistence_error = np.abs(
                y_persistence[1:]
                -
                y_true[1:]
            )

            mean_change = np.mean(
                actual_change
            )

            median_change = np.median(
                actual_change
            )

            lstm_mae = np.mean(
                lstm_error
            )

            persistence_mae = np.mean(
                persistence_error
            )

            if np.std(actual_change) > 0:

                lstm_corr = np.corrcoef(
                    actual_change,
                    lstm_error,
                )[0, 1]

                persistence_corr = np.corrcoef(
                    actual_change,
                    persistence_error,
                )[0, 1]

            else:
                lstm_corr = np.nan
                persistence_corr = np.nan

        else:

            mean_change = np.nan
            median_change = np.nan
            lstm_mae = np.nan
            persistence_mae = np.nan
            lstm_corr = np.nan
            persistence_corr = np.nan

        rows.append(
            {
                "index": feature_idx,
                "sensor_id": meta["sensor_id"],
                "approach": meta["approach"],
                "lane_id": meta["lane_id"],
                "sensor": meta["sensor"],
                "feature": meta["feature"],

                "mean_actual_change":
                    mean_change,

                "median_actual_change":
                    median_change,

                "lstm_mae":
                    lstm_mae,

                "persistence_mae":
                    persistence_mae,

                "lstm_mae_advantage":
                    persistence_mae
                    -
                    lstm_mae,

                "lstm_error_change_correlation":
                    lstm_corr,

                "persistence_error_change_correlation":
                    persistence_corr,
            }
        )

    result_df = pd.DataFrame(
        rows
    )

    path = (
        ERROR_DIR
        / "feature_change_error_analysis.csv"
    )

    result_df.to_csv(
        path,
        index=False,
    )

    saved(path)

    return result_df


# ============================================================
# GLOBAL SUMMARY
# ============================================================

def calculate_global_summary(
    actual,
    lstm,
    persistence,
    observation_df,
    feature_df,
    sensor_df,
):
    print_header("CALCULATING ERROR ANALYSIS SUMMARY")

    lstm_error = (
        lstm - actual
    )

    persistence_error = (
        persistence - actual
    )

    lstm_mae = np.mean(
        np.abs(lstm_error)
    )

    persistence_mae = np.mean(
        np.abs(persistence_error)
    )

    lstm_rmse = np.sqrt(
        np.mean(lstm_error ** 2)
    )

    persistence_rmse = np.sqrt(
        np.mean(persistence_error ** 2)
    )

    lstm_mse = np.mean(
        lstm_error ** 2
    )

    persistence_mse = np.mean(
        persistence_error ** 2
    )

    summary = {

        "test_samples":
            int(actual.shape[0]),

        "features":
            int(actual.shape[1]),

        "lstm_mae":
            float(lstm_mae),

        "lstm_rmse":
            float(lstm_rmse),

        "lstm_mse":
            float(lstm_mse),

        "persistence_mae":
            float(persistence_mae),

        "persistence_rmse":
            float(persistence_rmse),

        "persistence_mse":
            float(persistence_mse),

        "lstm_mae_improvement_percent":
            float(
                (
                    persistence_mae
                    -
                    lstm_mae
                )
                /
                persistence_mae
                * 100
            ),

        "lstm_rmse_improvement_percent":
            float(
                (
                    persistence_rmse
                    -
                    lstm_rmse
                )
                /
                persistence_rmse
                * 100
            ),

        "lstm_mse_improvement_percent":
            float(
                (
                    persistence_mse
                    -
                    lstm_mse
                )
                /
                persistence_mse
                * 100
            ),

        "features_lstm_better_mae":
            int(
                feature_df[
                    "lstm_better_mae"
                ].sum()
            ),

        "features_lstm_better_rmse":
            int(
                feature_df[
                    "lstm_better_rmse"
                ].sum()
            ),

        "sensors_lstm_better_mae":
            int(
                sensor_df[
                    "lstm_better_mae"
                ].sum()
            ),

        "sensors_lstm_better_rmse":
            int(
                sensor_df[
                    "lstm_better_rmse"
                ].sum()
            ),

        "sample_lstm_mae_win_rate_percent":
            float(
                observation_df[
                    "lstm_better_mae"
                ].mean()
                * 100
            ),

        "sample_lstm_rmse_win_rate_percent":
            float(
                observation_df[
                    "lstm_better_rmse"
                ].mean()
                * 100
            ),
    }

    return summary


# ============================================================
# GENERATE RECOMMENDATIONS
# ============================================================

def generate_recommendations(
    summary,
    feature_df,
    sensor_df,
    change_summary,
):
    recommendations = []

    # --------------------------------------------------------
    # MAE baseline
    # --------------------------------------------------------

    if (
        summary[
            "lstm_mae_improvement_percent"
        ]
        > 0
    ):
        recommendations.append(
            "LSTM mengungguli persistence berdasarkan MAE."
        )
    else:
        recommendations.append(
            "Persistence masih mengungguli LSTM berdasarkan MAE. "
            "Jangan mengklaim LSTM lebih baik secara keseluruhan."
        )

    # --------------------------------------------------------
    # RMSE
    # --------------------------------------------------------

    if (
        summary[
            "lstm_rmse_improvement_percent"
        ]
        > 0
    ):
        recommendations.append(
            "LSTM mengungguli persistence berdasarkan RMSE."
        )
    else:
        recommendations.append(
            "LSTM belum mengungguli persistence berdasarkan RMSE."
        )

    # --------------------------------------------------------
    # Feature count
    # --------------------------------------------------------

    total_features = len(
        feature_df
    )

    feature_win_rate = (
        summary[
            "features_lstm_better_mae"
        ]
        /
        total_features
        *
        100
    )

    if feature_win_rate < 50:
        recommendations.append(
            f"LSTM hanya unggul MAE pada "
            f"{feature_win_rate:.2f}% feature. "
            "Perlu investigasi feature-specific behavior."
        )

    # --------------------------------------------------------
    # Worst feature
    # --------------------------------------------------------

    worst_feature = (
        feature_df
        .sort_values(
            "lstm_mae",
            ascending=False,
        )
        .iloc[0]
    )

    recommendations.append(
        "Feature dengan MAE LSTM tertinggi adalah "
        f"{worst_feature['feature']} pada "
        f"{worst_feature['sensor']}."
    )

    # --------------------------------------------------------
    # Worst sensor
    # --------------------------------------------------------

    worst_sensor = (
        sensor_df
        .sort_values(
            "lstm_mae",
            ascending=False,
        )
        .iloc[0]
    )

    recommendations.append(
        "Sensor dengan MAE LSTM tertinggi adalah "
        f"{worst_sensor['sensor']}."
    )

    # --------------------------------------------------------
    # Traffic change
    # --------------------------------------------------------

    if (
        change_summary is not None
        and len(change_summary) > 0
    ):

        if "lstm_win_rate" in change_summary.columns:

            high_change = change_summary[
                change_summary["change_group"]
                == "High change"
            ]

            low_change = change_summary[
                change_summary["change_group"]
                == "Low change"
            ]

            if len(high_change) > 0:

                high_win = float(
                    high_change[
                        "lstm_win_rate"
                    ].iloc[0]
                )

                recommendations.append(
                    "Pada kelompok perubahan traffic tinggi, "
                    f"win rate LSTM terhadap persistence "
                    f"adalah {high_win:.2f}%."
                )

            if len(low_change) > 0:

                low_win = float(
                    low_change[
                        "lstm_win_rate"
                    ].iloc[0]
                )

                recommendations.append(
                    "Pada kelompok perubahan traffic rendah, "
                    f"win rate LSTM terhadap persistence "
                    f"adalah {low_win:.2f}%."
                )

    # --------------------------------------------------------
    # General recommendation
    # --------------------------------------------------------

    recommendations.append(
        "Sebelum hyperparameter tuning, lakukan eksperimen "
        "sequence length dan forecast horizon untuk mengetahui "
        "apakah persistence terlalu kuat karena horizon prediksi "
        "hanya 1 detik."
    )

    return recommendations


# ============================================================
# SAVE REPORT
# ============================================================

def save_report(
    summary,
    recommendations,
):
    report = {
        "analysis": {
            "name": "YOLO Traffic LSTM Error Analysis",
            "description": (
                "Post-hoc analysis of LSTM predictions "
                "against actual test targets and "
                "persistence baseline."
            ),
        },

        "summary": summary,

        "recommendations": recommendations,
    }

    path = (
        ERROR_DIR
        / "error_analysis_report.json"
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            indent=4,
        )

    saved(path)

    return report


# ============================================================
# PRINT FINAL SUMMARY
# ============================================================

def print_final_summary(
    summary,
    feature_df,
    sensor_df,
    recommendations,
):
    print_header(
        "YOLO LSTM ERROR ANALYSIS SUMMARY"
    )

    print()
    print("[GLOBAL TEST PERFORMANCE]")
    print()

    print(
        f"LSTM"
    )

    print(
        f"  MAE  : "
        f"{summary['lstm_mae']:.6f}"
    )

    print(
        f"  RMSE : "
        f"{summary['lstm_rmse']:.6f}"
    )

    print(
        f"  MSE  : "
        f"{summary['lstm_mse']:.6f}"
    )

    print()

    print(
        f"Persistence"
    )

    print(
        f"  MAE  : "
        f"{summary['persistence_mae']:.6f}"
    )

    print(
        f"  RMSE : "
        f"{summary['persistence_rmse']:.6f}"
    )

    print(
        f"  MSE  : "
        f"{summary['persistence_mse']:.6f}"
    )

    print()
    print(
        "[LSTM IMPROVEMENT OVER PERSISTENCE]"
    )

    print(
        f"  MAE  : "
        f"{summary['lstm_mae_improvement_percent']:.2f}%"
    )

    print(
        f"  RMSE : "
        f"{summary['lstm_rmse_improvement_percent']:.2f}%"
    )

    print(
        f"  MSE  : "
        f"{summary['lstm_mse_improvement_percent']:.2f}%"
    )

    print()
    print(
        "[FEATURE-LEVEL RESULT]"
    )

    print(
        f"  LSTM better MAE  : "
        f"{summary['features_lstm_better_mae']}"
        f"/{len(feature_df)}"
    )

    print(
        f"  LSTM better RMSE : "
        f"{summary['features_lstm_better_rmse']}"
        f"/{len(feature_df)}"
    )

    print()
    print(
        "[SENSOR-LEVEL RESULT]"
    )

    print(
        f"  LSTM better MAE  : "
        f"{summary['sensors_lstm_better_mae']}"
        f"/{len(sensor_df)}"
    )

    print(
        f"  LSTM better RMSE : "
        f"{summary['sensors_lstm_better_rmse']}"
        f"/{len(sensor_df)}"
    )

    print()
    print(
        "[SAMPLE-LEVEL RESULT]"
    )

    print(
        f"  LSTM MAE win rate  : "
        f"{summary['sample_lstm_mae_win_rate_percent']:.2f}%"
    )

    print(
        f"  LSTM RMSE win rate : "
        f"{summary['sample_lstm_rmse_win_rate_percent']:.2f}%"
    )

    print()
    print(
        "[KEY FINDINGS]"
    )

    for i, recommendation in enumerate(
        recommendations,
        start=1,
    ):

        print(
            f"{i}. {recommendation}"
        )

    print()
    print(
        "[OUTPUT DIRECTORY]"
    )

    print(
        ERROR_DIR
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "YOLO TRAFFIC LSTM ERROR ANALYSIS"
    )
    print("=" * 70)

    info(
        f"Project root     : {PROJECT_ROOT}"
    )

    info(
        f"Evaluation dir   : {EVALUATION_DIR}"
    )

    info(
        f"Error analysis   : {ERROR_DIR}"
    )

    # --------------------------------------------------------
    # 1. Validate files
    # --------------------------------------------------------

    validate_required_files()

    # --------------------------------------------------------
    # 2. Load predictions
    # --------------------------------------------------------

    (
        actual,
        lstm,
        persistence,
    ) = load_predictions()

    # --------------------------------------------------------
    # 3. Validate numerical data
    # --------------------------------------------------------

    validate_numeric_data(
        actual,
        lstm,
        persistence,
    )

    # --------------------------------------------------------
    # 4. Build metadata
    # --------------------------------------------------------

    metadata_df = (
        build_feature_metadata()
    )

    # --------------------------------------------------------
    # 5. Calculate error tables
    # --------------------------------------------------------

    (
        lstm_error,
        persistence_error,
        observation_df,
        feature_df,
        sensor_df,
    ) = calculate_error_tables(
        actual,
        lstm,
        persistence,
        metadata_df,
    )

    # --------------------------------------------------------
    # Save detailed observation analysis
    # --------------------------------------------------------

    observation_path = (
        ERROR_DIR
        / "sample_level_error_analysis.csv"
    )

    observation_df.to_csv(
        observation_path,
        index=False,
    )

    saved(observation_path)

    # --------------------------------------------------------
    # Save feature analysis
    # --------------------------------------------------------

    feature_path = (
        ERROR_DIR
        / "error_analysis_per_feature.csv"
    )

    feature_df.to_csv(
        feature_path,
        index=False,
    )

    saved(feature_path)

    # --------------------------------------------------------
    # Save sensor analysis
    # --------------------------------------------------------

    sensor_path = (
        ERROR_DIR
        / "error_analysis_per_sensor.csv"
    )

    sensor_df.to_csv(
        sensor_path,
        index=False,
    )

    saved(sensor_path)

    # --------------------------------------------------------
    # 6. Traffic change analysis
    # --------------------------------------------------------

    (
        change_df,
        change_summary,
    ) = analyze_traffic_change(
        actual,
        lstm,
        persistence,
        metadata_df,
    )

    # --------------------------------------------------------
    # 7. Bias analysis
    # --------------------------------------------------------

    bias_df = analyze_bias(
        actual,
        lstm,
        persistence,
        metadata_df,
    )

    # --------------------------------------------------------
    # 8. Sample win/loss
    # --------------------------------------------------------

    win_loss_summary = (
        analyze_sample_wins(
            observation_df
        )
    )

    # --------------------------------------------------------
    # 9. Worst areas
    # --------------------------------------------------------

    (
        worst_features_mae,
        worst_features_rmse,
        worst_sensors_mae,
        worst_sensors_rmse,
    ) = create_top_error_tables(
        feature_df,
        sensor_df,
    )

    # --------------------------------------------------------
    # 10. Feature-level traffic change
    # --------------------------------------------------------

    feature_change_df = (
        analyze_feature_change(
            actual,
            lstm,
            persistence,
            metadata_df,
        )
    )

    # --------------------------------------------------------
    # 11. Global summary
    # --------------------------------------------------------

    summary = calculate_global_summary(
        actual,
        lstm,
        persistence,
        observation_df,
        feature_df,
        sensor_df,
    )

    # --------------------------------------------------------
    # 12. Recommendations
    # --------------------------------------------------------

    recommendations = (
        generate_recommendations(
            summary,
            feature_df,
            sensor_df,
            change_summary,
        )
    )

    # --------------------------------------------------------
    # 13. Save report
    # --------------------------------------------------------

    save_report(
        summary,
        recommendations,
    )

    # --------------------------------------------------------
    # 14. Plots
    # --------------------------------------------------------

    print_header("CREATING ERROR ANALYSIS PLOTS")

    plot_feature_error_comparison(
        feature_df
    )

    plot_sensor_error_comparison(
        sensor_df
    )

    plot_error_distribution(
        actual,
        lstm,
        persistence,
    )

    plot_change_vs_error(
        change_df
    )

    plot_sample_mae(
        observation_df
    )

    # --------------------------------------------------------
    # 15. Final summary
    # --------------------------------------------------------

    print_final_summary(
        summary,
        feature_df,
        sensor_df,
        recommendations,
    )

    print()
    print("=" * 70)
    print(
        "YOLO LSTM ERROR ANALYSIS COMPLETED"
    )
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    warnings.filterwarnings(
        "ignore",
        category=RuntimeWarning,
    )

    main()