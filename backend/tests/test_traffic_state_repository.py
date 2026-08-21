from datetime import datetime

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import (
    ApproachStateModel,
    TrafficStateModel,
)
from app.repositories.traffic_state_repository import (
    TrafficStateRepository,
)
from app.schemas.traffic import (
    ApproachState,
    TrafficState,
)


def test_save_traffic_state():

    db = SessionLocal()

    try:
        state = TrafficState(
            intersectionId="simpang4-pingit",
            windowStart=datetime(
                2026,
                8,
                15,
                16,
                30,
                10,
            ),
            windowEnd=datetime(
                2026,
                8,
                15,
                16,
                30,
                15,
            ),
            approaches=[
                ApproachState(
                    approach="north",
                    volume=10,
                    carCount=5,
                    motorcycleCount=3,
                    busCount=1,
                    truckCount=1,
                    queueLengthVeh=5,
                    queueLengthMEst=12.5,
                    densityIndex=25.0,
                    avgSpeedKmh=None,
                ),
                ApproachState(
                    approach="south",
                    volume=0,
                    carCount=0,
                    motorcycleCount=0,
                    busCount=0,
                    truckCount=0,
                    queueLengthVeh=0,
                    queueLengthMEst=0,
                    densityIndex=0,
                    avgSpeedKmh=None,
                ),
                ApproachState(
                    approach="east",
                    volume=0,
                    carCount=0,
                    motorcycleCount=0,
                    busCount=0,
                    truckCount=0,
                    queueLengthVeh=0,
                    queueLengthMEst=0,
                    densityIndex=0,
                    avgSpeedKmh=None,
                ),
                ApproachState(
                    approach="west",
                    volume=0,
                    carCount=0,
                    motorcycleCount=0,
                    busCount=0,
                    truckCount=0,
                    queueLengthVeh=0,
                    queueLengthMEst=0,
                    densityIndex=0,
                    avgSpeedKmh=None,
                ),
            ],
        )

        repository = TrafficStateRepository(db)

        saved = repository.save_state(
            state
        )

        assert saved.id is not None

        # Verify parent
        parent = db.execute(
            select(TrafficStateModel).where(
                TrafficStateModel.id
                == saved.id
            )
        ).scalar_one()

        assert (
            parent.intersectionId
            is not None
        )

        # Verify children
        children = db.execute(
            select(ApproachStateModel).where(
                ApproachStateModel.trafficStateId
                == saved.id
            )
        ).scalars().all()

        assert len(children) == 4

    finally:
        db.close()