"""
collect_brisbane.py
Collector API Brisbane 24/7 untuk membentuk time series per TSC.
Tidak membutuhkan requests: memakai urllib bawaan Python.
"""

from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import os
import time
import urllib.parse
import urllib.request

API_URL = (
    "https://data.brisbane.qld.gov.au/"
    "api/explore/v2.1/catalog/datasets/"
    "traffic-data-at-intersection/records"
)

TSC = int(os.getenv("BRISBANE_TSC", "470"))
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "60"))

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "data" / "brisbane_realtime"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAW_FILE = OUTPUT_DIR / "raw_records.jsonl"
TIMESERIES_FILE = OUTPUT_DIR / "brisbane_timeseries.csv"

FIELDS = [
    "timestamp", "tsc", "lane_count", "vehicle_count",
    "reconstituted_flow", "density_proxy", "queue_proxy",
    "cycle_time", "link_plan"
]


def number(value, default=0.0):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_records():
    params = {
        "limit": 100,
        "where": f"tsc={TSC}",
        "order_by": "recorded DESC",
    }

    url = API_URL + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        data = json.loads(
            response.read().decode("utf-8")
        )

    return data.get("results", [])


def aggregate_latest_minute(records):
    if not records:
        return None

    timestamps = [
        r.get("recorded") for r in records if r.get("recorded")
    ]
    if not timestamps:
        return None

    latest = max(timestamps)

    rows = [
        r for r in records
        if r.get("recorded") == latest
    ]

    vehicle_count = 0.0
    lane_count = 0
    cycle_times = []
    link_plans = []

    for r in rows:
        lane_count += 1

        # ds1-ds4 = jumlah kendaraan/deteksi per movement.
        vehicle_count += sum(
            number(r.get(f"ds{i}")) for i in range(1, 5)
        )

        ct = number(r.get("ct"), None)
        if ct is not None:
            cycle_times.append(ct)

        lp = r.get("link_plan")
        if lp is not None:
            try:
                link_plans.append(float(lp))
            except (TypeError, ValueError):
                pass

    cycle_time = (
        sum(cycle_times) / len(cycle_times)
        if cycle_times else 0.0
    )

    link_plan = (
        max(set(link_plans), key=link_plans.count)
        if link_plans else 0.0
    )

    density_proxy = (
        vehicle_count / lane_count
        if lane_count else 0.0
    )

    # Proxy sederhana dari data yang tersedia.
    queue_proxy = vehicle_count

    timestamp = (
        datetime.fromisoformat(
            latest.replace("Z", "+00:00")
        )
        .astimezone(timezone.utc)
        .replace(second=0, microsecond=0)
        .isoformat()
    )

    return {
        "timestamp": timestamp,
        "tsc": TSC,
        "lane_count": lane_count,
        "vehicle_count": vehicle_count,
        "reconstituted_flow": vehicle_count,
        "density_proxy": density_proxy,
        "queue_proxy": queue_proxy,
        "cycle_time": cycle_time,
        "link_plan": link_plan,
    }


def save_raw(records):
    now = datetime.now(timezone.utc).isoformat()

    with open(RAW_FILE, "a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps({
                "collected_at": now,
                "record": record,
            }, ensure_ascii=False) + "\n")


def already_saved(timestamp):
    if not TIMESERIES_FILE.exists():
        return False

    with open(TIMESERIES_FILE, "r", encoding="utf-8") as f:
        return any(line.startswith(timestamp + ",") for line in f)


def save_timeseries(row):
    new_file = not TIMESERIES_FILE.exists()

    with open(
        TIMESERIES_FILE,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)

        if new_file:
            writer.writeheader()

        writer.writerow(row)


def collect_once():
    records = fetch_records()

    if not records:
        print("[WARNING] API tidak mengembalikan data.")
        return

    save_raw(records)

    row = aggregate_latest_minute(records)

    if row is None:
        print("[WARNING] Tidak bisa membuat agregasi.")
        return

    if already_saved(row["timestamp"]):
        print(f"[SKIP] Sudah tersimpan: {row['timestamp']}")
        return

    save_timeseries(row)

    print()
    print("[SAVED] Traffic observation")
    print(f"       Timestamp     : {row['timestamp']}")
    print(f"       TSC           : {row['tsc']}")
    print(f"       Lane count    : {row['lane_count']}")
    print(f"       Vehicle count : {row['vehicle_count']:.0f}")
    print(f"       Density proxy : {row['density_proxy']:.2f}")
    print(f"       Queue proxy   : {row['queue_proxy']:.0f}")


def main():
    print("=" * 70)
    print("BRISBANE REAL-TIME TRAFFIC COLLECTOR")
    print("=" * 70)
    print(f"[INFO] TSC      : {TSC}")
    print(f"[INFO] Interval : {INTERVAL_SECONDS} seconds")
    print(f"[INFO] Output   : {TIMESERIES_FILE}")
    print("[INFO] Berjalan 24/7. Ctrl+C untuk berhenti.")
    print("=" * 70)

    while True:
        started = time.time()

        try:
            collect_once()

        except KeyboardInterrupt:
            print("\n[STOP] Collector dihentikan.")
            break

        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
            print("[INFO] Akan mencoba lagi pada interval berikutnya.")

        elapsed = time.time() - started
        time.sleep(max(0, INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    main()
