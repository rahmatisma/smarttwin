from datetime import datetime, timedelta, timezone
import threading
from concurrent.futures import ThreadPoolExecutor

from app.services.live_scenario_cache_service import LiveScenarioCacheService


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, data):
        self.data = data

    def select(self, *_args): return self
    def eq(self, *_args): return self
    def limit(self, *_args): return self
    def execute(self): return _Response(self.data)


class _Supabase:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    def table(self, _name):
        if self.error:
            raise self.error
        return _Query(self.data)


def _valid_row(updated_at=None):
    return {
        "intersectionId": "simpang4-pingit",
        "updatedAt": updated_at or datetime.now(timezone.utc).isoformat(),
        "recommendation": {
            "recommendedPhase": "south",
            "recommendedGreenSeconds": 22,
            "currentGreenSeconds": 15,
            "currentPhase": "south",
        },
        "avgDelaySeconds": 13.37,
        "avgQueueLengthM": 35.0,
        "throughputVeh": 9,
        "los": "B",
        "candidateId": "balanced",
    }


def test_returns_fresh_cache_row():
    row = _valid_row()
    service = LiveScenarioCacheService(_Supabase([row]), max_age_seconds=120)
    assert service.get_fresh("simpang4-pingit") == row


def test_stale_cache_is_ignored():
    row = _valid_row(
        (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
    )
    service = LiveScenarioCacheService(_Supabase([row]), max_age_seconds=120)
    assert service.get_fresh("simpang4-pingit") is None


def test_database_error_is_safe_cache_miss():
    service = LiveScenarioCacheService(_Supabase(error=RuntimeError("offline")))
    assert service.get_fresh("simpang4-pingit") is None


def test_empty_cache_is_safe_cache_miss():
    service = LiveScenarioCacheService(_Supabase([]))
    assert service.get_fresh("simpang4-pingit") is None


def test_corrupt_cache_is_safe_cache_miss():
    row = _valid_row()
    row["recommendation"] = {"recommendedPhase": "south"}
    service = LiveScenarioCacheService(_Supabase([row]))
    assert service.get_fresh("simpang4-pingit") is None


def test_corrupt_full_cycle_is_safe_cache_miss():
    row = _valid_row()
    row["recommendation"]["cyclePlan"] = {"phases": "not-a-list"}
    service = LiveScenarioCacheService(_Supabase([row]))
    assert service.get_fresh("simpang4-pingit") is None


def test_cached_row_is_reused_but_not_beyond_its_data_expiry(monkeypatch):
    row = _valid_row()
    service = LiveScenarioCacheService(_Supabase([row]))
    assert service.get_fresh("simpang4-pingit") == row
    monkeypatch.setattr(service._supabase, "table", lambda _: (_ for _ in ()).throw(AssertionError("duplicate query")))
    assert service.get_fresh("simpang4-pingit") == row
    row["updatedAt"] = (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
    assert service.get_fresh("simpang4-pingit") is None


def test_failed_database_is_not_retried_on_every_poll_and_can_recover(monkeypatch):
    from app.services import live_scenario_cache_service as module
    clock = [0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    database = _Supabase(error=RuntimeError("offline"))
    service = LiveScenarioCacheService(database)
    assert service.get_fresh("simpang4-pingit") is None
    database.error = None
    database.data = [_valid_row()]
    clock[0] = 5
    assert service.get_fresh("simpang4-pingit") is None
    clock[0] = 16
    assert service.get_fresh("simpang4-pingit") == database.data[0]


def test_concurrent_requests_do_not_wait_for_or_duplicate_a_slow_database(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    calls = []
    service = LiveScenarioCacheService(_Supabase())
    def load(intersection):
        calls.append(intersection)
        started.set()
        assert release.wait(timeout=3)
        return _valid_row()
    monkeypatch.setattr(service, "_load_fresh", load)
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(service.get_fresh, "simpang4-pingit")
        try:
            assert started.wait(timeout=3)
            assert service.get_fresh("simpang4-pingit") is None
            assert calls == ["simpang4-pingit"]
        finally:
            release.set()
        assert request.result(timeout=3) is not None


def test_optional_cache_uses_its_own_short_database_timeout(monkeypatch):
    from app.services import supabase_client
    options = []
    monkeypatch.setattr(supabase_client, "_create_supabase", lambda option=None: options.append(option) or object())
    supabase_client.get_scenario_cache_supabase.cache_clear()
    supabase_client.get_supabase.cache_clear()
    try:
        supabase_client.get_scenario_cache_supabase()
        supabase_client.get_supabase()
        assert options[0].postgrest_client_timeout == 3
        assert options[1] is None
    finally:
        supabase_client.get_scenario_cache_supabase.cache_clear()
        supabase_client.get_supabase.cache_clear()
