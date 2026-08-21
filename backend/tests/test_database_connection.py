from app.services.supabase_client import get_supabase


def test_database_connection():
    """
    Memastikan backend berhasil terhubung ke Supabase.
    """
    result = get_supabase().table("intersections").select("id").limit(1).execute()
    assert result is not None