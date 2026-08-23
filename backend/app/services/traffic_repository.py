from __future__ import annotations

from datetime import datetime
from typing import Any

from postgrest.exceptions import APIError

from app.schemas.traffic import TrafficState
from app.services.supabase_client import get_supabase


class TrafficRepositoryError(Exception):
    """Error khusus untuk operasi traffic di Supabase."""

    pass


class TrafficRepository:
    """
    Repository untuk menyimpan dan mengambil TrafficState
    dari Supabase.

    Mendukung:
        1. Single-state operation
        2. Bulk upsert operation

    Struktur database:

        intersections
             ↓
        approaches
             ↓
        trafficStates
             ↓
        trafficApproachStates
    """

    # ============================================================
    # INTERSECTION
    # ============================================================

    def get_intersection_row_id(
        self,
        intersection_id: str,
    ) -> int:
        """
        Mengubah business ID intersection seperti:

            simpang4-pingit

        menjadi primary key database pada tabel intersections.
        """

        supabase = get_supabase()

        result = (
            supabase
            .table("intersections")
            .select("id")
            .eq("intersectionId", intersection_id)
            .maybe_single()
            .execute()
        )

        if result is None or not result.data:
            raise TrafficRepositoryError(
                f"Intersection '{intersection_id}' tidak ditemukan."
            )

        return int(result.data["id"])

    # ============================================================
    # APPROACH
    # ============================================================

    def get_approach_row_id(
        self,
        intersection_row_id: int,
        approach: str,
    ) -> int:
        """
        Mengambil primary key tabel approaches.
        """

        supabase = get_supabase()

        result = (
            supabase
            .table("approaches")
            .select("id")
            .eq("intersectionId", intersection_row_id)
            .eq("approach", approach)
            .maybe_single()
            .execute()
        )

        if result is None or not result.data:
            raise TrafficRepositoryError(
                (
                    f"Approach '{approach}' tidak ditemukan "
                    f"untuk intersection id {intersection_row_id}."
                )
            )

        return int(result.data["id"])

    # ============================================================
    # FIND EXISTING TRAFFIC STATE
    # ============================================================

    def find_traffic_state(
        self,
        *,
        intersection_row_id: int,
        window_start: datetime,
        window_end: datetime,
    ) -> dict[str, Any] | None:
        """
        Mencari TrafficState berdasarkan kombinasi:

            intersectionId
            windowStart
            windowEnd
        """

        supabase = get_supabase()

        result = (
            supabase
            .table("trafficStates")
            .select("*")
            .eq("intersectionId", intersection_row_id)
            .eq("windowStart", window_start.isoformat())
            .eq("windowEnd", window_end.isoformat())
            .maybe_single()
            .execute()
        )

        if result is None:
            return None

        return result.data

    # ============================================================
    # UPSERT SINGLE TRAFFIC STATE
    # ============================================================

    def upsert_traffic_state(
        self,
        *,
        intersection_row_id: int,
        window_start: datetime,
        window_end: datetime,
        source: str = "cv",
        processing_job_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Insert atau update satu row trafficStates.
        """

        supabase = get_supabase()

        existing = self.find_traffic_state(
            intersection_row_id=intersection_row_id,
            window_start=window_start,
            window_end=window_end,
        )

        payload = {
            "intersectionId": intersection_row_id,
            "windowStart": window_start.isoformat(),
            "windowEnd": window_end.isoformat(),
            "source": source,
            "processingJobId": processing_job_id,
        }

        if existing:
            result = (
                supabase
                .table("trafficStates")
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )

            if not result.data:
                raise TrafficRepositoryError(
                    "Gagal update trafficStates."
                )

            return result.data[0]

        result = (
            supabase
            .table("trafficStates")
            .insert(payload)
            .execute()
        )

        if not result.data:
            raise TrafficRepositoryError(
                "Gagal insert trafficStates."
            )

        return result.data[0]

    # ============================================================
    # FIND APPROACH STATE
    # ============================================================

    def find_approach_state(
        self,
        *,
        traffic_state_id: int,
        approach_id: int,
    ) -> dict[str, Any] | None:
        """
        Mencari trafficApproachStates berdasarkan:

            trafficStateId
            approachId
        """

        supabase = get_supabase()

        result = (
            supabase
            .table("trafficApproachStates")
            .select("*")
            .eq("trafficStateId", traffic_state_id)
            .eq("approachId", approach_id)
            .maybe_single()
            .execute()
        )

        if result is None:
            return None

        return result.data

    # ============================================================
    # UPSERT SINGLE APPROACH STATE
    # ============================================================

    def upsert_approach_state(
        self,
        *,
        traffic_state_id: int,
        approach_id: int,
        approach: str,
        volume: int,
        car_count: int,
        motorcycle_count: int,
        bus_count: int,
        truck_count: int,
        queue_length_veh: int,
        queue_length_m_est: float,
        density_index: float,
        avg_speed_kmh: float | None,
    ) -> dict[str, Any]:
        """
        Insert atau update detail traffic untuk satu approach.
        """

        supabase = get_supabase()

        existing = self.find_approach_state(
            traffic_state_id=traffic_state_id,
            approach_id=approach_id,
        )

        payload = {
            "trafficStateId": traffic_state_id,
            "approachId": approach_id,
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

        if existing:
            result = (
                supabase
                .table("trafficApproachStates")
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )

            if not result.data:
                raise TrafficRepositoryError(
                    "Gagal update trafficApproachStates."
                )

            return result.data[0]

        result = (
            supabase
            .table("trafficApproachStates")
            .insert(payload)
            .execute()
        )

        if not result.data:
            raise TrafficRepositoryError(
                "Gagal insert trafficApproachStates."
            )

        return result.data[0]

    # ============================================================
    # SAVE COMPLETE SINGLE TRAFFIC STATE
    # ============================================================

    def save_traffic_state(
        self,
        state: TrafficState,
        *,
        source: str = "cv",
        processing_job_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Menyimpan satu TrafficState lengkap.

        Flow:

            TrafficState
                ↓
            trafficStates
                ↓
            trafficApproachStates
        """

        intersection_row_id = self.get_intersection_row_id(
            state.intersectionId
        )

        traffic_state_row = self.upsert_traffic_state(
            intersection_row_id=intersection_row_id,
            window_start=state.windowStart,
            window_end=state.windowEnd,
            source=source,
            processing_job_id=processing_job_id,
        )

        traffic_state_id = int(
            traffic_state_row["id"]
        )

        saved_approaches = []

        for approach_state in state.approaches:

            approach_row_id = self.get_approach_row_id(
                intersection_row_id=intersection_row_id,
                approach=approach_state.approach,
            )

            approach_row = self.upsert_approach_state(
                traffic_state_id=traffic_state_id,
                approach_id=approach_row_id,
                approach=approach_state.approach,
                volume=approach_state.volume,
                car_count=approach_state.carCount,
                motorcycle_count=approach_state.motorcycleCount,
                bus_count=approach_state.busCount,
                truck_count=approach_state.truckCount,
                queue_length_veh=approach_state.queueLengthVeh,
                queue_length_m_est=approach_state.queueLengthMEst,
                density_index=approach_state.densityIndex,
                avg_speed_kmh=approach_state.avgSpeedKmh,
            )

            saved_approaches.append(
                approach_row
            )

        return {
            "traffic_state": traffic_state_row,
            "approaches": saved_approaches,
        }

    # ============================================================
    # BULK UPSERT TRAFFIC STATES
    # ============================================================

    def _save_states_without_conflict_target(
        self,
        states: list[TrafficState],
        *,
        source: str,
        processing_job_id: int | None,
    ) -> dict[str, Any]:
        """Fallback untuk database tanpa unique constraint yang sesuai."""

        traffic_states: list[dict[str, Any]] = []
        approaches: list[dict[str, Any]] = []

        for state in states:
            result = self.save_traffic_state(
                state,
                source=source,
                processing_job_id=processing_job_id,
            )
            traffic_states.append(result["traffic_state"])
            approaches.extend(result["approaches"])

        return {
            "traffic_states": traffic_states,
            "approaches": approaches,
            "traffic_state_count": len(traffic_states),
            "approach_state_count": len(approaches),
        }

    def bulk_upsert_traffic_states(
        self,
        states: list[TrafficState],
        *,
        source: str = "cv",
        processing_job_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Bulk upsert TrafficState dan seluruh ApproachState.

        Tujuan utama:
            menghindari ribuan request Supabase
            ketika memproses ratusan TrafficState.

        Flow:

            TrafficState[]
                 ↓
            Resolve intersection IDs
                 ↓
            Prepare trafficStates rows
                 ↓
            BULK UPSERT trafficStates
                 ↓
            Resolve trafficState IDs
                 ↓
            Prepare approach rows
                 ↓
            BULK UPSERT trafficApproachStates

        Return:

            {
                "traffic_states": [...],
                "approaches": [...],
                "traffic_state_count": int,
                "approach_state_count": int,
            }
        """

        if not states:
            return {
                "traffic_states": [],
                "approaches": [],
                "traffic_state_count": 0,
                "approach_state_count": 0,
            }

        supabase = get_supabase()

        # ========================================================
        # STEP 1
        # RESOLVE INTERSECTION IDs
        # ========================================================

        intersection_cache: dict[str, int] = {}

        for state in states:

            intersection_id = state.intersectionId

            if intersection_id not in intersection_cache:

                intersection_cache[intersection_id] = (
                    self.get_intersection_row_id(
                        intersection_id
                    )
                )

        # ========================================================
        # STEP 2
        # PREPARE TRAFFIC STATE ROWS
        # ========================================================

        traffic_state_payloads: list[dict[str, Any]] = []

        for state in states:

            intersection_row_id = intersection_cache[
                state.intersectionId
            ]

            traffic_state_payloads.append(
                {
                    "intersectionId": intersection_row_id,
                    "windowStart": state.windowStart.isoformat(),
                    "windowEnd": state.windowEnd.isoformat(),
                    "source": source,
                    "processingJobId": processing_job_id,
                }
            )

        # ========================================================
        # STEP 3
        # BULK UPSERT TRAFFIC STATES
        # ========================================================

        try:
            traffic_state_result = (
                supabase
                .table("trafficStates")
                .upsert(
                    traffic_state_payloads,
                    on_conflict=(
                        "intersectionId,"
                        "windowStart,"
                        "windowEnd"
                    ),
                )
                .execute()
            )
        except APIError as exc:
            if "42P10" in str(exc):
                return self._save_states_without_conflict_target(
                    states,
                    source=source,
                    processing_job_id=processing_job_id,
                )
            raise

        if not traffic_state_result.data:
            raise TrafficRepositoryError(
                "Bulk upsert trafficStates gagal."
            )

        saved_traffic_states = traffic_state_result.data

        # ========================================================
        # STEP 4
        # BUILD LOOKUP TRAFFIC STATE ID
        # ========================================================

        traffic_state_id_cache: dict[
            tuple[int, str, str],
            int,
        ] = {}

        for row in saved_traffic_states:

            key = (
                int(row["intersectionId"]),
                str(row["windowStart"]),
                str(row["windowEnd"]),
            )

            traffic_state_id_cache[key] = int(
                row["id"]
            )

        # ========================================================
        # STEP 5
        # RESOLVE APPROACH IDs
        # ========================================================

        approach_cache: dict[
            tuple[int, str],
            int,
        ] = {}

        for state in states:

            intersection_row_id = intersection_cache[
                state.intersectionId
            ]

            for approach_state in state.approaches:

                cache_key = (
                    intersection_row_id,
                    approach_state.approach,
                )

                if cache_key not in approach_cache:

                    approach_cache[cache_key] = (
                        self.get_approach_row_id(
                            intersection_row_id=(
                                intersection_row_id
                            ),
                            approach=(
                                approach_state.approach
                            ),
                        )
                    )

        # ========================================================
        # STEP 6
        # PREPARE APPROACH ROWS
        # ========================================================

        approach_payloads: list[dict[str, Any]] = []

        for state in states:

            intersection_row_id = intersection_cache[
                state.intersectionId
            ]

            traffic_state_key = (
                intersection_row_id,
                state.windowStart.isoformat(),
                state.windowEnd.isoformat(),
            )

            traffic_state_id = traffic_state_id_cache.get(
                traffic_state_key
            )

            if traffic_state_id is None:
                raise TrafficRepositoryError(
                    (
                        "TrafficState ID tidak ditemukan "
                        f"untuk intersection "
                        f"'{state.intersectionId}', "
                        f"window "
                        f"{state.windowStart.isoformat()}."
                    )
                )

            for approach_state in state.approaches:

                approach_id = approach_cache[
                    (
                        intersection_row_id,
                        approach_state.approach,
                    )
                ]

                approach_payloads.append(
                    {
                        "trafficStateId": traffic_state_id,
                        "approachId": approach_id,
                        "approach": approach_state.approach,
                        "volume": approach_state.volume,
                        "carCount": approach_state.carCount,
                        "motorcycleCount": (
                            approach_state.motorcycleCount
                        ),
                        "busCount": approach_state.busCount,
                        "truckCount": approach_state.truckCount,
                        "queueLengthVeh": (
                            approach_state.queueLengthVeh
                        ),
                        "queueLengthMEst": (
                            approach_state.queueLengthMEst
                        ),
                        "densityIndex": (
                            approach_state.densityIndex
                        ),
                        "avgSpeedKmh": (
                            approach_state.avgSpeedKmh
                        ),
                    }
                )

        # ========================================================
        # STEP 7
        # BULK UPSERT APPROACH STATES
        # ========================================================

        try:
            approach_result = (
                supabase
                .table("trafficApproachStates")
                .upsert(
                    approach_payloads,
                    on_conflict=(
                        "trafficStateId,"
                        "approachId"
                    ),
                )
                .execute()
            )
        except APIError as exc:
            if "42P10" in str(exc):
                return self._save_states_without_conflict_target(
                    states,
                    source=source,
                    processing_job_id=processing_job_id,
                )
            raise

        if not approach_result.data:
            raise TrafficRepositoryError(
                "Bulk upsert trafficApproachStates gagal."
            )

        saved_approaches = approach_result.data

        # ========================================================
        # STEP 8
        # RETURN RESULT
        # ========================================================

        return {
            "traffic_states": saved_traffic_states,
            "approaches": saved_approaches,
            "traffic_state_count": len(
                saved_traffic_states
            ),
            "approach_state_count": len(
                saved_approaches
            ),
        }

    # ============================================================
    # SAVE MANY STATES
    # ============================================================

    def save_traffic_states(
        self,
        states: list[TrafficState],
        *,
        source: str = "cv",
        processing_job_id: int | None = None,
    ) -> int:
        """
        Menyimpan banyak TrafficState menggunakan
        bulk upsert.

        Return:
            jumlah TrafficState yang berhasil diproses.
        """

        result = self.bulk_upsert_traffic_states(
            states,
            source=source,
            processing_job_id=processing_job_id,
        )

        return int(
            result["traffic_state_count"]
        )

    # ============================================================
    # GET LATEST TRAFFIC STATES
    # ============================================================

    def get_latest_traffic_states(
        self,
        *,
        intersection_row_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Mengambil traffic state terbaru untuk satu intersection."""

        if limit <= 0:
            raise ValueError("limit harus lebih besar dari 0.")

        supabase = get_supabase()

        result = (
            supabase
            .table("trafficStates")
            .select("*")
            .eq("intersectionId", intersection_row_id)
            .order("windowStart", desc=True)
            .limit(limit)
            .execute()
        )

        if result is None:
            return []

        return result.data or []

    # ============================================================
    # GET APPROACH STATES
    # ============================================================

    def get_approach_states(
        self,
        *,
        traffic_state_id: int,
    ) -> list[dict[str, Any]]:
        """Mengambil seluruh approach state dari satu traffic state."""

        supabase = get_supabase()

        result = (
            supabase
            .table("trafficApproachStates")
            .select("*")
            .eq("trafficStateId", traffic_state_id)
            .order("approachId")
            .execute()
        )

        if result is None:
            return []

        return result.data or []

    # ============================================================
    # GET TRAFFIC STATE WITH APPROACHES
    # ============================================================

    def get_traffic_state_with_approaches(
        self,
        *,
        traffic_state_id: int,
    ) -> dict[str, Any] | None:
        """Mengambil satu traffic state lengkap beserta approach state."""

        supabase = get_supabase()

        traffic_result = (
            supabase
            .table("trafficStates")
            .select("*")
            .eq("id", traffic_state_id)
            .maybe_single()
            .execute()
        )

        if traffic_result is None or not traffic_result.data:
            return None

        return {
            "trafficState": traffic_result.data,
            "approaches": self.get_approach_states(
                traffic_state_id=traffic_state_id
            ),
        }

    # ============================================================
    # GET LATEST COMPLETE TRAFFIC STATES
    # ============================================================

    def get_latest_complete_traffic_states(
        self,
        *,
        intersection_row_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Mengambil traffic state terbaru beserta seluruh approach-nya."""

        traffic_states = self.get_latest_traffic_states(
            intersection_row_id=intersection_row_id,
            limit=limit,
        )

        approach_result = (
            get_supabase()
            .table("approaches")
            .select("id, approach")
            .eq("intersectionId", intersection_row_id)
            .order("id")
            .execute()
        )
        intersection_approaches = (
            approach_result.data
            if approach_result is not None
            else []
        ) or []

        result: list[dict[str, Any]] = []

        for traffic_state in traffic_states:
            traffic_state_id = int(traffic_state["id"])

            approaches = self.get_approach_states(
                traffic_state_id=traffic_state_id
            )
            existing_approaches = {
                approach["approach"]
                for approach in approaches
            }

            for intersection_approach in intersection_approaches:
                approach_name = intersection_approach["approach"]

                if approach_name in existing_approaches:
                    continue

                approaches.append(
                    {
                        "trafficStateId": traffic_state_id,
                        "approachId": intersection_approach["id"],
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
                )

            approaches.sort(
                key=lambda approach: approach["approachId"]
            )

            result.append(
                {
                    "trafficState": traffic_state,
                    "approaches": approaches,
                }
            )

        return result