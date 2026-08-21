from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas.traffic import ApproachState, TrafficState


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
    Mengubah data CV dari CSV menjadi TrafficState.

    Input:
        CSV hasil Computer Vision.

    Format data CV:
        timestamp
        intersection_id
        approach
        lane_id
        vehicle_count
        car_count
        motorcycle_count
        bus_count
        truck_count
        queue_length_veh
        queue_length_m_est
        density_index

    Alur:

        CSV
         ↓
        Load + Validate
         ↓
        Time Window
         ↓
        Lane Data
         ↓
        Approach Aggregation
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
        Membaca CSV asli hasil Computer Vision.

        Tidak membuat dummy data.

        CSV harus memiliki seluruh REQUIRED_COLUMNS.
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

        if df.empty:
            raise ValueError(
                "CSV traffic kosong."
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
        # Validasi string penting
        # ----------------------------------------------------

        if (df["intersection_id"] == "").any():
            raise ValueError(
                "Terdapat intersection_id kosong."
            )

        if (df["lane_id"] == "").any():
            raise ValueError(
                "Terdapat lane_id kosong."
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
                f"{invalid_approaches}. "
                f"Approach yang diperbolehkan: "
                f"{EXPECTED_APPROACHES}"
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
            invalid_columns = [
                column
                for column in NUMERIC_COLUMNS
                if df[column].isna().any()
            ]

            raise ValueError(
                "Terdapat nilai numerik yang tidak valid "
                f"atau kosong pada kolom: {invalid_columns}"
            )

        # ----------------------------------------------------
        # Validasi integer metrics
        #
        # Count kendaraan dan queue kendaraan harus berupa
        # bilangan bulat.
        # ----------------------------------------------------

        integer_columns = (
            "vehicle_count",
            "car_count",
            "motorcycle_count",
            "bus_count",
            "truck_count",
            "queue_length_veh",
        )

        for column in integer_columns:
            if (
                df[column] % 1 != 0
            ).any():
                raise ValueError(
                    f"Kolom {column} harus berupa bilangan bulat."
                )

            df[column] = df[column].astype(int)

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
        # Validasi klasifikasi kendaraan
        #
        # vehicle_count harus konsisten dengan:
        #
        # car + motorcycle + bus + truck
        #
        # Karena semua berasal dari counting line.
        # ----------------------------------------------------

        classification_total = (
            df["car_count"]
            + df["motorcycle_count"]
            + df["bus_count"]
            + df["truck_count"]
        )

        inconsistent_mask = (
            df["vehicle_count"]
            != classification_total
        )

        if inconsistent_mask.any():
            first_invalid = df.loc[
                inconsistent_mask
            ].iloc[0]

            raise ValueError(
                "vehicle_count tidak konsisten dengan "
                "jumlah klasifikasi kendaraan pada "
                "setidaknya satu row. "
                f"Timestamp: {first_invalid['timestamp']}, "
                f"approach: {first_invalid['approach']}, "
                f"lane: {first_invalid['lane_id']}"
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

        Dengan window 5 detik:

            16:30:10 -> 16:30:15
            16:30:15 -> 16:30:20
            16:30:20 -> 16:30:25

        Karena data CV berasal per detik, beberapa timestamp
        akan masuk ke window yang sama.
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
    ) -> ApproachState:
        """
        Menggabungkan data beberapa lane menjadi
        satu ApproachState.

        Struktur:

            north
            ├── lane_1
            ├── lane_2
            └── lane_3

                    ↓

            ApproachState(north)

        ======================================================
        ATURAN AGREGASI
        ======================================================

        volume
            = total vehicle_count dalam window
              untuk seluruh lane.

        carCount
            = total car_count.

        motorcycleCount
            = total motorcycle_count.

        busCount
            = total bus_count.

        truckCount
            = total truck_count.

        queueLengthVeh
            = total queue_length_veh antar lane.

            IMPORTANT:
            Saat ini queue_length_veh dianggap
            merupakan queue PER LANE.

        queueLengthMEst
            = total queue_length_m_est antar lane.

            IMPORTANT:
            Saat ini queue_length_m_est dianggap
            merupakan queue PER LANE.

        densityIndex
            = rata-rata density_index antar lane.

            densityIndex adalah proxy lane occupancy,
            bukan kendaraan/km.

        avgSpeedKmh
            = None.

            CSV tidak menyediakan speed.
        """

        approach = str(
            group["approach"].iloc[0]
        )

        # ----------------------------------------------------
        # Volume
        #
        # vehicle_count = kendaraan yang MEMOTONG
        # counting line.
        #
        # BUKAN jumlah seluruh kendaraan yang terlihat
        # pada frame.
        #
        # Data CV dicatat per detik sehingga seluruh
        # counting event dalam window dijumlahkan.
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
        # Queue diasumsikan PER LANE.
        #
        # Contoh:
        #
        # lane_1 = 3 kendaraan
        # lane_2 = 2 kendaraan
        # lane_3 = 4 kendaraan
        #
        # approach queue = 3 + 2 + 4 = 9 kendaraan
        #
        # Jika nanti tim CV mengubah definisi queue menjadi
        # TOTAL APPROACH, bagian ini HARUS diubah agar
        # tidak terjadi double counting.
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
        # density_index tersedia per lane.
        #
        # Kita gunakan mean antar lane agar nilai approach
        # tidak otomatis membesar hanya karena approach
        # mempunyai lebih banyak lane.
        #
        # Ini adalah proxy occupancy/density.
        # BUKAN vehicles/km.
        # ----------------------------------------------------

        density_index = float(
            group["density_index"].mean()
        )

        # ----------------------------------------------------
        # Speed
        #
        # Tidak ada data speed pada CSV.
        #
        # None berarti data belum tersedia.
        #
        # JANGAN menggunakan 0.0.
        # ----------------------------------------------------

        avg_speed_kmh = None

        return ApproachState(
            approach=approach,
            volume=volume,
            carCount=car_count,
            motorcycleCount=motorcycle_count,
            busCount=bus_count,
            truckCount=truck_count,
            queueLengthVeh=queue_length_veh,
            queueLengthMEst=queue_length_m_est,
            densityIndex=density_index,
            avgSpeedKmh=avg_speed_kmh,
        )

    # ========================================================
    # BUILD TRAFFIC STATE
    # ========================================================

    def build_from_dataframe(
        self,
        df: pd.DataFrame,
    ) -> list[TrafficState]:
        """
        Menghasilkan list TrafficState dari DataFrame
        yang sudah divalidasi.
        """

        if df.empty:
            return []

        df = self._assign_windows(df)

        states: list[TrafficState] = []

        # ----------------------------------------------------
        # Group berdasarkan:
        #
        # intersection
        # +
        # time window
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

            approaches: list[ApproachState] = []

            # ------------------------------------------------
            # Pastikan output selalu mempunyai 4 approach:
            #
            # north
            # south
            # east
            # west
            #
            # Jika tidak ada data kendaraan pada approach,
            # metric kendaraan dan queue menjadi 0.
            # ------------------------------------------------

            for approach_name in EXPECTED_APPROACHES:

                approach_group = window_group[
                    window_group["approach"]
                    == approach_name
                ]

                if approach_group.empty:

                    approach_state = ApproachState(
                        approach=approach_name,
                        volume=0,
                        carCount=0,
                        motorcycleCount=0,
                        busCount=0,
                        truckCount=0,
                        queueLengthVeh=0,
                        queueLengthMEst=0.0,
                        densityIndex=0.0,
                        avgSpeedKmh=None,
                    )

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

            state = TrafficState(
                intersectionId=str(
                    intersection_id
                ),
                windowStart=pd.Timestamp(
                    window_start
                ).to_pydatetime(),
                windowEnd=pd.Timestamp(
                    window_end
                ).to_pydatetime(),
                approaches=approaches,
            )

            states.append(state)

        return states

    # ========================================================
    # BUILD FROM CSV
    # ========================================================

    def build_from_csv(
        self,
        csv_path: str | Path,
    ) -> list[TrafficState]:
        """
        Pipeline lengkap:

            CSV
             ↓
            load_csv()
             ↓
            build_from_dataframe()
             ↓
            TrafficState[]
        """

        df = self.load_csv(csv_path)

        return self.build_from_dataframe(df)


# ============================================================
# DEFAULT CSV PATH
# ============================================================

def get_default_csv_path() -> Path:
    """
    Mengambil lokasi CSV asli berdasarkan struktur project:

    smarttwin/
    ├── backend/
    │   └── app/
    │       └── pipeline/
    │           └── traffic_state_builder.py
    │
    └── cv/
        └── output/
            └── smarttwin_traffic_data.csv
    """

    project_root = (
        Path(__file__)
        .resolve()
        .parents[3]
    )

    return (
        project_root
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )


# ============================================================
# CLI / MANUAL TEST
# ============================================================

def main() -> None:
    """
    Menjalankan Traffic State Builder menggunakan
    CSV ASLI project.

    Tidak menggunakan dummy data.
    """

    csv_path = get_default_csv_path()

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
                states[0].model_dump(
                    mode="json"
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()