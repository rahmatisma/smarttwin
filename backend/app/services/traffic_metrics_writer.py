from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client

from app.services.supabase_client import get_supabase


class TrafficMetricsWriter:
    """
    Menulis hasil agregasi Computer Vision ke Supabase.

    Alur:

        YOLO / ByteTrack
              ↓
        lane metrics
              ↓
        create trafficState
              ↓
        create trafficLaneMetrics
              ↓
        TrafficStateBuilder
    """

    def __init__(
        self,
        supabase: Client | None = None,
    ) -> None:

        self.supabase = (
            supabase
            or get_supabase()
        )

    # ========================================================
    # GET INTERSECTION
    # ========================================================

    def get_intersection(
        self,
        intersection_id: str,
    ) -> dict[str, Any]:

        result = (
            self.supabase
            .table("intersections")
            .select(
                "id, intersectionId, name, status"
            )
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

        return rows[0]

    # ========================================================
    # GET LANE
    # ========================================================

    def get_lane(
        self,
        lane_id: str,
        intersection_row_id: int,
    ) -> dict[str, Any]:

        # Ambil seluruh lane
        lanes_result = (
            self.supabase
            .table("lanes")
            .select(
                """
                id,
                approachId,
                laneId,
                laneNumber,
                direction
                """
            )
            .eq(
                "laneId",
                lane_id,
            )
            .execute()
        )

        lanes = lanes_result.data or []

        if not lanes:
            raise ValueError(
                f"Lane '{lane_id}' "
                "tidak ditemukan."
            )

        # Cari lane yang benar-benar
        # berada di intersection tersebut
        approaches_result = (
            self.supabase
            .table("approaches")
            .select(
                "id, intersectionId, approach"
            )
            .eq(
                "intersectionId",
                intersection_row_id,
            )
            .execute()
        )

        approaches = (
            approaches_result.data or []
        )

        approach_ids = {
            int(row["id"])
            for row in approaches
        }

        for lane in lanes:

            if int(
                lane["approachId"]
            ) in approach_ids:

                return lane

        raise ValueError(
            f"Lane '{lane_id}' "
            "tidak berada pada intersection "
            f"id={intersection_row_id}."
        )

    # ========================================================
    # CREATE TRAFFIC STATE
    # ========================================================

    def create_traffic_state(
        self,
        intersection_row_id: int,
        window_start: datetime,
        window_end: datetime,
        source: str = "cv",
    ) -> int:

        payload = {
            "intersectionId": intersection_row_id,
            "windowStart": (
                window_start.isoformat()
            ),
            "windowEnd": (
                window_end.isoformat()
            ),
            "source": source,
            "processingJobId": None,
        }

        result = (
            self.supabase
            .table("trafficStates")
            .insert(payload)
            .execute()
        )

        rows = result.data or []

        if not rows:
            raise RuntimeError(
                "Gagal membuat trafficStates."
            )

        return int(
            rows[0]["id"]
        )

    # ========================================================
    # INSERT LANE METRICS
    # ========================================================

    def insert_lane_metrics(
        self,
        traffic_state_id: int,
        metrics: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        if not metrics:
            raise ValueError(
                "metrics tidak boleh kosong."
            )

        rows: list[dict[str, Any]] = []

        for metric in metrics:

            rows.append(
                {
                    "trafficStateId": traffic_state_id,
                    "laneId": int(
                        metric["laneId"]
                    ),
                    "timestamp": self.normalize_datetime(
                        metric.get(
                            "timestamp"
                        )
                    ),
                    "vehicleCount": int(
                        metric.get(
                            "vehicleCount",
                            0,
                        )
                    ),
                    "carCount": int(
                        metric.get(
                            "carCount",
                            0,
                        )
                    ),
                    "motorcycleCount": int(
                        metric.get(
                            "motorcycleCount",
                            0,
                        )
                    ),
                    "busCount": int(
                        metric.get(
                            "busCount",
                            0,
                        )
                    ),
                    "truckCount": int(
                        metric.get(
                            "truckCount",
                            0,
                        )
                    ),
                    "queueLengthVeh": int(
                        metric.get(
                            "queueLengthVeh",
                            0,
                        )
                    ),
                    "queueLengthMEst": float(
                        metric.get(
                            "queueLengthMEst",
                            0.0,
                        )
                    ),
                    "densityIndex": float(
                        metric.get(
                            "densityIndex",
                            0.0,
                        )
                    ),
                }
            )

        result = (
            self.supabase
            .table("trafficLaneMetrics")
            .insert(rows)
            .execute()
        )

        return result.data or []

    # ========================================================
    # COMPLETE CV WINDOW
    # ========================================================

    def write_cv_window(
        self,
        intersection_id: str,
        window_start: datetime,
        window_end: datetime,
        metrics: list[dict[str, Any]],
        source: str = "cv",
    ) -> dict[str, Any]:

        if not metrics:
            raise ValueError(
                "Tidak ada metric dari YOLO."
            )

        intersection = (
            self.get_intersection(
                intersection_id
            )
        )

        intersection_row_id = int(
            intersection["id"]
        )

        # ----------------------------------------------------
        # Validate semua lane
        # ----------------------------------------------------

        validated_metrics: list[
            dict[str, Any]
        ] = []

        for metric in metrics:

            lane_id = str(
                metric["laneId"]
            )

            lane = self.get_lane(
                lane_id=lane_id,
                intersection_row_id=(
                    intersection_row_id
                ),
            )

            validated_metric = dict(
                metric
            )

            validated_metric[
                "laneId"
            ] = int(lane["id"])

            validated_metrics.append(
                validated_metric
            )

        # ----------------------------------------------------
        # Create traffic state
        # ----------------------------------------------------

        traffic_state_id = (
            self.create_traffic_state(
                intersection_row_id=(
                    intersection_row_id
                ),
                window_start=window_start,
                window_end=window_end,
                source=source,
            )
        )

        # ----------------------------------------------------
        # Insert lane metrics
        # ----------------------------------------------------

        inserted_metrics = (
            self.insert_lane_metrics(
                traffic_state_id=(
                    traffic_state_id
                ),
                metrics=validated_metrics,
            )
        )

        return {
            "trafficStateId": (
                traffic_state_id
            ),
            "intersectionId": (
                intersection_id
            ),
            "windowStart": (
                window_start.isoformat()
            ),
            "windowEnd": (
                window_end.isoformat()
            ),
            "metricCount": len(
                inserted_metrics
            ),
        }

    # ========================================================
    # DATETIME
    # ========================================================

    @staticmethod
    def normalize_datetime(
        value: Any,
    ) -> str:

        if value is None:
            return datetime.now(
                timezone.utc
            ).isoformat()

        if isinstance(
            value,
            datetime,
        ):

            dt = value

        else:

            dt = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.isoformat()


traffic_metrics_writer = (
    TrafficMetricsWriter()
)