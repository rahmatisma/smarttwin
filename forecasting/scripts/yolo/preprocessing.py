from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


# ============================================================
# APPROACH MAPPING
# ============================================================

APPROACH_MAPPING = {
    "selatan": "south",
    "utara": "north",
    "barat": "west",
    "timur": "east",
}


# ============================================================
# FEATURES
# ============================================================

FEATURE_COLUMNS = [
    "south_total",
    "west_total",
    "east_total",
    "north_total",
]


# ============================================================
# LOAD + PREPARE
# ============================================================

def prepare_dataframe(
    filepath: str,
) -> pd.DataFrame:

    filepath = Path(filepath)

    if not filepath.exists():

        raise FileNotFoundError(
            f"Dataset tidak ditemukan:\n{filepath}"
        )

    print(
        f"Loading dataset:\n{filepath}"
    )

    df = pd.read_csv(filepath)

    required_columns = [
        "timestamp",
        "kamera",
        "lengan",
        "total_di_zona",
    ]

    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:

        raise ValueError(
            "Kolom dataset tidak lengkap. "
            f"Missing: {missing}"
        )

    # --------------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["timestamp"]
    )

    # --------------------------------------------------------
    # NORMALIZE APPROACH
    # --------------------------------------------------------

    df["lengan"] = (
        df["lengan"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["approach"] = (
        df["lengan"]
        .map(APPROACH_MAPPING)
    )

    # --------------------------------------------------------
    # NUMERIC
    # --------------------------------------------------------

    df["total_di_zona"] = pd.to_numeric(
        df["total_di_zona"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["total_di_zona"]
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    df = df.sort_values(
        "timestamp"
    )

    # --------------------------------------------------------
    # AGGREGATE
    # --------------------------------------------------------

    pivot = (
        df
        .pivot_table(
            index="timestamp",
            columns="approach",
            values="total_di_zona",
            aggfunc="mean",
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # ENSURE ALL APPROACHES
    # --------------------------------------------------------

    for approach in [
        "south",
        "west",
        "east",
        "north",
    ]:

        if approach not in pivot.columns:

            pivot[approach] = 0.0

    # --------------------------------------------------------
    # RENAME
    # --------------------------------------------------------

    pivot = pivot.rename(
        columns={
            "south": "south_total",
            "west": "west_total",
            "east": "east_total",
            "north": "north_total",
        }
    )

    # --------------------------------------------------------
    # REINDEX
    # --------------------------------------------------------

    pivot = pivot[
        [
            "timestamp",
            "south_total",
            "west_total",
            "east_total",
            "north_total",
        ]
    ]

    # --------------------------------------------------------
    # RESAMPLE 5 SECOND
    # --------------------------------------------------------

    pivot = (
        pivot
        .set_index("timestamp")
        .resample("5s")
        .mean()
    )

    # --------------------------------------------------------
    # MISSING VALUE
    # --------------------------------------------------------

    pivot[FEATURE_COLUMNS] = (
        pivot[FEATURE_COLUMNS]
        .interpolate(
            method="linear",
            limit_direction="both",
        )
    )

    pivot[FEATURE_COLUMNS] = (
        pivot[FEATURE_COLUMNS]
        .fillna(0.0)
    )

    pivot = pivot.reset_index()

    # --------------------------------------------------------
    # REMOVE IMPOSSIBLE NEGATIVE
    # --------------------------------------------------------

    pivot[FEATURE_COLUMNS] = (
        pivot[FEATURE_COLUMNS]
        .clip(lower=0)
    )

    return pivot


# ============================================================
# FEATURES
# ============================================================

def get_feature_columns():

    return FEATURE_COLUMNS.copy()


# ============================================================
# TRANSFORM
# ============================================================

def transform_dataframe(
    df: pd.DataFrame,
    scaler: MinMaxScaler,
):

    values = scaler.transform(
        df[FEATURE_COLUMNS]
    )

    return values.astype(
        np.float32
    )


# ============================================================
# SEQUENCES
# ============================================================

def create_sequences(
    values,
    lookback: int,
    horizon: int,
):

    X = []

    y = []

    total_length = len(values)

    max_start = (
        total_length
        - lookback
        - horizon
        + 1
    )

    for i in range(
        max_start
    ):

        X.append(
            values[
                i : i + lookback
            ]
        )

        y.append(
            values[
                i + lookback :
                i + lookback + horizon
            ]
        )

    if not X:

        raise ValueError(
            "Tidak cukup data untuk membuat sequence.\n"
            f"Jumlah rows: {total_length}\n"
            f"LOOKBACK: {lookback}\n"
            f"HORIZON: {horizon}"
        )

    return (
        np.asarray(
            X,
            dtype=np.float32,
        ),
        np.asarray(
            y,
            dtype=np.float32,
        ),
    )