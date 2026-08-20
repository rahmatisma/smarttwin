from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_WINDOW_SECONDS = 5

EXPECTED_APPROACHES = (
    "north",
    "south",
    "east",
    "west",
)

REQUIRED_COLUMNS = (
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
)

NUMERIC_COLUMNS = (
    "vehicle_count",
    "car_count",
    "motorcycle_count",
    "bus_count",
    "truck_count",
    "queue_length_veh",
    "queue_length_m_est",
    "density_index",
)


# ============================================================
# CONFIG
# ============================================================

@dataclass(frozen=True)
class TrafficStateBuilderConfig:
    """
    Konfigurasi Traffic State Builder.
    """

    window_seconds: int = DEFAULT_WINDOW_SECONDS

    def __post_init__(self) -> None:
        if self.window_seconds <= 0:
            raise ValueError(
                "window_seconds harus lebih besar dari 0."
            )


# ============================================================
# TRAFFIC STATE BUILDER
# ============================================================

class TrafficStateBuilder:
    """
    Mengubah data CV per timestamp + approach + lane
    menjadi TrafficState per time window.

    Alur:

        CSV
         ↓
        timestamp
         ↓
        time window
         ↓
        lane
         ↓
        approach
         ↓
        TrafficState
    """

    def __init__(
        self,
        config: TrafficStateBuilderConfig | None = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else TrafficStateBuilderConfig()
        )

    # ========================================================
    # LOAD CSV
    # ========================================================

    def load_csv(
        self,
        csv_path: str | Path,
    ) -> pd.DataFrame:
        """
        Membaca CSV hasil Computer Vision.
        """

        csv_path = Path(csv_path)

        if not csv_path.exists():
            raise FileNotFoundError(
                f"CSV traffic tidak ditemukan: {csv_path}"
            )

        df = pd.read_csv(csv_path)

        # ----------------------------------------------------
        # Validasi kolom
        # ----------------------------------------------------

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                "Kolom CSV tidak lengkap. "
                f"Kolom yang hilang: {missing_columns}"
            )

        # ----------------------------------------------------
        # Parse timestamp
        # ----------------------------------------------------

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        if df["timestamp"].isna().any():
            raise ValueError(
                "Terdapat timestamp yang tidak valid."
            )

        # ----------------------------------------------------
        # Normalisasi string
        # ----------------------------------------------------

        df["intersection_id"] = (
            df["intersection_id"]
            .astype(str)
            .str.strip()
        )

        df["approach"] = (
            df["approach"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        df["lane_id"] = (
            df["lane_id"]
            .astype(str)
            .str.strip()
        )

        # ----------------------------------------------------
        # Validasi approach
        # ----------------------------------------------------

        invalid_approaches = sorted(
            set(df["approach"])
            - set(EXPECTED_APPROACHES)
        )

        if invalid_approaches:
            raise ValueError(
                "Approach tidak valid: "
                f"{invalid_approaches}"
            )

        # ----------------------------------------------------
        # Numeric conversion
        # ----------------------------------------------------

        for column in NUMERIC_COLUMNS:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        if df[list(NUMERIC_COLUMNS)].isna().any().any():
            raise ValueError(
                "Terdapat nilai numerik yang tidak valid "
                "atau kosong pada CSV."
            )

        # ----------------------------------------------------
        # Validasi nilai negatif
        # ----------------------------------------------------

        negative_mask = (
            df[list(NUMERIC_COLUMNS)] < 0
        ).any(axis=1)

        if negative_mask.any():
            raise ValueError(
                "Terdapat nilai negatif pada metric traffic."
            )

        # ----------------------------------------------------
        # Sort berdasarkan waktu
        # ----------------------------------------------------

        df = df.sort_values(
            by=[
                "timestamp",
                "intersection_id",
                "approach",
                "lane_id",
            ]
        ).reset_index(drop=True)

        return df

    # ========================================================
    # TIME WINDOW
    # ========================================================

    def _assign_windows(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Menentukan time window untuk setiap row.

        Contoh window 5 detik:

        16:30:10 - 16:30:15
        16:30:15 - 16:30:20
        16:30:20 - 16:30:25
        """

        result = df.copy()

        window = f"{self.config.window_seconds}s"

        result["window_start"] = (
            result["timestamp"]
            .dt.floor(window)
        )

        result["window_end"] = (
            result["window_start"]
            + pd.Timedelta(
                seconds=self.config.window_seconds
            )
        )

        return result

    # ========================================================
    # AGGREGATE APPROACH
    # ========================================================

    def _aggregate_approach(
        self,
        group: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Menggabungkan data beberapa lane menjadi
        satu ApproachState.

        Contoh:

            south
            ├── lane_1
            ├── lane_2
            └── lane_3

        menjadi:

            south
            └── ApproachState

        ------------------------------------------------------
        ATURAN AGREGASI
        ------------------------------------------------------

        volume
            = jumlah vehicle_count antar lane

        carCount
            = jumlah car_count antar lane

        motorcycleCount
            = jumlah motorcycle_count antar lane

        busCount
            = jumlah bus_count antar lane

        truckCount
            = jumlah truck_count antar lane

        queueLengthVeh
            = jumlah queue_length_veh antar lane

        queueLengthMEst
            = jumlah queue_length_m_est antar lane

        densityIndex
            = rata-rata density_index antar lane

        avgSpeedKmh
            = None karena CSV belum memiliki speed.
        """

        approach = str(
            group["approach"].iloc[0]
        )

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        volume = int(
            group["vehicle_count"].sum()
        )

        # ----------------------------------------------------
        # Vehicle classification
        # ----------------------------------------------------

        car_count = int(
            group["car_count"].sum()
        )

        motorcycle_count = int(
            group["motorcycle_count"].sum()
        )

        bus_count = int(
            group["bus_count"].sum()
        )

        truck_count = int(
            group["truck_count"].sum()
        )

        # ----------------------------------------------------
        # Queue
        #
        # IMPORTANT:
        #
        # Untuk sementara kita menganggap nilai queue
        # pada CSV adalah queue PER LANE.
        #
        # Jadi ketika lane digabung menjadi approach,
        # queue dijumlahkan.
        #
        # Jika nanti tim CV mengonfirmasi bahwa queue
        # sebenarnya sudah merupakan total approach,
        # BAGIAN INI HARUS DIUBAH agar tidak double counting.
        # ----------------------------------------------------

        queue_length_veh = int(
            group["queue_length_veh"].sum()
        )

        queue_length_m_est = float(
            group["queue_length_m_est"].sum()
        )

        # ----------------------------------------------------
        # Density
        #
        # densityIndex adalah proxy lane occupancy.
        #
        # Bukan vehicles/km.
        #
        # Karena nilainya tersedia per lane, kita gunakan
        # rata-rata antar lane agar skala tidak otomatis
        # membesar hanya karena jumlah lane bertambah.
        # ----------------------------------------------------

        density_index = float(
            group["density_index"].mean()
        )

        # ----------------------------------------------------
        # Speed
        #
        # CSV tidak memiliki data speed.
        #
        # Jangan isi 0.
        # Jangan membuat nilai sendiri.
        #
        # None = data belum tersedia.
        # ----------------------------------------------------

        avg_speed_kmh = None

        return {
            "approach": approach,
            "volume": volume,
            "carCount": car_count,
            "motorcycleCount": motorcycle_count,
            "busCount": bus_count,
            "truckCount": truck_count,
            "queueLengthVeh": queue_length_veh,
            "queueLengthMEst": queue_length_m_est,
            "densityIndex": density_index,
            "avgSpeedKmh": avg_speed_kmh,
        }

    # ========================================================
    # BUILD TRAFFIC STATE
    # ========================================================

    def build_from_dataframe(
        self,
        df: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        """
        Menghasilkan list TrafficState dari DataFrame.
        """

        if df.empty:
            return []

        df = self._assign_windows(df)

        states: list[dict[str, Any]] = []

        # ----------------------------------------------------
        # Group:
        #
        # intersection
        # +
        # window
        # ----------------------------------------------------

        grouped = df.groupby(
            [
                "intersection_id",
                "window_start",
                "window_end",
            ],
            sort=True,
        )

        for (
            intersection_id,
            window_start,
            window_end,
        ), window_group in grouped:

            approaches: list[dict[str, Any]] = []

            # ------------------------------------------------
            # Pastikan output selalu memiliki 4 approach.
            #
            # Kalau sebuah approach tidak punya kendaraan,
            # nilainya tetap 0.
            # ------------------------------------------------

            for approach_name in EXPECTED_APPROACHES:

                approach_group = window_group[
                    window_group["approach"]
                    == approach_name
                ]

                if approach_group.empty:

                    approach_state = {
                        "approach": approach_name,
                        "volume": 0,
                        "carCount": 0,
                        "motorcycleCount": 0,
                        "busCount": 0,
                        "truckCount": 0,
                        "queueLengthVeh": 0,
                        "queueLengthMEst": 0.0,
                        "densityIndex": 0.0,
                        "avgSpeedKmh": None,
                    }

                else:

                    approach_state = (
                        self._aggregate_approach(
                            approach_group
                        )
                    )

                approaches.append(
                    approach_state
                )

            # ------------------------------------------------
            # TrafficState
            # ------------------------------------------------

            state = {
                "intersectionId": str(
                    intersection_id
                ),
                "windowStart": (
                    pd.Timestamp(window_start)
                    .isoformat()
                ),
                "windowEnd": (
                    pd.Timestamp(window_end)
                    .isoformat()
                ),
                "approaches": approaches,
            }

            states.append(state)

        return states

    # ========================================================
    # BUILD FROM CSV
    # ========================================================

    def build_from_csv(
        self,
        csv_path: str | Path,
    ) -> list[dict[str, Any]]:
        """
        Shortcut:

        CSV
        ↓
        DataFrame
        ↓
        TrafficState[]
        """

        df = self.load_csv(csv_path)

        return self.build_from_dataframe(df)


# ============================================================
# CLI / MANUAL TEST
# ============================================================

def main() -> None:

    project_root = (
        Path(__file__)
        .resolve()
        .parents[3]
    )

    csv_path = (
        project_root
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            window_seconds=5
        )
    )

    states = builder.build_from_csv(
        csv_path
    )

    print("=" * 60)
    print("TRAFFIC STATE BUILDER")
    print("=" * 60)

    print(f"CSV    : {csv_path}")
    print(f"States : {len(states)}")
    print()

    if states:
        import json

        print(
            json.dumps(
                states[0],
                indent=2,
            )
        )


if __name__ == "__main__":
    main()