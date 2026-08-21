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

    Struktur project:

    smarttwin/
    ├── backend/
    │   ├── app/
    │   └── tests/
    │       └── test_traffic_service.py
    │
    └── cv/
        └── output/
            └── smarttwin_traffic_data.csv

    Dari:
        backend/tests/

    naik:
        tests -> backend -> smarttwin

    lalu:
        cv/output/
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
    Memastikan CSV asli Computer Vision tersedia.

    Test ini sengaja tidak membuat dummy data.

    Traffic Service harus menggunakan:
        cv/output/smarttwin_traffic_data.csv
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
    Memastikan TrafficService dapat mengambil state
    terbaru dari CSV asli.

    Alur:

        CSV
          ↓
        TrafficStateBuilder
          ↓
        TrafficService
          ↓
        TrafficState
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
    # Return value harus object TrafficState.
    #
    # BUKAN dictionary.
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
    # Harus mempunyai 4 approach.
    # --------------------------------------------------------

    assert len(state.approaches) == 4

    approach_names = {
        approach.approach
        for approach in state.approaches
    }

    assert approach_names == {
        "north",
        "south",
        "east",
        "west",
    }


# ============================================================
# TEST 3
# ============================================================

def test_latest_state_contains_valid_approach_state():
    """
    Memastikan setiap approach yang dikembalikan oleh
    TrafficService benar-benar merupakan ApproachState
    sesuai contract terbaru.
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None
    assert isinstance(state, TrafficState)

    for approach in state.approaches:

        assert isinstance(
            approach,
            ApproachState,
        )

        # ----------------------------------------------------
        # Approach name
        # ----------------------------------------------------

        assert approach.approach in {
            "north",
            "south",
            "east",
            "west",
        }

        # ----------------------------------------------------
        # Semua metric tidak boleh negatif.
        # ----------------------------------------------------

        assert approach.volume >= 0

        assert approach.carCount >= 0

        assert approach.motorcycleCount >= 0

        assert approach.busCount >= 0

        assert approach.truckCount >= 0

        assert approach.queueLengthVeh >= 0

        assert approach.queueLengthMEst >= 0

        assert approach.densityIndex >= 0

        # ----------------------------------------------------
        # Speed belum tersedia dari CSV.
        #
        # HARUS None.
        #
        # Jangan diubah menjadi 0.
        # ----------------------------------------------------

        assert approach.avgSpeedKmh is None


# ============================================================
# TEST 4
# ============================================================

def test_latest_state_vehicle_classification_consistent():
    """
    Memastikan volume konsisten dengan klasifikasi kendaraan.

    Contract:

        volume
        =
        carCount
        + motorcycleCount
        + busCount
        + truckCount

    Catatan:

    vehicle_count pada CSV berasal dari kendaraan yang
    melewati counting line, bukan sekadar kendaraan yang
    terlihat pada frame.

    Traffic State Builder kemudian mengagregasikan nilai
    tersebut dari lane -> approach.
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
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

        assert (
            approach.volume
            == classification_total
        )


# ============================================================
# TEST 5
# ============================================================

def test_latest_state_queue_values_valid():
    """
    Memastikan queue pada state terbaru valid.

    Berdasarkan keputusan tim saat ini:

        queue_length_veh
            = queue per lane

        queue_length_m_est
            = queue length meter per lane

    Traffic State Builder menjumlahkan nilai antar-lane
    menjadi nilai queue pada approach.

    Contoh:

        north
        ├── lane_1 → queue 2 veh
        ├── lane_2 → queue 3 veh
        └── lane_3 → queue 1 veh

        hasil approach:

        queueLengthVeh = 6
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
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
# TEST 6
# ============================================================

def test_latest_state_density_valid():
    """
    Memastikan densityIndex valid.

    densityIndex merupakan proxy lane occupancy,
    bukan kendaraan/km.

    Pada level approach, builder menggunakan agregasi
    dari nilai density per lane.
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    for approach in state.approaches:

        assert (
            approach.densityIndex >= 0
        )


