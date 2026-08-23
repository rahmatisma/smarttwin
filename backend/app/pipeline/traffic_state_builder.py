from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from supabase import Client

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


# ============================================================
# OUTPUT MODELS
# ============================================================

class ApproachTrafficState(BaseModel):
    approach: str

    volume: int = 0

    carCount: int = 0
    motorcycleCount: int = 0
    busCount: int = 0
    truckCount: int = 0

    queueLengthVeh: int = 0
    queueLengthMEst: float = 0.0

    densityIndex: float = 0.0

    avgSpeedKmh: float | None = None


class BuiltTrafficState(BaseModel):
    trafficStateId: int

    intersectionId: str

    windowStart: datetime
    windowEnd: datetime

    approaches: list[ApproachTrafficState]

    source: str = "cv"


# ============================================================
# CONFIG
# ============================================================

@dataclass(frozen=True)
class TrafficStateBuilderConfig:
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
    Traffic State Builder.

    Sumber data:

        YOLO / Computer Vision
                |
                v
        trafficStates
                |
                v
        trafficLaneMetrics
                |
                v
        lanes
                |
                v
        approaches
                |
                v
        intersections

    Builder melakukan:

        1. Ambil trafficStates
        2. Ambil trafficLaneMetrics
        3. Hubungkan lane -> approach -> intersection
        4. Kelompokkan metric berdasarkan approach
        5. Hitung aggregate traffic state
        6. Simpan hasil ke trafficApproachStates
        7. Kembalikan data yang siap dipakai SUMO

    Tidak bergantung pada CSV.
    Tidak dikunci ke satu intersection.
    """

    def __init__(
        self,
        config: TrafficStateBuilderConfig | None = None,
        supabase: Client | None = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else TrafficStateBuilderConfig()
        )

        self.supabase = supabase or get_supabase()

    # ========================================================
    # INTERSECTIONS
    # ========================================================

<<<<<<< HEAD
    def loadCvOutput(
        self,
        crossPath: str | Path,
        densityPath: str | Path,
    ) -> pd.DataFrame:
        """
        Membaca dan menggabungkan output asli dari Computer Vision.
=======
    def get_active_intersections(self) -> list[dict[str, Any]]:
        """
        Mengambil seluruh intersection aktif.
>>>>>>> 6147cc07d11ab5910b7a950bceb53a0fe3c1d7a8
        """
        crossPath = Path(crossPath)
        densityPath = Path(densityPath)

