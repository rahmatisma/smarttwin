# backend/app/pipeline/traffic_state_builder.py

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

REQUIRED_COLUMNS = {
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
}


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class TrafficStateBuilderConfig:
    """
    Configuration untuk Traffic State Builder.
    """

    window_seconds: int = DEFAULT_WINDOW_SECONDS


# ============================================================
# TRAFFIC STATE BUILDER
# ============================================================

class TrafficStateBuilder:
    """
    Mengubah CSV hasil Computer Vision menjadi TrafficState.

    Input:
        timestamp × intersection × approach × lane

    Output:
        TrafficState per time window.
    """

    def __init__(
        self,
        config: TrafficStateBuilderConfig | None = None,
    ) -> None:
        self.config = config or TrafficStateBuilderConfig()

        if self.config.window_seconds <= 0:
            raise ValueError(
                "window_seconds harus lebih besar dari 0."
            )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def build_from_csv(
        self,
        csv_path: str | Path,
    ) -> list[dict[str, Any]]:
        """
        Membaca CSV dan menghasilkan list TrafficState.
        """

        csv_path = Path(csv_path)

        if not csv_path.exists():
            raise FileNotFoundError(
                f"CSV tidak ditemukan: {csv_path}"
            )

        df = pd.read_csv(csv_path)

        self._validate_columns(df)

        df = self._prepare_dataframe(df)

        return self._build_states(df)

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_columns(
        self,
        df: pd.DataFrame,
    ) -> None:
        """
        Memastikan CSV memiliki seluruh kolom yang dibutuhkan.
        """

        actual_columns = set(df.columns)

        missing_columns = REQUIRED_COLUMNS - actual_columns

        if missing_columns:
            raise ValueError(
                "Kolom CSV tidak lengkap. "
                f"Kolom yang hilang: {sorted(missing_columns)}"
            )

    # ========================================================
    # PREPARATION
    # ========================================================

    def _prepare_dataframe(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Membersihkan dan mempersiapkan dataframe.
        """

        df = df.copy()

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        if df["timestamp"].isna().any():
            invalid_count = int(df["timestamp"].isna().sum())

            raise ValueError(
                f"Terdapat {invalid_count} timestamp yang tidak valid."
            )

        # ----------------------------------------------------
        # Approach
        # ----------------------------------------------------

        df["approach"] = (
            df["approach"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        invalid_approaches = sorted(
            set(df["approach"]) - set(EXPECTED_APPROACHES)
        )

        if invalid_approaches:
            raise ValueError(
                "Ditemukan approach tidak valid: "
                f"{invalid_approaches}"
            )

        # ----------------------------------------------------
        # Numeric columns
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Missing numeric values
        # ----------------------------------------------------

        if df[numeric_columns].isna().any().any():
            missing_summary = (
                df[numeric_columns]
                .isna()
                .sum()
            )

            missing_summary = missing_summary[
                missing_summary > 0
            ]

            raise ValueError(
                "Terdapat nilai numerik yang tidak valid/NaN: "
                f"{missing_summary.to_dict()}"
            )

        # ----------------------------------------------------
        # Negative values
        # ----------------------------------------------------

        for column in numeric_columns:
            if (df[column] < 0).any():
                raise ValueError(
                    f"Kolom {column} memiliki nilai negatif."
                )

        # ----------------------------------------------------
        # Sort
        # ----------------------------------------------------

        df = df.sort_values(
            [
                "intersection_id",
                "timestamp",
                "approach",
                "lane_id",
            ]
        ).reset_index(drop=True)

        return df

    # ========================================================
    # WINDOW
    # ========================================================

    def _assign_windows(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Membuat time window dengan ukuran konfigurasi.

        Contoh window 5 detik:

        16:30:12 ── 16:30:17
        16:30:17 ── 16:30:22
        """

        df = df.copy()

        window_seconds = self.config.window_seconds

        # Anchor berdasarkan timestamp pertama.
        origin = df["timestamp"].min()

        elapsed_seconds = (
            df["timestamp"] - origin
        ).dt.total_seconds()

        window_index = (
            elapsed_seconds // window_seconds
        ).astype(int)

        df["_window_index"] = window_index

        df["_window_start"] = (
            origin
            + pd.to_timedelta(
                window_index * window_seconds,
                unit="s",
            )
        )

        df["_window_end"] = (
            df["_window_start"]
            + pd.to_timedelta(
                window_seconds,
                unit="s",
            )
        )

        return df

    # ========================================================
    # BUILD STATES
    # ========================================================

    def _build_states(
        self,
        df: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        """
        Menghasilkan TrafficState per window.
        """

        df = self._assign_windows(df)

        states: list[dict[str, Any]] = []

        grouped = df.groupby(
            [
                "intersection_id",
                "_window_index",
                "_window_start",
                "_window_end",
            ],
            sort=True,
        )

        for (
            intersection_id,
            _window_index,
            window_start,
            window_end,
        ), window_df in grouped:

            approaches = []

            for approach in EXPECTED_APPROACHES:
                approach_df = window_df[
                    window_df["approach"] == approach
                ]

                approach_state = self._build_approach_state(
                    approach=approach,
                    approach_df=approach_df,
                )

                approaches.append(
                    approach_state
                )

            state = {
                "intersectionId": str(
                    intersection_id
                ),
                "windowStart": self._datetime_to_iso(
                    window_start
                ),
                "windowEnd": self._datetime_to_iso(
                    window_end
                ),
                "approaches": approaches,
            }

            states.append(state)

        return states

    # ========================================================
    # APPROACH AGGREGATION
    # ========================================================

    def _build_approach_state(
        self,
        approach: str,
        approach_df: pd.DataFrame,
    ) -> dict[str, Any]:
        """
        Menggabungkan data beberapa lane menjadi satu approach.
        """

        # ----------------------------------------------------
        # Tidak ada data untuk approach
        # ----------------------------------------------------

        if approach_df.empty:
            return {
                "approach": approach,
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

        # ----------------------------------------------------
        # Volume
        #
        # vehicle_count = kendaraan yang crossing
        #
        # Dijumlahkan:
        #
        # timestamp × lane
        #          ↓
        # approach window
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Queue
        #
        # Queue bukan volume.
        #
        # Tidak dijumlahkan antar timestamp.
        # Menggunakan nilai maksimum dalam window.
        # ----------------------------------------------------

        queue_length_veh = int(
            approach_df[
                "queue_length_veh"
            ].max()
        )

        queue_length_m_est = float(
            approach_df[
                "queue_length_m_est"
            ].max()
        )

        # ----------------------------------------------------
        # Density
        #
        # densityIndex adalah proxy.
        #
        # Menggunakan rata-rata seluruh observasi
        # lane dalam window.
        # ----------------------------------------------------

        density_index = float(
            approach_df[
                "density_index"
            ].mean()
        )

        # ----------------------------------------------------
        # Speed
        #
        # CSV saat ini tidak memiliki speed.
        #
        # Jadi HARUS None.
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
    # DATETIME
    # ========================================================

    @staticmethod
    def _datetime_to_iso(
        value: datetime | pd.Timestamp,
    ) -> str:
        """
        Mengubah datetime menjadi ISO-8601.
        """

        if isinstance(value, pd.Timestamp):
            value = value.to_pydatetime()

        return value.isoformat()