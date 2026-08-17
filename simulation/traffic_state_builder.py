"""
TRAFFIC STATE BUILDER

Mengubah CSV per-detik per-lajur dari modul CV menjadi TrafficState
per jendela waktu, sesuai docs/data-contract.md.

    cv/output/smarttwin_traffic_data.csv        (per detik, per lajur)
                    |
                    v
    TrafficState per window                     (per 5 menit, per lengan)
                    |
                    v
    simulation/outputs/traffic_state_snapshot.json


KENAPA LEWAT JSON, BUKAN IMPORT LANGSUNG DARI BACKEND
-----------------------------------------------------
Backend jalan di environment-nya sendiri dan modul ini di venv
simulation. Import lintas-venv tidak akan pernah bisa diandalkan dari
lokasi mana pun, jadi batas antar-modulnya sengaja berupa BERKAS:
builder menulis snapshot JSON, backend membacanya (task terpisah).

Skema Pydantic-nya sendiri tetap diimpor dari backend supaya cuma ada
satu definisi TrafficState di repo — kalau skemanya berubah dan builder
ini tidak ikut, impornya yang gagal duluan, bukan diam-diam menghasilkan
JSON berbentuk lama.


SEMANTIK KOLOM SUMBER — penting sebelum mengubah agregasi
---------------------------------------------------------
CSV CV memuat DUA populasi yang berbeda, dan agregatnya tidak boleh
dicampur (lihat catatan "SEMANTIK KOLOM" di cv/vehicle_counter.py):

    vehicle_count       ALIRAN    - kendaraan yang MEMOTONG counting
                                    line selama detik itu
    queue_length_veh    KEHADIRAN - kendaraan yang terlihat di frame
    queue_length_m_est                dan berstatus antre
    density_index       KEHADIRAN - kendaraan terlihat / fraksi lebar
                                    lajur

Itu sebabnya volume dijumlahkan lintas waktu (aliran memang menumpuk),
sementara antrean di-max dan density di-rata-rata (kehadiran tidak
boleh ditumpuk — kendaraan yang sama muncul lagi di detik berikutnya).
"""

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# Skema Pydantic diambil dari backend — satu-satunya definisi di repo.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BACKEND_DIR = os.path.join(
    os.path.dirname(BASE_DIR),
    "backend"
)

sys.path.insert(0, BACKEND_DIR)

from app.schemas.traffic import (  # noqa: E402
    Approach,
    ApproachState,
    TrafficState,
)


# ============================================================
# KONFIGURASI
# ============================================================

# Lebar jendela agregasi, dalam menit. Diletakkan sebagai konstanta
# karena angka ini kemungkinan besar akan diubah-ubah saat kalibrasi:
# jendela pendek lebih responsif tapi lebih berisik, jendela panjang
# lebih halus tapi telat bereaksi.
#
# 5 menit dipilih karena masih aman terhadap hanyutnya jam antar-channel
# DVR (~10 detik di ujung rekaman) — lihat catatan sinkronisasi di
# cv/_arsip/README.md. Jendela di bawah ~1 menit tidak disarankan
# dengan data ini.
WINDOW_MINUTES = 5

DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(BASE_DIR),
    "cv",
    "output",
    "smarttwin_traffic_data.csv"
)

DEFAULT_SNAPSHOT_PATH = os.path.join(
    BASE_DIR,
    "outputs",
    "traffic_state_snapshot.json"
)

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


# ============================================================
# PEMBACAAN CSV
# ============================================================

def load_rows(csv_path):
    """
    Membaca CSV CV jadi list-of-dict dengan tipe yang sudah benar.

    Sengaja dipisah dari build_traffic_states() supaya fungsi agregasi
    di bawah tetap murni dan bisa diuji dengan list bikinan tangan,
    tanpa perlu berkas.

    pandas TIDAK dipakai: venv simulation tidak memuatnya, dan modul
    csv bawaan sudah cukup untuk bentuk data seperti ini.
    """
    rows = []

    with open(csv_path, newline="", encoding="utf-8") as file:

        for baris in csv.DictReader(file):

            # Baris lengan "tidak terukur" punya kolom angka kosong
            # (lihat LENGAN_TIDAK_TERUKUR di cv/vehicle_counter.py).
            # Dilewati, BUKAN dianggap nol — nol berarti "terukur,
            # hasilnya nol kendaraan", klaim yang tidak kita punya.
            if baris["vehicle_count"] == "":
                continue

            rows.append({
                "timestamp": datetime.strptime(
                    baris["timestamp"],
                    TIMESTAMP_FORMAT
                ),
                "intersection_id": baris["intersection_id"],
                "approach": baris["approach"],
                "lane_id": baris["lane_id"],
                "vehicle_count": int(baris["vehicle_count"]),
                "queue_length_veh": int(baris["queue_length_veh"]),
                "queue_length_m_est": float(baris["queue_length_m_est"]),
                "density_index": float(baris["density_index"]),
            })

    return rows


