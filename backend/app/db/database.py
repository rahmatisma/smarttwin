from collections.abc import Generator

from supabase import Client

from app.core.config import settings
from app.services.supabase_client import get_supabase


def get_db() -> Generator[Client, None, None]:
    """
    Dependency untuk FastAPI.

    Dependency kompatibilitas untuk route lama.

    Supabase client bersifat stateless dan di-cache oleh
    get_supabase(), jadi tidak perlu membuka atau menutup session.
    """
    yield get_supabase()