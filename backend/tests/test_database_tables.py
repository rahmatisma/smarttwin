from sqlalchemy import inspect

from app.db.database import engine


EXPECTED_TABLES = {
    "intersections",
    "approaches",
    "lanes",
    "cameras",
    "videoUploads",
    "trafficStates",
    "approachStates",
    "signalStatuses",
    "forecasts",
    "forecastPredictions",
    "recommendations",
    "simulationRuns",
    "simulationMetrics",
}


def test_database_tables_exist():
    """
    Memastikan semua tabel utama SmartTwin
    sudah tersedia di PostgreSQL Supabase.
    """

    inspector = inspect(engine)

    tables = set(
        inspector.get_table_names()
    )

    missing_tables = (
        EXPECTED_TABLES - tables
    )

    assert not missing_tables, (
        "Tabel berikut belum tersedia: "
        f"{sorted(missing_tables)}"
    )