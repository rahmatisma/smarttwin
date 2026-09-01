import pytest

from app.services.supabase_client import get_supabase


pytestmark = pytest.mark.integration


def test_supabase_connection():
    supabase = get_supabase()

    result = (
        supabase
        .table("intersections")
        .select("*")
        .limit(1)
        .execute()
    )

    assert result is not None

    print("\nSupabase response:")
    print(result.data)
