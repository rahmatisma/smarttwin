from __future__ import annotations

from pathlib import Path

from app.schemas.traffic import (
    ApproachState,
    TrafficState,
)
from app.services.traffic_service import TrafficService


# ============================================================
# CSV PATH
# ============================================================

def get_csv_path() -> Path:
    """
    Mengambil CSV asli hasil Computer Vision.

    Struktur:

    smarttwin/
    ├── backend/
    │   ├── app/
    │   └── tests/
    │       └── test_traffic_service.py
    │
    └── cv/
        └── output/
            └── smarttwin_traffic_data.csv
    """

    project_root = (
        Path(__file__)
        .resolve()
        .parents[2]
    )

    return (
        project_root
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )


# ============================================================
# TEST 1
# ============================================================

def test_csv_exists():
    """
    Memastikan CSV asli CV tersedia.
    """

    csv_path = get_csv_path()

    assert csv_path.exists(), (
        f"CSV traffic tidak ditemukan: {csv_path}"
    )


# ============================================================
# TEST 2
# ============================================================

def test_get_latest_state():
    """
    Memastikan TrafficService mengambil TrafficState
    terbaru dari CSV asli.
    """

    csv_path = get_csv_path()

    assert csv_path.exists(), (
        f"CSV traffic tidak ditemukan: {csv_path}"
    )

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    # --------------------------------------------------------
    # State harus tersedia.
    # --------------------------------------------------------

    assert state is not None

    # --------------------------------------------------------
    # Return harus berupa TrafficState.
    # --------------------------------------------------------

    assert isinstance(
        state,
        TrafficState,
    )

    # --------------------------------------------------------
    # Intersection
    # --------------------------------------------------------

    assert state.intersectionId == (
        "simpang4-pingit"
    )

    # --------------------------------------------------------
    # Window
    # --------------------------------------------------------

    assert (
        state.windowStart
        < state.windowEnd
    )

    # --------------------------------------------------------
    # APPROACHES adalah LIST.
    #
    # BUKAN:
    #
    #     state.approaches == 4
    #
    # Yang benar:
    #
    #     len(state.approaches) == 4
    # --------------------------------------------------------

    assert len(state.approaches) == 4


# ============================================================
# TEST 3
# ============================================================

def test_get_latest_state_has_four_approaches():
    """
    Memastikan empat approach selalu tersedia:

        north
        south
        east
        west
    """

    service = TrafficService(
        csv_path=get_csv_path(),
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    actual = {
        approach.approach
        for approach in state.approaches
    }

    expected = {
        "north",
        "south",
        "east",
        "west",
    }

    assert actual == expected


# ============================================================
# TEST 4
# ============================================================

def test_approach_objects_follow_contract():
    """
    Memastikan setiap item approaches merupakan
    ApproachState.
    """

    service = TrafficService(
        csv_path=get_csv_path(),
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    for approach in state.approaches:

        assert isinstance(
            approach,
            ApproachState,
        )


# ============================================================
# TEST 5
# ============================================================

def test_approach_metrics_are_non_negative():
    """
    Semua metric traffic tidak boleh negatif.
    """

    service = TrafficService(
        csv_path=get_csv_path(),
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    for approach in state.approaches:

        assert approach.volume >= 0

        assert approach.carCount >= 0

        assert approach.motorcycleCount >= 0

        assert approach.busCount >= 0

        assert approach.truckCount >= 0

        assert approach.queueLengthVeh >= 0

        assert approach.queueLengthMEst >= 0

        assert approach.densityIndex >= 0


# ============================================================
# TEST 6
# ============================================================

def test_vehicle_classification_matches_volume():
    """
    Volume harus konsisten dengan klasifikasi kendaraan.

    volume =
        carCount
        + motorcycleCount
        + busCount
        + truckCount
    """

    service = TrafficService(
        csv_path=get_csv_path(),
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    for approach in state.approaches:

        classification_total = (
            approach.carCount
            + approach.motorcycleCount
            + approach.busCount
            + approach.truckCount
        )

        assert approach.volume == (
            classification_total
        )


# ============================================================
# TEST 7
# ============================================================

def test_speed_is_none():
    """
    CSV CV belum menyediakan speed.

    Karena itu:

        avgSpeedKmh = None

    BUKAN 0.
    """

    service = TrafficService(
        csv_path=get_csv_path(),
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    for approach in state.approaches:

        assert approach.avgSpeedKmh is None


# ============================================================
# TEST 8
# ============================================================

def test_queue_values_are_valid():
    """
    Queue tidak boleh negatif.

    Saat ini kita menganggap queue pada CSV
    merupakan nilai per lane.

    Builder menggabungkan lane menjadi approach.
    """

    service = TrafficService(
        csv_path=get_csv_path(),
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    for approach in state.approaches:

        assert (
            approach.queueLengthVeh >= 0
        )

        assert (
            approach.queueLengthMEst >= 0
        )


# ============================================================
# TEST 9
# ============================================================

def test_density_is_valid():
    """
    densityIndex merupakan proxy lane occupancy.

    Bukan vehicles/km.
    """

    service = TrafficService(
        csv_path=get_csv_path(),
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    for approach in state.approaches:

        assert (
            approach.densityIndex >= 0
        )


# ============================================================
# TEST 10
# ============================================================

def test_latest_state_window_is_five_seconds():
    """
    Memastikan window TrafficService = 5 detik.
    """

    service = TrafficService(
        csv_path=get_csv_path(),
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    duration = (
        state.windowEnd
        - state.windowStart
    )

    assert duration.total_seconds() == 5