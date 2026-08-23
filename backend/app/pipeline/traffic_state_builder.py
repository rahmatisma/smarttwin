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

    def loadCsv(
        self,
        csvPath: str | Path,
    ) -> pd.DataFrame:
        """
        Membaca CSV asli hasil Computer Vision.
        """

        csvPath = Path(csvPath)

        if not csvPath.exists():
            raise FileNotFoundError(
                f"CSV traffic tidak ditemukan: {csvPath}"
            )

        dataFrame = pd.read_csv(csvPath)

        missingColumns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in dataFrame.columns
        ]

        if missingColumns:
            raise ValueError(
                "Kolom CSV tidak lengkap. "
                f"Kolom yang hilang: {missingColumns}"
            )

        if dataFrame.empty:
            raise ValueError(
                "CSV traffic kosong."
            )

        # ====================================================
        # TIMESTAMP
        # ====================================================

        dataFrame["timestamp"] = pd.to_datetime(
            dataFrame["timestamp"],
            errors="coerce",
        )

        if dataFrame["timestamp"].isna().any():
            raise ValueError(
                "Terdapat timestamp yang tidak valid."
            )

        # ====================================================
        # STRING NORMALIZATION
        # ====================================================

        dataFrame["intersectionId"] = (
            dataFrame["intersectionId"]
            .astype(str)
            .str.strip()
        )

        dataFrame["approach"] = (
            dataFrame["approach"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        dataFrame["laneId"] = (
            dataFrame["laneId"]
            .astype(str)
            .str.strip()
        )

        if (dataFrame["intersectionId"] == "").any():
            raise ValueError(
                "Terdapat intersectionId kosong."
            )

        if (dataFrame["laneId"] == "").any():
            raise ValueError(
                "Terdapat laneId kosong."
            )

        # ====================================================
        # APPROACH VALIDATION
        # ====================================================

        invalidApproaches = sorted(
            set(dataFrame["approach"])
            - set(EXPECTED_APPROACHES)
        )

        if invalidApproaches:
            raise ValueError(
                "Approach tidak valid: "
                f"{invalidApproaches}. "
                f"Approach yang diperbolehkan: "
                f"{EXPECTED_APPROACHES}"
            )

        # ====================================================
        # NUMERIC CONVERSION
        # ====================================================

        for column in NUMERIC_COLUMNS:
            dataFrame[column] = pd.to_numeric(
                dataFrame[column],
                errors="coerce",
            )

        if dataFrame[list(NUMERIC_COLUMNS)].isna().any().any():
            invalidColumns = [
                column
                for column in NUMERIC_COLUMNS
                if dataFrame[column].isna().any()
            ]

            raise ValueError(
                "Terdapat nilai numerik yang tidak valid "
                f"atau kosong pada kolom: {invalidColumns}"
            )

        # ====================================================
        # INTEGER VALIDATION
        # ====================================================

        integerColumns = (
            "vehicleCount",
            "carCount",
            "motorcycleCount",
            "busCount",
            "truckCount",
            "queueLengthVeh",
        )

        for column in integerColumns:
            if (
                dataFrame[column] % 1 != 0
            ).any():
                raise ValueError(
                    f"Kolom {column} harus berupa bilangan bulat."
                )

            dataFrame[column] = (
                dataFrame[column].astype(int)
            )

        # ====================================================
        # NEGATIVE VALUES
        # ====================================================

        negativeMask = (
            dataFrame[list(NUMERIC_COLUMNS)] < 0
        ).any(axis=1)

        if negativeMask.any():
            raise ValueError(
                "Terdapat nilai negatif pada metric traffic."
            )

        # ====================================================
        # VEHICLE CLASSIFICATION CONSISTENCY
        # ====================================================

        classificationTotal = (
            dataFrame["carCount"]
            + dataFrame["motorcycleCount"]
            + dataFrame["busCount"]
            + dataFrame["truckCount"]
        )

        inconsistentMask = (
            dataFrame["vehicleCount"]
            != classificationTotal
        )

        if inconsistentMask.any():
            firstInvalid = dataFrame.loc[
                inconsistentMask
            ].iloc[0]

            raise ValueError(
                "vehicleCount tidak konsisten dengan "
                "jumlah klasifikasi kendaraan pada "
                "setidaknya satu row. "
                f"Timestamp: {firstInvalid['timestamp']}, "
                f"approach: {firstInvalid['approach']}, "
                f"lane: {firstInvalid['laneId']}"
            )

        # ====================================================
        # SORT
        # ====================================================

        dataFrame = dataFrame.sort_values(
            by=[
                "timestamp",
                "intersectionId",
                "approach",
                "laneId",
            ]
        ).reset_index(drop=True)

        return dataFrame

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
            group["vehicleCount"].sum()
        )

        carCount = int(
            group["carCount"].sum()
        )

        motorcycleCount = int(
            group["motorcycleCount"].sum()
        )

        busCount = int(
            group["busCount"].sum()
        )

        truckCount = int(
            group["truckCount"].sum()
        )

        queueLengthVeh = int(
            group["queueLengthVeh"].sum()
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

    def buildFromCsv(
        self,
        csvPath: str | Path,
    ) -> list[TrafficState]:

        dataFrame = self.loadCsv(
            csvPath
        )

        return self.buildFromDataFrame(
            dataFrame
        )


# ============================================================
# DEFAULT CSV PATH
# ============================================================

def getDefaultCsvPath() -> Path:

    projectRoot = (
        Path(__file__)
        .resolve()
        .parents[3]
    )

    return (
        projectRoot
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )


# ============================================================
# CLI
# ============================================================

def main() -> None:

    csvPath = getDefaultCsvPath()

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            windowSeconds=5
        )
    )

    states = builder.buildFromCsv(
        csvPath
    )

    print("=" * 60)
    print("TRAFFIC STATE BUILDER")
    print("=" * 60)

    print(f"CSV    : {csvPath}")
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