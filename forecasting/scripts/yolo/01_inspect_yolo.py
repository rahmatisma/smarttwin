from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_PATH = (
    BASE_DIR
    / "data"
    / "smarttwin_traffic_data_copy.csv"
)


# ============================================================
# CONFIGURATION
# ============================================================

FEATURE_NAMES = [
    "vehicle_count",
    "queue_length_veh",
    "density_index"
]


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("YOLO TRAFFIC DATASET INSPECTION")
    print("=" * 70)

    print()
    print("[INFO] Dataset:")
    print(f"       {DATA_PATH}")

    if not DATA_PATH.exists():

        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n{DATA_PATH}"
        )

    df = pd.read_csv(
        DATA_PATH
    )

    print()
    print("=" * 70)
    print("DATASET INFORMATION")
    print("=" * 70)

    print(
        f"[INFO] Rows           : "
        f"{len(df):,}"
    )

    print(
        f"[INFO] Columns        : "
        f"{len(df.columns)}"
    )

    print(
        f"[INFO] Timestamp count: "
        f"{df['timestamp'].nunique():,}"
    )

    print()
    print("[INFO] Columns:")

    for column in df.columns:

        print(
            f"       - {column}"
        )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    print()
    print("=" * 70)
    print("TIME RANGE")
    print("=" * 70)

    print(
        f"[INFO] Start: "
        f"{df['timestamp'].min()}"
    )

    print(
        f"[INFO] End  : "
        f"{df['timestamp'].max()}"
    )

    print(
        f"[INFO] Duration: "
        f"{df['timestamp'].max() - df['timestamp'].min()}"
    )

    # --------------------------------------------------------
    # Intersection
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("INTERSECTION")
    print("=" * 70)

    print(
        df["intersection_id"]
        .value_counts()
        .to_string()
    )

    # --------------------------------------------------------
    # Approaches
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("APPROACHES")
    print("=" * 70)

    print(
        df["approach"]
        .value_counts()
        .to_string()
    )

    # --------------------------------------------------------
    # Lanes
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("LANES")
    print("=" * 70)

    print(
        df["lane_id"]
        .value_counts()
        .to_string()
    )

    # --------------------------------------------------------
    # Sensors
    # --------------------------------------------------------

    sensor_table = (
        df[
            [
                "approach",
                "lane_id"
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "approach",
                "lane_id"
            ]
        )
    )

    print()
    print("=" * 70)
    print("SENSOR CANDIDATES")
    print("=" * 70)

    print(
        sensor_table.to_string(
            index=False
        )
    )

    print()
    print(
        f"[INFO] Number of lane sensors: "
        f"{len(sensor_table)}"
    )

    # --------------------------------------------------------
    # Features
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SELECTED FEATURES")
    print("=" * 70)

    for feature in FEATURE_NAMES:

        print(
            f"[INFO] {feature}"
        )

        print(
            f"       min  : "
            f"{df[feature].min()}"
        )

        print(
            f"       max  : "
            f"{df[feature].max()}"
        )

        print(
            f"       mean : "
            f"{df[feature].mean()}"
        )

    # --------------------------------------------------------
    # Timestamp interval
    # --------------------------------------------------------

    timestamps = (
        df["timestamp"]
        .drop_duplicates()
        .sort_values()
    )

    differences = (
        timestamps.diff()
        .dropna()
    )

    print()
    print("=" * 70)
    print("TIMESTAMP INTERVAL")
    print("=" * 70)

    print(
        differences
        .value_counts()
        .head(15)
        .to_string()
    )

    # --------------------------------------------------------
    # Rows per timestamp
    # --------------------------------------------------------

    rows_per_timestamp = (
        df.groupby(
            "timestamp"
        )
        .size()
    )

    print()
    print("=" * 70)
    print("ROWS PER TIMESTAMP")
    print("=" * 70)

    print(
        rows_per_timestamp
        .describe()
        .to_string()
    )

    # --------------------------------------------------------
    # Missing lane combinations
    # --------------------------------------------------------

    expected_sensors = (
        df[
            [
                "approach",
                "lane_id"
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "approach",
                "lane_id"
            ]
        )
    )

    expected_sensor_count = (
        len(expected_sensors)
    )

    incomplete = (
        rows_per_timestamp
        < expected_sensor_count
    )

    print()
    print(
        f"[INFO] Expected sensors/timestep: "
        f"{expected_sensor_count}"
    )

    print(
        f"[INFO] Incomplete timestamps: "
        f"{incomplete.sum():,}"
    )

    print()
    print("=" * 70)
    print("INSPECTION COMPLETED")
    print("=" * 70)


if __name__ == "__main__":

    main()