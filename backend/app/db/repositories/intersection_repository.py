from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Approach,
    Intersection,
    Lane,
)


class IntersectionRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_by_intersection_id(
        self,
        intersection_id: str,
    ) -> Intersection | None:

        statement = select(Intersection).where(
            Intersection.intersectionId
            == intersection_id
        )

        return self.db.execute(
            statement
        ).scalar_one_or_none()

    def create_intersection(
        self,
        intersection_id: str,
        name: str,
        latitude: float | None = None,
        longitude: float | None = None,
        description: str | None = None,
    ) -> Intersection:

        intersection = Intersection(
            intersectionId=intersection_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            description=description,
            isActive=True,
        )

        self.db.add(intersection)
        self.db.commit()
        self.db.refresh(intersection)

        return intersection

    def create_approach(
        self,
        intersection_db_id: int,
        approach: str,
        name: str | None = None,
        sort_order: int = 0,
    ) -> Approach:

        item = Approach(
            intersectionId=intersection_db_id,
            approach=approach,
            name=name,
            sortOrder=sort_order,
            isActive=True,
        )

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        return item

    def create_lane(
        self,
        approach_db_id: int,
        lane_id: str,
        lane_name: str | None = None,
        lane_index: int | None = None,
    ) -> Lane:

        lane = Lane(
            approachId=approach_db_id,
            laneId=lane_id,
            laneName=lane_name,
            laneIndex=lane_index,
            isActive=True,
        )

        self.db.add(lane)
        self.db.commit()
        self.db.refresh(lane)

        return lane