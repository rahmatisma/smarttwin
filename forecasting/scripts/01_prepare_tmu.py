from pathlib import Path
import json
import re

import numpy as np
import pandas as pd


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "TMU.csv"
OUTPUT_DIR = BASE_DIR / "outputs"

PROCESSED_DIR = OUTPUT_DIR / "processed"
METRICS_DIR = OUTPUT_DIR / "metrics"


# ============================================================
# EXPECTED RAW COLUMNS
# ============================================================

RAW_COLUMNS = [
    "local_date",
    "local_time",
    "day_type_id",
    "total_carriageway_flow",
    "vehicles_less_5_2m",
    "vehicles_5_21m_6_6m",
    "vehicles_6_61m_11_6m",
    "vehicles_above_11_6m",
    "speed_value",
    "quality_index",
    "network_link_id",
    "ntis_model_version",
]


# ============================================================
# VEHICLE CLASSIFICATION
# ============================================================
#
# IMPORTANT:
#
# We DO NOT call these:
#   small / medium / large
#
# because the original TMU data only provides vehicle
# length categories.
#
# These are kept as the original length-based categories.
# ============================================================

VEHICLE_COLUMNS = [
    "vehicles_less_5_2m",
    "vehicles_5_21m_6_6m",
    "vehicles_6_61m_11_6m",
    "vehicles_above_11_6m",
]


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clean_numeric_value(value):
    """
    Clean values that may contain markdown-like characters,
    whitespace, commas, or other non-numeric characters.

    Examples:
        '*1'       -> 1
        '**99.37'  -> 99.37
        ' 15 '     -> 15
        ''         -> NaN
    """

    if pd.isna(value):
        return np.nan

    value = str(value).strip()

    if value == "":
        return np.nan

    # Remove markdown formatting characters
    value = value.replace("*", "")

    # Remove possible backticks
    value = value.replace("`", "")

    # Keep digits, decimal point and minus sign
    value = re.sub(r"[^0-9.\-]", "", value)

    if value in ("", "-", ".", "-."):
        return np.nan

    try:
        return float(value)
    except ValueError:
        return np.nan


def find_data_header(file_path):
    """
    Find the actual traffic-data header.

    The TMU file contains metadata first:

        TMU ID, Legacy TMU ID, Site Name

    followed later by:

        Local Date, Local Time, Day Type ID, ...

    We locate the second header dynamically instead of
    hard-coding skiprows=3.
    """

    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:

        for line_number, line in enumerate(f):

            normalized = line.strip().lower()

            if (
                normalized.startswith("local date")
                and "local time" in normalized
                and "total carriageway flow" in normalized
            ):
                return line_number

    raise ValueError(
        "Tidak ditemukan header data TMU "
        "'Local Date, Local Time, ...' di file."
    )


def extract_metadata(file_path):
    """
    Extract the TMU metadata from the first section.
    """

    metadata = {}

    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:

        lines = [line.strip() for line in f.readlines()]

    if len(lines) >= 2:

        # First metadata header
        metadata_header = lines[0].split(",")

        # Second metadata row
        metadata_values = lines[1].split(",")

        if len(metadata_header) >= 1:
            metadata["tmu_id"] = metadata_values[0].strip()

        if len(metadata_header) >= 2:
            metadata["legacy_tmu_id"] = metadata_values[1].strip()

        if len(metadata_values) >= 3:

            metadata["site_name"] = ",".join(
                metadata_values[2:]
            ).strip()

    return metadata


# ============================================================
# LOAD DATA
# ============================================================

def load_data(file_path):

    print(f"[INFO] Loading: {file_path}")

    header_row = find_data_header(file_path)

    print(f"[INFO] Data header found at CSV line: {header_row + 1}")

    metadata = extract_metadata(file_path)

    print("[INFO] TMU metadata:")
    print(f"       TMU ID        : {metadata.get('tmu_id', 'N/A')}")
    print(f"       Legacy TMU ID: {metadata.get('legacy_tmu_id', 'N/A')}")
    print(f"       Site          : {metadata.get('site_name', 'N/A')}")

    # Read ONLY the actual traffic table
    df = pd.read_csv(
        file_path,
        skiprows=header_row,
        header=0,
        encoding="utf-8-sig",
        engine="python",
    )

    # Remove accidental unnamed columns
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

    # Normalize column names
    df.columns = [
        str(column)
        .strip()
        .replace("*", "")
        for column in df.columns
    ]

    # Make sure the expected columns exist
    if len(df.columns) != len(RAW_COLUMNS):

        print(
            f"[WARNING] Expected {len(RAW_COLUMNS)} columns, "
            f"but found {len(df.columns)} columns."
        )

        print("[INFO] Columns detected:")

        for i, column in enumerate(df.columns):
            print(f"       {i}: {column}")

    # Rename based on column position
    if len(df.columns) >= len(RAW_COLUMNS):

        df = df.iloc[:, :len(RAW_COLUMNS)]
        df.columns = RAW_COLUMNS

    else:

        raise ValueError(
            f"Kolom data TMU kurang dari yang diharapkan. "
            f"Ditemukan {len(df.columns)}, "
            f"dibutuhkan minimal {len(RAW_COLUMNS)}."
        )

    return df, metadata


# ============================================================
# CLEAN DATA
# ============================================================

def clean_data(df):

    print("\n[INFO] Cleaning data...")

    df = df.copy()

    # --------------------------------------------------------
    # Remove completely empty rows
    # --------------------------------------------------------

    before = len(df)

    df = df.dropna(how="all")

    print(
        f"[INFO] Removed empty rows: "
        f"{before - len(df)}"
    )

    # --------------------------------------------------------
    # Clean string columns
    # --------------------------------------------------------

    df["local_date"] = (
        df["local_date"]
        .astype(str)
        .str.strip()
    )

    df["local_time"] = (
        df["local_time"]
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # Numeric columns
    # --------------------------------------------------------

    numeric_columns = [
        "day_type_id",
        "total_carriageway_flow",
        "vehicles_less_5_2m",
        "vehicles_5_21m_6_6m",
        "vehicles_6_61m_11_6m",
        "vehicles_above_11_6m",
        "speed_value",
        "quality_index",
        "network_link_id",
        "ntis_model_version",
    ]

    for column in numeric_columns:

        df[column] = df[column].apply(
            clean_numeric_value
        )

    # --------------------------------------------------------
    # Timestamp
    # --------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["local_date"] + " " + df["local_time"],
        errors="coerce",
    )

    invalid_timestamp = df["timestamp"].isna().sum()

    if invalid_timestamp > 0:

        print(
            f"[WARNING] Invalid timestamps: "
            f"{invalid_timestamp}"
        )

    # --------------------------------------------------------
    # Remove rows without essential values
    # --------------------------------------------------------

    essential_columns = [
        "timestamp",
        "total_carriageway_flow",
        "speed_value",
    ]

    before = len(df)

    df = df.dropna(
        subset=essential_columns
    )

    print(
        f"[INFO] Removed rows missing essential values: "
        f"{before - len(df)}"
    )

    # --------------------------------------------------------
    # Sort chronologically
    # --------------------------------------------------------

    df = (
        df
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Remove duplicate timestamps
    # --------------------------------------------------------
    #
    # For a single TMU site, one timestamp should represent
    # one observation.
    # --------------------------------------------------------

    duplicate_count = df["timestamp"].duplicated().sum()

    if duplicate_count > 0:

        print(
            f"[WARNING] Duplicate timestamps found: "
            f"{duplicate_count}"
        )

        df = (
            df
            .drop_duplicates(
                subset=["timestamp"],
                keep="first",
            )
            .reset_index(drop=True)
        )

    return df


# ============================================================
# FEATURE ENGINEERING
# ============================================================

def create_features(df):

    print("\n[INFO] Creating forecasting features...")

    df = df.copy()

    # --------------------------------------------------------
    # Original traffic flow
    # --------------------------------------------------------

    df["vehicle_count"] = (
        df["total_carriageway_flow"]
    )

    # --------------------------------------------------------
    # Vehicle composition
    # --------------------------------------------------------

    df["vehicle_length_total"] = (
        df["vehicles_less_5_2m"]
        + df["vehicles_5_21m_6_6m"]
        + df["vehicles_6_61m_11_6m"]
        + df["vehicles_above_11_6m"]
    )

    # --------------------------------------------------------
    # Percentages
    # --------------------------------------------------------

    denominator = df["vehicle_count"].replace(
        0,
        np.nan
    )

    df["pct_vehicles_less_5_2m"] = (
        df["vehicles_less_5_2m"]
        / denominator
        * 100
    )

    df["pct_vehicles_5_21m_6_6m"] = (
        df["vehicles_5_21m_6_6m"]
        / denominator
        * 100
    )

    df["pct_vehicles_6_61m_11_6m"] = (
        df["vehicles_6_61m_11_6m"]
        / denominator
        * 100
    )

    df["pct_vehicles_above_11_6m"] = (
        df["vehicles_above_11_6m"]
        / denominator
        * 100
    )

    # --------------------------------------------------------
    # Time features
    # --------------------------------------------------------

    df["hour"] = df["timestamp"].dt.hour

    df["minute"] = df["timestamp"].dt.minute

    df["day_of_week"] = (
        df["timestamp"].dt.dayofweek
    )

    df["day_of_month"] = (
        df["timestamp"].dt.day
    )

    df["month"] = (
        df["timestamp"].dt.month
    )

    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype(int)

    # --------------------------------------------------------
    # Cyclic time encoding
    # --------------------------------------------------------

    df["hour_sin"] = np.sin(
        2 * np.pi * df["hour"] / 24
    )

    df["hour_cos"] = np.cos(
        2 * np.pi * df["hour"] / 24
    )

    df["day_sin"] = np.sin(
        2 * np.pi * df["day_of_week"] / 7
    )

    df["day_cos"] = np.cos(
        2 * np.pi * df["day_of_week"] / 7
    )

    # --------------------------------------------------------
    # Traffic change
    # --------------------------------------------------------

    df["vehicle_count_change"] = (
        df["vehicle_count"].diff()
    )

    df["speed_change"] = (
        df["speed_value"].diff()
    )

    # --------------------------------------------------------
    # Rolling traffic statistics
    # --------------------------------------------------------

    df["vehicle_count_rolling_mean_1h"] = (
        df["vehicle_count"]
        .rolling(window=4, min_periods=1)
        .mean()
    )

    df["vehicle_count_rolling_std_1h"] = (
        df["vehicle_count"]
        .rolling(window=4, min_periods=1)
        .std()
        .fillna(0)
    )

    df["speed_rolling_mean_1h"] = (
        df["speed_value"]
        .rolling(window=4, min_periods=1)
        .mean()
    )

    # --------------------------------------------------------
    # Density proxy
    # --------------------------------------------------------
    #
    # IMPORTANT:
    #
    # TMU does NOT provide road length / lane length.
    #
    # Therefore we cannot calculate physical traffic density
    # in vehicles/km directly.
    #
    # Instead, create a NORMALIZED DENSITY PROXY.
    #
    # This is useful for modeling but must NOT be claimed as
    # real physical density.
    # --------------------------------------------------------

    max_flow = df["vehicle_count"].max()

    if max_flow > 0:

        df["density_proxy"] = (
            df["vehicle_count"] / max_flow
        )

    else:

        df["density_proxy"] = 0.0

    # --------------------------------------------------------
    # Queue proxy
    # --------------------------------------------------------
    #
    # Again, TMU has no direct queue-length measurement.
    #
    # We therefore create a conservative proxy based on:
    #
    #   high traffic volume
    #   + reduced speed
    #
    # It is NOT a real queue measurement.
    # --------------------------------------------------------

    speed_threshold = (
        df["speed_value"]
        .quantile(0.25)
    )

    flow_threshold = (
        df["vehicle_count"]
        .quantile(0.75)
    )

    df["queue_proxy"] = np.where(
        (
            (df["vehicle_count"] >= flow_threshold)
            &
            (df["speed_value"] <= speed_threshold)
        ),
        df["vehicle_count"] * 0.30,
        0.0,
    )

    # --------------------------------------------------------
    # Missing values created by diff/rolling
    # --------------------------------------------------------

    df = df.replace(
        [np.inf, -np.inf],
        np.nan
    )

    return df


# ============================================================
# VALIDATION
# ============================================================

def validate_data(df):

    print("\n" + "=" * 70)
    print("DATA VALIDATION")
    print("=" * 70)

    print(
        f"[INFO] Total rows : {len(df):,}"
    )

    print(
        f"[INFO] Total cols : {len(df.columns)}"
    )

    print(
        f"[INFO] Time start : "
        f"{df['timestamp'].min()}"
    )

    print(
        f"[INFO] Time end   : "
        f"{df['timestamp'].max()}"
    )

    # --------------------------------------------------------
    # Sampling interval
    # --------------------------------------------------------

    intervals = (
        df["timestamp"]
        .sort_values()
        .diff()
        .dropna()
        .dt.total_seconds()
        / 60
    )

    if len(intervals) > 0:

        print(
            f"[INFO] Median interval: "
            f"{intervals.median():.2f} minutes"
        )

        print(
            f"[INFO] Min interval   : "
            f"{intervals.min():.2f} minutes"
        )

        print(
            f"[INFO] Max interval   : "
            f"{intervals.max():.2f} minutes"
        )

    # --------------------------------------------------------
    # Missing values
    # --------------------------------------------------------

    print("\n[INFO] Missing values:")

    missing = (
        df.isna()
        .sum()
        .sort_values(ascending=False)
    )

    for column, count in missing.items():

        if count > 0:

            percentage = (
                count / len(df) * 100
            )

            print(
                f"       {column}: "
                f"{count:,} "
                f"({percentage:.2f}%)"
            )

    # --------------------------------------------------------
    # Basic traffic statistics
    # --------------------------------------------------------

    print("\n[INFO] Traffic statistics:")

    print(
        f"       Vehicle count mean : "
        f"{df['vehicle_count'].mean():.2f}"
    )

    print(
        f"       Vehicle count max  : "
        f"{df['vehicle_count'].max():.2f}"
    )

    print(
        f"       Speed mean         : "
        f"{df['speed_value'].mean():.2f}"
    )

    print(
        f"       Speed min          : "
        f"{df['speed_value'].min():.2f}"
    )

    print(
        f"       Speed max          : "
        f"{df['speed_value'].max():.2f}"
    )


# ============================================================
# SAVE OUTPUT
# ============================================================

def save_outputs(df, metadata):

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    METRICS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Main processed dataset
    # --------------------------------------------------------

    output_csv = (
        PROCESSED_DIR
        / "tmu_processed.csv"
    )

    df.to_csv(
        output_csv,
        index=False
    )

    print(
        f"\n[OK] Processed dataset saved:"
    )

    print(
        f"     {output_csv}"
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata_output = (
        PROCESSED_DIR
        / "tmu_metadata.json"
    )

    with open(
        metadata_output,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            metadata,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(
        f"[OK] Metadata saved:"
    )

    print(
        f"     {metadata_output}"
    )

    # --------------------------------------------------------
    # Feature configuration
    # --------------------------------------------------------

    feature_config = {

        "target_variables": [
            "vehicle_count",
            "speed_value",
            "density_proxy",
            "queue_proxy",
        ],

        "vehicle_composition": [
            "vehicles_less_5_2m",
            "vehicles_5_21m_6_6m",
            "vehicles_6_61m_11_6m",
            "vehicles_above_11_6m",
        ],

        "time_features": [
            "hour",
            "minute",
            "day_of_week",
            "day_of_month",
            "month",
            "is_weekend",
            "hour_sin",
            "hour_cos",
            "day_sin",
            "day_cos",
        ],

        "traffic_features": [
            "vehicle_count_change",
            "speed_change",
            "vehicle_count_rolling_mean_1h",
            "vehicle_count_rolling_std_1h",
            "speed_rolling_mean_1h",
        ],

        "proxy_features": [
            "density_proxy",
            "queue_proxy",
        ],

        "notes": [
            "density_proxy is NOT physical density.",
            "queue_proxy is NOT measured queue length.",
            "TMU vehicle classes are length-based categories.",
        ],
    }

    config_output = (
        PROCESSED_DIR
        / "feature_config.json"
    )

    with open(
        config_output,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            feature_config,
            f,
            indent=4
        )

    print(
        f"[OK] Feature configuration saved:"
    )

    print(
        f"     {config_output}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("TMU DATA PREPARATION")
    print("=" * 70)

    # --------------------------------------------------------
    # Check input
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"File tidak ditemukan:\n{INPUT_FILE}"
        )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    df, metadata = load_data(
        INPUT_FILE
    )

    print(
        f"\n[INFO] Raw data rows: "
        f"{len(df):,}"
    )

    # --------------------------------------------------------
    # Clean
    # --------------------------------------------------------

    df = clean_data(df)

    # --------------------------------------------------------
    # Feature engineering
    # --------------------------------------------------------

    df = create_features(df)

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    validate_data(df)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_outputs(
        df,
        metadata
    )

    print("\n" + "=" * 70)
    print("TMU PREPARATION COMPLETE")
    print("=" * 70)

    print(
        "\n[INFO] Next step:"
    )

    print(
        "       python scripts/02_train_lstm.py"
    )


if __name__ == "__main__":
    main()