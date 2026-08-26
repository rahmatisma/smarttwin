from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


INTERVAL_SECONDS = 5
ZONE_CAPACITY = 33.0
APPROACHES = ("west", "south", "east", "north")

CROSS_LABEL_MAP = {
    "barat": "west",
    "selatan": "south",
    "DIPONEGORO": "east",
    "MAGELANG": "north",
}

SNAPSHOT_APPROACH_MAP = {
    "barat": "west",
    "selatan": "south",
    "timur": "east",
    "simpang_tengah": "north",
}

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
DEFAULT_CROSSING = DATA_DIR / "crossing_simpang.csv"
DEFAULT_SNAPSHOT = DATA_DIR / "snapshot_zona.csv"
DEFAULT_OUTPUT = DATA_DIR / "processed" / "traffic_per_approach_5s.csv"

TRAFFIC_FEATURES = (
    "vehicleCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
)


def _require_columns(frame: pd.DataFrame, columns: set[str], source: Path) -> None:
    missing = sorted(columns.difference(frame.columns))
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan di {source}: {missing}")


def load_crossing(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    _require_columns(frame, {"timestamp", "label_garis", "jumlah_crossing"}, path)

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["approach"] = frame["label_garis"].map(CROSS_LABEL_MAP)
    frame["vehicleCount"] = pd.to_numeric(
        frame["jumlah_crossing"], errors="coerce"
    ).fillna(0.0)
    frame = frame.dropna(subset=["timestamp", "approach"])
    frame["timestamp"] = frame["timestamp"].dt.floor(f"{INTERVAL_SECONDS}s")

    return (
        frame.groupby(["timestamp", "approach"], as_index=False)
        .agg(vehicleCount=("vehicleCount", "sum"))
        .sort_values(["approach", "timestamp"])
    )


def load_snapshot(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    _require_columns(frame, {"timestamp", "lengan", "total_di_zona"}, path)

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame["approach"] = frame["lengan"].map(SNAPSHOT_APPROACH_MAP)
    frame = frame.dropna(subset=["timestamp", "approach"])
    frame["timestamp"] = frame["timestamp"].dt.floor(f"{INTERVAL_SECONDS}s")

    numeric_columns = (
        "total_di_zona",
        "queue_length_veh",
        "queue_length_m_est",
    )
    for column in numeric_columns:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    result = (
        frame.groupby(["timestamp", "approach"], as_index=False)
        .agg(
            totalInZone=("total_di_zona", "mean"),
            queueLengthVeh=("queue_length_veh", "mean"),
            queueLengthMEst=("queue_length_m_est", "mean"),
        )
        .sort_values(["approach", "timestamp"])
    )
    result["densityIndex"] = (result["totalInZone"] / ZONE_CAPACITY).clip(0, 1)
    return result.drop(columns=["totalInZone"])


def prepare_dataset(crossing_path: Path, snapshot_path: Path) -> pd.DataFrame:
    crossing = load_crossing(crossing_path)
    snapshot = load_snapshot(snapshot_path)

    # Inner join sengaja dipakai: model hanya menerima timestep yang benar-benar
    # memiliki observasi crossing dan zona. Gap tidak diisi traffic nol palsu.
    merged = pd.merge(
        crossing,
        snapshot,
        on=["timestamp", "approach"],
        how="inner",
        validate="one_to_one",
    )
    merged = merged.replace([np.inf, -np.inf], np.nan)
    merged = merged.dropna(subset=list(TRAFFIC_FEATURES))
    merged["vehicleCount"] = merged["vehicleCount"].clip(lower=0)
    merged["queueLengthVeh"] = merged["queueLengthVeh"].clip(lower=0)
    merged["queueLengthMEst"] = merged["queueLengthMEst"].clip(lower=0)
    merged["densityIndex"] = merged["densityIndex"].clip(0, 1)

    merged["isNorthProxy"] = merged["approach"].eq("north")
    merged = merged[
        ["timestamp", "approach", *TRAFFIC_FEATURES, "isNorthProxy"]
    ].sort_values(["timestamp", "approach"]).reset_index(drop=True)

    missing_approaches = set(APPROACHES).difference(merged["approach"].unique())
    if missing_approaches:
        raise ValueError(f"Dataset tidak memiliki approach: {sorted(missing_approaches)}")
    return merged


def print_summary(frame: pd.DataFrame) -> None:
    print("\nDataset per-approach siap:")
    print(frame.groupby("approach").size().to_string())
    print(f"Rentang: {frame['timestamp'].min()} sampai {frame['timestamp'].max()}")
    for approach, group in frame.groupby("approach"):
        gaps = group["timestamp"].sort_values().diff().dt.total_seconds()
        print(
            f"{approach:>5}: rows={len(group)}, "
            f"gap_non_5s={int((gaps.dropna() != INTERVAL_SECONDS).sum())}"
        )
    print("\nCatatan: north memakai zona simpang_tengah sebagai proxy.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare traffic per approach")
    parser.add_argument("--crossing", type=Path, default=DEFAULT_CROSSING)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    frame = prepare_dataset(args.crossing, args.snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print_summary(frame)
    print(f"\nTersimpan: {args.output}")


if __name__ == "__main__":
    main()
