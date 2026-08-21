from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Approach(Base):
    __tablename__ = "approaches"

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

    approach: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    sortOrder: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    isActive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )