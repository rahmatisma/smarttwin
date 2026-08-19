from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from app.schemas.traffic import Approach, ApproachState, TrafficState


# ============================================================
# Configuration
# ============================================================

CSV_PATH = (
    Path(__file__).resolve().parents[3]
    / "cv"
    / "output"
    / "smarttwin_traffic_data.csv"
)

WINDOW_SECONDS = 5


# ============================================================
# CSV → TrafficState
# ============================================================

def load_traffic_csv() -> pd.DataFrame:
    """
    Membaca data traffic hasil Computer Vision dari CSV.
    """

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Traffic CSV tidak ditemukan: {CSV_PATH}"
        )

    df = pd.read_csv(CSV_PATH)

    required_columns = [
        "timestamp",
        "intersection_id",
        "approach",
        "lane_id",
        "vehicle_count",
        "car_count",
        "motorcycle_count",
        "bus_count",
        "truck_count",
        "queue_length_veh",
        "queue_length_m_est",
        "density_index",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom CSV tidak lengkap. Missing: {missing_columns}"
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    numeric_columns = [
        "vehicle_count",
        "car_count",
        "motorcycle_count",
        "bus_count",
        "truck_count",
        "queue_length_veh",
        "queue_length_m_est",
        "density_index",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "timestamp",
            "intersection_id",
            "approach",
            "lane_id",
        ]
    )

    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


# ============================================================
# Time Window
# ============================================================

def get_latest_complete_window(
    df: pd.DataFrame,
    window_seconds: int = WINDOW_SECONDS,
) -> tuple[pd.DataFrame, datetime, datetime]:
    """
    Mengambil window waktu terbaru yang lengkap.

    Window menggunakan interval:

        [window_start, window_end)

    Contoh window 5 detik:

        16:30:10 sampai sebelum 16:30:15

    sehingga timestamp:
        16:30:10
        16:30:11
        16:30:12
        16:30:13
        16:30:14

    masuk ke window tersebut.
    """

    if df.empty:
        raise ValueError("CSV traffic tidak memiliki data.")

    latest_timestamp = df["timestamp"].max()

    # Membuat batas window berdasarkan kelipatan waktu.
    window_end = latest_timestamp.floor(
        f"{window_seconds}s"
    )

    window_start = window_end - timedelta(
        seconds=window_seconds
    )

    window_df = df[
        (df["timestamp"] >= window_start)
        & (df["timestamp"] < window_end)
    ].copy()

    if window_df.empty:
        raise ValueError(
            "Tidak ditemukan data pada latest complete window."
        )

    return window_df, window_start.to_pydatetime(), window_end.to_pydatetime()


# ============================================================
# Lane → Approach
# ============================================================

def build_approach_state(
    approach_df: pd.DataFrame,
    approach: str,
) -> ApproachState:
    """
    Menggabungkan beberapa lane menjadi satu ApproachState.

    Aturan agregasi:

    volume / vehicle class:
        SUM

    queue:
        MAX per lane dalam window,
        kemudian SUM antar lane.

    density:
        MEAN dari seluruh observasi lane dalam window.

    speed:
        None karena CSV belum memiliki data speed.
    """

    # --------------------------------------------------------
    # Volume dan vehicle class
    # --------------------------------------------------------

    volume = int(
        approach_df["vehicle_count"].sum()
    )

    car_count = int(
        approach_df["car_count"].sum()
    )

    motorcycle_count = int(
        approach_df["motorcycle_count"].sum()
    )

    bus_count = int(
        approach_df["bus_count"].sum()
    )

    truck_count = int(
        approach_df["truck_count"].sum()
    )

    # --------------------------------------------------------
    # Queue
    #
    # Queue merupakan kondisi kendaraan yang sedang mengantre,
    # bukan jumlah kendaraan yang muncul selama window.
    #
    # Karena data berasal dari beberapa timestamp + lane,
    # kita mengambil peak queue setiap lane selama window,
    # kemudian menjumlahkan peak antar lane.
    # --------------------------------------------------------

    lane_queue = (
        approach_df
        .groupby("lane_id", as_index=False)
        .agg(
            queue_length_veh=(
                "queue_length_veh",
                "max",
            ),
            queue_length_m_est=(
                "queue_length_m_est",
                "max",
            ),
        )
    )

    queue_length_veh = int(
        lane_queue["queue_length_veh"].sum()
    )

    queue_length_m_est = float(
        lane_queue["queue_length_m_est"].sum()
    )

    # --------------------------------------------------------
    # Density
    #
    # density_index adalah proxy occupancy.
    # Tidak dijumlahkan antar timestamp karena akan membuat
    # angka membesar hanya karena window lebih panjang.
    #
    # Rata-rata seluruh observasi lane digunakan sebagai
    # representasi density pada window.
    # --------------------------------------------------------

    density_index = float(
        approach_df["density_index"].mean()
    )

    # --------------------------------------------------------
    # Build ApproachState
    # --------------------------------------------------------

    return ApproachState(
        approach=Approach(approach),
        volume=volume,
        carCount=car_count,
        motorcycleCount=motorcycle_count,
        busCount=bus_count,
        truckCount=truck_count,
        queueLengthVeh=max(0, queue_length_veh),
        queueLengthMEst=max(0.0, queue_length_m_est),
        densityIndex=max(0.0, density_index),
        avgSpeedKmh=None,
    )


# ============================================================
# Build TrafficState
# ============================================================

def build_latest_traffic_state() -> TrafficState:
    """
    Membaca CSV dan menghasilkan TrafficState terbaru.

    Alur:

        CSV
         ↓
        Time Window
         ↓
        Lane → Approach
         ↓
        TrafficState
    """

    df = load_traffic_csv()

    (
        window_df,
        window_start,
        window_end,
    ) = get_latest_complete_window(df)

    intersection_ids = (
        window_df["intersection_id"]
        .dropna()
        .unique()
        .tolist()
    )

    if len(intersection_ids) != 1:
        raise ValueError(
            "TrafficState saat ini mengharapkan satu intersection "
            f"per window. Ditemukan: {intersection_ids}"
        )

    intersection_id = str(
        intersection_ids[0]
    )

    approaches = []

    for approach_name in [
        "north",
        "south",
        "east",
        "west",
    ]:
        approach_df = window_df[
            window_df["approach"] == approach_name
        ].copy()

        if approach_df.empty:
            continue

        approaches.append(
            build_approach_state(
                approach_df,
                approach_name,
            )
        )

    if not approaches:
        raise ValueError(
            "Tidak ada approach yang valid pada traffic window."
        )

    return TrafficState(
        intersectionId=intersection_id,
        windowStart=window_start,
        windowEnd=window_end,
        approaches=approaches,
    )