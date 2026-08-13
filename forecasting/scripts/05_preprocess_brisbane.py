"""
05_preprocess_brisbane.py

Preprocess Brisbane Traffic Management — Intersection volume dataset.

Input:
    data/Brisbane.csv

Output:
    outputs/brisbane/processed/brisbane_processed.csv
    outputs/brisbane/processed/brisbane_metadata.json
    outputs/brisbane/processed/feature_config.json

Dataset source:
    Brisbane City Council Open Data
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "Brisbane.csv"
)

OUTPUT_DIR = (
    BASE_DIR
    / "outputs"
    / "brisbane"
    / "processed"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "brisbane_processed.csv"
)

METADATA_FILE = (
    OUTPUT_DIR
    / "brisbane_metadata.json"
)

FEATURE_CONFIG_FILE = (
    OUTPUT_DIR
    / "feature_config.json"
)


# ============================================================
# CONFIGURATION
# ============================================================

SEQUENCE_LENGTH = 16

FORECAST_HORIZON = 1

TRAIN_RATIO = 0.70

VAL_RATIO = 0.15

TEST_RATIO = 0.15


# ============================================================
# REQUIRED COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "recorded",
    "ct",
    "link_plan",
    "ss",
    "tsc",
    "lane",
    "ds1",
    "mf1",
    "rf1",
    "ds2",
    "mf2",
    "rf2",
    "ds3",
    "mf3",
    "rf3",
    "ds4",
    "mf4",
    "rf4",
]


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("BRISBANE TRAFFIC DATA PREPROCESSING")
    print("=" * 70)

    # --------------------------------------------------------
    # FILE CHECK
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n{INPUT_FILE}"
        )

    print()
    print("[OK] Dataset ditemukan:")
    print(f"     {INPUT_FILE}")

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DATA LOADING")
    print("=" * 70)

    df = pd.read_csv(
        INPUT_FILE
    )

    print(
        f"[INFO] Rows    : {len(df):,}"
    )

    print(
        f"[INFO] Columns : {len(df.columns)}"
    )

    # --------------------------------------------------------
    # VALIDATE COLUMNS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("COLUMN VALIDATION")
    print("=" * 70)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
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
        "[OK] Semua kolom dataset tersedia."
    )

    # --------------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("TIMESTAMP PROCESSING")
    print("=" * 70)

    df["recorded"] = pd.to_datetime(
        df["recorded"],
        errors="coerce",
        utc=True
    )

    missing_timestamp = (
        df["recorded"]
        .isna()
        .sum()
    )

    print(
        f"[INFO] Invalid timestamps: "
        f"{missing_timestamp}"
    )

    df = df.dropna(
        subset=["recorded"]
    ).copy()

    # --------------------------------------------------------
    # NUMERIC COLUMNS
    # --------------------------------------------------------

    numeric_columns = [
        "ct",
        "link_plan",
        "ss",
        "tsc",
        "ds1",
        "mf1",
        "rf1",
        "ds2",
        "mf2",
        "rf2",
        "ds3",
        "mf3",
        "rf3",
        "ds4",
        "mf4",
        "rf4",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # DATA RANGE
    # --------------------------------------------------------

    print()
    print(
        f"[INFO] Time range:"
    )

    print(
        f"       {df['recorded'].min()}"
    )

    print(
        f"       {df['recorded'].max()}"
    )

    # --------------------------------------------------------
    # FIND BEST INTERSECTION
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("INTERSECTION SELECTION")
    print("=" * 70)

    tsc_counts = (
        df.groupby("tsc")
        .size()
        .sort_values(
            ascending=False
        )
    )

    if len(tsc_counts) == 0:

        raise ValueError(
            "Tidak ditemukan TSC."
        )

    selected_tsc = tsc_counts.index[0]

    selected_count = (
        tsc_counts.iloc[0]
    )

    print(
        f"[INFO] TSC terpilih: "
        f"{selected_tsc}"
    )

    print(
        f"[INFO] Jumlah records: "
        f"{selected_count:,}"
    )

    print()
    print(
        "[INFO] Top 10 TSC berdasarkan jumlah records:"
    )

    for tsc, count in (
        tsc_counts.head(10).items()
    ):

        print(
            f"       TSC {tsc}: "
            f"{count:,} records"
        )

    # --------------------------------------------------------
    # FILTER TSC
    # --------------------------------------------------------

    df = df[
        df["tsc"] == selected_tsc
    ].copy()

    # --------------------------------------------------------
    # CREATE FLOW FEATURES
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("CREATING TRAFFIC FEATURES")
    print("=" * 70)

    measured_flow_columns = [
        "mf1",
        "mf2",
        "mf3",
        "mf4",
    ]

    saturation_columns = [
        "ds1",
        "ds2",
        "ds3",
        "ds4",
    ]

    # --------------------------------------------------------
    # Vehicle count
    # --------------------------------------------------------

    df["vehicle_count"] = (
        df[
            measured_flow_columns
        ]
        .fillna(0)
        .sum(axis=1)
    )

    # --------------------------------------------------------
    # Reconstituted flow
    # --------------------------------------------------------

    df["reconstituted_flow"] = (
        df[
            [
                "rf1",
                "rf2",
                "rf3",
                "rf4",
            ]
        ]
        .fillna(0)
        .sum(axis=1)
    )

    # --------------------------------------------------------
    # Density / saturation proxy
    # --------------------------------------------------------

    df["density_proxy"] = (
        df[
            saturation_columns
        ]
        .mean(
            axis=1,
            skipna=True
        )
    )

    # --------------------------------------------------------
    # Queue proxy
    # --------------------------------------------------------

    df["queue_proxy"] = (
        df["vehicle_count"]
        *
        (
            df["density_proxy"]
            / 100.0
        )
    )

    # --------------------------------------------------------
    # CYCLE TIME
    # --------------------------------------------------------

    df["cycle_time"] = (
        df["ct"]
    )

    # --------------------------------------------------------
    # AGGREGATE TO ONE TIMESTAMP
    # --------------------------------------------------------

    print()
    print(
        "[INFO] Aggregating records per minute..."
    )

    df["timestamp"] = (
        df["recorded"]
        .dt.floor("min")
    )

    aggregated = (
        df.groupby("timestamp")
        .agg(
            vehicle_count=(
                "vehicle_count",
                "sum"
            ),

            reconstituted_flow=(
                "reconstituted_flow",
                "sum"
            ),

            density_proxy=(
                "density_proxy",
                "mean"
            ),

            queue_proxy=(
                "queue_proxy",
                "sum"
            ),

            cycle_time=(
                "cycle_time",
                "mean"
            ),

            link_plan=(
                "link_plan",
                "mean"
            ),
        )
        .reset_index()
    )

    aggregated = (
        aggregated
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # REMOVE DUPLICATE TIMESTAMPS
    # --------------------------------------------------------

    print(
        f"[INFO] Aggregated rows: "
        f"{len(aggregated):,}"
    )

    # --------------------------------------------------------
    # TIME FEATURES
    # --------------------------------------------------------

    print()
    print(
        "[INFO] Creating time features..."
    )

    aggregated["hour"] = (
        aggregated[
            "timestamp"
        ].dt.hour
    )

    aggregated["minute"] = (
        aggregated[
            "timestamp"
        ].dt.minute
    )

    aggregated["hour_sin"] = (
        np.sin(
            2
            * np.pi
            * (
                aggregated["hour"]
                / 24
            )
        )
    )

    aggregated["hour_cos"] = (
        np.cos(
            2
            * np.pi
            * (
                aggregated["hour"]
                / 24
            )
        )
    )

    aggregated["day_sin"] = (
        np.sin(
            2
            * np.pi
            * (
                aggregated[
                    "timestamp"
                ].dt.dayofweek
                / 7
            )
        )
    )

    aggregated["day_cos"] = (
        np.cos(
            2
            * np.pi
            * (
                aggregated[
                    "timestamp"
                ].dt.dayofweek
                / 7
            )
        )
    )

    aggregated["is_weekend"] = (
        aggregated[
            "timestamp"
        ].dt.dayofweek >= 5
    ).astype(int)

    # --------------------------------------------------------
    # CHANGE FEATURES
    # --------------------------------------------------------

    aggregated[
        "vehicle_count_change"
    ] = (
        aggregated[
            "vehicle_count"
        ].diff()
    )

    aggregated[
        "density_change"
    ] = (
        aggregated[
            "density_proxy"
        ].diff()
    )

    # --------------------------------------------------------
    # ROLLING FEATURES
    # --------------------------------------------------------

    aggregated[
        "vehicle_count_rolling_mean_15m"
    ] = (
        aggregated[
            "vehicle_count"
        ]
        .rolling(
            window=15,
            min_periods=1
        )
        .mean()
    )

    aggregated[
        "vehicle_count_rolling_std_15m"
    ] = (
        aggregated[
            "vehicle_count"
        ]
        .rolling(
            window=15,
            min_periods=1
        )
        .std()
        .fillna(0)
    )

    aggregated[
        "density_rolling_mean_15m"
    ] = (
        aggregated[
            "density_proxy"
        ]
        .rolling(
            window=15,
            min_periods=1
        )
        .mean()
    )

    # --------------------------------------------------------
    # CLEAN
    # --------------------------------------------------------

    numeric_columns_final = (
        aggregated
        .select_dtypes(
            include=[np.number]
        )
        .columns
    )

    aggregated[
        numeric_columns_final
    ] = (
        aggregated[
            numeric_columns_final
        ]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .fillna(0)
    )

    # --------------------------------------------------------
    # FEATURE CONFIG
    # --------------------------------------------------------

    input_features = [
        "vehicle_count",
        "reconstituted_flow",
        "density_proxy",
        "queue_proxy",
        "cycle_time",
        "link_plan",
        "vehicle_count_change",
        "density_change",
        "vehicle_count_rolling_mean_15m",
        "vehicle_count_rolling_std_15m",
        "density_rolling_mean_15m",
        "hour_sin",
        "hour_cos",
        "day_sin",
        "day_cos",
        "is_weekend",
    ]

    target_features = [
        "vehicle_count",
        "density_proxy",
        "queue_proxy",
    ]

    # --------------------------------------------------------
    # SAVE PROCESSED DATA
    # --------------------------------------------------------

    aggregated.to_csv(
        OUTPUT_FILE,
        index=False
    )

    # --------------------------------------------------------
    # SAVE CONFIG
    # --------------------------------------------------------

    feature_config = {

        "input_features": input_features,

        "target_features": target_features,

        "sequence_length": SEQUENCE_LENGTH,

        "forecast_horizons": [
            FORECAST_HORIZON
        ],

        "train_ratio": TRAIN_RATIO,

        "val_ratio": VAL_RATIO,

        "test_ratio": TEST_RATIO,

        "selected_tsc": int(
            selected_tsc
        ),

        "note": (
            "Speed is not included because "
            "the Brisbane dataset does not "
            "provide direct speed measurements."
        ),
    }

    with open(
        FEATURE_CONFIG_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            feature_config,
            file,
            indent=4
        )

    # --------------------------------------------------------
    # SAVE METADATA
    # --------------------------------------------------------

    metadata = {

        "dataset": (
            "Brisbane City Council "
            "Traffic Management — "
            "Intersection volume"
        ),

        "selected_tsc": int(
            selected_tsc
        ),

        "original_rows": int(
            len(df)
        ),

        "processed_rows": int(
            len(aggregated)
        ),

        "start_time": str(
            aggregated[
                "timestamp"
            ].min()
        ),

        "end_time": str(
            aggregated[
                "timestamp"
            ].max()
        ),

        "targets": target_features,

        "input_features": input_features,

        "sequence_length": (
            SEQUENCE_LENGTH
        ),

        "forecast_horizon": (
            FORECAST_HORIZON
        ),
    }

    with open(
        METADATA_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PREPROCESSING COMPLETED")
    print("=" * 70)

    print()
    print(
        f"[OK] Selected TSC: "
        f"{selected_tsc}"
    )

    print(
        f"[OK] Processed rows: "
        f"{len(aggregated):,}"
    )

    print(
        f"[OK] Time range:"
    )

    print(
        f"     {aggregated['timestamp'].min()}"
    )

    print(
        f"     {aggregated['timestamp'].max()}"
    )

    print()
    print(
        "[OK] Input features:"
    )

    for index, feature in enumerate(
        input_features,
        start=1
    ):

        print(
            f"     {index:02d}. {feature}"
        )

    print()
    print(
        "[OK] Targets:"
    )

    for index, target in enumerate(
        target_features,
        start=1
    ):

        print(
            f"     {index}. {target}"
        )

    print()
    print(
        f"[SAVED] {OUTPUT_FILE}"
    )

    print(
        f"[SAVED] {FEATURE_CONFIG_FILE}"
    )

    print(
        f"[SAVED] {METADATA_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()