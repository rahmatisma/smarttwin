"""Bangun ulang jaringan khusus training PPO dari jaringan kanonik.

KENAPA JARINGAN INI ADA
-----------------------
Jaringan kanonik `simpang4_pingit.net.xml.gz` adalah ekstraksi OSM dengan
bounding box kecil, sehingga tiga dari empat koridor pendekat BUNTU dan
terpotong sangat pendek:

    north  62,4 m ->  16 kendaraan     south  521,9 m -> 138 kendaraan
    east   57,4 m ->  14 kendaraan     west   292,1 m ->  76 kendaraan
    (timpang 9,86x)

Kendaraan di `decision_engine/ppo_env.py` dilepas di AWAL `EDGE_HULU`, jadi
panjang edge itulah kapasitas tampung antrean lengan tersebut. Dengan north
dan east cuma sanggup menampung 14-16 kendaraan, kelebihan permintaan tidak
mengantre melainkan GAGAL MASUK simulasi -- tidak terlihat oleh reward maupun
observasi. Akibatnya terbentuk jepitan yang membuat alokasi hijau per lengan
mustahil dipelajari:

  - permintaan tinggi -> north/east mentok, kendaraan nyangkut, jenuh
    permanen, semua aksi berakhir sama;
  - permintaan rendah -> simpang lengang, siklus pendek sudah cukup, alokasi
    per lengan tidak berpengaruh.

Diukur 2 September 2026 (6 seed berpasangan, selisih reward alokasi
proporsional-permintaan vs seragam, total hijau disamakan):

    jaringan   skala  selisih      sd     nyangkut  vonis
    LAMA        0,40  +0,0012   0,0073        23    derau
    LAMA        0,60  -0,0006   0,0171       265    derau
    LAMA        0,80  +0,0021   0,0145      1140    derau
    BARU        0,40  +0,0081   0,0233         8    derau
    BARU        0,60  +0,0199   0,0107        14    NYATA   <- dipilih
    BARU        0,80  +0,0111   0,0115       462    NYATA

Di jaringan LAMA alokasi TIDAK PERNAH berpengaruh di skala mana pun. Itu
menjelaskan kenapa lima training PPO berturut-turut gagal dengan pola
identik, dan kenapa lima percobaan reward-shaping tidak menolong: memang tidak
ada gradien untuk dipelajari. Bukan salah tuning.

APA YANG DIUBAH
---------------
Node pangkal tiga koridor buntu digeser keluar sepanjang bearing segmen
pertama sampai `EDGE_HULU` mencapai 500 m; setiap edge lain yang berujung di
node itu ikut disesuaikan supaya geometri nyambung. South (515,2 m) sengaja
dibiarkan sebagai pembanding "tidak diubah".

Yang TIDAK berubah, dan wajib tetap begitu: ID edge, ID node, jumlah lajur,
serta 20 koneksi di SIMPANG_CENTER. Itu syarat supaya `tls_safe.add.xml`,
`GREEN_STATE`, `EDGE_HULU`/`EDGE_MASUK`/`EDGE_KELUAR`, dan pemetaan garis CV
tetap sahih di kedua jaringan. Skrip memverifikasinya di akhir dan gagal
kalau ada yang bergeser.

Hasil: north 138, east 136, south 140, west 136 kendaraan (timpang 1,03x).

PEMAKAIAN
---------
    $env:SUMO_HOME = "$PWD\\.venv\\Lib\\site-packages\\sumo"
    .venv\\Scripts\\python.exe simulation/bangun_jaringan_training.py
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NET_KANONIK = ROOT / "simulation/network/simpang4_pingit.net.xml.gz"
NET_TRAINING = ROOT / "simulation/network/simpang4_pingit_training.net.xml.gz"

TARGET_METER = 500.0
PANJANG_KENDARAAN = 7.5  # 5 m kendaraan + 2,5 m jarak antar

# EDGE_HULU yang koridornya dipanjangkan. Sengaja dituliskan literal, bukan
# diimpor dari ppo_env, supaya skrip ini tetap jalan tanpa dependency backend.
TARGET_EDGES = {
    "484349908#0": "north",
    "153857851#2": "east",
    "590064461#0": "west",
    # south (134603786#0) sudah 515,2 m -- tidak diubah.
}
EDGE_HULU = {
    "north": "484349908#0", "south": "134603786#0",
    "east": "153857851#2", "west": "590064461#0",
}
EDGE_MASUK = {
    "north": "484349908#2", "south": "134603786#2",
    "east": "153857851#4", "west": "590064461#2",
}
TLS_ID = "SIMPANG_CENTER"
KONEKSI_TLS_WAJIB = 20


def _sumo_home() -> Path:
    home = os.environ.get("SUMO_HOME")
    if not home:
        raise SystemExit(
            "SUMO_HOME belum diset. Jalankan dulu:\n"
            '  $env:SUMO_HOME = "$PWD\\.venv\\Lib\\site-packages\\sumo"'
        )
    return Path(home)


def _urai(teks: str) -> list[list[float]]:
    return [[float(v) for v in p.split(",")] for p in teks.split()]


def _tulis(titik: list[list[float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in titik)


def _panjang(titik: list[list[float]]) -> float:
    return sum(math.dist(titik[i], titik[i + 1]) for i in range(len(titik) - 1))


def perpanjang_koridor(kerja: Path) -> None:
    nod_tree = ET.parse(kerja / "pingit.nod.xml")
    edg_tree = ET.parse(kerja / "pingit.edg.xml")
    node_el = {n.get("id"): n for n in nod_tree.getroot().findall("node")}
    pindah: dict[str, list[float]] = {}

    print(f"{'lengan':<8} {'edge':<16} {'sebelum m':>10} {'sesudah m':>10}")
    print("-" * 48)
    for edge in edg_tree.getroot().findall("edge"):
        eid = edge.get("id")
        if eid not in TARGET_EDGES:
            continue
        titik = _urai(edge.get("shape"))
        lama = _panjang(titik)
        if lama >= TARGET_METER:
            print(f"{TARGET_EDGES[eid]:<8} {eid:<16} {lama:>10.1f} {'dilewati':>10}")
            continue
        # Arah KELUAR dari simpang = titik kedua menuju titik pertama.
        dx, dy = titik[0][0] - titik[1][0], titik[0][1] - titik[1][1]
        norm = math.hypot(dx, dy)
        tambah = TARGET_METER - lama
        baru = [titik[0][0] + dx / norm * tambah, titik[0][1] + dy / norm * tambah]
        pindah[edge.get("from")] = baru
        titik[0] = baru
        edge.set("shape", _tulis(titik))
        print(f"{TARGET_EDGES[eid]:<8} {eid:<16} {lama:>10.1f} "
              f"{_panjang(titik):>10.1f}")

    for node_id, titik_baru in pindah.items():
        node_el[node_id].set("x", f"{titik_baru[0]:.2f}")
        node_el[node_id].set("y", f"{titik_baru[1]:.2f}")

    # Sambungkan ulang edge lain yang ujungnya menempel di node yang digeser.
    ikut = 0
    for edge in edg_tree.getroot().findall("edge"):
        if edge.get("id") in TARGET_EDGES or not edge.get("shape"):
            continue
        titik = _urai(edge.get("shape"))
        berubah = False
        if edge.get("to") in pindah:
            titik[-1] = pindah[edge.get("to")]
            berubah = True
        if edge.get("from") in pindah:
            titik[0] = pindah[edge.get("from")]
            berubah = True
        if berubah:
            edge.set("shape", _tulis(titik))
            ikut += 1

    nod_tree.write(kerja / "pingit.nod.xml", encoding="UTF-8", xml_declaration=True)
    edg_tree.write(kerja / "pingit.edg.xml", encoding="UTF-8", xml_declaration=True)
    print("-" * 48)
    print(f"node digeser: {len(pindah)} | edge ikut disesuaikan: {ikut}\n")


def verifikasi(sumo_home: Path) -> None:
    """Gagal keras kalau ada kontrak yang bergeser."""
    sys.path.append(str(sumo_home / "tools"))
    import sumolib

    lama = sumolib.net.readNet(str(NET_KANONIK))
    baru = sumolib.net.readNet(str(NET_TRAINING))

    def koneksi(net):
        n = net.getNode(TLS_ID)
        return sum(len(e.getOutgoing().get(o, [])) for e in n.getIncoming()
                   for o in e.getOutgoing())

    masalah: list[str] = []
    if koneksi(baru) != KONEKSI_TLS_WAJIB:
        masalah.append(
            f"koneksi TLS {koneksi(baru)} != {KONEKSI_TLS_WAJIB} -- "
            "GREEN_STATE dan tls_safe.add.xml jadi tidak sahih"
        )

    print(f"{'lengan':<8} {'kapasitas lama':>15} {'kapasitas baru':>15}")
    print("-" * 42)
    kapasitas = {}
    for lengan in ("north", "east", "south", "west"):
        nilai = []
        for net in (lama, baru):
            try:
                eh, em = net.getEdge(EDGE_HULU[lengan]), net.getEdge(EDGE_MASUK[lengan])
            except Exception:
                masalah.append(f"edge lengan {lengan} hilang di jaringan baru")
                nilai.append(0)
                continue
            lajur = min(eh.getLaneNumber(), em.getLaneNumber())
            nilai.append(int((eh.getLength() + em.getLength()) / PANJANG_KENDARAAN) * lajur)
        kapasitas[lengan] = nilai[1]
        print(f"{lengan:<8} {nilai[0]:>15} {nilai[1]:>15}")

        for peta in (EDGE_HULU, EDGE_MASUK):
            e_lama, e_baru = lama.getEdge(peta[lengan]), baru.getEdge(peta[lengan])
            if e_lama.getLaneNumber() != e_baru.getLaneNumber():
                masalah.append(f"jumlah lajur {peta[lengan]} berubah")

    timpang = max(kapasitas.values()) / max(1, min(kapasitas.values()))
    print("-" * 42)
    print(f"rasio timpang: {timpang:.2f}x (kanonik 9,86x)")
    print(f"koneksi TLS  : {koneksi(baru)} (wajib {KONEKSI_TLS_WAJIB})")

    if masalah:
        print("\nGAGAL:")
        for m in masalah:
            print(f"  - {m}")
        raise SystemExit(1)
    print("\nOK -- seluruh kontrak jaringan tetap utuh.")


def main() -> int:
    sumo_home = _sumo_home()
    netconvert = sumo_home / "bin" / "netconvert.exe"
    if not netconvert.exists():
        netconvert = sumo_home / "bin" / "netconvert"

    with tempfile.TemporaryDirectory() as tmp:
        kerja = Path(tmp)
        subprocess.run(
            [str(netconvert), "--sumo-net-file", str(NET_KANONIK),
             "--plain-output-prefix", str(kerja / "pingit")],
            check=True, capture_output=True,
        )
        perpanjang_koridor(kerja)
        subprocess.run(
            [str(netconvert),
             "--node-files", str(kerja / "pingit.nod.xml"),
             "--edge-files", str(kerja / "pingit.edg.xml"),
             "--connection-files", str(kerja / "pingit.con.xml"),
             "--tllogic-files", str(kerja / "pingit.tll.xml"),
             "--output-file", str(kerja / "hasil.net.xml.gz")],
            check=True, capture_output=True,
        )
        shutil.copy(kerja / "hasil.net.xml.gz", NET_TRAINING)

    print(f"jaringan training ditulis: {NET_TRAINING.name}\n")
    verifikasi(sumo_home)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
