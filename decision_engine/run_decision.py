"""
run_decision.py
Membaca percobaan_logic_simpang.csv (zona, rata-rata per 5 detik)
→ feed ke RuleBasedEngine → simpan signal_decisions.csv

Format kolom input (percobaan_logic_simpang.csv):
  timestamp, kamera, lengan, total_di_zona, motor_di_zona,
  mobil_di_zona, truk_di_zona, bus_di_zona, frame_number

Fallback: smarttwin_traffic_data.csv (crossing-based, sementara)
"""

import csv
import sys
import os
from collections import defaultdict

# Pastikan bisa import rule_based_engine dari direktori yang sama
sys.path.insert(0, os.path.dirname(__file__))
from rule_based_engine import RuleBasedEngine

# ─── Konfigurasi Path ─────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZONA_CSV       = os.path.join(BASE_DIR, "cv", "output", "percobaan_logic_simpang.csv")
FALLBACK_CSV   = os.path.join(BASE_DIR, "cv", "output", "smarttwin_traffic_data.csv")
OUTPUT_CSV     = os.path.join(BASE_DIR, "cv", "output", "signal_decisions.csv")

# Nama lengan valid (kolom "lengan" di percobaan_logic_simpang.csv sudah pakai nama ini)
LENGAN_VALID = {"selatan", "barat", "timur", "simpang_tengah"}

# Mapping fallback: kolom "approach" di smarttwin_traffic_data.csv
APPROACH_MAP_FALLBACK = {
    "west":  "barat",
    "south": "selatan",
    "east":  "timur",
    "north": "simpang_tengah",
}

# ─── Baca percobaan_logic_simpang.csv (zona) ─────────────────────────────────
def baca_zona_csv(path: str):
    """
    Kolom: timestamp, kamera, lengan, total_di_zona, motor_di_zona,
           mobil_di_zona, truk_di_zona, bus_di_zona, frame_number

    Group by (timestamp, lengan) — sum across kamera.
    Return: {timestamp → {lengan → {total, motor, mobil, truk, bus}}}
    """
    data = defaultdict(lambda: defaultdict(lambda: {
        "total": 0, "motor": 0, "mobil": 0, "truk": 0, "bus": 0
    }))

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts     = row["timestamp"].strip()
            lengan = row["lengan"].strip().lower()
            if lengan not in LENGAN_VALID:
                continue

            data[ts][lengan]["total"] += int(float(row["total_di_zona"]))
            data[ts][lengan]["motor"] += int(float(row["motor_di_zona"]))
            data[ts][lengan]["mobil"] += int(float(row["mobil_di_zona"]))
            data[ts][lengan]["truk"]  += int(float(row["truk_di_zona"]))
            data[ts][lengan]["bus"]   += int(float(row["bus_di_zona"]))

    return data

# ─── Baca smarttwin_traffic_data.csv (fallback, crossing-based) ──────────────
def baca_fallback_csv(path: str):
    data = defaultdict(lambda: defaultdict(lambda: {
        "total": 0, "motor": 0, "mobil": 0, "truk": 0, "bus": 0
    }))

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts       = row["timestamp"].strip()
            approach = row["approach"].strip().lower()
            lengan   = APPROACH_MAP_FALLBACK.get(approach)
            if lengan is None:
                continue

            data[ts][lengan]["total"] += int(float(row["queue_length_veh"]))
            data[ts][lengan]["motor"] += int(float(row["motorcycle_count"]))
            data[ts][lengan]["mobil"] += int(float(row["car_count"]))
            data[ts][lengan]["truk"]  += int(float(row["truck_count"]))
            data[ts][lengan]["bus"]   += int(float(row["bus_count"]))

    return data

# ─── Jalankan Engine per Timestamp ───────────────────────────────────────────
def run(engine, data: dict):
    """
    Iterasi setiap timestamp, feed ke engine, kumpulkan keputusan.
    Return list of result rows.
    """
    results = []
    timestamps = sorted(data.keys())

    for ts in timestamps:
        # Susun traffic_state yang diharapkan RuleBasedEngine
        traffic_state = {}
        for lengan, agg in data[ts].items():
            traffic_state[lengan] = {
                "total": agg["total"],
                "motor": agg["motor"],
                "mobil": agg["mobil"],
                "truk":  agg["truk"],
                "bus":   agg["bus"],
            }

        # Pastikan semua 4 lengan ada (isi 0 jika tidak muncul di timestamp ini)
        for lengan in LENGAN_VALID:
            if lengan not in traffic_state:
                traffic_state[lengan] = {
                    "total": 0, "motor": 0, "mobil": 0, "truk": 0, "bus": 0
                }

        keputusan = engine.decide(traffic_state)

        for lengan, info in keputusan.items():
            results.append({
                "timestamp":   ts,
                "lengan":      lengan,
                "green_time":  info["green_duration"],
                "prioritas":   info["prioritas"],
                "skor":        info["skor"],
                "total_kend":  traffic_state[lengan]["total"],
            })

    return results

# ─── Tulis Output CSV ─────────────────────────────────────────────────────────
def tulis_csv(path: str, rows: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = ["timestamp", "lengan", "green_time", "prioritas", "skor", "total_kend"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Pilih sumber data: zona CSV (utama) atau fallback
    if os.path.exists(ZONA_CSV):
        INPUT_CSV  = ZONA_CSV
        baca_csv   = baca_zona_csv
        sumber     = "zona (percobaan_logic_simpang.csv)"
    elif os.path.exists(FALLBACK_CSV):
        INPUT_CSV  = FALLBACK_CSV
        baca_csv   = baca_fallback_csv
        sumber     = "crossing fallback (smarttwin_traffic_data.csv)"
        print("[SmartTwin] PERINGATAN: percobaan_logic_simpang.csv tidak ditemukan.")
        print("            Menggunakan fallback crossing-based. Hasil kurang akurat.")
    else:
        print("[ERROR] Tidak ada CSV yang ditemukan.")
        print(f"        Cari: {ZONA_CSV}")
        print(f"        atau: {FALLBACK_CSV}")
        sys.exit(1)

    print(f"[SmartTwin] Sumber data : {sumber}")
    print(f"[SmartTwin] Membaca     : {INPUT_CSV}")
    print("[SmartTwin] Grouping data per timestamp dan lengan...")
    data = baca_csv(INPUT_CSV)
    print(f"[SmartTwin] Total timestamp unik: {len(data)}")

    engine = RuleBasedEngine()

    print("[SmartTwin] Menjalankan Decision Engine...")
    results = run(engine, data)
    print(f"[SmartTwin] Total keputusan: {len(results)} baris")

    tulis_csv(OUTPUT_CSV, results)
    print(f"[SmartTwin] Disimpan ke: {OUTPUT_CSV}")

    # --- Preview 10 baris pertama -------------------------------------
    print("\n[SmartTwin] --- Preview 10 Baris Pertama ---")
    print(f"{'Timestamp':<25} {'Lengan':<18} {'Green':>6} {'Prioritas':<10} {'Skor':>6} {'Total':>6}")
    print("-" * 75)
    for row in results[:10]:
        print(
            f"{row['timestamp']:<25} "
            f"{row['lengan']:<18} "
            f"{row['green_time']:>5}s "
            f"{row['prioritas']:<10} "
            f"{row['skor']:>6} "
            f"{row['total_kend']:>6}"
        )