"""
feed_to_supabase.py
Insert hasil CV + Decision Engine ke Supabase Digital-Twins-KMIPN-2026

Tabel yang diisi:
  trafficStates         ← header per timestamp
  trafficApproachStates ← data kepadatan per lengan
  recommendations       ← output signal green time dari Decision Engine

Format CSV input:
  percobaan_logic_simpang.csv (rata-rata per 5 detik):
    timestamp, kamera, lengan, total_di_zona, motor_di_zona,
    mobil_di_zona, truk_di_zona, bus_di_zona, frame_number

  signal_decisions.csv:
    timestamp, lengan, green_time, prioritas, skor, total_kend

Jalankan SETELAH:
  1. vehicle_counter_copy.py  → percobaan_logic_simpang.csv
  2. run_decision.py           → signal_decisions.csv
"""

import csv
import os
import sys
from datetime import datetime, timezone

try:
    from supabase import create_client, Client
except ImportError:
    print("[ERROR] supabase-py belum terinstall.")
    print("        Jalankan: pip install supabase")
    sys.exit(1)

# ─── Konfigurasi Supabase ──────────────────────────────────────────────────
SUPABASE_URL = "https://cjxsuodiivriifetvrir.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNqeHN1b2RpaXZyaWlmZXR2cmlyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcyMjk2MDUsImV4cCI6MjEwMjgwNTYwNX0.9oN-HQa7RZ0eR76Jfy2R2tsj3K4ZnNm1VIF6O1XsUYA"

# ─── Konstanta (dari Supabase) ─────────────────────────────────────────────
INTERSECTION_DB_ID = 1          # id row di tabel intersections

APPROACH_ID_MAP = {
    # lengan kita  → approach_id di Supabase
    "simpang_tengah": 1,        # north
    "selatan":        2,        # south
    "timur":          3,        # east  (Jl. Diponegoro, bukan Kyai Mojo)
    "barat":          4,        # west  (Jl. Kyai Mojo, bukan Diponegoro)
}

# lengan kita (Indonesia) → approach di Supabase (Inggris) — dashboard
# frontend cuma mengenali "north"/"south"/"east"/"west" di kolom
# trafficApproachStates.approach (lihat src/types/traffic.ts). Tanpa
# ini, baris yang ditulis lewat script ini tidak pernah kebaca UI.
LENGAN_TO_APPROACH = {
    "barat": "west", "selatan": "south",
    "timur": "east", "simpang_tengah": "north",
}

# ─── Path File ────────────────────────────────────────────────────────────
BASE_DIR          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAFFIC_CSV       = os.path.join(BASE_DIR, "cv", "output", "percobaan_logic_simpang.csv")
SIGNAL_CSV        = os.path.join(BASE_DIR, "cv", "output", "signal_decisions.csv")

# Fallback ke smarttwin_traffic_data.csv jika zona CSV belum ada
TRAFFIC_CSV_FALLBACK = os.path.join(BASE_DIR, "cv", "output", "smarttwin_traffic_data.csv")

# ─── Helper ───────────────────────────────────────────────────────────────
def ts_to_iso(ts_str: str) -> str:
    """Konversi timestamp string ke ISO 8601 dengan timezone UTC."""
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return ts_str  # kembalikan apa adanya jika sudah dalam format ISO

