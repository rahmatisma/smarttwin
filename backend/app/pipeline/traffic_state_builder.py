from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from supabase import Client

from app.schemas.traffic import ApproachState, TrafficState
from app.services.supabase_client import get_supabase


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
    "intersectionId",
    "approach",
    "laneId",
    "vehicleCount",
    "carCount",
    "motorcycleCount",
    "busCount",
    "truckCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
)

NUMERIC_COLUMNS = (
    "vehicleCount",
    "carCount",
    "motorcycleCount",
    "busCount",
    "truckCount",
    "queueLengthVeh",
    "queueLengthMEst",
    "densityIndex",
)


# ============================================================
# CONFIG
# ============================================================

@dataclass(frozen=True)
class TrafficStateBuilderConfig:
    """
    Konfigurasi Traffic State Builder.
    """

    windowSeconds: int = DEFAULT_WINDOW_SECONDS

    def __post_init__(self) -> None:
        if self.windowSeconds <= 0:
            raise ValueError(
                "windowSeconds harus lebih besar dari 0."
            )


# ============================================================
# TRAFFIC STATE BUILDER
# ============================================================

class TrafficStateBuilder:
    """
    Mengubah data CV dari CSV menjadi TrafficState.

    Input:
        CSV hasil Computer Vision.

    Output:
        TrafficState[]

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

    def loadCvOutput(
        self,
        crossPath: str | Path,
        densityPath: str | Path,
    ) -> pd.DataFrame:
        """
        Membaca dan menggabungkan output asli dari Computer Vision.
        """
        crossPath = Path(crossPath)
        densityPath = Path(densityPath)

        if not crossPath.exists() or not densityPath.exists():
            raise FileNotFoundError("Satu atau lebih CSV CV output tidak ditemukan.")

        df_cross = pd.read_csv(crossPath)
        df_density = pd.read_csv(densityPath)

        # 1. Standardize Timestamps
        df_cross["timestamp"] = pd.to_datetime(df_cross["timestamp"], errors="coerce")
        df_density["timestamp"] = pd.to_datetime(df_density["timestamp"], errors="coerce")

        if df_cross.empty and df_density.empty:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        # 2. Map Kamera to Approach (Hard override berdasarkan spec)
        camera_map = {
            "CCTV_1": "south",
            "CCTV_2": "west",
            "CCTV_3": "east",
            "CCTV_4": "north",
        }

        df_cross["approach"] = df_cross["kamera"].map(camera_map)
        df_density["approach"] = df_density["kamera"].map(camera_map)

        # Drop rows without known camera
        df_cross = df_cross.dropna(subset=["approach"])
        df_density = df_density.dropna(subset=["approach"])

        # 3. Aggregate crossing per timestamp & approach
        cross_agg = df_cross.groupby(["timestamp", "approach"], as_index=False).agg({
            "jumlah_crossing": "sum",
            "motor_crossing": "sum",
            "mobil_crossing": "sum",
            "truk_crossing": "sum",
            "bus_crossing": "sum",
        })

        # Aggregate density per timestamp & approach
        density_agg = df_density.groupby(["timestamp", "approach"], as_index=False).agg({
            "total_di_zona": "mean",
            "motor_di_zona": "mean",
            "mobil_di_zona": "mean",
            "truk_di_zona": "mean",
            "bus_di_zona": "mean",
            "frame_number": "first",
        })

        # 4. Merge
        merged = pd.merge(cross_agg, density_agg, on=["timestamp", "approach"], how="outer").fillna(0)

        # 5. Normalize into standard required columns
        merged["intersectionId"] = "simpang4-pingit"
        merged["laneId"] = "all_lanes"

        merged = merged.rename(columns={
            "total_di_zona": "vehicleCount",
            "mobil_di_zona": "carCount",
            "motor_di_zona": "motorcycleCount",
            "bus_di_zona": "busCount",
            "truk_di_zona": "truckCount",
        })
        
        # Use snapshot count for density index as well
        merged["densityIndex"] = merged["vehicleCount"]

        merged["queueLengthVeh"] = 0
        merged["queueLengthMEst"] = 0.0

        for col in NUMERIC_COLUMNS:
            if col not in merged.columns:
                merged[col] = 0

        # Integer validation
        integerColumns = (
            "vehicleCount",
            "carCount",
            "motorcycleCount",
            "busCount",
            "truckCount",
            "queueLengthVeh",
        )
        for col in integerColumns:
            merged[col] = merged[col].round().astype(int)

        merged = merged.sort_values(
            by=[
                "timestamp",
                "intersectionId",
                "approach",
                "laneId",
            ]
        ).reset_index(drop=True)

        return merged

    # ========================================================
    # TIME WINDOW
    # ========================================================

    def assignWindows(
        self,
        dataFrame: pd.DataFrame,
    ) -> pd.DataFrame:

        result = dataFrame.copy()

        window = f"{self.config.windowSeconds}s"

        result["windowStart"] = (
            result["timestamp"]
            .dt.floor(window)
        )

        result["windowEnd"] = (
            result["windowStart"]
            + pd.Timedelta(
                seconds=self.config.windowSeconds
            )
        )

        return result

    # ========================================================
    # APPROACH AGGREGATION
    # ========================================================

    def aggregateApproach(
        self,
        group: pd.DataFrame,
    ) -> ApproachState:

        approach = str(
            group["approach"].iloc[0]
        )

        volume = int(
            group["vehicleCount"].iloc[-1]
        )

        carCount = int(
            group["carCount"].iloc[-1]
        )

        motorcycleCount = int(
            group["motorcycleCount"].iloc[-1]
        )

        busCount = int(
            group["busCount"].iloc[-1]
        )

        truckCount = int(
            group["truckCount"].iloc[-1]
        )

        queueLengthVeh = int(
            group["queueLengthVeh"].iloc[-1]
        )

        queueLengthMEst = float(
            group["queueLengthMEst"].sum()
        )

        densityIndex = float(
            group["densityIndex"].mean()
        )

        # CSV belum mempunyai speed.
        avgSpeedKmh = None

        return ApproachState(
            approach=approach,
            volume=volume,
            carCount=carCount,
            motorcycleCount=motorcycleCount,
            busCount=busCount,
            truckCount=truckCount,
            queueLengthVeh=queueLengthVeh,
            queueLengthMEst=queueLengthMEst,
            densityIndex=densityIndex,
            avgSpeedKmh=avgSpeedKmh,
        )

    # ========================================================
    # BUILD STATES
    # ========================================================

    def buildFromDataFrame(
        self,
        dataFrame: pd.DataFrame,
    ) -> list[TrafficState]:

        if dataFrame.empty:
            return []

        dataFrame = self.assignWindows(
            dataFrame
        )

        states: list[TrafficState] = []

        grouped = dataFrame.groupby(
            [
                "intersectionId",
                "windowStart",
                "windowEnd",
            ],
            sort=True,
        )

        for (
            intersectionId,
            windowStart,
            windowEnd,
        ), windowGroup in grouped:

            approaches: list[ApproachState] = []

            for approachName in EXPECTED_APPROACHES:

                approachGroup = windowGroup[
                    windowGroup["approach"]
                    == approachName
                ]

                if approachGroup.empty:

                    approachState = ApproachState(
                        approach=approachName,
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

                    approachState = (
                        self.aggregateApproach(
                            approachGroup
                        )
                    )

                approaches.append(
                    approachState
                )

            state = TrafficState(
                intersectionId=str(
                    intersectionId
                ),
                windowStart=pd.Timestamp(
                    windowStart
                ).to_pydatetime(),
                windowEnd=pd.Timestamp(
                    windowEnd
                ).to_pydatetime(),
                approaches=approaches,
            )

            states.append(state)

        return states

    # ========================================================
    # BUILD FROM SUPABASE
    # ========================================================

    def buildFromSupabase(
        self,
        *,
        intersectionId: str | None = None,
        limit: int | None = None,
        supabase: Client | None = None,
    ) -> list[TrafficState]:
        """Membaca trafficStates dan trafficApproachStates dari Supabase."""

        if limit is not None and limit <= 0:
            raise ValueError("limit harus lebih besar dari 0.")

        client = supabase or get_supabase()

        traffic_query = (
            client
            .table("trafficStates")
            .select("id, intersectionId, windowStart, windowEnd")
            .order("windowStart", desc=True)
        )

        if limit is not None:
            traffic_query = traffic_query.limit(limit)

        traffic_result = traffic_query.execute()
        traffic_rows = (
            traffic_result.data
            if traffic_result is not None
            else []
        ) or []

        if not traffic_rows:
            return []

        intersection_row_ids = {
            int(row["intersectionId"])
            for row in traffic_rows
        }

        intersections_result = (
            client
            .table("intersections")
            .select("id, intersectionId")
            .in_("id", list(intersection_row_ids))
            .execute()
        )
        intersection_names = {
            int(row["id"]): str(row["intersectionId"])
            for row in (
                intersections_result.data
                if intersections_result is not None
                else []
            ) or []
        }

        traffic_state_ids = [
            int(row["id"])
            for row in traffic_rows
        ]

        approach_result = (
            client
            .table("trafficApproachStates")
            .select(
                "trafficStateId, approachId, approach, volume, "
                "carCount, motorcycleCount, busCount, truckCount, "
                "queueLengthVeh, queueLengthMEst, densityIndex, "
                "avgSpeedKmh"
            )
            .in_("trafficStateId", traffic_state_ids)
            .order("approachId")
            .execute()
        )
        approaches_by_state: dict[int, dict[str, ApproachState]] = {}

        for row in (
            approach_result.data
            if approach_result is not None
            else []
        ) or []:
            traffic_state_id = int(row["trafficStateId"])
            approach_name = str(row["approach"]).strip().lower()
            approaches_by_state.setdefault(
                traffic_state_id,
                {},
            )[approach_name] = ApproachState(
                approach=approach_name,
                volume=int(row["volume"]),
                carCount=int(row["carCount"]),
                motorcycleCount=int(row["motorcycleCount"]),
                busCount=int(row["busCount"]),
                truckCount=int(row["truckCount"]),
                queueLengthVeh=int(row["queueLengthVeh"]),
                queueLengthMEst=float(row["queueLengthMEst"]),
                densityIndex=float(row["densityIndex"]),
                avgSpeedKmh=(
                    None
                    if row["avgSpeedKmh"] is None
                    else float(row["avgSpeedKmh"])
                ),
            )

        states: list[TrafficState] = []

        for row in traffic_rows:
            traffic_state_id = int(row["id"])
            intersection_row_id = int(row["intersectionId"])
            intersection_name = intersection_names.get(
                intersection_row_id
            )

            if intersection_name is None:
                raise ValueError(
                    "Intersection tidak ditemukan untuk "
                    f"trafficStateId {traffic_state_id}."
                )

            state_approaches = approaches_by_state.get(
                traffic_state_id,
                {},
            )

            approaches = [
                state_approaches.get(
                    approach_name,
                    ApproachState(
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
                    ),
                )
                for approach_name in EXPECTED_APPROACHES
            ]

            states.append(
                TrafficState(
                    intersectionId=intersection_name,
                    windowStart=pd.to_datetime(
                        row["windowStart"]
                    ).to_pydatetime(),
                    windowEnd=pd.to_datetime(
                        row["windowEnd"]
                    ).to_pydatetime(),
                    approaches=approaches,
                )
            )

        return states

    # ========================================================
    # BUILD FROM CSV
    # ========================================================

    def buildFromCvOutput(
        self,
        crossPath: str | Path,
        densityPath: str | Path,
        video_time: float | None = None,
    ) -> list[TrafficState]:

        dataFrame = self.loadCvOutput(
            crossPath,
            densityPath
        )

        if video_time is not None and not dataFrame.empty and "frame_number" in dataFrame.columns:
            target_frame = video_time * 30.0
            dataFrame["frame_diff"] = (dataFrame["frame_number"] - target_frame).abs()
            min_diff_timestamp = dataFrame.groupby("timestamp")["frame_diff"].mean().idxmin()
            
            matched_df = dataFrame[dataFrame["timestamp"] == min_diff_timestamp]
            matched_frame = matched_df["frame_number"].iloc[0]
            matched_video_time = matched_frame / 30.0
            
            self.last_matched_video_time = matched_video_time
            
            print(f"\nREQUEST {video_time:.2f}")
            print(f"MATCHED {matched_video_time:.2f}")
            print(f"TIMESTAMP {min_diff_timestamp}\n")
            
            dataFrame = matched_df

        return self.buildFromDataFrame(
            dataFrame
        )


# ============================================================
# DEFAULT CSV PATH
# ============================================================

# ============================================================
# DEFAULT CV PATHS
# ============================================================

def getDefaultCrossPath() -> Path:
    projectRoot = Path(__file__).resolve().parents[3]
    return projectRoot / "cv" / "output" / "crossing_simpang.csv"

def getDefaultDensityPath() -> Path:
    projectRoot = Path(__file__).resolve().parents[3]
    return projectRoot / "cv" / "output" / "percobaan_logic_simpang.csv"

# ============================================================
# CLI
# ============================================================

def main() -> None:

    crossPath = getDefaultCrossPath()
    densityPath = getDefaultDensityPath()

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            windowSeconds=5
        )
    )

    states = builder.buildFromCvOutput(
        crossPath,
        densityPath
    )

    print("=" * 60)
    print("TRAFFIC STATE BUILDER")
    print("=" * 60)

    print(f"Cross CSV   : {crossPath}")
    print(f"Density CSV : {densityPath}")
    print(f"States      : {len(states)}")
    print()

    if states:
        import json
        print(
            json.dumps(
                states[0].model_dump(
                    mode="json"
                ),
                indent=2,
                default=str
            )
        )


if __name__ == "__main__":
    main()