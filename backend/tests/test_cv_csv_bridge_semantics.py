import pandas as pd

from app.pipeline.cv_csv_bridge import _load_merged


def test_crossing_flow_is_not_replaced_by_zone_presence(tmp_path):
    crossing = tmp_path / "crossing.csv"
    density = tmp_path / "density.csv"
    timestamp = "2026-08-15T17:19:15"

    pd.DataFrame([
        {
            "timestamp": timestamp,
            "label_garis": "selatan",
            "jumlah_crossing": 0,
        }
    ]).to_csv(crossing, index=False)
    pd.DataFrame([
        {
            "timestamp": timestamp,
            "lengan": "selatan",
            "total_di_zona": 10,
            "mobil_di_zona": 6,
            "motor_di_zona": 4,
            "bus_di_zona": 0,
            "truk_di_zona": 0,
            "queue_length_veh": 5,
            "queue_length_m_est": 12.5,
        }
    ]).to_csv(density, index=False)

    row = _load_merged(crossing, density).iloc[0]

    assert row["vehicleCount"] == 0
    assert row["carCount"] == 6
    assert row["motorcycleCount"] == 4
    assert row["queueLengthVeh"] == 5
    assert row["densityIndex"] == 10
