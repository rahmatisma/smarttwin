import pytest

from app.services.supabase_client import get_supabase


pytestmark = pytest.mark.integration


EXPECTED_TABLES = {
    "approaches",
    "cameraVideos",
    "cameras",
    "cctvHistory",
    "cvProcessingJobs",
    "forecastPredictions",
    "forecasts",
    "intersections",
    "lanes",
    "recommendations",
    "signalPhases",
    "signalStatuses",
    "simulationMetrics",
    "simulations",
    "systemLogs",
    "trafficApproachStates",
    "trafficLaneMetrics",
    "trafficStates",
    "userSettings",
    "users",
}


def test_database_tables_exist():
    """
    Memastikan tabel utama SmartTwin tersedia
    di Supabase.
    """

    supabase = get_supabase()

    missing_tables = []

    for table_name in EXPECTED_TABLES:
        try:
            supabase.table(table_name).select("*").limit(1).execute()
        except Exception:
            missing_tables.append(table_name)

    assert not missing_tables, (
        "Tabel berikut tidak dapat diakses di Supabase: "
        f"{sorted(missing_tables)}"
    )
