from sqlalchemy import text

from app.db.database import engine


def test_database_connection():
    """
    Memastikan backend berhasil terhubung
    ke PostgreSQL Supabase.
    """

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1")
        )

        value = result.scalar()

    assert value == 1