from __future__ import annotations

from datetime import datetime
from sqlalchemy import Float, Integer
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TrafficStateModel(Base):
    __tablename__ = "trafficStates"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    intersectionId: Mapped[int] = mapped_column(
        ForeignKey(
            "intersections.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    windowStart: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    windowEnd: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

class ApproachStateModel(Base):
    __tablename__ = "approachStates"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    trafficStateId: Mapped[int] = mapped_column(
        ForeignKey(
            "trafficStates.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    approachId: Mapped[int] = mapped_column(
        ForeignKey(
            "approaches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    volume: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    carCount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    motorcycleCount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    busCount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    truckCount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    queueLengthVeh: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    queueLengthMEst: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
    )

    densityIndex: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0,
    )

    avgSpeedKmh: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )