"""
REPLAY DEMAND CSV KE SUMO

Memutar ulang 49 menit rekaman Simpang Pingit di SUMO dengan waktu
kemunculan kendaraan mengikuti pola crossing ASLI per detik dari
cv/output/smarttwin_traffic_data.csv — bukan disebar rata di dalam
jendela.

    CSV per detik per lajur
            |
            v
    kurva keberangkatan per detik per lengan   (fungsi murni, testable)
            |
            v
    outputs/replay_demand.rou.xml              (berkas rute SUMO)
            |
            v
    SUMO + TraCI, 2.940 detik                  (instrumentasi keberangkatan)


KENAPA BERKAS RUTE, BUKAN traci.vehicle.add() SAAT SIMULASI JALAN
-----------------------------------------------------------------
Keduanya bisa. Dipilih berkas rute karena demand di sini sudah
DIKETAHUI SELURUHNYA di muka dan tidak bergantung pada keadaan
simulasi — ini pemutaran ulang rekaman, bukan pengendalian adaptif.
Konsekuensinya:

  - SUMO sendiri yang mengantre penyisipan saat mulut lengan penuh.
    Dengan traci.vehicle.add(), penyisipan yang gagal jadi urusan kita
    dan gampang hilang diam-diam.
  - Berkas rutenya jadi artefak yang bisa diperiksa, di-diff, dan
    dijalankan ulang tanpa CSV maupun skrip ini.
  - Sejalan dengan Minggu 1: snapshot_dashboard_data.py juga memuat
    berkas rute (outputs/demo_*.rou.xml).

TraCI tetap dipakai, tapi untuk MENGUKUR, bukan menyuntik: tiap langkah
kita catat kendaraan yang benar-benar berangkat, sehingga selisih antara
yang diminta dan yang terwujud bisa dilaporkan angkanya.

Begitu nanti masuk kendali adaptif (fase sinyal bereaksi ke keadaan),
barulah traci.vehicle.add() jadi pilihan yang tepat. Untuk replay, ia
cuma menambah cara gagal tanpa menambah kemampuan.
"""

import csv
import os
import random
import sys
from collections import defaultdict
from datetime import datetime

if "SUMO_HOME" not in os.environ:
    sys.exit(
        "SUMO_HOME belum di-set. Dari folder simulation:\n"
        "  .\\.venv\\Scripts\\Activate.ps1\n"
        "  $env:SUMO_HOME = \"$PWD\\.venv\\Lib\\site-packages\\sumo\""
    )

sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))

import sumolib  # noqa: E402
import traci  # noqa: E402


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(BASE_DIR),
    "cv", "output", "smarttwin_traffic_data.csv"
)

NET_PATH = os.path.join(
    BASE_DIR, "network", "simpang4_pingit.net.xml.gz"
)

ROUTE_OUT = os.path.join(BASE_DIR, "outputs", "replay_demand.rou.xml")

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

SEED = 42


# ============================================================
# GEOMETRI SIMPANG
# ============================================================
#
# Diverifikasi dari network/simpang4_pingit.net.xml.gz lewat sumolib
# (sudut kompas terhadap node SIMPANG_CENTER). Keempat belokan dari
# tiap lengan terbukti sah di network ini.

# Mulut lengan — edge terakhir sebelum masuk simpang.
EDGE_MASUK = {
    "north": "484349908#2",
    "south": "134603786#2",
    "east":  "153857851#4",
    "west":  "590064461#2",
}

# Edge HULU tempat kendaraan benar-benar disisipkan.
#
# Mulut lengan cuma 7-13 m; menyisipkan langsung di situ membuat
# penyisipan gagal begitu antrean menumpuk. Edge hulu di bawah satu
# jalan yang sama (perhatikan id dasarnya sama, cuma beda ruas).
#
# PERHATIKAN north: landasannya cuma 50 m, jauh lebih pendek dari
# south (515 m) dan west (282 m). Lengan dengan permintaan tertinggi
# justru punya ruang penyisipan paling sempit — lihat catatan hasil.
EDGE_HULU = {
    "north": "484349908#0",   #  50 m
    "south": "134603786#0",   # 515 m
    "east":  "153857851#2",   #  46 m
    "west":  "590064461#0",   # 282 m
}

EDGE_KELUAR = {
    "north": "201299423#0",
    "south": "153857907#0",
    "east":  "590386082#0",
    "west":  "25006154#0",
}

# Arah tujuan per lengan asal.
#
# Network dibangun dengan lefthand=true (Indonesia jalur kiri), jadi
# dari arah datang: belok KIRI itu ke sisi kiri arah jalan.
# Contoh: datang dari utara berarti bergerak ke selatan; lurus = keluar
# selatan, kiri = keluar timur, kanan = keluar barat.
BELOKAN = {
    "north": {"lurus": "south", "kiri": "east",  "kanan": "west"},
    "south": {"lurus": "north", "kiri": "west",  "kanan": "east"},
    "east":  {"lurus": "west",  "kiri": "north", "kanan": "south"},
    "west":  {"lurus": "east",  "kiri": "south", "kanan": "north"},
}

# ------------------------------------------------------------
# TODO — PROPORSI BELOK: ANGKA ASUMSI, BUKAN HASIL PENGUKURAN
# ------------------------------------------------------------
#
# CSV CV tidak memuat trayek: yang tercatat cuma "kendaraan memotong
# garis di lengan X", bukan ia keluar ke mana. Jadi proporsi di bawah
# DIKARANG, dan seluruh distribusi arus keluar di hasil replay ini
# ikut mewarisi karangan itu.
#
# CATATAN PENTING soal asal-usulnya: sempat diduga angka ini bisa
# diambil dari setelan randomTrips.py Minggu 1. TIDAK BISA —
# randomTrips.py tidak punya konsep proporsi belok sama sekali. Yang
# dia punya cuma --fringe-factor, --insertion-density, --min-distance,
# dan pemilihan edge tujuan ACAK di seluruh jaringan. Jadi tidak ada
# angka warisan yang bisa dipakai; yang di bawah ini murni default
# yang dipilih sadar-sadar.
#
# 50/25/25 dipilih karena netral: tidak mengistimewakan arah mana pun
# selain kecenderungan umum lalu lintas lurus.
#
# CARA MENGGANTI kalau nanti ada data lapangan: ubah angka di sini
# saja. Penghitungan arus masuk (volume per lengan) TIDAK bergantung
# padanya, jadi uji kekekalan di bawah tetap sah walau proporsinya
# meleset. Yang terpengaruh cuma sebaran arus KELUAR dan konflik di
# dalam simpang.
PROPORSI_BELOK = {
    "lurus": 0.50,
    "kiri":  0.25,
    "kanan": 0.25,
}

# ------------------------------------------------------------
# KELAS KENDARAAN
# ------------------------------------------------------------
#
# Awalan id mengikuti yang benar-benar dipakai randomTrips.py Minggu 1
# (dipulihkan dari build.bat commit 7429bcd): --prefix bus, motorcycle,
# veh, truck. Perhatikan mobil penumpang memakai "veh", BUKAN "car".
KELAS = {
    "motorcycle_count": ("motorcycle", "motorcycle"),
    "car_count":        ("veh",        "passenger"),
    "bus_count":        ("bus",        "bus"),
    "truck_count":      ("truck",      "truck"),
}


# ============================================================
# 1. PARSING KURVA WAKTU — FUNGSI MURNI
# ============================================================

def load_raw_rows(csv_path):
    """
    Membaca CSV di level MENTAH: per timestamp, per lajur, per lengan.

    Sengaja tidak lewat traffic_state_builder: yang dibutuhkan di sini
    justru granularitas detik yang hilang begitu diagregasi ke window.
    """
    rows = []

    with open(csv_path, newline="", encoding="utf-8") as file:

        for baris in csv.DictReader(file):

            # Baris lengan "tidak terukur" — kolom angkanya kosong.
            if baris["vehicle_count"] == "":
                continue

            rows.append({
                "timestamp": datetime.strptime(
                    baris["timestamp"], TIMESTAMP_FORMAT
                ),
                "approach": baris["approach"],
                "motorcycle_count": int(baris["motorcycle_count"]),
                "car_count": int(baris["car_count"]),
                "bus_count": int(baris["bus_count"]),
                "truck_count": int(baris["truck_count"]),
                "vehicle_count": int(baris["vehicle_count"]),
            })

    return rows


def build_departure_curve(rows):
    """
    FUNGSI MURNI: list-of-dict masuk, kurva keberangkatan keluar.

        {approach: [(detik_simulasi, kelas_kendaraan), ...]}

    Cara kerjanya:

    1. Jumlahkan lintas-LAJUR pada tiap detik — SUMO butuh total satu
       lengan, bukan pecahan per lajur.
    2. Pecahan kelasnya diambil APA ADANYA dari car/motorcycle/bus/
       truck_count, bukan lewat proporsi. Keempat kolom itu memang
       berjumlah persis vehicle_count (dijamin di write_csv modul CV),
       jadi tidak ada yang perlu dibagi-bagi atau dibulatkan.
    3. Detik simulasi dihitung relatif terhadap timestamp paling awal
       di seluruh CSV, sehingga sepuluh window berjalan BERURUTAN
       sebagai satu simulasi 2.940 detik — bukan sepuluh potong
       300 detik yang terpisah.

    Detik yang tidak punya baris tidak menghasilkan keberangkatan.
    Itu benar: rekaman aslinya memang berlubang di sambungan keping,
    dan mengisinya berarti mengarang lalu lintas.
    """
    if not rows:
        return {}, None

    t0 = min(r["timestamp"] for r in rows)

    # (approach, detik) -> {kelas: jumlah}
    per_detik = defaultdict(lambda: defaultdict(int))

    for row in rows:

        detik = int((row["timestamp"] - t0).total_seconds())

        for kolom, (prefix, _) in KELAS.items():
            if row[kolom]:
                per_detik[(row["approach"], detik)][prefix] += row[kolom]

    kurva = defaultdict(list)

    for (approach, detik), kelas_jumlah in per_detik.items():
        for prefix, jumlah in kelas_jumlah.items():
            for _ in range(jumlah):
                kurva[approach].append((detik, prefix))

    for approach in kurva:
        kurva[approach].sort(key=lambda x: x[0])

    return dict(kurva), t0


def ringkas_kurva(kurva):
    """Total kendaraan per lengan dari kurva — buat uji kekekalan."""
    return {a: len(v) for a, v in sorted(kurva.items())}


# ============================================================
# 2. BERKAS RUTE
# ============================================================

def pilih_tujuan(approach, rng):
    """Arah keluar, diundi berbobot PROPORSI_BELOK."""
    arah = rng.choices(
        list(PROPORSI_BELOK.keys()),
        weights=list(PROPORSI_BELOK.values()),
        k=1
    )[0]

    return BELOKAN[approach][arah], arah


