import sys
from pathlib import Path


SIMULATION_ROOT = Path(__file__).resolve().parents[1]
if str(SIMULATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMULATION_ROOT))

import scenario_worker as worker  # noqa: E402


def test_once_returns_nonzero_when_iteration_fails(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["scenario_worker.py", "--once"])
    monkeypatch.setattr(worker, "connectSupabase", lambda: object())

    def fail(_supabase, **_kwargs):
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr(worker, "evaluate_once", fail)
    assert worker.main() == 1


def test_once_returns_zero_after_cache_write(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["scenario_worker.py", "--once"])
    monkeypatch.setattr(worker, "connectSupabase", lambda: object())
    monkeypatch.setattr(
        worker,
        "evaluate_once",
        lambda _supabase, **_kwargs: {
            "updatedAt": "2026-08-27T00:00:00+00:00",
            "candidateId": "balanced",
            "los": "B",
        },
    )
    assert worker.main() == 0