# ============================================================
# JENDELA WAKTU
# ============================================================

def window_start_of(timestamp, window_minutes=WINDOW_MINUTES):
    """
    Membulatkan timestamp KE BAWAH ke batas jendela terdekat.

    Dibulatkan ke bawah dari tengah malam, bukan dari baris pertama,
    supaya batas jendelanya jatuh di menit yang enak dibaca (16:30,
    16:35, ...) dan tetap sama walau nanti CSV-nya dipotong lain.
    """
    menit_sejak_tengah_malam = (
        timestamp.hour * 60
        + timestamp.minute
    )

    menit_jendela = (
        menit_sejak_tengah_malam
        // window_minutes
        * window_minutes
    )

    return timestamp.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    ) + timedelta(minutes=menit_jendela)


# ============================================================
# AGREGASI
# ============================================================

def build_traffic_states(rows, window_minutes=WINDOW_MINUTES):
    """
    Fungsi MURNI: list-of-dict masuk, list[TrafficState] keluar.

    Agregasinya dua tahap, dan urutannya penting — lintas-LAJUR dulu,
    baru lintas-WAKTU:

        Field                | lintas-lajur | lintas-waktu
        ---------------------|--------------|-------------
        volume               | sum          | sum
        queue_length_veh     | sum          | max
        queue_length_m_est   | max          | max
        density_index        | mean         | mean

    Alasan tiap pilihan:

    - volume sum/sum   : aliran. Kendaraan di lajur berbeda itu
                         kendaraan berbeda, dan detik berbeda juga
                         kendaraan berbeda (dijaga counted_ids di CV).
    - queue sum/max    : dijumlahkan lintas lajur karena antrean satu
                         lengan itu total seluruh lajurnya; di-max
                         lintas waktu karena yang menarik adalah
                         antrean TERPANJANG dalam jendela, bukan
                         totalnya — menjumlahkan lintas waktu akan
                         menghitung mobil yang sama berkali-kali.
    - m_est max/max    : sepadan dengan queue_length_veh supaya kedua
                         kolom antrean tetap bicara soal kejadian yang
                         sama. TIDAK dijumlahkan lintas lajur karena
                         panjang antrean fisik lengan ditentukan lajur
                         terpanjang, bukan jumlah panjang tiap lajur.
    - density mean/mean: indeks ternormalisasi. Menjumlahkannya tidak
                         punya arti fisik.

    avg_speed_kmh selalu None: CSV CV tidak punya kolom kecepatan sama
    sekali, dan menurunkannya dari tracking butuh kalibrasi kamera yang
    belum ada. None berarti BELUM DIUKUR — bukan 0 km/h.
    """

    # ------------------------------------------------------------
    # Tahap 1 — lintas LAJUR, pada tiap detik
    # ------------------------------------------------------------
    #
    # Kunci: (window, approach, timestamp) -> daftar baris lajur

    per_detik = defaultdict(list)

    intersection_ids = set()

    for row in rows:

        intersection_ids.add(row["intersection_id"])

        kunci = (
            window_start_of(row["timestamp"], window_minutes),
            row["approach"],
            row["timestamp"],
        )

        per_detik[kunci].append(row)

    # Hasil tahap 1: satu nilai per (window, approach, detik)
    detik_teragregasi = defaultdict(list)

    for (window, approach, _), baris_lajur in per_detik.items():

        detik_teragregasi[(window, approach)].append({
            "volume": sum(
                r["vehicle_count"] for r in baris_lajur
            ),
            "queue_length_veh": sum(
                r["queue_length_veh"] for r in baris_lajur
            ),
            "queue_length_m_est": max(
                r["queue_length_m_est"] for r in baris_lajur
            ),
            "density_index": (
                sum(r["density_index"] for r in baris_lajur)
                / len(baris_lajur)
            ),
        })

    # ------------------------------------------------------------
    # Tahap 2 — lintas WAKTU, di dalam jendela
    # ------------------------------------------------------------

    per_window = defaultdict(dict)

    for (window, approach), detik in detik_teragregasi.items():

        per_window[window][approach] = ApproachState(
            approach=Approach(approach),

            volume=sum(
                d["volume"] for d in detik
            ),

            queueLengthVeh=max(
                d["queue_length_veh"] for d in detik
            ),

            queueLengthMEst=max(
                d["queue_length_m_est"] for d in detik
            ),

            densityIndex=(
                sum(d["density_index"] for d in detik)
                / len(detik)
            ),

            # BELUM DIUKUR. Jangan diisi 0.0 supaya "kelihatan
            # lengkap" — 0.0 lolos validasi dan terbaca sebagai
            # kendaraan diam.
            avgSpeedKmh=None,
        )

    # ------------------------------------------------------------
    # Rakit TrafficState
    # ------------------------------------------------------------

    if not intersection_ids:
        return []

    # Seluruh kamera memantau simpang yang sama, jadi id-nya konstan.
    # Kalau ternyata lebih dari satu, itu tanda CSV-nya tercampur dan
    # lebih baik berhenti daripada diam-diam memilih salah satu.
    if len(intersection_ids) > 1:
        raise ValueError(
            f"CSV memuat lebih dari satu intersection_id: "
            f"{sorted(intersection_ids)}"
        )

    intersection_id = intersection_ids.pop()

    states = []

    for window in sorted(per_window):

        approaches = per_window[window]

        states.append(
            TrafficState(
                intersectionId=intersection_id,
                windowStart=window,
                windowEnd=window + timedelta(minutes=window_minutes),

                # Diurutkan tetap north/south/east/west supaya
                # keluarannya bisa dibandingkan antar-run.
                approaches=[
                    approaches[a.value]
                    for a in Approach
                    if a.value in approaches
                ],
            )
        )

    return states


def windows_tidak_lengkap(states):
    """
    Jendela yang tidak memuat keempat lengan.

    Tidak diisi nol: lengan yang tidak punya baris pada jendela itu
    berarti TIDAK ADA DATANYA, dan itu beda dari "terukur nol
    kendaraan". Dikembalikan supaya pemanggilnya bisa memutuskan
    sendiri — dilewati, atau dijadikan alasan berhenti.
    """
    kurang = []

    for state in states:

        ada = {a.approach.value for a in state.approaches}

        hilang = [
            a.value for a in Approach
            if a.value not in ada
        ]

        if hilang:
            kurang.append((state.windowStart, hilang))

    return kurang


# ============================================================
# KELUARAN
# ============================================================

def write_snapshot(states, path):
    """
    Menulis list[TrafficState] ke JSON.

    mode="json" WAJIB: tanpa itu windowStart/windowEnd tetap objek
    datetime dan json.dump melempar "Object of type datetime is not
    JSON serializable". Dengan mode="json", Pydantic v2 sudah
    mengubahnya jadi string ISO lebih dulu.
    """
    os.makedirs(
        os.path.dirname(path),
        exist_ok=True
    )

    payload = [
        state.model_dump(mode="json")
        for state in states
    ]

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False
        )

    return path


# ============================================================
# MAIN — sanity check manual
# ============================================================

def main():
    csv_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else DEFAULT_CSV_PATH
    )

    print("=" * 66)
    print("TRAFFIC STATE BUILDER")
    print("=" * 66)
    print(f"CSV      : {csv_path}")
    print(f"Window   : {WINDOW_MINUTES} menit")
    print()

    rows = load_rows(csv_path)

    print(f"Baris terbaca : {len(rows)}")

    states = build_traffic_states(rows)

    print(f"Window       : {len(states)}")

    if states:
        print(
            f"Rentang      : {states[0].windowStart} "
            f"-> {states[-1].windowEnd}"
        )

    kurang = windows_tidak_lengkap(states)

    if kurang:
        print()
        print(
            f"[PERINGATAN] {len(kurang)} window tidak memuat "
            f"keempat lengan:"
        )
        for window, hilang in kurang[:5]:
            print(f"  {window} -> tidak ada: {', '.join(hilang)}")
    else:
        print("Kelengkapan  : semua window punya 4 lengan")

    path = write_snapshot(states, DEFAULT_SNAPSHOT_PATH)

    print()
    print(f"Snapshot     : {path}")

    print()
    print("=" * 66)
    print("3 WINDOW PERTAMA")
    print("=" * 66)

    for state in states[:3]:

        print()
        print(
            f"{state.windowStart.strftime('%H:%M:%S')} - "
            f"{state.windowEnd.strftime('%H:%M:%S')}  "
            f"({state.intersectionId})"
        )

        print(
            f"  {'lengan':<7}{'volume':>8}{'q_veh':>8}"
            f"{'q_m_est':>10}{'density':>10}{'speed':>8}"
        )

        for a in state.approaches:
            print(
                f"  {a.approach.value:<7}{a.volume:>8}"
                f"{a.queueLengthVeh:>8}{a.queueLengthMEst:>10.1f}"
                f"{a.densityIndex:>10.3f}"
                f"{str(a.avgSpeedKmh):>8}"
            )


if __name__ == "__main__":
    main()
