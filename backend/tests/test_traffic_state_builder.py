from pathlib import Path

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)


def test_build_traffic_state_from_csv():
    """
    End-to-end test untuk Traffic State Builder.

    Struktur project:

    smarttwin/
    ├── backend/
    │   ├── app/
    │   └── tests/
    │       └── test_traffic_state_builder.py
    │
    └── cv/
        └── output/
            └── smarttwin_traffic_data.csv

    Builder membaca CSV CV lalu menghasilkan
    TrafficState dalam bentuk dictionary.
    """

    # =========================================================
    # CSV PATH
    # =========================================================

    project_root = Path(__file__).resolve().parents[2]

    csv_path = (
        project_root
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )

    assert csv_path.exists(), (
        f"CSV traffic tidak ditemukan: {csv_path}"
    )

    # =========================================================
    # BUILD
    # =========================================================

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            window_seconds=5
        )
    )

    states = builder.build_from_csv(csv_path)

    # Harus menghasilkan TrafficState.
    assert len(states) > 0

    # Builder saat ini mengembalikan dictionary.
    state = states[0]

    assert isinstance(state, dict)

    # =========================================================
    # TRAFFIC STATE
    # =========================================================

    assert state["intersectionId"] == "simpang4-pingit"

    assert "windowStart" in state
    assert "windowEnd" in state
    assert "approaches" in state

    assert state["windowStart"] is not None
    assert state["windowEnd"] is not None

    # Simpang 4 harus memiliki 4 approach.
    assert len(state["approaches"]) == 4

    approaches = {
        approach["approach"]
        for approach in state["approaches"]
    }

    assert approaches == {
        "north",
        "south",
        "east",
        "west",
    }

    # =========================================================
    # APPROACH STATE
    # =========================================================

    for approach in state["approaches"]:

        # -----------------------------------------------------
        # Field wajib sesuai data contract.
        # -----------------------------------------------------

        assert "approach" in approach
        assert "volume" in approach

        assert "carCount" in approach
        assert "motorcycleCount" in approach
        assert "busCount" in approach
        assert "truckCount" in approach

        assert "queueLengthVeh" in approach
        assert "queueLengthMEst" in approach

        assert "densityIndex" in approach
        assert "avgSpeedKmh" in approach

        # -----------------------------------------------------
        # Nilai tidak boleh negatif.
        # -----------------------------------------------------

        assert approach["volume"] >= 0

        assert approach["carCount"] >= 0
        assert approach["motorcycleCount"] >= 0
        assert approach["busCount"] >= 0
        assert approach["truckCount"] >= 0

        assert approach["queueLengthVeh"] >= 0
        assert approach["queueLengthMEst"] >= 0

        assert approach["densityIndex"] >= 0

        # -----------------------------------------------------
        # Volume harus sama dengan total vehicle class.
        #
        # volume =
        # car + motorcycle + bus + truck
        # -----------------------------------------------------

        expected_volume = (
            approach["carCount"]
            + approach["motorcycleCount"]
            + approach["busCount"]
            + approach["truckCount"]
        )

        assert approach["volume"] == expected_volume

        # -----------------------------------------------------
        # Speed belum tersedia dari CSV CV.
        #
        # Jadi harus None/null.
        #
        # JANGAN diganti menjadi 0.
        # -----------------------------------------------------

        assert approach["avgSpeedKmh"] is None


def test_traffic_state_has_expected_contract_fields():
    """
    Memastikan setiap TrafficState menggunakan
    nama field sesuai data contract.
    """

    project_root = Path(__file__).resolve().parents[2]

    csv_path = (
        project_root
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            window_seconds=5
        )
    )

    states = builder.build_from_csv(csv_path)

    assert len(states) > 0

    state = states[0]

    # Field TrafficState yang diperbolehkan.
    expected_state_fields = {
        "intersectionId",
        "windowStart",
        "windowEnd",
        "approaches",
    }

    assert set(state.keys()) == expected_state_fields


def test_approach_state_has_expected_contract_fields():
    """
    Memastikan ApproachState tidak kembali menggunakan
    nama field lama seperti:

    queueLengthM
    densityVehPerKm

    dan sudah menggunakan field baru:

    queueLengthVeh
    queueLengthMEst
    densityIndex
    """

    project_root = Path(__file__).resolve().parents[2]

    csv_path = (
        project_root
        / "cv"
        / "output"
        / "smarttwin_traffic_data.csv"
    )

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            window_seconds=5
        )
    )

    states = builder.build_from_csv(csv_path)

    assert len(states) > 0

    state = states[0]

    for approach in state["approaches"]:

        expected_fields = {
            "approach",
            "volume",
            "carCount",
            "motorcycleCount",
            "busCount",
            "truckCount",
            "queueLengthVeh",
            "queueLengthMEst",
            "densityIndex",
            "avgSpeedKmh",
        }

        assert set(approach.keys()) == expected_fields

        # Pastikan field lama sudah tidak muncul.
        assert "queueLengthM" not in approach
        assert "densityVehPerKm" not in approach