# ============================================================
# TEST 7
# ============================================================

def test_latest_state_speed_is_none():
    """
    Memastikan avgSpeedKmh tetap None.

    CSV Computer Vision saat ini tidak mempunyai
    data kecepatan.

    None berarti:

        "data speed belum tersedia"

    dan BUKAN:

        0 km/h
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    for approach in state.approaches:

        assert approach.avgSpeedKmh is None


# ============================================================
# TEST 8
# ============================================================

def test_latest_state_window_is_five_seconds():
    """
    Memastikan TrafficService menggunakan window 5 detik.
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    duration = (
        state.windowEnd
        - state.windowStart
    )

    assert duration.total_seconds() == 5


# ============================================================
# TEST 9
# ============================================================

def test_latest_state_has_all_four_approaches():
    """
    TrafficState harus selalu mempunyai:

        north
        south
        east
        west

    Walaupun salah satu approach pada window tersebut
    tidak memiliki kendaraan yang terdeteksi.
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    expected = {
        "north",
        "south",
        "east",
        "west",
    }

    actual = {
        approach.approach
        for approach in state.approaches
    }

    assert actual == expected


# ============================================================
# TEST 10
# ============================================================

def test_latest_state_window_is_valid():
    """
    Memastikan window state terbaru mempunyai
    timestamp yang valid.
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    assert state.windowStart is not None

    assert state.windowEnd is not None

    assert (
        state.windowStart
        < state.windowEnd
    )


# ============================================================
# TEST 11
# ============================================================

def test_latest_state_is_latest_window():
    """
    Memastikan get_latest_state() benar-benar mengambil
    TrafficState terakhir berdasarkan windowStart.

    Ini penting karena CSV berisi banyak time window.
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    # Ambil seluruh state dari builder/service.
    states = service.builder.build_from_csv(
        csv_path
    )

    assert len(states) > 0

    expected_latest = states[-1]

    assert state.windowStart == (
        expected_latest.windowStart
    )

    assert state.windowEnd == (
        expected_latest.windowEnd
    )


# ============================================================
# TEST 12
# ============================================================

def test_latest_state_schema_matches_contract():
    """
    Validasi ringkas terhadap struktur contract terbaru.

    TrafficState:

        intersectionId
        windowStart
        windowEnd
        approaches

    ApproachState:

        approach
        volume
        carCount
        motorcycleCount
        busCount
        truckCount
        queueLengthVeh
        queueLengthMEst
        densityIndex
        avgSpeedKmh
    """

    csv_path = get_csv_path()

    service = TrafficService(
        csv_path=csv_path,
        window_seconds=5,
    )

    state = service.get_latest_state()

    assert state is not None

    # --------------------------------------------------------
    # TrafficState
    # --------------------------------------------------------

    assert hasattr(
        state,
        "intersectionId",
    )

    assert hasattr(
        state,
        "windowStart",
    )

    assert hasattr(
        state,
        "windowEnd",
    )

    assert hasattr(
        state,
        "approaches",
    )

    # --------------------------------------------------------
    # ApproachState
    # --------------------------------------------------------

    for approach in state.approaches:

        assert hasattr(
            approach,
            "approach",
        )

        assert hasattr(
            approach,
            "volume",
        )

        assert hasattr(
            approach,
            "carCount",
        )

        assert hasattr(
            approach,
            "motorcycleCount",
        )

        assert hasattr(
            approach,
            "busCount",
        )

        assert hasattr(
            approach,
            "truckCount",
        )

        assert hasattr(
            approach,
            "queueLengthVeh",
        )

        assert hasattr(
            approach,
            "queueLengthMEst",
        )

        assert hasattr(
            approach,
            "densityIndex",
        )

        assert hasattr(
            approach,
            "avgSpeedKmh",
        )