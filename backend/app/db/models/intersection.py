from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Intersection(Base):
    __tablename__ = "intersections"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    intersectionId: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
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

    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )