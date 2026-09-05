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


def test_evaluate_once_feeds_averaged_state_to_pkji_not_single_window(monkeypatch):
    """Jalur live (bukan replay) harus mengirim hasil
    loadAveragedTrafficState() sebagai pkji_traffic_state -- BUKAN
    `state` (1 jendela) yang dipakai baseline. Ini regresi utama P-6b:
    tanpa ini, aggressive/balanced kembali sensitif ke 1 cuplikan 5
    detik dan halaman Riwayat kembali terlihat "sama semua".
    """
    single_window_state = object()
    averaged_state = object()
    captured = {}

    monkeypatch.setattr(worker, "loadTrafficState", lambda: single_window_state)
    monkeypatch.setattr(worker, "loadAveragedTrafficState", lambda: averaged_state)
    monkeypatch.setattr(
        worker, "ForecastClient", lambda: type("F", (), {"get_live_forecast": lambda self: None})()
    )

    def fake_evaluate_state(state, **kwargs):
        captured["state"] = state
        captured["pkji_traffic_state"] = kwargs.get("pkji_traffic_state")
        return {
            "recommendation": {"source": "scenario-generator"},
            "los": "B",
            "candidateId": "balanced",
        }

    monkeypatch.setattr(worker, "evaluate_state", fake_evaluate_state)
    monkeypatch.setattr(worker, "write_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "write_history", lambda *_args, **_kwargs: None)

    worker.evaluate_once(object(), full_cycle=True)

    assert captured["state"] is single_window_state
    assert captured["pkji_traffic_state"] is averaged_state
    assert captured["pkji_traffic_state"] is not captured["state"]


def test_evaluate_state_full_cycle_forwards_pkji_traffic_state(monkeypatch):
    """evaluate_state() harus meneruskan pkji_traffic_state ke
    recommend_full_cycle() saat full_cycle=True, dan TIDAK mengirimnya
    ke recommend() (jalur satu-lengan lama) saat full_cycle=False --
    recommend() tidak menerima parameter itu sama sekali."""
    captured = {}

    class _FakeCyclePlan:
        def model_dump(self, mode="json"):
            return {}

    class _FakeRecommendation:
        def model_dump(self, mode="json"):
            return {"source": "scenario-generator"}

    class _FakeEngine:
        last_winner = {
            "avgDelaySeconds": 10.0,
            "avgQueueLengthM": 20.0,
            "los": "B",
            "candidateId": "balanced",
            "throughputVeh": 5,
        }
        last_cycle_plan = _FakeCyclePlan()
        last_results: list = []

        def recommend_full_cycle(self, **kwargs):
            captured["full_cycle_kwargs"] = kwargs
            return _FakeRecommendation()

        def recommend(self, **kwargs):
            captured["recommend_kwargs"] = kwargs
            return _FakeRecommendation()

    monkeypatch.setattr(worker, "_make_engine", lambda *_a, **_k: _FakeEngine())

    sentinel_state = object()
    sentinel_pkji_state = object()
    worker.evaluate_state(
        sentinel_state,
        full_cycle=True,
        pkji_traffic_state=sentinel_pkji_state,
    )
    assert captured["full_cycle_kwargs"]["pkji_traffic_state"] is sentinel_pkji_state
    assert captured["full_cycle_kwargs"]["state"] is sentinel_state

    captured.clear()
    worker.evaluate_state(
        sentinel_state,
        full_cycle=False,
        pkji_traffic_state=sentinel_pkji_state,
    )
    assert "pkji_traffic_state" not in captured["recommend_kwargs"]


def test_evaluate_once_replay_mode_skips_averaging(monkeypatch):
    """Mode replay meloncat ke trafficStateId tertentu yang tidak selalu
    berurutan dengan 'window 2 menit terakhir' versi live -- sengaja
    tetap pakai state satu jendela (perilaku lama), bukan rata-rata."""
    replay_state = type(
        "S", (), {"windowStart": "t0", "windowEnd": "t1"}
    )()
    captured = {}

    class _FakeReplay:
        def next(self):
            return replay_state, 1, 538

    def fake_evaluate_state(state, **kwargs):
        captured["pkji_traffic_state"] = kwargs.get("pkji_traffic_state")
        return {
            "recommendation": {"source": "scenario-generator"},
            "los": "B",
            "candidateId": "balanced",
        }

    monkeypatch.setattr(worker, "evaluate_state", fake_evaluate_state)
    monkeypatch.setattr(worker, "write_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "write_history", lambda *_args, **_kwargs: None)

    worker.evaluate_once(object(), full_cycle=True, replay=_FakeReplay())

    assert captured["pkji_traffic_state"] is None
