from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from forecasting.scripts.lstm.train import create_sequences  # noqa: E402


def test_create_sequences_rejects_timestamp_gap():
    values = np.arange(30 * 4, dtype=np.float32).reshape(30, 4)
    start = datetime(2026, 8, 15, tzinfo=timezone.utc)
    timestamps = [start + timedelta(seconds=5 * index) for index in range(30)]
    timestamps[15] = timestamps[14] + timedelta(seconds=30)

    x_values, y_values = create_sequences(
        values,
        timestamps,
        input_steps=4,
        output_steps=2,
    )

    assert len(x_values) < 25
    assert len(x_values) == len(y_values)