<<<<<<< HEAD
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
=======
        result = (
            self.supabase
>>>>>>> 6147cc07d11ab5910b7a950bceb53a0fe3c1d7a8
            .table("intersections")
            .select(
                "id, intersectionId, name, status"
            )
            .eq("status", "active")
            .order("id")
            .execute()
        )

        return result.data or []

    # ========================================================
    # APPROACHES
    # ========================================================

    def get_approaches(self) -> list[dict[str, Any]]:
        """
        Mengambil seluruh approach.
        """

        result = (
            self.supabase
            .table("approaches")
            .select(
                "id, intersectionId, approach, name"
            )
            .order("id")
            .execute()
        )

        return result.data or []

    # ========================================================
    # LANES
    # ========================================================

    def get_lanes(self) -> list[dict[str, Any]]:
        """
        Mengambil seluruh lane.
        """

        result = (
            self.supabase
            .table("lanes")
            .select(
                "id, approachId, laneId, laneNumber, direction"
            )
            .order("id")
            .execute()
        )

        return result.data or []

    # ========================================================
    # TRAFFIC STATES
    # ========================================================

    def get_latest_traffic_states(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Mengambil traffic state terbaru dari seluruh intersection.
        """

        result = (
            self.supabase
            .table("trafficStates")
            .select(
                """
                id,
                intersectionId,
                windowStart,
                windowEnd,
                source,
                processingJobId,
                createdAt
                """
            )
            .order(
                "windowStart",
                desc=True,
            )
            .limit(limit)
            .execute()
        )

        return result.data or []

    # ========================================================
    # TRAFFIC LANE METRICS
    # ========================================================

    def get_lane_metrics(
        self,
        traffic_state_ids: list[int],
    ) -> list[dict[str, Any]]:
        """
        Mengambil metric YOLO berdasarkan trafficStateId.

        PENTING:
        trafficLaneMetrics TIDAK mempunyai intersectionId.

        Relasinya:

            trafficLaneMetrics.laneId
                    ↓
                lanes.id
                    ↓
                approaches.id
                    ↓
            approaches.intersectionId
        """

        if not traffic_state_ids:
            return []

        result = (
            self.supabase
            .table("trafficLaneMetrics")
            .select(
                """
                id,
                trafficStateId,
                laneId,
                timestamp,
                vehicleCount,
                carCount,
                motorcycleCount,
                busCount,
                truckCount,
                queueLengthVeh,
                queueLengthMEst,
                densityIndex
                """
            )
            .in_(
                "trafficStateId",
                traffic_state_ids,
            )
            .order(
                "timestamp",
                desc=False,
            )
            .execute()
        )

        return result.data or []

    # ========================================================
    # BUILD RELATION MAP
    # ========================================================

    def build_relation_maps(
        self,
    ) -> tuple[
        dict[int, dict[str, Any]],
        dict[int, dict[str, Any]],
        dict[int, dict[str, Any]],
    ]:
        """
        Membuat mapping:

        lane_id
            -> lane

        approach_id
            -> approach

        intersection_id
            -> intersection
        """

        intersections = self.get_active_intersections()
        approaches = self.get_approaches()
        lanes = self.get_lanes()

        intersection_map = {
            int(row["id"]): row
            for row in intersections
        }

        approach_map = {
            int(row["id"]): row
            for row in approaches
        }

        lane_map = {
            int(row["id"]): row
            for row in lanes
        }

        return (
            intersection_map,
            approach_map,
            lane_map,
        )

    # ========================================================
    # AGGREGATE APPROACH
    # ========================================================

    def aggregate_approach(
        self,
        rows: list[dict[str, Any]],
        approach_name: str,
    ) -> ApproachTrafficState:
        """
        Menggabungkan seluruh lane dalam satu approach.
        """

        if not rows:
            return ApproachTrafficState(
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

        volume = sum(
            int(row.get("vehicleCount") or 0)
            for row in rows
        )

        car_count = sum(
            int(row.get("carCount") or 0)
            for row in rows
        )

        motorcycle_count = sum(
            int(row.get("motorcycleCount") or 0)
            for row in rows
        )

        bus_count = sum(
            int(row.get("busCount") or 0)
            for row in rows
        )

        truck_count = sum(
            int(row.get("truckCount") or 0)
            for row in rows
        )

        queue_length_veh = sum(
            int(row.get("queueLengthVeh") or 0)
            for row in rows
        )

        queue_length_m = sum(
            float(row.get("queueLengthMEst") or 0)
            for row in rows
        )

        density_values = [
            float(row.get("densityIndex") or 0)
            for row in rows
        ]

        density_index = (
            sum(density_values)
            / len(density_values)
            if density_values
            else 0.0
        )

        return ApproachTrafficState(
            approach=approach_name,
            volume=volume,
            carCount=car_count,
            motorcycleCount=motorcycle_count,
            busCount=bus_count,
            truckCount=truck_count,
            queueLengthVeh=queue_length_veh,
            queueLengthMEst=queue_length_m,
            densityIndex=density_index,
            avgSpeedKmh=None,
        )

    # ========================================================
    # BUILD SINGLE TRAFFIC STATE
    # ========================================================

    def build_state(
        self,
        traffic_state: dict[str, Any],
        lane_metrics: list[dict[str, Any]],
        intersection_map: dict[int, dict[str, Any]],
        approach_map: dict[int, dict[str, Any]],
        lane_map: dict[int, dict[str, Any]],
    ) -> BuiltTrafficState | None:
        """
        Membentuk satu TrafficState dari metric YOLO.
        """

        traffic_state_id = int(
            traffic_state["id"]
        )

        intersection_row_id = int(
            traffic_state["intersectionId"]
        )

        intersection = intersection_map.get(
            intersection_row_id
        )

        if intersection is None:
            return None

        intersection_name = str(
            intersection["intersectionId"]
        )

        # ----------------------------------------------------
        # Group metric berdasarkan approach
        # ----------------------------------------------------

        approach_rows: dict[str, list[dict[str, Any]]] = {
            approach: []
            for approach in EXPECTED_APPROACHES
        }

        for metric in lane_metrics:

            lane_row_id = int(
                metric["laneId"]
            )

            lane = lane_map.get(
                lane_row_id
            )

            if lane is None:
                continue

            approach_row_id = int(
                lane["approachId"]
            )

            approach = approach_map.get(
                approach_row_id
            )

            if approach is None:
                continue

            approach_name = (
                str(approach["approach"])
                .strip()
                .lower()
            )

            if approach_name not in EXPECTED_APPROACHES:
                continue

            approach_rows[
                approach_name
            ].append(metric)

        # ----------------------------------------------------
        # Aggregate
        # ----------------------------------------------------

        approaches: list[ApproachTrafficState] = []

        for approach_name in EXPECTED_APPROACHES:

            approach_state = self.aggregate_approach(
                rows=approach_rows[approach_name],
                approach_name=approach_name,
            )

            approaches.append(
                approach_state
            )

        return BuiltTrafficState(
            trafficStateId=traffic_state_id,
            intersectionId=intersection_name,
            windowStart=self.parse_datetime(
                traffic_state["windowStart"]
            ),
            windowEnd=self.parse_datetime(
                traffic_state["windowEnd"]
            ),
            approaches=approaches,
            source=str(
                traffic_state.get(
                    "source",
                    "cv",
                )
            ),
        )

    # ========================================================
    # SAVE APPROACH STATES
    # ========================================================

    def save_approach_states(
        self,
        traffic_state_id: int,
        built_state: BuiltTrafficState,
    ) -> None:
        """
        Menyimpan hasil agregasi ke:

            trafficApproachStates

        Catatan:
        Karena data approach state merupakan hasil builder,
        kita hapus hasil lama untuk trafficStateId tersebut
        lalu insert ulang.
        """

        self.supabase \
            .table("trafficApproachStates") \
            .delete() \
            .eq(
                "trafficStateId",
                traffic_state_id,
            ) \
            .execute()

        rows: list[dict[str, Any]] = []

        for approach in built_state.approaches:

            # Cari approach ID berdasarkan intersection
            approach_result = (
                self.supabase
                .table("approaches")
                .select("id, approach")
                .eq(
                    "approach",
                    approach.approach,
                )
                .eq(
                    "intersectionId",
                    self.get_intersection_row_id(
                        built_state.intersectionId
                    ),
                )
                .limit(1)
                .execute()
            )

            approach_rows = (
                approach_result.data or []
            )

            if not approach_rows:
                continue

            approach_id = int(
                approach_rows[0]["id"]
            )

            rows.append(
                {
                    "trafficStateId": traffic_state_id,
                    "approachId": approach_id,
                    "approach": approach.approach,
                    "volume": approach.volume,
                    "carCount": approach.carCount,
                    "motorcycleCount": approach.motorcycleCount,
                    "busCount": approach.busCount,
                    "truckCount": approach.truckCount,
                    "queueLengthVeh": approach.queueLengthVeh,
                    "queueLengthMEst": approach.queueLengthMEst,
                    "densityIndex": approach.densityIndex,
                    "avgSpeedKmh": approach.avgSpeedKmh,
                }
            )

        if rows:
            (
                self.supabase
                .table("trafficApproachStates")
                .insert(rows)
                .execute()
            )

    # ========================================================
    # INTERSECTION ROW ID
    # ========================================================

    def get_intersection_row_id(
        self,
        intersection_id: str,
    ) -> int:
        """
        Mengubah:

            simpang4-pingit

        menjadi:

            intersections.id
        """

        result = (
            self.supabase
            .table("intersections")
            .select("id")
            .eq(
                "intersectionId",
                intersection_id,
            )
            .limit(1)
            .execute()
        )

        rows = result.data or []

        if not rows:
            raise ValueError(
                f"Intersection '{intersection_id}' "
                "tidak ditemukan."
            )

        return int(
            rows[0]["id"]
        )

    # ========================================================
    # BUILD LATEST
    # ========================================================

    def build_latest_states(
        self,
        limit: int = 100,
        save: bool = True,
    ) -> list[BuiltTrafficState]:
        """
        Memproses traffic state terbaru dari SEMUA intersection.
        """

        traffic_states = (
            self.get_latest_traffic_states(
                limit=limit
            )
        )

        if not traffic_states:
            return []

        traffic_state_ids = [
            int(row["id"])
            for row in traffic_states
        ]

        lane_metrics = (
            self.get_lane_metrics(
                traffic_state_ids
            )
        )

        if not lane_metrics:
            return []

        (
            intersection_map,
            approach_map,
            lane_map,
        ) = self.build_relation_maps()

        metrics_by_state: dict[
            int,
            list[dict[str, Any]]
        ] = {}

        for metric in lane_metrics:

            state_id = int(
                metric["trafficStateId"]
            )

            metrics_by_state.setdefault(
                state_id,
                []
            ).append(metric)

        built_states: list[BuiltTrafficState] = []

        for traffic_state in traffic_states:

            state_id = int(
                traffic_state["id"]
            )

            state_metrics = (
                metrics_by_state.get(
                    state_id,
                    []
                )
            )

            if not state_metrics:
                continue

            built_state = self.build_state(
                traffic_state=traffic_state,
                lane_metrics=state_metrics,
                intersection_map=intersection_map,
                approach_map=approach_map,
                lane_map=lane_map,
            )

            if built_state is None:
                continue

            if save:
                self.save_approach_states(
                    traffic_state_id=state_id,
                    built_state=built_state,
                )

            built_states.append(
                built_state
            )

        return built_states

    # ========================================================
    # BUILD SINGLE INTERSECTION
    # ========================================================

    def build_latest_state_for_intersection(
        self,
        intersection_id: str,
        save: bool = True,
    ) -> BuiltTrafficState | None:
        """
        Optional helper untuk testing satu intersection.

        BUKAN berarti sistem hanya mendukung satu intersection.
        """

        intersection_row_id = (
            self.get_intersection_row_id(
                intersection_id
            )
        )

        traffic_result = (
            self.supabase
            .table("trafficStates")
            .select(
                """
                id,
                intersectionId,
                windowStart,
                windowEnd,
                source,
                processingJobId,
                createdAt
                """
            )
            .eq(
                "intersectionId",
                intersection_row_id,
            )
            .order(
                "windowStart",
                desc=True,
            )
            .limit(1)
            .execute()
        )

        traffic_states = (
            traffic_result.data or []
        )

        if not traffic_states:
            return None

        traffic_state = traffic_states[0]

        state_id = int(
            traffic_state["id"]
        )

        lane_metrics = (
            self.get_lane_metrics(
                [state_id]
            )
        )

        if not lane_metrics:
            return None

        (
            intersection_map,
            approach_map,
            lane_map,
        ) = self.build_relation_maps()

        built_state = self.build_state(
            traffic_state=traffic_state,
            lane_metrics=lane_metrics,
            intersection_map=intersection_map,
            approach_map=approach_map,
            lane_map=lane_map,
        )

        if built_state is None:
            return None

        if save:
            self.save_approach_states(
                traffic_state_id=state_id,
                built_state=built_state,
            )

        return built_state

    # ========================================================
    # DATETIME
    # ========================================================

    @staticmethod
    def parse_datetime(
        value: Any,
    ) -> datetime:

        if isinstance(value, datetime):
            return value

        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    # ========================================================
    # PRINT STATE
    # ========================================================

    @staticmethod
    def print_state(
        state: BuiltTrafficState,
    ) -> None:

        print()
        print("=" * 70)
        print("TRAFFIC STATE")
        print("=" * 70)

        print(
            f"Traffic State ID : "
            f"{state.trafficStateId}"
        )

        print(
            f"Intersection     : "
            f"{state.intersectionId}"
        )

        print(
            f"Window           : "
            f"{state.windowStart} -> "
            f"{state.windowEnd}"
        )

        print(
            f"Source           : "
            f"{state.source}"
        )

        print("-" * 70)

        for approach in state.approaches:

            print(
                f"{approach.approach.upper():<8} | "
                f"volume={approach.volume:<5} | "
                f"car={approach.carCount:<5} | "
                f"motor={approach.motorcycleCount:<5} | "
                f"bus={approach.busCount:<5} | "
                f"truck={approach.truckCount:<5} | "
                f"queue={approach.queueLengthVeh:<5} | "
                f"queueM={approach.queueLengthMEst:.2f} | "
                f"density={approach.densityIndex:.3f}"
            )

        print("=" * 70)

    # ========================================================
    # RUN ONCE
    # ========================================================

    def run_once(
        self,
        limit: int = 100,
        save: bool = True,
    ) -> list[BuiltTrafficState]:

        states = self.build_latest_states(
            limit=limit,
            save=save,
        )

        if not states:
            print()
            print(
                "Tidak ada traffic state yang memiliki "
                "trafficLaneMetrics."
            )
            print()
            return []

        for state in states:
            self.print_state(state)

        print()
        print(
            f"Berhasil membangun "
            f"{len(states)} traffic state."
        )

        return states

<<<<<<< HEAD
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
=======

# ============================================================
# MAIN
>>>>>>> 6147cc07d11ab5910b7a950bceb53a0fe3c1d7a8
# ============================================================

def main() -> None:

<<<<<<< HEAD
    crossPath = getDefaultCrossPath()
    densityPath = getDefaultDensityPath()
=======
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "SmartTwin Traffic State Builder"
        )
    )

    parser.add_argument(
        "--intersection-id",
        type=str,
        default=None,
        help=(
            "Optional. Contoh: simpang4-pingit"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help=(
            "Jumlah traffic state terbaru "
            "yang diproses."
        ),
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help=(
            "Jangan menyimpan hasil ke "
            "trafficApproachStates."
        ),
    )

    args = parser.parse_args()
>>>>>>> 6147cc07d11ab5910b7a950bceb53a0fe3c1d7a8

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            windowSeconds=5
        )
    )

<<<<<<< HEAD
    states = builder.buildFromCvOutput(
        crossPath,
        densityPath
    )
=======
    print("=" * 70)
    print("SMARTTWIN TRAFFIC STATE BUILDER")
    print("=" * 70)
    print("Source : Supabase")
    print("Window : 5 seconds")
>>>>>>> 6147cc07d11ab5910b7a950bceb53a0fe3c1d7a8

    # --------------------------------------------------------
    # SINGLE INTERSECTION
    # --------------------------------------------------------

<<<<<<< HEAD
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
=======
    if args.intersection_id:

        print(
            "Mode   : Single Intersection"
        )

        print(
            f"Target : "
            f"{args.intersection_id}"
        )

        state = (
            builder
            .build_latest_state_for_intersection(
                intersection_id=args.intersection_id,
                save=not args.no_save,
>>>>>>> 6147cc07d11ab5910b7a950bceb53a0fe3c1d7a8
            )
        )

        if state is None:

            print()
            print(
                "Tidak ada trafficLaneMetrics "
                "untuk intersection ini."
            )

            return

        builder.print_state(state)

        return

    # --------------------------------------------------------
    # ALL INTERSECTIONS
    # --------------------------------------------------------

    print(
        "Mode   : ALL ACTIVE INTERSECTIONS"
    )

    builder.run_once(
        limit=args.limit,
        save=not args.no_save,
    )


if __name__ == "__main__":
    main()