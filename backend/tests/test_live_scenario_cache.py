from datetime import datetime, timedelta, timezone

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
