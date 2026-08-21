from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Lane(Base):
    __tablename__ = "lanes"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    approachId: Mapped[int] = mapped_column(
        ForeignKey(
            "approaches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    laneId: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    laneName: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    laneIndex: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    isActive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )