"""
run_decision.py
Membaca percobaan_logic_simpang.csv (zona, rata-rata per 5 detik)
→ feed ke RuleBasedEngine (kontrak TrafficState/SignalRecommendation
resmi, lihat rule_based_engine.py) → simpan signal_decisions.csv

Format kolom input (percobaan_logic_simpang.csv):
  timestamp, kamera, lengan, total_di_zona, motor_di_zona,
  mobil_di_zona, truk_di_zona, bus_di_zona, frame_number

Fallback: smarttwin_traffic_data.csv (crossing-based, sementara)

Satu baris output = SATU rekomendasi per timestamp (lengan yang
direkomendasikan jadi hijau berikutnya), BUKAN alokasi keempat lengan
sekaligus -- itu sengaja, lihat catatan di rule_based_engine.py soal
kenapa SignalRecommendation cuma satu recommended_phase per panggilan.
"""

import csv
import sys
import os
from collections import defaultdict
from datetime import datetime, timezone

# Pastikan bisa import rule_based_engine dari direktori yang sama
sys.path.insert(0, os.path.dirname(__file__))
from rule_based_engine import RuleBasedEngine

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
)
from app.schemas.traffic import ApproachState, TrafficState  # noqa: E402

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

# lengan (Indonesia, dipakai CSV CV) -> approach (Inggris, dipakai
# TrafficState/ApproachState resmi). Sama persis dengan
# backend/app/pipeline/cv_csv_bridge.py::DENSITY_LENGAN_MAP, disalin
# di sini supaya run_decision.py tidak perlu bergantung pada modul
# backend selain schemas.
LENGAN_KE_APPROACH = {
    "selatan": "south",
    "barat": "west",
    "timur": "east",
    "simpang_tengah": "north",
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
    Iterasi setiap timestamp, susun TrafficState, feed ke engine.

    current_green_seconds TIDAK diisi (biarkan default WAKTU_HIJAU_MIN
    di rule_based_engine.py) -- CSV historis ini tidak merekam fase mana
    yang sungguh sedang hijau di dunia nyata pada tiap timestamp, jadi
    memalsukan kontinuitas antar-baris cuma akan menghasilkan angka
    expected_delay_reduction_percent yang kelihatan presisi padahal
    tidak. Sesi live (lewat TraCI, bukan replay CSV) yang punya state
    sinyal sungguhan wajib mengisi parameter ini.

    Return list of result rows (satu baris = satu SignalRecommendation).
    """
    results = []
    timestamps = sorted(data.keys())

    for ts in timestamps:
        approach_states = []
        for lengan in LENGAN_VALID:
            agg = data[ts].get(
                lengan, {"total": 0, "motor": 0, "mobil": 0, "truk": 0, "bus": 0}
            )
            approach_states.append(
                ApproachState(
                    approach=LENGAN_KE_APPROACH[lengan],
                    volume=agg["total"],
                    motorcycleCount=agg["motor"],
                    carCount=agg["mobil"],
                    truckCount=agg["truk"],
                    busCount=agg["bus"],
                )
            )

        traffic_state = TrafficState(
            intersectionId="simpang4-pingit",
            windowStart=datetime.now(timezone.utc),
            windowEnd=datetime.now(timezone.utc),
            approaches=approach_states,
        )

        rekomendasi = engine.decide(traffic_state)

        results.append({
            "timestamp": ts,
            "recommended_phase": rekomendasi.recommended_phase,
            "green_time": rekomendasi.recommended_green_seconds,
            "current_green_seconds": rekomendasi.current_green_seconds,
            "confidence": rekomendasi.confidence,
            "expected_delay_reduction_percent": rekomendasi.expected_delay_reduction_percent,
            "reason": rekomendasi.reason,
        })

    return results

# ─── Tulis Output CSV ─────────────────────────────────────────────────────────
def tulis_csv(path: str, rows: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "timestamp", "recommended_phase", "green_time",
        "current_green_seconds", "confidence",
        "expected_delay_reduction_percent", "reason",
    ]
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
    print(
        f"{'Timestamp':<25} {'Phase':<8} {'Green':>6} "
        f"{'Confidence':>10} {'Reason'}"
    )
    print("-" * 100)
    for row in results[:10]:
        print(
            f"{row['timestamp']:<25} "
            f"{row['recommended_phase']:<8} "
            f"{row['green_time']:>5}s "
            f"{row['confidence']:>10} "
            f"{row['reason']}"
        )