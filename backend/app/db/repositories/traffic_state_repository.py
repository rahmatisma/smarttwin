from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Approach,
    ApproachStateModel,
    Intersection,
    TrafficStateModel,
)
from app.schemas.traffic import TrafficState


class TrafficStateRepository:

    def __init__(self, db: Session):
        self.db = db

    def save_state(
        self,
        state: TrafficState,
    ) -> TrafficStateModel:

        # ====================================================
        # FIND INTERSECTION
        # ====================================================

        intersection_statement = select(
            Intersection
        ).where(
            Intersection.intersectionId
            == state.intersectionId
        )

        intersection = self.db.execute(
            intersection_statement
        ).scalar_one_or_none()

        if intersection is None:
            raise ValueError(
                "Intersection tidak ditemukan: "
                f"{state.intersectionId}"
            )

        # ====================================================
        # PREVENT DUPLICATE TRAFFIC STATE
        # ====================================================

        existing_statement = select(
            TrafficStateModel
        ).where(
            TrafficStateModel.intersectionId
            == intersection.id,
            TrafficStateModel.windowStart
            == state.windowStart,
            TrafficStateModel.windowEnd
            == state.windowEnd,
        )

        existing = self.db.execute(
            existing_statement
        ).scalar_one_or_none()

        if existing is not None:
            return existing

        # ====================================================
        # CREATE TRAFFIC STATE
        # ====================================================

        traffic_state = TrafficStateModel(
            intersectionId=intersection.id,
            windowStart=state.windowStart,
            windowEnd=state.windowEnd,
        )

        self.db.add(traffic_state)

        self.db.flush()

        # ====================================================
        # APPROACH STATES
        # ====================================================

        for approach_state in state.approaches:

            approach_statement = select(
                Approach
            ).where(
                Approach.intersectionId
                == intersection.id,
                Approach.approach
                == approach_state.approach,
            )

            approach = self.db.execute(
                approach_statement
            ).scalar_one_or_none()

            if approach is None:
                raise ValueError(
                    "Approach tidak ditemukan: "
                    f"{approach_state.approach}"
                )

            db_approach_state = (
                ApproachStateModel(
                    trafficStateId=traffic_state.id,
                    approachId=approach.id,
                    volume=approach_state.volume,
                    carCount=approach_state.carCount,
                    motorcycleCount=(
                        approach_state.motorcycleCount
                    ),
                    busCount=approach_state.busCount,
                    truckCount=approach_state.truckCount,
                    queueLengthVeh=(
                        approach_state.queueLengthVeh
                    ),
                    queueLengthMEst=(
                        approach_state.queueLengthMEst
                    ),
                    densityIndex=(
                        approach_state.densityIndex
                    ),
                    avgSpeedKmh=(
                        approach_state.avgSpeedKmh
                    ),
                )
            )

            self.db.add(
                db_approach_state
            )

        self.db.commit()

        self.db.refresh(
            traffic_state
        )

        return traffic_state