def safe_int(val, default=0) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# ─── Feed trafficStates + trafficApproachStates ───────────────────────────
def feed_traffic_states(supabase: "Client", csv_path: str, is_zona_csv: bool):
    """
    Baca CSV kepadatan zona (percobaan_logic_simpang.csv) atau
    fallback smarttwin_traffic_data.csv, insert ke trafficStates &
    trafficApproachStates.
    """
    from collections import defaultdict

    print(f"\n[1/2] Membaca: {csv_path}")
    if not os.path.exists(csv_path):
        print(f"      File tidak ditemukan, skip.")
        return {}

    # Group rows per timestamp
    data = defaultdict(lambda: defaultdict(dict))

    LENGAN_FALLBACK_MAP = {
        "west": "barat", "south": "selatan",
        "east": "timur", "north": "simpang_tengah",
    }

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts     = row["timestamp"].strip()

            if is_zona_csv:
                # percobaan_logic_simpang.csv → kolom "lengan" sudah pakai nama Indonesia
                lengan = row.get("lengan", "").strip().lower()
            else:
                # smarttwin_traffic_data.csv → kolom "approach" pakai nama Inggris
                raw    = row.get("approach", "").strip().lower()
                lengan = LENGAN_FALLBACK_MAP.get(raw, raw)

            if lengan not in APPROACH_ID_MAP:
                continue

            # Aggregate per (timestamp, lengan)
            agg = data[ts][lengan]
            if is_zona_csv:
                # Kolom dari percobaan_logic_simpang.csv:
                # timestamp, kamera, lengan, total_di_zona, motor_di_zona,
                # mobil_di_zona, truk_di_zona, bus_di_zona, frame_number
                # Rata-rata per 5 detik — langsung assign (sudah di-aggregate di CSV)
                agg["volume"]          = safe_int(row.get("total_di_zona", 0))
                agg["motorcycleCount"] = safe_int(row.get("motor_di_zona", 0))
                agg["carCount"]        = safe_int(row.get("mobil_di_zona", 0))
                agg["truckCount"]      = safe_int(row.get("truk_di_zona", 0))
                agg["busCount"]        = safe_int(row.get("bus_di_zona", 0))
                agg["queueLengthVeh"]  = safe_int(row.get("total_di_zona", 0))
                agg["densityIndex"]    = 0.0  # tidak ada di CSV zona, biarkan 0
            else:
                # Kolom dari smarttwin_traffic_data.csv (fallback, crossing-based)
                agg["volume"]          = agg.get("volume", 0) + safe_int(row.get("vehicle_count", 0))
                agg["motorcycleCount"] = agg.get("motorcycleCount", 0) + safe_int(row.get("motorcycle_count", 0))
                agg["carCount"]        = agg.get("carCount", 0) + safe_int(row.get("car_count", 0))
                agg["truckCount"]      = agg.get("truckCount", 0) + safe_int(row.get("truck_count", 0))
                agg["busCount"]        = agg.get("busCount", 0) + safe_int(row.get("bus_count", 0))
                agg["queueLengthVeh"]  = agg.get("queueLengthVeh", 0) + safe_int(row.get("queue_length_veh", 0))
                agg["densityIndex"]    = max(agg.get("densityIndex", 0), safe_float(row.get("density_index", 0)))

    timestamps = sorted(data.keys())
    print(f"      {len(timestamps)} timestamp unik ditemukan.")

    ts_to_dbid = {}   # timestamp_str → trafficState.id (untuk join recommendations)
    BATCH = 50

    for i in range(0, len(timestamps), BATCH):
        batch_ts = timestamps[i:i+BATCH]

        # Insert trafficStates
        state_rows = [
            {
                "intersectionId": INTERSECTION_DB_ID,
                "windowStart":    ts_to_iso(ts),
                "windowEnd":      ts_to_iso(ts),   # granularity 1 detik
                "source":         "cv_zona" if is_zona_csv else "cv_crossing",
            }
            for ts in batch_ts
        ]
        resp = supabase.table("trafficStates").insert(state_rows).execute()
        inserted_states = resp.data

        # Petakan timestamp → id yang baru dibuat
        for rec in inserted_states:
            # windowStart → cocokkan ke timestamp string
            ws = rec["windowStart"][:19].replace("T", " ")  # "2026-08-15 16:30:12"
            ts_to_dbid[ws] = rec["id"]

        # Insert trafficApproachStates
        approach_rows = []
        for ts in batch_ts:
            state_id = ts_to_dbid.get(ts)
            if state_id is None:
                continue
            for lengan, agg in data[ts].items():
                approach_rows.append({
                    "trafficStateId":  state_id,
                    "approachId":      APPROACH_ID_MAP[lengan],
                    "approach":        LENGAN_TO_APPROACH[lengan],
                    "volume":          agg.get("volume", 0),
                    "carCount":        agg.get("carCount", 0),
                    "motorcycleCount": agg.get("motorcycleCount", 0),
                    "busCount":        agg.get("busCount", 0),
                    "truckCount":      agg.get("truckCount", 0),
                    "queueLengthVeh":  agg.get("queueLengthVeh", 0),
                    "queueLengthMEst": 0.0,
                    "densityIndex":    agg.get("densityIndex", 0.0),
                })

        if approach_rows:
            supabase.table("trafficApproachStates").insert(approach_rows).execute()

        print(f"      Batch {i//BATCH + 1}: {len(batch_ts)} timestamps di-insert.", end="\r")

    print(f"\n      ✅ trafficStates + trafficApproachStates selesai.")
    return ts_to_dbid

