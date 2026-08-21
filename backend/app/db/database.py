from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


# ============================================================
# DATABASE ENGINE
# ============================================================

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)


# ============================================================
# SESSION
# ============================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ============================================================
# BASE MODEL
# ============================================================

class Base(DeclarativeBase):
    pass


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

def get_db() -> Generator[Session, None, None]:
    """
    Dependency untuk FastAPI.

    Setiap request mendapatkan satu database session.
    Session selalu ditutup setelah request selesai.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()