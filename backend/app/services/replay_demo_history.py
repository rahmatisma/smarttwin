"""Read the available YOLO recording; never invent yesterday's observations."""
import csv
from bisect import bisect_right
from datetime import datetime, timedelta, timezone

ARMS = {"simpang_tengah": "north", "timur": "east", "selatan": "south", "barat": "west"}
COUNTS = {"car": "mobil_di_zona", "motorcycle": "motor_di_zona", "truck": "truk_di_zona", "bus": "bus_di_zona"}


class RecordedHistory:
    def __init__(self, path):
        self.rows = {arm: [] for arm in ARMS.values()}
        with open(path, encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                arm = ARMS.get(row["lengan"])
                if not arm:
                    continue
                timestamp = datetime.fromisoformat(row["timestamp"])
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone(timedelta(hours=7)))
                self.rows[arm].append({"time": timestamp.timestamp(), "timestamp": timestamp.isoformat(),
                                       "counts": {key: max(0, round(float(row[column]))) for key, column in COUNTS.items()}})
        if any(not rows for rows in self.rows.values()):
            raise ValueError("CSV hasil YOLO harus berisi data untuk empat lengan.")
        for rows in self.rows.values():
            rows.sort(key=lambda row: row["time"])
        self.times = {arm: [row["time"] for row in rows] for arm, rows in self.rows.items()}
        self.start = max(times[0] for times in self.times.values())
        self.end = min(times[-1] for times in self.times.values())
        self.playback_start = min(self.start + 300, self.end)

    def sample(self, arm, timestamp):
        index = bisect_right(self.times[arm], timestamp) - 1
        return self.rows[arm][index] if index >= 0 else None

    def history_window(self, arm, cutoff, age):
        # Only records already seen before the failure, even during a long outage.
        return [row for row in self.rows[arm] if max(self.start, cutoff - age) <= row["time"] < cutoff]