# ─── Feed recommendations (signal decisions) ──────────────────────────────
def feed_signal_decisions(supabase: "Client"):
    print(f"\n[2/2] Membaca: {SIGNAL_CSV}")
    if not os.path.exists(SIGNAL_CSV):
        print(f"      File tidak ditemukan, skip.")
        return

    rows_to_insert = []
    with open(SIGNAL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            skor     = safe_int(row["skor"])
            prioritas = row["prioritas"]

            # Confidence 0.0–1.0 dari skor (cap di 30)
            confidence = min(skor / 30.0, 1.0)

            # Estimasi delay reduction: tinggi→30%, sedang→15%, rendah→5%
            delay_map = {"tinggi": 30.0, "sedang": 15.0, "rendah": 5.0}
            delay_pct = delay_map.get(prioritas, 5.0)

            rows_to_insert.append({
                "intersectionId":               INTERSECTION_DB_ID,
                "timestamp":                    ts_to_iso(row["timestamp"]),
                "recommendedPhase":             row["lengan"],
                "recommendedGreenSeconds":      safe_int(row["green_time"]),
                "currentGreenSeconds":          30,       # default fixed sebelumnya
                "expectedDelayReductionPercent": delay_pct,
                "confidence":                   round(confidence, 4),
                "reason": (
                    f"rule_based | prioritas={prioritas} | "
                    f"skor={skor} | total_kend={row['total_kend']}"
                ),
                "source": "rule_based_engine",
            })

    # Insert bertahap
    BATCH = 100
    for i in range(0, len(rows_to_insert), BATCH):
        supabase.table("recommendations").insert(rows_to_insert[i:i+BATCH]).execute()
        print(f"      Batch {i//BATCH + 1}: {min(i+BATCH, len(rows_to_insert))}/{len(rows_to_insert)} rows.", end="\r")

    print(f"\n      ✅ recommendations selesai. Total: {len(rows_to_insert)} rows.")

# ─── Main ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  SmartTwin → Supabase Feed")
    print("  Project: Digital-Twins-KMIPN-2026")
    print("=" * 60)

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Pilih CSV zona atau fallback
    if os.path.exists(TRAFFIC_CSV):
        feed_traffic_states(supabase, TRAFFIC_CSV, is_zona_csv=True)
    elif os.path.exists(TRAFFIC_CSV_FALLBACK):
        print(f"\n[INFO] percobaan_logic_simpang.csv belum ada.")
        print(f"       Menggunakan fallback: smarttwin_traffic_data.csv")
        feed_traffic_states(supabase, TRAFFIC_CSV_FALLBACK, is_zona_csv=False)
    else:
        print("\n[SKIP] Tidak ada traffic CSV yang ditemukan.")

    feed_signal_decisions(supabase)

    print("\n" + "=" * 60)
    print("  Selesai! Data sudah masuk ke Supabase.")
    print("=" * 60)