def write_route_file(kurva, path, seed=SEED):
    """
    Menulis berkas rute SUMO dari kurva keberangkatan.

    Tiap kendaraan dapat <vehicle depart="T"> dengan T = detik aslinya,
    dan rute eksplisit hulu -> mulut lengan -> keluar.

    id kendaraan memuat lengan asal (mis. "veh_north_00123") supaya saat
    replay nanti keberangkatan bisa dihitung per lengan tanpa perlu
    tabel bantu.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)

    rng = random.Random(seed)

    semua = []

    for approach, kejadian in kurva.items():
        for detik, prefix in kejadian:
            edge_keluar_arah, arah = pilih_tujuan(approach, rng)

            semua.append({
                "depart": detik,
                "approach": approach,
                "prefix": prefix,
                "edges": " ".join([
                    EDGE_HULU[approach],
                    EDGE_MASUK[approach],
                    EDGE_KELUAR[edge_keluar_arah],
                ]),
                "arah": arah,
            })

    # SUMO menuntut <vehicle> terurut menaik menurut depart.
    semua.sort(key=lambda v: (v["depart"], v["approach"]))

    vtypes = {
        "motorcycle": ("motorcycle", 2.2, 0.9),
        "veh":        ("passenger",  5.0, 1.8),
        "bus":        ("bus",       12.0, 2.5),
        "truck":      ("truck",     10.0, 2.5),
    }

    with open(path, "w", encoding="utf-8") as f:

        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<!-- DIBUAT OTOMATIS oleh replay_from_csv.py.\n")
        f.write("     Waktu berangkat = detik crossing asli dari CSV CV.\n")
        f.write("     Arah belok = asumsi PROPORSI_BELOK, BUKAN data. -->\n")
        f.write("<routes>\n")

        for prefix, (vclass, panjang, lebar) in vtypes.items():
            f.write(
                f'    <vType id="{prefix}" vClass="{vclass}" '
                f'length="{panjang}" width="{lebar}" '
                f'departLane="best" departSpeed="max"/>\n'
            )

        f.write("\n")

        urut = defaultdict(int)

        for v in semua:
            urut[v["approach"]] += 1

            f.write(
                f'    <vehicle id="{v["prefix"]}_{v["approach"]}_'
                f'{urut[v["approach"]]:05d}" type="{v["prefix"]}" '
                f'depart="{v["depart"]}">\n'
                f'        <route edges="{v["edges"]}"/>\n'
                f'    </vehicle>\n'
            )

        f.write("</routes>\n")

    return path, semua


# ============================================================
# 3. EKSEKUSI TRACI
# ============================================================

def run_replay(route_path, durasi_detik, gui=False, quiet=True):
    """
    Menjalankan replay dan MENGHITUNG keberangkatan nyata per lengan.

    TraCI di sini cuma alat ukur — penyisipan kendaraan ditangani SUMO
    dari berkas rute. Yang dicatat:

      berangkat  : benar-benar masuk jaringan
      tertahan   : masih mengantre di ujung simulasi karena mulut
                   lengannya penuh (SUMO menyebutnya pending)
    """
    # checkBinary(), BUKAN string "sumo" mentah.
    #
    # SUMO di proyek ini dipasang sebagai paket pip di dalam venv, jadi
    # binernya cuma ada di PATH kalau venv-nya sedang aktif. Skrip yang
    # memanggil "sumo" langsung akan mati dengan WinError 2 begitu
    # dijalankan lewat path interpreter penuh tanpa Activate.ps1.
    # checkBinary() menyelesaikannya dari $SUMO_HOME/bin.
    biner = sumolib.checkBinary("sumo-gui" if gui else "sumo")

    perintah = [
        biner,
        "-n", NET_PATH,
        "-r", route_path,
        "--step-length", "1",
        "--no-step-log",
        "--duration-log.statistics",
    ]

    if quiet:
        perintah.append("--no-warnings")

    traci.start(perintah)

    tls_id = traci.trafficlight.getIDList()[0]

    berangkat = defaultdict(int)

    langkah = 0

    while langkah < durasi_detik:

        traci.simulationStep()

        for vid in traci.simulation.getDepartedIDList():
            # id berbentuk "<prefix>_<approach>_<urut>"
            berangkat[vid.split("_")[1]] += 1

        langkah += 1

    tertahan = traci.simulation.getPendingVehicles()

    tertahan_per_lengan = defaultdict(int)
    for vid in tertahan:
        tertahan_per_lengan[vid.split("_")[1]] += 1

    sisa_di_jaringan = traci.vehicle.getIDCount()

    traci.close()

    return {
        "tls_id": tls_id,
        "berangkat": dict(berangkat),
        "tertahan": dict(tertahan_per_lengan),
        "sisa_di_jaringan": sisa_di_jaringan,
    }


# ============================================================
# MAIN
# ============================================================

def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV_PATH

    print("=" * 70)
    print("REPLAY DEMAND CSV -> SUMO")
    print("=" * 70)
    print(f"CSV     : {csv_path}")
    print(f"Network : {NET_PATH}")
    print()

    rows = load_raw_rows(csv_path)
    print(f"Baris CSV terbaca : {len(rows)}")

    kurva, t0 = build_departure_curve(rows)

    diminta = ringkas_kurva(kurva)

    durasi = max(
        d for kejadian in kurva.values() for d, _ in kejadian
    ) + 1

    print(f"Mulai rekaman     : {t0}")
    print(f"Durasi simulasi   : {durasi} detik "
          f"({durasi / 60:.1f} menit)")
    print(f"Kendaraan diminta : {sum(diminta.values())}")
    print()

    # ---- sanity: kurva memang tidak rata ----
    print("Sebaran per detik (contoh north, 60 detik pertama):")
    per_detik_north = defaultdict(int)
    for d, _ in kurva.get("north", []):
        per_detik_north[d] += 1
    baris = " ".join(
        str(per_detik_north.get(d, 0)) for d in range(60)
    )
    print(f"  {baris}")
    print()

    path, semua = write_route_file(kurva, ROUTE_OUT)
    print(f"Berkas rute       : {path}")

    arah_pakai = defaultdict(int)
    for v in semua:
        arah_pakai[v["arah"]] += 1
    total_arah = sum(arah_pakai.values())
    print(
        "Sebaran belok     : " + ", ".join(
            f"{k} {v} ({v / total_arah:.1%})"
            for k, v in sorted(arah_pakai.items())
        )
    )
    print()

    print("Menjalankan SUMO (headless)...")
    hasil = run_replay(path, durasi)

    print(f"TLS               : {hasil['tls_id']}")
    print()

    print("=" * 70)
    print("UJI KEKEKALAN — diminta (CSV) vs berangkat (SUMO)")
    print("=" * 70)
    print(f"{'lengan':<8}{'diminta':>10}{'berangkat':>12}"
          f"{'tertahan':>11}{'selisih':>10}{'%':>8}")

    total_d = total_b = 0

    for a in ["north", "south", "east", "west"]:
        d = diminta.get(a, 0)
        b = hasil["berangkat"].get(a, 0)
        t = hasil["tertahan"].get(a, 0)
        total_d += d
        total_b += b
        print(
            f"{a:<8}{d:>10}{b:>12}{t:>11}{b - d:>10}"
            f"{(b / d * 100 if d else 0):>7.1f}%"
        )

    print(
        f"{'TOTAL':<8}{total_d:>10}{total_b:>12}"
        f"{sum(hasil['tertahan'].values()):>11}"
        f"{total_b - total_d:>10}"
        f"{(total_b / total_d * 100 if total_d else 0):>7.1f}%"
    )

    print()
    print(f"Masih di jaringan saat simulasi berhenti: "
          f"{hasil['sisa_di_jaringan']}")


if __name__ == "__main__":
    main()
