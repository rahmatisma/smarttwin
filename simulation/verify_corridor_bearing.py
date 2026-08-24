"""
Verifikasi identitas koridor: cocokkan nama jalan asli (dari tag OSM
'name', masih tersimpan di atribut name= tiap edge network SUMO) dengan
klasifikasi arah mata angin (utara/timur/selatan/barat) yang dipakai CV
& backend (CROSS_LABEL_MAP, DENSITY_LENGAN_MAP di
backend/app/pipeline/cv_csv_bridge.py).

Kenapa perlu: nama lengan di CV (MAGELANG/DIPONEGORO, dari label garis
crossing CCTV_2) ditentukan manual lewat klik cv/kalibrasi_crossing.py,
tanpa verifikasi independen. Skrip ini kroscek klaim itu langsung ke
geometri network hasil netconvert dari OSM -- sumber yang independen
dari proses kalibrasi manual.

Logika bearing SAMA dengan snapshot_dashboard_data.py (0 derajat =
utara, searah jarum jam) -- dipakai ulang di sini secara mandiri
(bukan impor) karena file itu butuh sumolib, sedangkan verifikasi ini
sengaja hanya pakai gzip + xml.etree bawaan Python supaya bisa jalan
tanpa venv simulation/ (paket eclipse-sumo cukup berat untuk sekadar
baca atribut edge).

Jalankan:
    python simulation/verify_corridor_bearing.py

Hasil run 24 Agustus 2026 (dicatat di
docs/pembagian-tugas-24-agustus.md dan docs/audit-24-agustus.md):
    Jalan Diponegoro -> timur   (74.5-93.0 derajat)
    Jalan Magelang   -> utara   (351.8-6.3 derajat)
    Jalan Tentara Pelajar -> selatan (168.7-187.9 derajat)
    Jalan Kyai Mojo  -> barat   (255.1-274.4 derajat)
Cocok persis dengan CROSS_LABEL_MAP di cv_csv_bridge.py -- identitas
koridor timur (Diponegoro) & utara (Magelang) terverifikasi independen.
"""

import gzip
import math
import os
import xml.etree.ElementTree as ET

NET_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "network", "simpang4_pingit.net.xml.gz",
)
CENTER_NODE_ID = "SIMPANG_CENTER"


def classify_direction(angle_deg):
    """0 derajat = utara, searah jarum jam (konvensi kompas) --
    sama persis dengan snapshot_dashboard_data.py."""
    if 45 <= angle_deg < 135:
        return "timur"
    if 135 <= angle_deg < 225:
        return "selatan"
    if 225 <= angle_deg < 315:
        return "barat"
    return "utara"


def main():
    with gzip.open(NET_PATH, "rt", encoding="utf-8") as f:
        root = ET.fromstring(f.read())

    coords = {}
    for junction in root.findall("junction"):
        x, y = junction.get("x"), junction.get("y")
        if x is not None and y is not None:
            coords[junction.get("id")] = (float(x), float(y))

    if CENTER_NODE_ID not in coords:
        raise SystemExit(f"Node {CENTER_NODE_ID} tidak ditemukan di network.")

    cx, cy = coords[CENTER_NODE_ID]

    # Kumpulkan tiap edge bernama yang langsung menyentuh SIMPANG_CENTER,
    # hitung bearing node TETANGGA (bukan center) relatif ke center --
    # itu arah fisik jalan itu memanjang dari simpang.
    street_bearings = {}
    for edge in root.findall("edge"):
        if edge.get("function") == "internal":
            continue
        name = edge.get("name")
        if not name:
            continue

        frm, to = edge.get("from"), edge.get("to")
        neighbor = None
        if frm == CENTER_NODE_ID and to in coords:
            neighbor = to
        elif to == CENTER_NODE_ID and frm in coords:
            neighbor = frm
        if neighbor is None:
            continue

        nx, ny = coords[neighbor]
        angle = math.degrees(math.atan2(nx - cx, ny - cy)) % 360
        street_bearings.setdefault(name, []).append(
            (classify_direction(angle), round(angle, 1), edge.get("id"))
        )

    print(f"{'Jalan':<24} {'Arah':<10} {'Bearing (derajat)':<20} Edge")
    for name, entries in sorted(street_bearings.items()):
        for direction, angle, edge_id in entries:
            print(f"{name:<24} {direction:<10} {angle:<20} {edge_id}")


if __name__ == "__main__":
    main()
