from __future__ import annotations

from typing import Any

from app.services.traffic_repository import (
    TrafficRepository,
    TrafficRepositoryError,
)


class TrafficServiceError(Exception):
    """
    Error khusus untuk traffic service.
    """

    pass


class TrafficService:
    """
    Business logic untuk membaca traffic data.

    Service ini menjadi penghubung antara:

        API
         ↓
        TrafficService
         ↓
        TrafficRepository
         ↓
        Supabase
    """

    def __init__(
        self,
        repository: TrafficRepository | None = None,
    ) -> None:
        self.repository = (
            repository
            if repository is not None
            else TrafficRepository()
        )

    # ========================================================
    # GET INTERSECTION DATABASE ID
    # ========================================================

    def get_intersection_row_id(
        self,
        intersection_id: str,
    ) -> int:
        """
        Mengubah business ID intersection
        menjadi database primary key.
        """

        try:
            return self.repository.get_intersection_row_id(
                intersection_id
            )

        except TrafficRepositoryError as exc:
            raise TrafficServiceError(
                str(exc)
            ) from exc

    # ========================================================
    # GET LATEST TRAFFIC
    # ========================================================

    def get_latest_traffic(
        self,
        *,
        intersection_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Mengambil traffic state terbaru
        beserta approach states.
        """

        if not intersection_id.strip():
            raise TrafficServiceError(
                "intersection_id tidak boleh kosong."
            )

        if limit <= 0:
            raise TrafficServiceError(
                "limit harus lebih besar dari 0."
            )

        if limit > 100:
            raise TrafficServiceError(
                "limit maksimal adalah 100."
            )

        try:
            intersection_row_id = (
                self.repository.get_intersection_row_id(
                    intersection_id
                )
            )

            return (
                self.repository
                .get_latest_complete_traffic_states(
                    intersection_row_id=intersection_row_id,
                    limit=limit,
                )
            )

        except TrafficRepositoryError as exc:
            raise TrafficServiceError(
                str(exc)
            ) from exc

    # ========================================================
    # GET ONE TRAFFIC STATE
    # ========================================================

    def get_traffic_state(
        self,
        *,
        intersection_id: str,
        traffic_state_id: int,
    ) -> dict[str, Any] | None:
        """
        Mengambil satu traffic state lengkap.
        """

        if not intersection_id.strip():
            raise TrafficServiceError(
                "intersection_id tidak boleh kosong."
            )

        if traffic_state_id <= 0:
            raise TrafficServiceError(
                "traffic_state_id tidak valid."
            )

        try:
            intersection_row_id = (
                self.repository.get_intersection_row_id(
                    intersection_id
                )
            )

            traffic_state = (
                self.repository
                .get_traffic_state_with_approaches(
                    traffic_state_id=traffic_state_id
                )
            )

            if traffic_state is None:
                return None

            database_intersection_id = int(
                traffic_state["trafficState"][
                    "intersectionId"
                ]
            )

            if (
                database_intersection_id
                != intersection_row_id
            ):
                return None

            return traffic_state

        except TrafficRepositoryError as exc:
            raise TrafficServiceError(
                str(exc)
            ) from exc