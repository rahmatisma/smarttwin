import csv
import os
import sys
import argparse
from datetime import datetime, timezone

try:
    from supabase import create_client, Client
except ImportError:
    print("[ERROR] supabase-py belum terinstall.")
    print("        Jalankan: pip install supabase")
    sys.exit(1)

# ─── Konfigurasi Supabase ──────────────────────────────────────────────────
SUPABASE_URL = "https://cjxsuodiivriifetvrir.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNqeHN1b2RpaXZyaWlmZXR2cmlyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzIyOTYwNSwiZXhwIjoyMTAyODA1NjA1fQ.xYVQm_p7Fg5ZeqBilztNe90zPbzGBy9gR6WXFt0LPhs"

INTERSECTION_DB_ID = 1

APPROACH_ID_MAP = {
    "simpang_tengah": 1,
    "selatan": 2,
    "timur": 3,
    "barat": 4,
}

LENGAN_TO_APPROACH = {
    "barat": "west", "selatan": "south",
    "timur": "east", "simpang_tengah": "north",
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAFFIC_CSV = os.path.join(BASE_DIR, "cv", "output", "percobaan_logic_simpang.csv")
SIGNAL_CSV = os.path.join(BASE_DIR, "cv", "output", "signal_decisions.csv")
TRAFFIC_CSV_FALLBACK = os.path.join(BASE_DIR, "cv", "output", "smarttwin_traffic_data.csv")

def ts_to_iso(ts_str: str) -> str:
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return ts_str

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

def clear_database(supabase: Client):
    print("\n[INITIAL SYNC] Membersihkan data lama...")
    tables = ["trafficApproachStates", "recommendations", "trafficStates"]
    for table in tables:
        try:
            res = supabase.table(table).select('id').limit(5000).execute()
            if res.data:
                ids = [r['id'] for r in res.data]
                # Batch delete
                chunk_size = 200
                for i in range(0, len(ids), chunk_size):
                    chunk = ids[i:i+chunk_size]
                    supabase.table(table).delete().in_('id', chunk).execute()
                print(f"  - Deleted {len(ids)} rows dari {table}")
            else:
                print(f"  - {table} sudah kosong")
        except Exception as e:
            print(f"  [WARNING] Gagal menghapus {table}. RLS policy mungkin memblokir DELETE. ({e})")

def is_changed(old_dict, new_dict, keys):
    for k in keys:
        if old_dict.get(k) != new_dict.get(k):
            return True
    return False

def feed_traffic_states(supabase: Client, csv_path: str, is_zona_csv: bool):
    from collections import defaultdict

    print(f"\n[1/2] Membaca: {csv_path}")
    if not os.path.exists(csv_path):
        print("      File tidak ditemukan, skip.")
        return {}

    data = defaultdict(lambda: defaultdict(dict))
    LENGAN_FALLBACK_MAP = {
        "west": "barat", "south": "selatan",
        "east": "timur", "north": "simpang_tengah",
    }

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row["timestamp"].strip()
            
            if is_zona_csv:
                lengan = row.get("lengan", "").strip().lower()
            else:
                raw = row.get("approach", "").strip().lower()
                lengan = LENGAN_FALLBACK_MAP.get(raw, raw)
            
            if lengan not in APPROACH_ID_MAP:
                continue

            agg = data[ts][lengan]
            if is_zona_csv:
                agg["volume"] = safe_int(row.get("total_di_zona", 0))
                agg["motorcycleCount"] = safe_int(row.get("motor_di_zona", 0))
                agg["carCount"] = safe_int(row.get("mobil_di_zona", 0))
                agg["truckCount"] = safe_int(row.get("truk_di_zona", 0))
                agg["busCount"] = safe_int(row.get("bus_di_zona", 0))
                agg["queueLengthVeh"] = safe_int(row.get("total_di_zona", 0))
                agg["densityIndex"] = 0.0
            else:
                agg["volume"] = agg.get("volume", 0) + safe_int(row.get("vehicle_count", 0))
                agg["motorcycleCount"] = agg.get("motorcycleCount", 0) + safe_int(row.get("motorcycle_count", 0))
                agg["carCount"] = agg.get("carCount", 0) + safe_int(row.get("car_count", 0))
                agg["truckCount"] = agg.get("truckCount", 0) + safe_int(row.get("truck_count", 0))
                agg["busCount"] = agg.get("busCount", 0) + safe_int(row.get("bus_count", 0))
                agg["queueLengthVeh"] = agg.get("queueLengthVeh", 0) + safe_int(row.get("queue_length_veh", 0))
                agg["densityIndex"] = max(agg.get("densityIndex", 0), safe_float(row.get("density_index", 0)))

    timestamps = sorted(data.keys())
    print(f"      CSV unique timestamps: {len(timestamps)}")

    ts_to_dbid = {}
    BATCH = 50

    stats = {"states_new": 0, "states_skip": 0, "app_new": 0, "app_upd": 0, "app_skip": 0}

    for i in range(0, len(timestamps), BATCH):
        batch_ts = timestamps[i:i+BATCH]
        batch_iso = [ts_to_iso(ts) for ts in batch_ts]

        # 1. IDENTIFY EXISTING RECORD for trafficStates
        existing_states = {}
        res = supabase.table("trafficStates").select("id, windowStart").eq("intersectionId", INTERSECTION_DB_ID).in_("windowStart", batch_iso).execute()
        for r in res.data:
            existing_states[r["windowStart"]] = r["id"]

        states_to_insert = []
        for ts in batch_ts:
            iso = ts_to_iso(ts)
            if iso in existing_states:
                ts_to_dbid[ts] = existing_states[iso]
                stats["states_skip"] += 1
            else:
                states_to_insert.append({
                    "intersectionId": INTERSECTION_DB_ID,
                    "windowStart": iso,
                    "windowEnd": iso,
                    "source": "cv_zona" if is_zona_csv else "cv_crossing",
                })
                
        if states_to_insert:
            inserted = supabase.table("trafficStates").insert(states_to_insert).execute()
            stats["states_new"] += len(states_to_insert)
            for rec in inserted.data:
                for ts in batch_ts:
                    if ts_to_iso(ts) == rec["windowStart"]:
                        ts_to_dbid[ts] = rec["id"]

        # 2. IDENTIFY EXISTING RECORD for trafficApproachStates
        state_ids = [ts_to_dbid[ts] for ts in batch_ts if ts in ts_to_dbid]
        existing_approaches = {}
        if state_ids:
            res_app = supabase.table("trafficApproachStates").select("*").in_("trafficStateId", state_ids).execute()
            for r in res_app.data:
                existing_approaches[(r["trafficStateId"], r["approachId"])] = r
        
        apps_to_insert = []
        apps_to_update = []
        compare_keys = ["volume", "carCount", "motorcycleCount", "busCount", "truckCount", "queueLengthVeh", "densityIndex"]

        for ts in batch_ts:
            state_id = ts_to_dbid.get(ts)
            if not state_id: continue
            
            for lengan, agg in data[ts].items():
                app_id = APPROACH_ID_MAP[lengan]
                new_row = {
                    "trafficStateId": state_id,
                    "approachId": app_id,
                    "approach": LENGAN_TO_APPROACH[lengan],
                    "volume": agg.get("volume", 0),
                    "carCount": agg.get("carCount", 0),
                    "motorcycleCount": agg.get("motorcycleCount", 0),
                    "busCount": agg.get("busCount", 0),
                    "truckCount": agg.get("truckCount", 0),
                    "queueLengthVeh": agg.get("queueLengthVeh", 0),
                    "queueLengthMEst": 0.0,
                    "densityIndex": agg.get("densityIndex", 0.0),
                }

                key = (state_id, app_id)
                if key in existing_approaches:
                    old_row = existing_approaches[key]
                    if is_changed(old_row, new_row, compare_keys):
                        # UPDATE
                        new_row["id"] = old_row["id"]
                        apps_to_update.append(new_row)
                        stats["app_upd"] += 1
                    else:
                        stats["app_skip"] += 1
                else:
                    apps_to_insert.append(new_row)
                    stats["app_new"] += 1

        try:
            if apps_to_insert:
                supabase.table("trafficApproachStates").insert(apps_to_insert).execute()
            if apps_to_update:
                for row in apps_to_update:
                    supabase.table("trafficApproachStates").update(row).eq('id', row['id']).execute()
        except Exception as e:
             print(f"\n[WARNING] Update/Insert gagal (mungkin RLS): {e}")

        print(f"      Batch {i//BATCH + 1}: Diproses.", end="\r")

    print("\n      [SYNC COMPLETE] trafficStates + trafficApproachStates selesai.")
    print(f"      [SYNC STATS] States -> New: {stats['states_new']}, Skip: {stats['states_skip']}")
    print(f"      [SYNC STATS] Approaches -> New: {stats['app_new']}, Changed (Update): {stats['app_upd']}, Unchanged (Skip): {stats['app_skip']}")
    return ts_to_dbid

def feed_signal_decisions(supabase: Client):
    print(f"\n[2/2] Membaca: {SIGNAL_CSV}")
    if not os.path.exists(SIGNAL_CSV):
        print("      File tidak ditemukan, skip.")
        return

    csv_data = []
    with open(SIGNAL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            csv_data.append(row)

    print(f"      CSV rows: {len(csv_data)}")
    
    stats = {"new": 0, "upd": 0, "skip": 0}
    compare_keys = ["recommendedGreenSeconds", "expectedDelayReductionPercent", "confidence", "reason"]
    BATCH = 100

    for i in range(0, len(csv_data), BATCH):
        batch = csv_data[i:i+BATCH]
        batch_ts = [ts_to_iso(r["timestamp"]) for r in batch]
        
        # IDENTIFY EXISTING RECORD
        existing_recs = {}
        res = supabase.table("recommendations").select("*").eq("intersectionId", INTERSECTION_DB_ID).in_("timestamp", batch_ts).execute()
        for r in res.data:
            existing_recs[(r["timestamp"], r["recommendedPhase"])] = r
            
        recs_to_insert = []
        recs_to_update = []
        
        for row in batch:
            skor = safe_int(row["skor"])
            prioritas = row["prioritas"]
            confidence = min(skor / 30.0, 1.0)
            delay_map = {"tinggi": 30.0, "sedang": 15.0, "rendah": 5.0}
            delay_pct = delay_map.get(prioritas, 5.0)
            iso = ts_to_iso(row["timestamp"])

            new_row = {
                "intersectionId": INTERSECTION_DB_ID,
                "timestamp": iso,
                "recommendedPhase": row["lengan"],
                "recommendedGreenSeconds": safe_int(row["green_time"]),
                "currentGreenSeconds": 30,
                "expectedDelayReductionPercent": delay_pct,
                "confidence": round(confidence, 4),
                "reason": f"rule_based | prioritas={prioritas} | skor={skor} | total_kend={row['total_kend']}",
                "source": "rule_based_engine",
            }
            
            key = (iso, row["lengan"])
            if key in existing_recs:
                old_row = existing_recs[key]
                if is_changed(old_row, new_row, compare_keys):
                    new_row["id"] = old_row["id"]
                    recs_to_update.append(new_row)
                    stats["upd"] += 1
                else:
                    stats["skip"] += 1
            else:
                recs_to_insert.append(new_row)
                stats["new"] += 1

        try:
            if recs_to_insert:
                supabase.table("recommendations").insert(recs_to_insert).execute()
            if recs_to_update:
                for r in recs_to_update:
                    supabase.table("recommendations").update(r).eq('id', r['id']).execute()
        except Exception as e:
            print(f"\n[WARNING] Update/Insert gagal (mungkin RLS): {e}")
            
        print(f"      Batch {i//BATCH + 1}: Diproses.", end="\r")

    print("\n      [SYNC COMPLETE] recommendations selesai.")
    print(f"      [SYNC STATS] Recommendations -> New: {stats['new']}, Changed (Update): {stats['upd']}, Unchanged (Skip): {stats['skip']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Feed YOLO CSV to Supabase")
    parser.add_argument("--initial-sync", action="store_true", help="Clear target tables before sync")
    args = parser.parse_args()

    print("=" * 60)
    print("  SmartTwin → Supabase Feed (Incremental Sync)")
    print("  Project: Digital-Twins-KMIPN-2026")
    print("=" * 60)

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    if args.initial_sync:
        clear_database(supabase)

    if os.path.exists(TRAFFIC_CSV):
        feed_traffic_states(supabase, TRAFFIC_CSV, is_zona_csv=True)
    elif os.path.exists(TRAFFIC_CSV_FALLBACK):
        print("\n[INFO] percobaan_logic_simpang.csv belum ada. Menggunakan fallback.")
        feed_traffic_states(supabase, TRAFFIC_CSV_FALLBACK, is_zona_csv=False)
    else:
        print("\n[SKIP] Tidak ada traffic CSV yang ditemukan.")

    feed_signal_decisions(supabase)

    print("\n" + "=" * 60)
    print("  Sinkronisasi Selesai!")
    print("=" * 60)