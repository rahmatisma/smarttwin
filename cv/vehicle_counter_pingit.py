"""
SMARTTWIN — PERCOBAAN LOGIKA ZONA (bukan crossing)

Salinan kerja dari vehicle_counter.py yang MENGGANTI logika hitungnya.
File aslinya tidak disentuh sama sekali; ini eksperimen terpisah.

    vehicle_counter.py   ALIRAN    — kendaraan yang MEMOTONG garis hitung
    file ini             KEHADIRAN — kendaraan yang ADA DI DALAM zona

Pipeline:
    Video
      |
    YOLO26s + ByteTrack
      |
    Titik tengah bbox: cx=(x1+x2)/2, cy=(y1+y2)/2
      |
    point_in_polygon(cx, cy, zona)        <- ray casting
      |
    Jumlah kendaraan di dalam zona, PER FRAME
      |
    Rata-rata per jendela 5 detik
      |
    cv/output/percobaan_logic_simpang.csv


BEDANYA DENGAN CROSSING — kenapa angkanya tidak sebanding
---------------------------------------------------------
Crossing itu ALIRAN: satu kendaraan menyumbang SATU kali seumur
hidupnya, tepat saat ia memotong garis. Zona ini KEHADIRAN: satu
kendaraan yang berhenti di dalam zona menyumbang di SETIAP frame
selama ia masih di situ.

Konsekuensinya, dan ini penting sebelum angkanya dipakai:

  - Angka zona TIDAK bisa dibandingkan dengan kolom vehicle_count
    di smarttwin_traffic_data.csv. Satuannya beda — yang satu
    kendaraan/detik, yang satu kendaraan (cacah sesaat).
  - Angka zona naik saat lampu MERAH (kendaraan menumpuk diam) dan
    turun saat HIJAU. Crossing kebalikannya. Jangan kaget kalau
    grafiknya berlawanan fase.
  - Yang sepadan dengan zona ini adalah kolom queue_length_veh dan
    density_index di CSV lama, bukan kolom volume.

Ini justru bisa jadi kelebihannya: untuk mengukur KEPADATAN simpang
(yang dibutuhkan Decision Engine buat memutuskan lengan mana yang
perlu hijau lebih lama), cacah kehadiran memang ukuran yang lebih
langsung daripada laju crossing.


YANG DIWARISI DARI FILE ASLI
----------------------------
Model, confidence, daftar kelas, dan mesin jam dinding diimpor
LANGSUNG dari vehicle_counter.py, bukan disalin ulang. Jadi kalau
konfigurasi di sana berubah, eksperimen ini ikut berubah dan tidak
diam-diam memakai angka basi. File aslinya dijaga
`if __name__ == "__main__":` sehingga impor ini tidak menjalankan
proses 4-kamera apa pun (pola yang sama sudah dipakai
process_uploaded_video.py).

Timestamp memakai JAM REKAMAN dari sync_report.json, bukan
datetime.now() — supaya barisnya bisa disandingkan dengan CSV lama
pada detik yang sama.


YANG SENGAJA TIDAK ADA DI SINI
------------------------------
Tidak ada kolom crossing, tidak ada lane_id, tidak ada estimasi
antrean dalam meter, tidak ada filter ARAH_MASUK. Zona tidak punya
arah — kendaraan yang masuk simpang dan yang keluar simpang
dihitung sama saja selama titik tengahnya ada di dalam poligon.
Itu batas yang melekat pada pendekatan ini, bukan yang belum
sempat dikerjakan.

Cara pakai:
    python vehicle_counter_copy.py                 # 5 menit pertama
    python vehicle_counter_copy.py --durasi 600    # 10 menit
    python vehicle_counter_copy.py --langkah 1     # tiap frame (lambat)
"""

import argparse
import concurrent.futures
import csv
import os
import sys

import cv2
import imageio_ffmpeg
import numpy as np
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Konfigurasi diwarisi dari file asli — jangan disalin ulang di sini.
from vehicle_counter import (  # noqa: E402
    CONFIDENCE,
    MODEL_PATH,
    TRACK_CLASSES,
    VIDEO_DIR,
    muat_peta_jam,
)

# Modul upload HF/Supabase punya proyek ini sendiri (dipakai juga
# oleh process_uploaded_video.py) -- dipakai apa adanya, bukan
# ditulis ulang. Lihat upload_dan_update() soal kenapa pola INSERT +
# fileUrl proxy backend dipilih, bukan UPDATE baris existing.
import hf_writer as hw  # noqa: E402
import supabase_writer as sw  # noqa: E402


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CSV_PATH = os.path.join(
    OUTPUT_DIR,
    "percobaan_logic_simpang.csv"
)

# CSV terpisah untuk hasil crossing-line (lihat CROSSING_LINES) --
# beda metrik dari zona (ALIRAN, bukan KEHADIRAN), jadi disengaja
# tidak dicampur satu file dengan CSV_PATH.
CROSSING_CSV_PATH = os.path.join(
    OUTPUT_DIR,
    "crossing_simpang.csv"
)

# CSV terpisah lagi untuk SNAPSHOT per detik -- bacaan mentah frame
# TERAKHIR yang diproses tiap detik, TIDAK dirata-rata seperti
# CSV_PATH. Dibuat buat tampilan yang terasa "hidup" (angka naik-
# turun tiap detik mengikuti kendaraan masuk/keluar zona), beda
# tujuan dari CSV_PATH yang buat angka analitis stabil.
SNAPSHOT_CSV_PATH = os.path.join(
    OUTPUT_DIR,
    "snapshot_zona.csv"
)


# ============================================================
# JENDELA WAKTU
# ============================================================
#
# 5 detik, dan isinya RATA-RATA cacah per frame di dalam jendela
# itu — bukan jumlah. Menjumlahkan kehadiran antar-frame akan
# menghitung kendaraan diam yang sama berkali-kali; persis
# kesalahan yang sedang terjadi di backend/app/pipeline/
# traffic_state_builder.py (queue di-sum lintas detik).

WINDOW_DETIK = 5


# ============================================================
# ZONA KEPADATAN
# ============================================================
#
# Poligon dalam RASIO 0.0-1.0 terhadap lebar/tinggi frame, satuan
# yang sama dengan COUNTING_LINES di file asli — jadi zona ini
# ikut aman kalau resolusi videonya berubah.
#
# Nilai di bawah adalah usulan awal yang SUDAH DIKOREKSI setelah
# melihat frame nyata (t=30 detik) tiap kamera. Usulan aslinya
# ditulis di komentar tiap entri supaya bisa dikembalikan dengan
# satu baris edit.
#
# CATATAN PENAMAAN LENGAN — tolong dibaca sebelum mengubah:
# nama lengan di bawah mengikuti pemetaan yang sudah dikonfirmasi
# dari screenshot CCTV + peta lokasi (lihat bagian 2
# vehicle_counter.py), BUKAN nomor kameranya:
#
#     CCTV_1 = Pingit 1 = Jl. Tentara Pelajar     -> SELATAN
#     CCTV_2 = Pingit 2 = Jl. Magelang            -> UTARA
#     CCTV_3 = Pingit 3 = Jl. Kyai Mojo           -> BARAT
#     CCTV_4 = Pingit 4 = Jl. P. Diponegoro       -> TIMUR
#
# Nomor kamera dan arah mata angin memang tidak berurutan. Versi
# lama kode ini pernah tertukar persis di CCTV 1 dan CCTV 2.

ZONA_KEPADATAN = {

    "CCTV_1": {
        # Jl. Tentara Pelajar — ruas lurus. Pita mengikuti SUMBU
        # JALAN dan menyempit ke kanan-atas mengikuti titik hilang,
        # bukan kotak mendatar.
        #
        # Riwayat:
        #   v1 (kotak)  [(0.10,0.50),(0.90,0.50),(0.90,0.80),(0.10,0.80)]
        #   v2 (kerb)   [(0.10,0.50),(0.86,0.50),(0.74,0.80),(0.10,0.80)]
        #   v3          [(0.02,0.72),(0.84,0.13),(0.88,0.19),(0.10,0.92)]
        #               Pembacaan pertama coretan biru. Terlalu
        #               sempit: pita memotong lajur antrean secara
        #               diagonal, motor di tepi kerb jatuh di LUAR
        #               (terlihat sebagai titik merah pada bukti),
        #               dan separuh kiri pita malah menutup aspal
        #               kosong lajur berlawanan.
        #   v4          [(0.00,0.80),(0.84,0.13),(0.90,0.21),(0.38,1.00)]
        #               Pita dilebarkan ke bawah-kanan sampai
        #               memeluk seluruh lajur menuju stop line,
        #               termasuk deretan motor di tepi kerb.
        #               Dibaca dari coretan dua garis biru pada
        #               frame 22 Agustus 2026 (17:41), sejajar
        #               sumbu jalan dan menyempit ke titik hilang
        #               di kanan atas.
        #   v5          [(0.00,0.75),(0.65,0.00),(1.00,0.15),(0.20,1.00)]
        #               Parallelogram diagonal mengikuti area antara
        #               dua garis merah pada frame, sejajar
        #               perspektif jalan.
        #   v6 SEKARANG — dikalibrasi langsung lewat klik interaktif
        #               (cv/kalibrasi_zona.py --kamera CCTV_1),
        #               bukan tebak-tebakan rasio manual lagi.
        "polygon": [
            (0.14, 0.70),
            (0.58, 1.00),
            (0.84, 0.10),
            (0.78, 0.08),
        ],
        "nama_lengan": "selatan",
    },

    "CCTV_2": {
        # Jl. Magelang — kameranya memotret BADAN SIMPANG
        # (ada pulau bundaran di tengah frame), bukan ruas lurus.
        # Karena itu labelnya simpang_tengah, bukan "utara":
        # kendaraan di zona ini berbelok ke segala arah, jadi
        # angkanya kepadatan simpang, bukan kepadatan satu lengan.
        #
        # Riwayat:
        #   v1 (kotak)  [(0.20,0.15),(0.80,0.15),(0.80,0.75),(0.20,0.75)]
        #   v2 (kotak)  tepi atas dinaikkan ke 0.30 supaya tidak
        #               memakan atap/baliho di atas cakrawala
        #   v3          [(0.29,0.21),(0.37,0.21),(0.50,0.35),(0.62,0.43),
        #                (0.73,0.47),(0.60,0.52),(0.45,0.58),(0.39,0.60)]
        #                Baji mengikuti coretan biru: sisi kiri
        #                menyusuri mulut koridor Magelang, sisi kanan
        #                melengkung mengikuti arus yang membelok ke
        #                timur.
        #   v4 SEKARANG — dikalibrasi langsung lewat klik interaktif
        #                (cv/kalibrasi_zona.py --kamera CCTV_2).
        "polygon": [
            (0.30, 0.23),
            (0.36, 0.49),
            (0.61, 0.47),
            (0.38, 0.22),
        ],
        "nama_lengan": "simpang_tengah",
    },

    "CCTV_3": {
        # Jl. Kyai Mojo — dua arah dipisah median bergaris
        # hitam-putih. Zona hanya mengambil jalur ATAS median,
        # yaitu jalur yang MENUJU simpang (terverifikasi lewat
        # optical flow: vx=+5,6..+7,8 di jalur atas, vx=-12..-18
        # di jalur bawah — lihat COUNTING_LINES["west"] di file
        # asli).
        #
        # Riwayat:
        #   v1 (kotak)  [(0.00,0.25),(1.00,0.25),(1.00,0.60),(0.00,0.60)]
        #   v2 (miring) tepi atas dimiringkan supaya tidak memakan
        #               pekarangan berpagar berisi kendaraan parkir
        #   v3          [(0.19,0.29),(0.92,0.55),(0.89,0.78),(0.09,0.35)]
        #               Pita sejajar sumbu jalan, dibaca dari coretan
        #               dua garis biru. Menipis di kiri (jauh) dan
        #               menebal di kanan (dekat kamera), sesuai
        #               perspektif lajur berlebar tetap.
        #   v4 SEKARANG — dikalibrasi langsung lewat klik interaktif
        #               (cv/kalibrasi_zona.py --kamera CCTV_3).
        "polygon": [
            (0.11, 0.36),
            (0.84, 0.75),
            (0.96, 0.54),
            (0.21, 0.32),
        ],
        "nama_lengan": "barat",
    },

    "CCTV_4": {
        # Jl. P. Diponegoro.
        #
        # Riwayat:
        #   v1 SEKARANG — dikalibrasi langsung lewat klik interaktif
        #               (cv/kalibrasi_zona.py --kamera CCTV_4).
        "polygon": [
            (0.79, 0.28),
            (0.56, 0.44),
            (0.72, 0.49),
            (0.84, 0.30),
        ],
        "nama_lengan": "timur",
    },
}


# ============================================================
# GARIS CROSSING (kalibrasi cv/kalibrasi_crossing.py)
# ============================================================
#
# Aktif dipakai lewat hitung_crossing() -- hasilnya ditulis ke
# CROSSING_CSV_PATH (crossing_simpang.csv), terpisah dari CSV zona
# (ZONA_KEPADATAN) karena beda metrik: ALIRAN (crossing), bukan
# KEHADIRAN (zona).
#
# CCTV_2 dapat DUA garis (bukan satu) karena framenya memotret dua
# lengan sekaligus -- Jl. Magelang dan Jl. P. Diponegoro -- persis
# skenario yang dijelaskan di docstring kalibrasi_crossing.py.
#
# CCTV_4 SENGAJA tidak ada di sini (garis_untuk_kamera balikin []
# untuknya). Sudut kameranya tidak menangkap crossing kendaraan dari
# arah Jl. P. Diponegoro dengan jelas -- garis "DIPONEGORO" milik
# CCTV_2 di atas itu sumber crossing sah utk lengan timur. Zona
# CCTV_4 (ZONA_KEPADATAN) tetap dipakai terpisah untuk density timur,
# bukan volume/crossing -- lihat CROSS_LABEL_MAP & DENSITY_LENGAN_MAP
# di backend/app/pipeline/cv_csv_bridge.py untuk pemetaan lengkapnya.

CROSSING_LINES = {
    "CCTV_1": {
        "x1": 0.49, "y1": 1.00, "x2": 0.14, "y2": 0.67,
    },
    "CCTV_2": {
        "MAGELANG": {"x1": 0.31, "y1": 0.53, "x2": 0.63, "y2": 0.49},
        "DIPONEGORO": {"x1": 0.86, "y1": 0.70, "x2": 0.75, "y2": 0.46},
    },
    "CCTV_3": {
        "x1": 0.86, "y1": 0.78, "x2": 0.98, "y2": 0.53,
    },
}


# ============================================================
# RESOLUSI INFERENSI YOLO
# ============================================================
#
# 1280, bukan default 640. Alasannya terukur: pada run 640,
# pangsa motor di zona cuma 17-21% untuk CCTV_2 dan CCTV_3,
# padahal motor 79,3% dari seluruh crossing pada CSV 49 menit.
# Motor di ujung jauh frame cuma beberapa piksel dan hilang di
# imgsz 640. Karena motor mayoritas mutlak arus di simpang ini,
# kehilangan itu langsung merusak angka kepadatannya.
#
# Biayanya waktu inferensi naik kira-kira 2-3x.

IMGSZ = 1280


# ============================================================
# PEMETAAN KELAS YOLO -> NAMA KOLOM CSV
# ============================================================
#
# Id-nya sama persis dengan VEHICLE_CLASSES di file asli, cuma
# namanya diindonesiakan supaya cocok dengan kolom CSV percobaan
# ini. person (0) dan bicycle (1) tetap ikut dideteksi lewat
# TRACK_CLASSES supaya ByteTrack punya konteks yang sama seperti
# di file asli, tapi TIDAK pernah masuk hitungan zona.

KELAS_KE_KOLOM = {
    3: "motor",
    2: "mobil",
    7: "truk",
    5: "bus",
}


# ============================================================
# PARAMETER ANTREAN
# ============================================================
#
# Diadaptasi dari vehicle_counter.py (yang punya logika antrean asli,
# dipakai jalur upload video manual) -- BUKAN disalin mentah, karena
# file itu kerja di piksel mentah + titik tengah bbox, sedangkan file
# ini kerja di rasio 0.0-1.0 + titik acuan roda (y2). Lihat diskusi
# 25 Agustus, lihat docs/hasil-run-antrean-25-agustus.md.
#
# Kendaraan dianggap "sedang antre" kalau SEMUA syarat ini benar:
#   1. Titik acuannya ada di dalam zona lengan ini (sudah dicek oleh
#      hitung_kendaraan_di_zona, dipakai ulang di hitung_antrean)
#   2. Pergeseran posisi antar-frame di bawah ANTREAN_GERAK_RASIO_MAKS
#   3. Sudah "hampir diam" minimal ANTREAN_MIN_FRAME_DIAM frame
#      berturut-turut

# Ambang gerak antar-frame dalam RASIO (bukan piksel). Konversi kasar
# dari 3.0 piksel (nilai asli vehicle_counter.py) di frame lebar
# ~1280px -> ~0.0023, dibulatkan naik ke 0.004.
#
# KOREKSI 25 Agustus (review kode) -- komentar sebelumnya bilang
# "lebih toleran", itu TIDAK akurat: hitung_antrean() cuma dipanggil
# tiap frame yang LOLOS --langkah (default 5, lihat proses_tick()),
# jadi dua posisi yang dibandingkan sebenarnya berjarak 5 frame video
# ASLI (~0.2 detik di 25fps), bukan 1 frame seperti asumsi konversi
# di atas. Dalam satuan kecepatan (gerak per frame asli), ambang
# efektifnya jadi ~3x LEBIH KETAT dari 3px/frame yang asli, bukan
# lebih toleran. BUTUH DIKALIBRASI ULANG setelah lihat hasil run
# sungguhan -- angka ini titik awal, bukan final.
ANTREAN_GERAK_RASIO_MAKS = 0.004

# Minimal 5 KALI proses_tick() (bukan 5 frame video asli, lihat
# koreksi di atas) berturut-turut gerak kecil sebelum dianggap benar-
# benar antre. Dengan --langkah default 5 di ~25fps, ini setara ~1
# detik nyata -- BEDA dari vehicle_counter.py aslinya (~0.2 detik,
# karena skrip itu tidak melompati frame yang sama). Kebetulan 1
# detik lebih masuk akal buat "antre" (bukan cuma jeda sesaat), tapi
# ini kebetulan, bukan hasil kalibrasi sengaja -- perlu dicek ulang
# saat lihat hasil run sungguhan.
ANTREAN_MIN_FRAME_DIAM = 5

# Jumlah lajur per lengan -- diambil dari tabel `lanes` di Supabase
# (dicek 25 Agustus 2026). BUKAN ditebak: barat memang cuma 1 lajur,
# tiga lengan lain 2 lajur. Kalau kalibrasi lajur berubah di database,
# perbarui juga angka di sini.
#
# KEY-nya harus persis nama_lengan yang dihasilkan ZONA_KEPADATAN di
# file INI (selatan/simpang_tengah/barat/timur) -- BUKAN nama approach
# konseptual di backend (utara/selatan/timur/barat). CCTV_2 nama_lengan-
# nya "simpang_tengah" (bukan "utara"), sengaja dipetakan ke "utara"
# di cv_csv_bridge.py::DENSITY_LENGAN_MAP sebagai proxy -- lihat
# catatan di sana. Ditemukan 25 Agustus (review kode): sebelum
# diperbaiki, key "utara" di sini tidak pernah cocok, jadi
# simpang_tengah diam-diam jatuh ke default 1 lajur.
LAJUR_PER_LENGAN = {
    "selatan": 2,
    "simpang_tengah": 2,  # proxy utara, sama seperti DENSITY_LENGAN_MAP
    "timur": 2,
    "barat": 1,
}

# Sama seperti vehicle_counter.py -- ESTIMASI KESEPAKATAN TIM, BUKAN
# kutipan dari tabel resmi PKJI 2023. Jangan dipresentasikan sebagai
# angka standar kalau ditanya juri.
QUEUE_SPACE_M = {
    "motor": 2,
    "mobil": 5,
    "bus": 10,
    "truk": 10,
}


# ============================================================
# GEOMETRI
# ============================================================

def point_in_polygon(px, py, polygon):
    """
    Cek apakah titik (px, py) ada di dalam polygon.

    Ray casting: tarik sinar horizontal ke kanan dari titik itu,
    hitung berapa kali ia memotong sisi poligon. Ganjil = di
    dalam, genap = di luar.

    px/py dan isi polygon sama-sama dalam RASIO 0.0-1.0.
    """
    n = len(polygon)
    inside = False
    j = n - 1

    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        ):
            inside = not inside

        j = i

    return inside


def sisi_garis(px, py, p1, p2):
    """
    Sisi titik (px, py) relatif garis p1->p2, lewat tanda cross
    product (x2-x1)(py-y1) - (y2-y1)(px-x1). Positif di satu sisi,
    negatif di sisi lain, 0 kalau persis di garis.

    px/py dan p1/p2 sama-sama RASIO 0.0-1.0, konsisten dengan
    point_in_polygon(). Dipakai hitung_crossing() untuk mendeteksi
    kendaraan yang berpindah sisi antar-frame -- itu tandanya
    melintasi garis.
    """
    x1, y1 = p1
    x2, y2 = p2

    return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)


def mapping_class(class_id):
    """
    Id kelas YOLO -> nama kolom CSV. None kalau bukan kendaraan
    (person/bicycle) atau kelas yang tidak dikenal.
    """
    return KELAS_KE_KOLOM.get(int(class_id))


def hitung_kendaraan_di_zona(
    detections,
    zona_polygon,
    frame_width,
    frame_height,
):
    """
    Hitung kendaraan yang titik tengah bbox-nya ada di dalam zona.

    detections: list dari (x1, y1, x2, y2, class_id, track_id)

    track_id sengaja ikut dibawa walau tidak dipakai menghitung —
    cacah ini murni per frame, jadi tidak perlu identitas objek.
    Dibiarkan di dalam tuple supaya bisa dipakai kalau nanti mau
    menelusuri kendaraan tertentu saat debug.

    Balikannya juga memuat daftar titik untuk visualisasi, supaya
    gambar bukti dan angka CSV dijamin datang dari perhitungan
    yang SAMA — bukan dari dua jalur kode yang bisa berbeda.
    """
    hasil = {
        "total": 0,
        "motor": 0,
        "mobil": 0,
        "truk": 0,
        "bus": 0,
        "titik_dalam": [],
        "titik_luar": [],
        # Kotak (bbox) mentah dalam PIKSEL, bukan rasio -- dipakai
        # popup live (gambar_live), beda dari titik_dalam/titik_luar
        # yang dalam rasio buat gambar_bukti. Sengaja dihasilkan dari
        # klasifikasi inside/outside yang SAMA persis dengan yang
        # menentukan angka CSV, bukan dihitung ulang terpisah.
        "kotak_dalam": [],
        "kotak_luar": [],
    }

    for det in detections:
        x1, y1, x2, y2, class_id, track_id = det

        # Titik acuan dalam rasio.
        #
        # cy memakai TEPI BAWAH bbox (y2), bukan titik tengah:
        # itu kira-kira tempat roda menyentuh jalan, jadi
        # posisinya di dunia nyata. Titik tengah badan kendaraan
        # melayang di udara, dan makin besar kendaraannya makin
        # jauh ia melayang — pickup dan truk dekat kamera jadi
        # terbaca di luar zona padahal rodanya jelas di dalam.
        # Terlihat langsung pada bukti CCTV_1 run pertama.
        cx = ((x1 + x2) / 2) / frame_width
        cy = y2 / frame_height

        nama_kelas = mapping_class(class_id)

        # person/bicycle: tidak dihitung dan tidak digambar.
        if nama_kelas is None:
            continue

        kotak = (x1, y1, x2, y2, nama_kelas)

        if point_in_polygon(cx, cy, zona_polygon):
            hasil["total"] += 1
            hasil[nama_kelas] += 1
            hasil["titik_dalam"].append((cx, cy))
            hasil["kotak_dalam"].append(kotak)
        else:
            hasil["titik_luar"].append((cx, cy))
            hasil["kotak_luar"].append(kotak)

    return hasil


def _sumbu_lateral_zona(zona_polygon):
    """
    Cari sumbu LEBAR jalan (lintas-lajur) dari titik-titik poligon
    zona, lewat PCA -- BUKAN diasumsikan sumbu-x gambar.

    Ditambahkan 25 Agustus 2026 (temuan review kode): zona seperti
    CCTV_1/CCTV_4 diagonal mengikuti perspektif jalan, jadi sumbu-x
    mentah bisa lebih dekat ke arah KEDALAMAN jalan daripada LEBAR
    jalan -- pengelompokan lajur yang pakai cx apa adanya jadi keliru
    di zona semacam itu.

    Poligon zona lebih PANJANG mengikuti arah jalan (kedalaman, dari
    jauh sampai garis stop) daripada LEBAR jalan (lintas-lajur, cuma
    beberapa meter). Jadi sumbu dengan sebaran titik TERKECIL
    diasumsikan sumbu lebar jalan -- itu yang dipakai mengelompokkan
    kendaraan per lajur di hitung_antrean(). Sumbu dengan sebaran
    TERBESAR (kedalaman) sengaja TIDAK dipakai buat pengelompokan.

    Return (pusat, sumbu_lebar) -- sumbu_lebar vektor satuan.
    """

    titik = np.array(zona_polygon, dtype=float)
    pusat = titik.mean(axis=0)
    tersentral = titik - pusat

    kovarian = np.cov(tersentral.T)
    nilai_eigen, vektor_eigen = np.linalg.eigh(kovarian)

    # eigh mengurutkan nilai eigen NAIK -- kolom indeks 0 adalah
    # sumbu dengan sebaran TERKECIL di antara titik poligon.
    sumbu_lebar = vektor_eigen[:, 0]

    return tuple(pusat), tuple(sumbu_lebar)


def hitung_antrean(
    state,
    detections,
    zona_polygon,
    frame_width,
    frame_height,
    lengan,
):
    """
    Hitung kendaraan yang sedang ANTRE (berhenti) di dalam zona, dan
    estimasi panjang antrean dalam meter.

    Beda dengan hitung_kendaraan_di_zona(): itu KEHADIRAN (semua
    kendaraan di zona, bergerak atau diam). Ini subset yang lebih
    ketat -- cuma yang sudah "hampir diam" beberapa frame berturut-
    turut (lihat ANTREAN_MIN_FRAME_DIAM). detections perlu track_id
    (dari ByteTrack) supaya bisa dibandingkan posisinya dengan frame
    sebelumnya lewat state.antrean_last_pos/antrean_stopped_frames.

    queue_length_veh: total kendaraan yang lolos 3 syarat, TIDAK
    peduli posisi kiri-kanannya -- ini murni "ada berapa yang antre".

    queue_length_m_est: BUKAN sekadar jumlah semua kendaraan x jatah
    meter per kelas (itu keliru kalau kendaraan sejajar di lajur
    beda -- lihat diskusi 25 Agustus). Kendaraan yang lolos
    dikelompokkan dulu jadi "lajur empirik", lalu diambil KEDALAMAN
    LAJUR TERPANJANG -- bukan dijumlah semua lajur. Ini juga sesuai
    definisi umum panjang antrean di teknik lalu lintas: diukur dari
    lajur yang paling penuh, bukan total kendaraan gabungan semua
    lajur.

    PENTING soal sumbu pengelompokan (diperbaiki 25 Agustus, temuan
    review kode): zona TIDAK selalu sejajar sumbu gambar -- CCTV_1
    dan CCTV_4 poligonnya diagonal mengikuti perspektif jalan menuju
    titik hilang (lihat riwayat kalibrasi di ZONA_KEPADATAN). Kalau
    dikelompokkan pakai koordinat x MENTAH, sumbu itu malah lebih
    dekat ke arah KEDALAMAN jalan daripada LEBAR jalan -- kendaraan
    di lajur fisik yang sama tapi beda jarak dari garis stop bisa
    masuk bucket berbeda, dan sebaliknya. Makanya di sini poligon
    di-dekomposisi dulu lewat PCA (lihat _sumbu_lateral_zona): sumbu
    dengan sebaran TERKECIL di antara titik poligon diasumsikan sumbu
    LEBAR jalan (lintas-lajur, karena zona lebih panjang mengikuti
    jalan daripada lebar jalan), lalu tiap kendaraan diproyeksikan ke
    sumbu itu sebelum dikelompokkan -- bukan pakai cx apa adanya.

    Catatan jujur: pengelompokan lajur ini tetap pendekatan kasar
    (lebar zona dibagi rata jumlah lajur, bukan deteksi batas lajur
    asli) -- zona sendiri tidak dikalibrasi per lajur (lihat catatan
    "YANG SENGAJA TIDAK ADA DI SINI" di kepala file). PCA memperbaiki
    SUMBU pengelompokannya, bukan menghilangkan asumsi "kendaraan
    tersebar rata sepanjang lebar jalan".

    KETERBATASAN YANG DIKETAHUI, SENGAJA TIDAK DIPERBAIKI (di luar
    scope waktu, dicatat 25 Agustus lewat review kode):

    1. ID-switch ByteTrack di antrean padat. Kendaraan yang saling
       menutupi (kondisi paling sering justru pas benar-benar macet
       -- yang paling ingin diukur) bikin ByteTrack ganti track_id.
       Tiap ganti id, riwayat "sudah diam berapa lama" mulai dari 0
       lagi -- kendaraan itu butuh ~1 detik lagi sebelum terhitung
       antre. Efeknya SISTEMATIS menurunkan queue_length_veh, paling
       parah justru saat kondisi paling padat. Tidak fatal (tetap
       jauh lebih berguna dari konstanta 0 yang lama), tapi jangan
       dipresentasikan sebagai angka akurat/presisi.
    2. state.antrean_last_pos/antrean_stopped_frames cuma dibersihkan
       kalau kendaraan TERDETEKSI di luar zona (lihat pop() di bawah).
       Kalau track_id hilang begitu saja (keluar frame, oklusi total),
       entrinya tinggal selamanya di dict. Untuk 49 menit x 4 kamera
       paling beberapa ribu entri -- tidak masalah praktis, tapi kalau
       skrip ini dipakai buat rekaman berjam-jam/hari, perlu ada
       pembersihan berkala.
    """

    kandidat = []

    for det in detections:
        x1, y1, x2, y2, class_id, track_id = det

        if track_id is None:
            # ByteTrack belum sempat kasih id -- tidak ada riwayat
            # posisi buat dibandingkan, tidak bisa dinilai "diam"
            # atau tidak.
            continue

        nama_kelas = mapping_class(class_id)

        if nama_kelas is None:
            continue

        # Titik acuan SAMA PERSIS dengan hitung_kendaraan_di_zona --
        # tepi bawah bbox (roda), rasio 0.0-1.0. Kalau titik acuannya
        # beda, kendaraan yang "di zona" versi satu bisa "di luar
        # zona" versi lain, dan dua metrik jadi tidak sepadan.
        cx = ((x1 + x2) / 2) / frame_width
        cy = y2 / frame_height

        if not point_in_polygon(cx, cy, zona_polygon):
            # Tidak di zona -- reset riwayat diamnya, biar kalau
            # kendaraan ini balik masuk zona nanti dihitung dari nol,
            # bukan mewarisi status diam dari sebelum dia keluar.
            state.antrean_stopped_frames.pop(track_id, None)
            state.antrean_last_pos.pop(track_id, None)
            continue

        pos_lama = state.antrean_last_pos.get(track_id)
        state.antrean_last_pos[track_id] = (cx, cy)

        if pos_lama is None:
            # Frame pertama track_id ini terlihat -- belum ada
            # riwayat buat dibandingkan, mulai dari 0.
            state.antrean_stopped_frames[track_id] = 0
            continue

        dx = cx - pos_lama[0]
        dy = cy - pos_lama[1]
        gerak = (dx * dx + dy * dy) ** 0.5

        if gerak <= ANTREAN_GERAK_RASIO_MAKS:
            state.antrean_stopped_frames[track_id] = (
                state.antrean_stopped_frames.get(track_id, 0) + 1
            )
        else:
            state.antrean_stopped_frames[track_id] = 0

        if state.antrean_stopped_frames[track_id] >= ANTREAN_MIN_FRAME_DIAM:
            kandidat.append((cx, cy, nama_kelas))

    hasil_antrean = {
        "queue_length_veh": len(kandidat),
        "queue_length_m_est": 0.0,
    }

    if not kandidat:
        return hasil_antrean

    # ------------------------------------------------------------
    # Kelompokkan jadi "lajur empirik" berdasarkan proyeksi ke sumbu
    # LEBAR jalan (lihat _sumbu_lateral_zona -- BUKAN sumbu-x mentah,
    # itu keliru buat zona diagonal seperti CCTV_1/CCTV_4), lalu
    # ambil kedalaman lajur TERPANJANG.
    # ------------------------------------------------------------

    jumlah_lajur = max(1, LAJUR_PER_LENGAN.get(lengan, 1))

    pusat, sumbu_lebar = _sumbu_lateral_zona(zona_polygon)

    proyeksi_poligon = [
        (titik[0] - pusat[0]) * sumbu_lebar[0]
        + (titik[1] - pusat[1]) * sumbu_lebar[1]
        for titik in zona_polygon
    ]
    proyeksi_min = min(proyeksi_poligon)
    proyeksi_max = max(proyeksi_poligon)
    lebar_zona = max(proyeksi_max - proyeksi_min, 1e-6)
    lebar_lajur = lebar_zona / jumlah_lajur

    kedalaman_per_lajur = [0.0 for _ in range(jumlah_lajur)]

    for cx, cy, nama_kelas in kandidat:
        proyeksi = (
            (cx - pusat[0]) * sumbu_lebar[0]
            + (cy - pusat[1]) * sumbu_lebar[1]
        )
        idx_lajur = int((proyeksi - proyeksi_min) / lebar_lajur)
        idx_lajur = max(0, min(jumlah_lajur - 1, idx_lajur))
        kedalaman_per_lajur[idx_lajur] += QUEUE_SPACE_M[nama_kelas]

    hasil_antrean["queue_length_m_est"] = round(
        max(kedalaman_per_lajur), 2
    )

    return hasil_antrean


def garis_untuk_kamera(nama_kamera, lengan_default):
    """
    Normalisasi CROSSING_LINES[nama_kamera] jadi list seragam
    {"label", "p1", "p2"}.

    Sumbernya bisa dua bentuk (lihat komentar CROSSING_LINES): SATU
    garis flat (dict x1/y1/x2/y2 langsung -- kamera satu lengan,
    mis. CCTV_1) atau BEBERAPA garis bernama (dict label -> garis --
    kamera yang framenya memotret >1 lengan, mis. CCTV_2 dengan
    MAGELANG dan DIPONEGORO). Kamera flat tidak punya label eksplisit
    di CROSSING_LINES, jadi dipakai nama lengan zona-nya sebagai
    ganti.

    Balikan [] kalau kamera ini tidak ada di CROSSING_LINES sama
    sekali (mis. CCTV_4, belum dikalibrasi) -- caller cukup tidak
    dapat garis apa pun, bukan error.
    """
    raw = CROSSING_LINES.get(nama_kamera)

    if raw is None:
        return []

    if "x1" in raw:
        return [{
            "label": lengan_default,
            "p1": (raw["x1"], raw["y1"]),
            "p2": (raw["x2"], raw["y2"]),
        }]

    return [
        {
            "label": label,
            "p1": (garis["x1"], garis["y1"]),
            "p2": (garis["x2"], garis["y2"]),
        }
        for label, garis in raw.items()
    ]


def hitung_crossing(state, detections):
    """
    Deteksi kendaraan yang melintasi salah satu garis crossing milik
    kamera ini di frame ini, dibandingkan posisi track_id yang sama
    di frame SEBELUMNYA (state.prev_pos) -- bukan posisi sesaat,
    supaya "melintas" berarti benar-benar berpindah sisi garis.

    Anti double-count: sekali track_id tercatat melintasi satu
    garis, track_id itu ditandai di state.sudah_dihitung[label] dan
    tidak akan dihitung lagi di garis yang sama walau dia bolak-balik
    dekat garis di frame-frame berikutnya.

    Hasil crossing diakumulasi ke DUA tempat sekaligus:
    state.crossing_akumulasi[label] (direset tiap jendela 5 detik,
    lihat tulis_baris_csv_crossing) dan state.crossing_total[label]
    (tidak pernah direset, dipakai gambar_live() buat panel "total
    sejauh ini"). state.prev_pos diperbarui di akhir supaya SEMUA
    garis membandingkan terhadap posisi frame-sebelumnya yang sama,
    bukan posisi yang sudah dimutakhirkan garis lain duluan.
    """
    if not state.garis_list:
        return

    posisi_baru = {}

    for x1, y1, x2, y2, class_id, track_id in detections:
        if track_id is None:
            # ByteTrack belum sempat kasih id -- tidak ada riwayat
            # buat dibandingkan, lewati.
            continue

        nama_kelas = mapping_class(class_id)

        if nama_kelas is None:
            continue

        cx = ((x1 + x2) / 2) / state.width
        cy = y2 / state.height
        posisi_baru[track_id] = (cx, cy)

        pos_lama = state.prev_pos.get(track_id)

        if pos_lama is None:
            # Track baru muncul frame ini -- belum ada posisi
            # sebelumnya buat dibandingkan.
            continue

        for garis in state.garis_list:
            label = garis["label"]

            if track_id in state.sudah_dihitung[label]:
                continue

            sisi_lama = sisi_garis(*pos_lama, garis["p1"], garis["p2"])
            sisi_baru = sisi_garis(cx, cy, garis["p1"], garis["p2"])

            # Tanda berlawanan (dan sama-sama bukan nol) berarti
            # berpindah sisi -- itu crossing.
            if sisi_lama * sisi_baru < 0:
                for akum in (
                    state.crossing_akumulasi[label],
                    state.crossing_total[label],
                ):
                    akum["total"] += 1
                    akum[nama_kelas] += 1

                state.sudah_dihitung[label].add(track_id)

    state.prev_pos = posisi_baru


# ============================================================
# VISUALISASI
# ============================================================

def gambar_bukti(
    frame,
    zona_polygon,
    hasil,
    nama_kamera,
    nama_lengan,
    path_keluar,
):
    """
    Simpan satu frame contoh: poligon zona biru, titik tengah
    kendaraan di DALAM zona hijau, di LUAR zona merah.
    """
    h, w = frame.shape[:2]
    kanvas = frame.copy()

    titik_poly = np.array(
        [[int(x * w), int(y * h)] for x, y in zona_polygon],
        dtype=np.int32,
    )

    # Arsiran zona
    lapisan = kanvas.copy()
    cv2.fillPoly(lapisan, [titik_poly], (255, 140, 0))
    kanvas = cv2.addWeighted(lapisan, 0.25, kanvas, 0.75, 0)
    cv2.polylines(kanvas, [titik_poly], True, (255, 140, 0), 3)

    for cx, cy in hasil["titik_luar"]:
        cv2.circle(
            kanvas, (int(cx * w), int(cy * h)), 8, (0, 0, 255), -1
        )

    for cx, cy in hasil["titik_dalam"]:
        cv2.circle(
            kanvas, (int(cx * w), int(cy * h)), 9, (0, 220, 0), -1
        )
        cv2.circle(
            kanvas, (int(cx * w), int(cy * h)), 9, (255, 255, 255), 2
        )

    baris = [
        f"{nama_kamera}  ({nama_lengan})",
        f"DI DALAM ZONA : {hasil['total']}",
        f"  motor {hasil['motor']}  mobil {hasil['mobil']}"
        f"  truk {hasil['truk']}  bus {hasil['bus']}",
        f"di luar zona  : {len(hasil['titik_luar'])}",
    ]

    # Ditempel di KIRI BAWAH, bukan kiri atas: jam burned-in CCTV
    # ada di kiri atas dan dua-duanya jadi tidak terbaca kalau
    # ditumpuk.
    tinggi_panel = 40 * len(baris) + 24
    y0 = h - tinggi_panel - 18

    panel = kanvas.copy()
    cv2.rectangle(
        panel, (0, y0), (int(w * 0.46), h - 8), (0, 0, 0), -1
    )
    kanvas = cv2.addWeighted(panel, 0.55, kanvas, 0.45, 0)

    y = y0 + 44
    for i, teks in enumerate(baris):
        skala = 1.1 if i == 0 else 0.85
        cv2.putText(
            kanvas, teks, (18, y),
            cv2.FONT_HERSHEY_SIMPLEX, skala, (0, 0, 0), 6
        )
        cv2.putText(
            kanvas, teks, (18, y),
            cv2.FONT_HERSHEY_SIMPLEX, skala, (255, 255, 255), 2
        )
        y += 40

    cv2.imwrite(path_keluar, kanvas)

    return path_keluar


NAMA_JUDUL_PANEL = "=== SMARTTWIN ZONA MONITOR ==="
NAMA_KELAS_TAMPILAN = ("motor", "mobil", "truk", "bus")


def gambar_live(
    frame, zona_polygon, hasil, nama_kamera, nama_lengan, idx,
    garis_list=None, crossing_total=None,
):
    """
    Gambar overlay buat popup window real-time (cv2.imshow), TIDAK
    disimpan ke disk -- beda tujuan dari gambar_bukti() yang
    menyimpan satu file bukti statis.

    Kotak bbox diambil dari hasil["kotak_dalam"]/["kotak_luar"]
    (piksel, hasil klasifikasi yang SAMA dengan yang dipakai
    menghitung angka CSV), jadi apa yang kelihatan di layar dijamin
    sinkron dengan angka yang ditulis.

    garis_list/crossing_total (dari KameraState.garis_list dan
    .crossing_total) opsional -- default None/[] kalau kamera ini
    tidak punya garis crossing terkalibrasi (mis. CCTV_4), supaya
    fungsi ini tetap aman dipanggil tanpa argumen itu.

    Mengembalikan frame BARU (frame asli tidak diubah), supaya frame
    yang sama masih bisa dipakai gambar_bukti() setelahnya kalau
    posisinya kebetulan sama.
    """
    garis_list = garis_list or []
    crossing_total = crossing_total or {}

    h, w = frame.shape[:2]
    kanvas = frame.copy()

    # --------------------------------------------------------
    # 1. Garis polygon zona -- BIRU, thickness 2
    # --------------------------------------------------------
    titik_poly = np.array(
        [[int(x * w), int(y * h)] for x, y in zona_polygon],
        dtype=np.int32,
    )
    cv2.polylines(kanvas, [titik_poly], True, (255, 0, 0), 2)

    # --------------------------------------------------------
    # 1b. Garis crossing -- ORANYE, thickness 2, label + jumlah
    #     kumulatif (seumur run, bukan per-jendela) di tengah garis
    # --------------------------------------------------------
    for garis in garis_list:
        p1 = (int(garis["p1"][0] * w), int(garis["p1"][1] * h))
        p2 = (int(garis["p2"][0] * w), int(garis["p2"][1] * h))
        cv2.line(kanvas, p1, p2, (0, 165, 255), 2)

        label = garis["label"]
        jumlah = crossing_total.get(label, {}).get("total", 0)
        tengah = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)

        cv2.putText(
            kanvas, f"{label}: {jumlah}", tengah,
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2,
        )

    # --------------------------------------------------------
    # 2. Bounding box tiap kendaraan -- HIJAU di dalam, MERAH
    #    di luar zona
    # --------------------------------------------------------
    for x1, y1, x2, y2, nama_kelas in hasil["kotak_dalam"]:
        cv2.rectangle(
            kanvas, (int(x1), int(y1)), (int(x2), int(y2)),
            (0, 255, 0), 2,
        )
        cv2.putText(
            kanvas, nama_kelas, (int(x1), max(15, int(y1) - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2,
        )

    for x1, y1, x2, y2, nama_kelas in hasil["kotak_luar"]:
        cv2.rectangle(
            kanvas, (int(x1), int(y1)), (int(x2), int(y2)),
            (0, 0, 255), 2,
        )

    # --------------------------------------------------------
    # 3. Panel info -- kiri atas, background hitam semi-transparan
    # --------------------------------------------------------
    baris_panel = [
        NAMA_JUDUL_PANEL,
        f"Kamera  : {nama_kamera} ({nama_lengan})",
        f"Frame   : {idx}",
        "-" * 30,
        "DALAM ZONA:",
        f"  Total  : {hasil['total']}",
        f"  Motor  : {hasil['motor']}",
        f"  Mobil  : {hasil['mobil']}",
        f"  Truk   : {hasil['truk']}",
        f"  Bus    : {hasil['bus']}",
    ]

    if garis_list:
        baris_panel.append("-" * 30)
        baris_panel.append("CROSSING (total sejauh ini):")
        for garis in garis_list:
            label = garis["label"]
            jumlah = crossing_total.get(label, {}).get("total", 0)
            baris_panel.append(f"  {label}: {jumlah}")

    baris_panel.append("-" * 30)
    baris_panel.append("Tekan Q untuk keluar")

    tinggi_baris = 18
    panel_lebar = 280
    panel_tinggi = tinggi_baris * len(baris_panel) + 20

    overlay = kanvas.copy()
    cv2.rectangle(
        overlay, (10, 10), (10 + panel_lebar, 10 + panel_tinggi),
        (0, 0, 0), -1,
    )
    cv2.addWeighted(overlay, 0.6, kanvas, 0.4, 0, kanvas)

    y = 10 + tinggi_baris
    for teks in baris_panel:
        cv2.putText(
            kanvas, teks, (18, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
        )
        y += tinggi_baris

    # --------------------------------------------------------
    # 4. Counter besar di tengah atas -- KUNING, buat presentasi
    # --------------------------------------------------------
    teks_total = f"TOTAL: {hasil['total']} kendaraan"
    (teks_w, _), _ = cv2.getTextSize(
        teks_total, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2
    )
    x_tengah = max(0, (w - teks_w) // 2)

    cv2.putText(
        kanvas, teks_total, (x_tengah, 40),
        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4,
    )
    cv2.putText(
        kanvas, teks_total, (x_tengah, 40),
        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2,
    )

    return kanvas


# ============================================================
# EKSTRAKSI DETEKSI
# ============================================================

def ekstrak_deteksi(result):
    """
    Ubah keluaran Ultralytics jadi list tuple
    (x1, y1, x2, y2, class_id, track_id).

    track_id bisa None kalau ByteTrack belum sempat memberi id
    pada objek yang baru muncul — tidak masalah, cacah zona tidak
    bergantung padanya.
    """
    boxes = result.boxes

    if boxes is None or boxes.id is None and len(boxes) == 0:
        return []

    xyxy = boxes.xyxy.cpu().numpy()
    cls = boxes.cls.cpu().numpy()

    if boxes.id is not None:
        ids = boxes.id.cpu().numpy()
    else:
        ids = [None] * len(xyxy)

    deteksi = []

    for (x1, y1, x2, y2), c, t in zip(xyxy, cls, ids):
        deteksi.append(
            (
                float(x1), float(y1), float(x2), float(y2),
                int(c),
                int(t) if t is not None else None,
            )
        )

    return deteksi


# ============================================================
# STATE SATU KAMERA (dipakai jalankan_gabungan)
# ============================================================
#
# Dulu ada proses_kamera() yang memproses satu video sampai habis
# baru pindah ke kamera berikutnya -- window popup-nya jadi
# bergantian, bukan bareng. Diganti KameraState + proses_tick()
# supaya semua kamera bisa dibaca selang-seling (round-robin), tiap
# kamera tetap tampil di window cv2.imshow sendiri-sendiri, tanpa
# threading (satu frame per kamera per putaran, bergiliran).

# cameraId (baris tabel `cameras` di Supabase) tiap kamera -- HARDCODE
# via query manual ke project Digital-Twins-KMIPN-2026, bukan lookup
# dinamis, karena cuma 4 kamera tetap di intersection simpang4-pingit
# ini. Dicocokkan lewat NOMOR kamera (CCTV 1..4 di kolom `name`),
# BUKAN kolom `approach` -- approach di database untuk CCTV_3/CCTV_4
# TERBALIK (east/west) dibanding lengan barat/timur yang
# didokumentasikan di ZONA_KEPADATAN di atas. Itu bug data terpisah
# di Supabase, DI LUAR SCOPE file ini -- nomor kameranya sendiri
# tidak ambigu, jadi pemetaan di bawah tetap benar.
CAMERA_ID_MAP = {
    "CCTV_1": 18,
    "CCTV_2": 27,
    "CCTV_3": 28,
    "CCTV_4": 29,
}

INTERSECTION_SLUG = "simpang4-pingit"

# Upload jalan di thread terpisah (lihat KameraState.tutup() dan
# upload_dan_update()) supaya kamera-kamera tidak saling menunggu.
# max_workers=4 karena cuma ada 4 kamera -- semuanya bisa paralel
# penuh sekaligus, tidak perlu antre.
_UPLOAD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="upload-hf"
)
_UPLOAD_FUTURES = []


def _muat_kredensial_backend():
    """
    Suntik SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY/HF_TOKEN/HF_REPO_ID
    dari backend/.env ke os.environ, SEKALI di awal main().

    hf_writer.py dan supabase_writer.py didesain baca kredensial dari
    os.environ yang di-inject cv_trigger_service.py saat men-spawn
    subprocess CV produksi -- lihat komentar di kedua file itu.
    Karena vehicle_counter_copy.py dijalankan manual/standalone
    (bukan subprocess backend), env itu tidak pernah ke-set otomatis,
    jadi disuntik manual di sini dari file yang SAMA yang dipakai
    backend (backend/.env), bukan file .env baru di cv/.

    Tidak pakai python-dotenv (tidak ada di requirements cv/) --
    parsing manual KEY=VALUE apa adanya sudah cukup buat 4 baris yang
    dibutuhkan.
    """
    env_path = os.path.join(BASE_DIR, "..", "backend", ".env")

    if not os.path.exists(env_path):
        print(
            f"[!] {env_path} tidak ada -- upload HuggingFace/Supabase "
            f"akan gagal."
        )
        return

    dibutuhkan = {
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "HF_TOKEN", "HF_REPO_ID",
    }

    with open(env_path, encoding="utf-8") as f:
        for baris in f:
            baris = baris.strip()

            if not baris or baris.startswith("#") or "=" not in baris:
                continue

            kunci, _, nilai = baris.partition("=")
            kunci = kunci.strip()

            if kunci in dibutuhkan and kunci not in os.environ:
                os.environ[kunci] = nilai.strip()


def upload_dan_update(nama_kamera, path_mp4):
    """
    Upload video anotasi ke HuggingFace lalu INSERT baris BARU di
    cameraVideos (Supabase) -- ikut PERSIS pola
    process_uploaded_video.upload_annotated_video(): INSERT baris
    baru (bukan UPDATE baris existing lewat name-match, yang
    berisiko menimpa video produksi yang salah), dan fileUrl diisi
    endpoint proxy backend (bukan link HuggingFace mentah -- repo-nya
    private, link mentah tidak akan bisa diputar langsung di
    browser).

    Dipanggil dari thread terpisah (lihat KameraState.tutup()) supaya
    upload beberapa kamera jalan paralel, tidak saling menunggu.
    """
    camera_id = CAMERA_ID_MAP.get(nama_kamera)

    if camera_id is None:
        print(
            f"[{nama_kamera}] Tidak terdaftar di CAMERA_ID_MAP, "
            f"upload dilewati."
        )
        return

    print(f"[{nama_kamera}] Mengupload ke HuggingFace...")

    try:
        filename = f"anotasi_{nama_kamera}.mp4"

        hasil = hw.upload_annotated_video(
            local_path=path_mp4,
            intersection_id=INTERSECTION_SLUG,
            filename=filename,
        )

        file_size_bytes = os.path.getsize(path_mp4)

        video_id = sw.insert_annotated_video(
            camera_id=camera_id,
            video_name=filename,
            repository_id=hasil.repository_id,
            file_path=hasil.file_path,
            file_size_bytes=file_size_bytes,
        )

        sw.set_video_file_url(
            video_id, f"/api/v1/cctv/videos/{video_id}/stream"
        )

        print(f"[{nama_kamera}] ✅ Upload selesai, Supabase diupdate.")
    except Exception as exc:  # noqa: BLE001
        print(f"[{nama_kamera}] Gagal upload/update Supabase: {exc}")


class KameraState:
    """Menampung semua state yang dulu jadi variabel lokal di
    proses_kamera(): posisi baca video, jendela CSV yang lagi
    diakumulasi, model YOLO/ByteTrack milik kamera ini sendiri, dan
    frame terakhir yang siap ditampilkan di window kamera ini."""

    def __init__(self, nama_kamera, zona, durasi_detik, imgsz):
        self.nama_kamera = nama_kamera
        self.poligon = zona["polygon"]
        self.lengan = zona["nama_lengan"]
        self.imgsz = imgsz

        self.tersedia = False
        self.selesai = False
        self.cap = None
        self.model = None
        self.peta = None
        self.tampil_frame = None
        self.hasil_terakhir = {
            "total": 0, "motor": 0, "mobil": 0, "truk": 0, "bus": 0,
            "kotak_dalam": [], "kotak_luar": [],
        }

        # Video anotasi (imageio_ffmpeg, BUKAN cv2.VideoWriter -- yang
        # terakhir gagal di Windows karena DLL openh264 hilang, sudah
        # dibuktikan gagal di cv/process_uploaded_video.py). Writer
        # dibuka LAZY di jalankan_gabungan() begitu tampil_frame
        # pertama siap, bukan di sini -- soalnya butuh frame asli
        # (bukan cuma width/height dari VideoCapture) supaya ukurannya
        # dijamin sama persis dengan yang benar-benar dikirim.
        self.video_anotasi_path = os.path.join(
            OUTPUT_DIR, f"anotasi_{nama_kamera}.mp4"
        )
        self.writer = None

        video_path = os.path.join(VIDEO_DIR, f"{nama_kamera}.mp4")

        if not os.path.exists(video_path):
            print(f"[LEWAT] {video_path} tidak ada.")
            self.selesai = True
            return

        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            print(f"[LEWAT] {video_path} gagal dibuka.")
            self.selesai = True
            return

        self.cap = cap
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 25
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Jam dinding dari posisi frame. GAGAL KERAS kalau videonya
        # tidak tercatat di sync_report.json — supaya jam laptop
        # tidak pernah menyamar jadi jam rekaman.
        self.peta = muat_peta_jam(video_path, self.fps)

        # Model per kamera sendiri-sendiri: state ByteTrack tidak
        # boleh bocor antar-video.
        self.model = YOLO(MODEL_PATH)

        self.batas_frame = int(durasi_detik * self.fps)
        self.idx = -1
        self.window_aktif = None
        self.akumulasi = []
        self.frame_terakhir = 0
        self.totals = []
        self.path_bukti = None
        self.n_proses = 0

        # Snapshot per detik: bacaan mentah frame TERAKHIR yang
        # diproses dalam detik itu, TIDAK dirata-rata -- beda
        # jendela (per detik) dan beda semantik (sesaat, bukan rata-
        # rata) dari window_aktif/akumulasi di atas yang buat
        # CSV_PATH. Lihat tulis_baris_csv_snapshot().
        self.detik_snapshot_aktif = None
        self.snapshot_hasil_aktif = None
        self.snapshot_frame_aktif = None

        # Crossing-line: garis_list [] kalau kamera ini belum
        # dikalibrasi di CROSSING_LINES (mis. CCTV_4) -- semua fungsi
        # crossing gracefully no-op dalam kasus itu.
        self.garis_list = garis_untuk_kamera(nama_kamera, self.lengan)
        self.prev_pos = {}

        # State antrean -- terpisah dari prev_pos di atas (yang buat
        # crossing) supaya semantiknya tidak bercampur. track_id ->
        # posisi (cx, cy) rasio frame lalu, dan track_id -> berapa
        # frame berturut-turut sudah "hampir diam". Lihat
        # hitung_antrean().
        self.antrean_last_pos = {}
        self.antrean_stopped_frames = {}
        self.sudah_dihitung = {g["label"]: set() for g in self.garis_list}
        self.crossing_akumulasi = {
            g["label"]: {
                "total": 0, "motor": 0, "mobil": 0, "truk": 0, "bus": 0,
            }
            for g in self.garis_list
        }
        self.crossing_riwayat = {g["label"]: [] for g in self.garis_list}

        # Beda dari crossing_akumulasi (direset tiap jendela 5 detik
        # buat CSV): ini akumulasi SEUMUR RUN, tidak pernah direset --
        # dipakai gambar_live() buat panel/label "total sejauh ini",
        # bukan angka per-jendela yang keliatan macet di 0 kebanyakan
        # waktu antar-event.
        self.crossing_total = {
            g["label"]: {
                "total": 0, "motor": 0, "mobil": 0, "truk": 0, "bus": 0,
            }
            for g in self.garis_list
        }

        self.tersedia = True

        print(
            f"\n[{nama_kamera}] {self.width}x{self.height} "
            f"@ {self.fps:.2f} fps -> lengan '{self.lengan}', "
            f"{len(self.poligon)} titik zona, "
            f"{len(self.garis_list)} garis crossing, imgsz={imgsz}"
        )

    def tutup(self):
        if self.cap is not None:
            self.cap.release()

        if self.writer is not None:
            self.writer.close()
            self.writer = None
            print(f"[{self.nama_kamera}] Video anotasi selesai disimpan.")

            future = _UPLOAD_EXECUTOR.submit(
                upload_dan_update, self.nama_kamera, self.video_anotasi_path
            )
            _UPLOAD_FUTURES.append(future)


def tulis_baris_csv(state, penulis_csv):
    """Tulis satu baris CSV dari jendela 5 detik yang baru selesai
    diakumulasi untuk kamera ini. Diekstrak dari bekas closure
    tutup_window() di proses_kamera() supaya bisa dipanggil per
    KameraState, bukan cuma dari dalam satu fungsi tertutup."""

    if not state.akumulasi:
        return

    n = len(state.akumulasi)

    rata = {
        k: sum(a[k] for a in state.akumulasi) / n
        for k in (
            "total", "motor", "mobil", "truk", "bus",
            "queue_length_veh", "queue_length_m_est",
        )
    }

    penulis_csv.writerow({
        "timestamp": state.peta.waktu(state.window_aktif).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "kamera": state.nama_kamera,
        "lengan": state.lengan,
        "total_di_zona": round(rata["total"], 2),
        "motor_di_zona": round(rata["motor"], 2),
        "mobil_di_zona": round(rata["mobil"], 2),
        "truk_di_zona": round(rata["truk"], 2),
        "bus_di_zona": round(rata["bus"], 2),
        "queue_length_veh": round(rata["queue_length_veh"], 2),
        "queue_length_m_est": round(rata["queue_length_m_est"], 2),
        "frame_number": state.frame_terakhir,
    })

    state.totals.append(rata["total"])


def tulis_baris_csv_snapshot(state, penulis_csv_snapshot):
    """Tulis satu baris SNAPSHOT untuk detik yang baru saja lewat --
    isinya bacaan MENTAH dari frame TERAKHIR yang diproses dalam
    detik itu (state.snapshot_hasil_aktif), TIDAK dirata-rata
    seperti tulis_baris_csv(). Kalau dalam detik itu ada beberapa
    frame diproses, yang dipakai cuma yang PALING AKHIR -- bukan
    rata-rata ataupun jumlah semuanya.

    Guard-nya snapshot_hasil_aktif is None (belum pernah ada frame
    diproses sama sekali), independen dari state akumulasi/window
    milik tulis_baris_csv/tulis_baris_csv_crossing."""

    if state.snapshot_hasil_aktif is None:
        return

    hasil = state.snapshot_hasil_aktif

    penulis_csv_snapshot.writerow({
        "timestamp": state.peta.waktu(state.detik_snapshot_aktif).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "kamera": state.nama_kamera,
        "lengan": state.lengan,
        "total_di_zona": hasil["total"],
        "motor_di_zona": hasil["motor"],
        "mobil_di_zona": hasil["mobil"],
        "truk_di_zona": hasil["truk"],
        "bus_di_zona": hasil["bus"],
        "queue_length_veh": hasil["queue_length_veh"],
        "queue_length_m_est": hasil["queue_length_m_est"],
        "frame_number": state.snapshot_frame_aktif,
    })


def tulis_baris_csv_crossing(state, penulis_csv_crossing):
    """Tulis satu baris per garis crossing kamera ini untuk jendela
    5 detik yang baru selesai (jumlah_crossing = SUM kejadian dalam
    jendela itu, bukan rata-rata -- ini ALIRAN, beda dengan zona
    yang KEHADIRAN), lalu reset akumulasinya buat jendela berikutnya.

    Ditulis 0 kalau memang tidak ada yang melintas jendela itu (bukan
    dilewati) supaya deret waktunya tetap utuh per jendela, bukan
    bolong-bolong.

    Guard-nya window_aktif is not None (bukan state.akumulasi seperti
    tulis_baris_csv) supaya independen dari kapan tulis_baris_csv
    mereset akumulasi zona-nya sendiri -- dua metrik ini ditulis
    berdampingan di proses_tick tapi tidak boleh saling bergantung
    urutan pemanggilan."""

    if state.window_aktif is None:
        return

    timestamp = state.peta.waktu(state.window_aktif).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    for garis in state.garis_list:
        label = garis["label"]
        akum = state.crossing_akumulasi[label]

        penulis_csv_crossing.writerow({
            "timestamp": timestamp,
            "kamera": state.nama_kamera,
            "label_garis": label,
            "jumlah_crossing": akum["total"],
            "motor_crossing": akum["motor"],
            "mobil_crossing": akum["mobil"],
            "truk_crossing": akum["truk"],
            "bus_crossing": akum["bus"],
            "frame_number": state.frame_terakhir,
        })

        state.crossing_riwayat[label].append(akum["total"])

        akum["total"] = 0
        akum["motor"] = 0
        akum["mobil"] = 0
        akum["truk"] = 0
        akum["bus"] = 0


def proses_tick(
    state, langkah, frame_visual,
    penulis_csv, penulis_csv_crossing, penulis_csv_snapshot,
):
    """
    Baca dan proses SATU frame untuk satu kamera (satu "giliran"
    dalam round-robin). Bukan loop -- dipanggil berulang oleh
    jalankan_gabungan(), satu kali per putaran per kamera.

    Selalu memperbarui state.tampil_frame dengan frame TERBARU
    (mentah kalau lagi frame yang dilewati --langkah, dengan overlay
    kalau frame ini yang diproses YOLO) supaya video di window tetap
    terlihat mengalir mulus walau kotak deteksi cuma di-refresh tiap
    N frame.
    """
    if state.selesai:
        return

    ok, frame = state.cap.read()

    if not ok:
        state.selesai = True
        return

    state.idx += 1

    if state.idx >= state.batas_frame:
        state.selesai = True
        return

    if state.idx % langkah != 0:
        # Frame dilewati dari YOLO, tapi tetap ditampilkan mentah
        # (+ overlay hasil terakhir) supaya gerakan videonya mulus.
        state.tampil_frame = gambar_live(
            frame, state.poligon, state.hasil_terakhir,
            state.nama_kamera, state.lengan, state.idx,
            state.garis_list, state.crossing_total,
        )
        return

    detik = state.peta.detik_dinding(state.idx)

    # Frame di luar peta keping: lebih baik dilewati daripada
    # ditulis dengan jam karangan.
    if detik is None:
        state.tampil_frame = gambar_live(
            frame, state.poligon, state.hasil_terakhir,
            state.nama_kamera, state.lengan, state.idx,
            state.garis_list, state.crossing_total,
        )
        return

    awal_window = int(detik // WINDOW_DETIK) * WINDOW_DETIK

    if state.window_aktif is None:
        state.window_aktif = awal_window

    if awal_window != state.window_aktif:
        tulis_baris_csv(state, penulis_csv)
        tulis_baris_csv_crossing(state, penulis_csv_crossing)
        state.akumulasi = []
        state.window_aktif = awal_window

    results = state.model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        classes=TRACK_CLASSES,
        conf=CONFIDENCE,
        imgsz=state.imgsz,
        verbose=False,
    )

    deteksi = ekstrak_deteksi(results[0])

    hasil = hitung_kendaraan_di_zona(
        deteksi,
        state.poligon,
        state.width,
        state.height,
    )

    # Butuh posisi track_id frame-SEBELUMNYA (state.prev_pos), jadi
    # HARUS dipanggil di sini, tiap frame yang diproses -- bukan cuma
    # saat jendela tutup seperti tulis_baris_csv_crossing.
    hitung_crossing(state, deteksi)

    # Sama alasannya -- butuh riwayat posisi tiap track_id per frame
    # (state.antrean_last_pos/antrean_stopped_frames), jadi harus
    # dipanggil tiap frame juga. Hasilnya digabung ke dict `hasil`
    # yang sama dengan zona, supaya ikut mengalir otomatis ke CSV
    # snapshot & CSV jendela 5 detik lewat state.akumulasi.
    hasil.update(
        hitung_antrean(
            state,
            deteksi,
            state.poligon,
            state.width,
            state.height,
            state.lengan,
        )
    )

    # Snapshot per detik: bucket 1 detik TERPISAH dari jendela 5
    # detik di atas. Begitu detiknya berganti, flush bacaan TERAKHIR
    # dari detik yang baru lewat (bukan rata-rata), baru pindah ke
    # bucket detik yang baru dan simpan hasil frame ini sebagai
    # bacaan (sementara) terakhirnya.
    detik_bulat = int(detik)

    if state.detik_snapshot_aktif is None:
        state.detik_snapshot_aktif = detik_bulat
    elif detik_bulat != state.detik_snapshot_aktif:
        tulis_baris_csv_snapshot(state, penulis_csv_snapshot)
        state.detik_snapshot_aktif = detik_bulat

    state.snapshot_hasil_aktif = hasil
    state.snapshot_frame_aktif = state.idx

    state.akumulasi.append(hasil)
    state.hasil_terakhir = hasil
    state.frame_terakhir = state.idx
    state.n_proses += 1

    # Laporan tiap 30 frame yang DIPROSES — untuk memastikan
    # angkanya masuk akal sambil run masih jalan, bukan baru
    # ketahuan di akhir.
    if state.n_proses % 30 == 0:
        crossing_ringkas = ", ".join(
            f"{label}={akum['total']}"
            for label, akum in state.crossing_akumulasi.items()
        )
        print(
            f"  {state.nama_kamera} f{state.idx:>6} "
            f"({state.idx / state.fps:>5.0f}s)"
            f"  zona={hasil['total']:>3}"
            f"  (motor {hasil['motor']}, mobil {hasil['mobil']}, "
            f"truk {hasil['truk']}, bus {hasil['bus']})"
            f"  luar={len(hasil['titik_luar'])}"
            + (f"  crossing[{crossing_ringkas}]" if crossing_ringkas else "")
        )

    # Gambar bukti diambil dari frame yang sama sekali ini, jadi
    # angkanya dijamin hasil perhitungan yang sama.
    if state.path_bukti is None and state.idx >= frame_visual:
        state.path_bukti = gambar_bukti(
            frame,
            state.poligon,
            hasil,
            state.nama_kamera,
            state.lengan,
            os.path.join(
                OUTPUT_DIR,
                f"zona_test_{state.nama_kamera.replace('_', '')}.jpg",
            ),
        )

    state.tampil_frame = gambar_live(
        frame, state.poligon, hasil,
        state.nama_kamera, state.lengan, state.idx,
        state.garis_list, state.crossing_total,
    )


def jalankan_gabungan(
    dipilih, durasi_detik, langkah, frame_visual, imgsz,
    penulis_csv, penulis_csv_crossing, penulis_csv_snapshot, tampilkan_live,
):
    """
    Ganti proses_kamera() lama: semua kamera terpilih dibaca
    ROUND-ROBIN (satu frame CCTV_1, satu frame CCTV_2, satu frame
    CCTV_3, ulangi) dalam SATU loop, satu thread -- bukan diproses
    penuh satu-satu, jadi semua kamera berjalan "bersamaan" walau
    tetap single-threaded.

    Kalau tampilkan_live, tiap kamera dapat window cv2.imshow SENDIRI
    ("SmartTwin - <nama_kamera>") -- bukan satu grid gabungan --
    supaya tiap window bisa dipindah/diperbesar bebas. Q di window
    mana pun (waitKey global, bukan per-window) menghentikan semua
    kamera bersamaan.

    Balikannya list (nama_kamera, lengan, totals) buat statistik zona
    -- format sama persis dengan yang dulu dikumpulkan manual di
    main(). Statistik crossing dicetak langsung di sini (bukan ikut
    dibalikin) karena bentuknya per-garis, bukan per-kamera. Snapshot
    per detik (penulis_csv_snapshot) tidak punya statistik ringkasan
    tersendiri -- isinya memang dimaksudkan dibaca mentah per baris.
    """
    states = [
        KameraState(nama_kamera, zona, durasi_detik, imgsz)
        for nama_kamera, zona in dipilih.items()
    ]

    aktif = [s for s in states if s.tersedia]

    if tampilkan_live:
        for state in aktif:
            cv2.namedWindow(
                f"SmartTwin - {state.nama_kamera}", cv2.WINDOW_NORMAL
            )

    dihentikan_user = False

    try:
        while any(not s.selesai for s in aktif):
            for state in aktif:
                if not state.selesai:
                    proses_tick(
                        state, langkah, frame_visual,
                        penulis_csv, penulis_csv_crossing, penulis_csv_snapshot,
                    )

                if tampilkan_live and state.tampil_frame is not None:
                    cv2.imshow(
                        f"SmartTwin - {state.nama_kamera}",
                        state.tampil_frame,
                    )

                # Video anotasi -- SENGAJA tidak digantung ke
                # tampilkan_live seperti imshow di atas: run headless
                # (--tanpa-tampilan, mis. full run tanpa GUI) tetap
                # butuh rekamannya, cuma popup-nya yang dimatikan.
                if state.tampil_frame is not None:
                    if state.writer is None:
                        state.writer = imageio_ffmpeg.write_frames(
                            state.video_anotasi_path,
                            (state.width, state.height),
                            fps=state.fps,
                            codec="libx264",
                            pix_fmt_in="bgr24",
                            pix_fmt_out="yuv420p",
                            # Tanpa ini, bitrate defaultnya ~6 Mbps --
                            # video durasi penuh (~43 menit) jadi ~2GB
                            # per kamera, upload ke HF bisa berjam-jam.
                            # 800k sama seperti cap proven di
                            # process_uploaded_video.py.
                            bitrate="800k",
                            output_params=["-movflags", "+faststart"],
                        )
                        state.writer.send(None)
                        print(
                            f"[{state.nama_kamera}] Merekam anotasi -> "
                            f"{state.video_anotasi_path}"
                        )

                    state.writer.send(state.tampil_frame.tobytes())

            if tampilkan_live and aktif:
                # waitKey dipanggil SEKALI per putaran (bukan per
                # kamera) -- cukup buat memompa semua window sekaligus
                # dan menangkap Q dari window mana pun yang fokus.
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("\n  [Q] Dihentikan user, semua kamera berhenti.")
                    dihentikan_user = True
                    break
    finally:
        for state in aktif:
            tulis_baris_csv(state, penulis_csv)
            tulis_baris_csv_crossing(state, penulis_csv_crossing)
            tulis_baris_csv_snapshot(state, penulis_csv_snapshot)
            state.tutup()

        if tampilkan_live:
            cv2.destroyAllWindows()

    statistik = []

    for state in aktif:
        if state.path_bukti is None and state.akumulasi:
            print(
                f"  [!] {state.nama_kamera}: frame visual "
                f"{frame_visual} tidak tercapai, gambar bukti dilewati."
            )

        print(
            f"  {state.nama_kamera}: {len(state.totals)} jendela ditulis"
            + (f", bukti -> {os.path.basename(state.path_bukti)}"
               if state.path_bukti else "")
        )

        for label, riwayat in state.crossing_riwayat.items():
            total = sum(riwayat)
            print(
                f"    crossing '{label}': {total} kendaraan "
                f"({len(riwayat)} jendela)"
            )

        statistik.append((state.nama_kamera, state.lengan, state.totals))

    if dihentikan_user:
        print("\nDihentikan oleh user (Q). Berhenti.")

    return statistik


# ============================================================
# STATISTIK
# ============================================================

def cetak_statistik(statistik):
    print()
    print("=" * 68)
    print("STATISTIK KEPADATAN ZONA (kendaraan, rata-rata per jendela 5 detik)")
    print("=" * 68)
    print(f"{'kamera':<10}{'lengan':<18}{'jendela':>9}"
          f"{'rata2':>10}{'min':>8}{'max':>8}")

    for nama, lengan, totals in statistik:
        if not totals:
            print(f"{nama:<10}{lengan:<18}{'0':>9}"
                  f"{'-':>10}{'-':>8}{'-':>8}")
            continue

        print(
            f"{nama:<10}{lengan:<18}{len(totals):>9}"
            f"{sum(totals) / len(totals):>10.2f}"
            f"{min(totals):>8.2f}{max(totals):>8.2f}"
        )


def cetak_cuplikan_csv(n=20, path=CSV_PATH):
    print()
    print("=" * 68)
    print(f"{n} BARIS PERTAMA — {os.path.basename(path)}")
    print("=" * 68)

    with open(path, "r", encoding="utf-8", newline="") as f:
        for i, baris in enumerate(f):
            if i > n:
                break
            print(baris.rstrip())


# ============================================================
# MAIN
# ============================================================

KOLOM = [
    "timestamp",
    "kamera",
    "lengan",
    "total_di_zona",
    "motor_di_zona",
    "mobil_di_zona",
    "truk_di_zona",
    "bus_di_zona",
    "queue_length_veh",
    "queue_length_m_est",
    "frame_number",
]

# CSV crossing terpisah -- lihat CROSSING_CSV_PATH. jumlah_crossing
# dkk itu SUM kejadian dalam jendela 5 detik, bukan rata-rata seperti
# kolom _di_zona.
KOLOM_CROSSING = [
    "timestamp",
    "kamera",
    "label_garis",
    "jumlah_crossing",
    "motor_crossing",
    "mobil_crossing",
    "truk_crossing",
    "bus_crossing",
    "frame_number",
]

# CSV snapshot per detik -- kolomnya SAMA NAMA dengan KOLOM (zona),
# tapi isinya bacaan mentah (int) satu frame terakhir tiap detik,
# BUKAN rata-rata seperti KOLOM.
KOLOM_SNAPSHOT = [
    "timestamp",
    "kamera",
    "lengan",
    "total_di_zona",
    "motor_di_zona",
    "mobil_di_zona",
    "truk_di_zona",
    "bus_di_zona",
    "queue_length_veh",
    "queue_length_m_est",
    "frame_number",
]


def main():
    parser = argparse.ArgumentParser(
        description="Percobaan hitung kepadatan berbasis zona."
    )
    parser.add_argument(
        "--durasi", type=int, default=300,
        help="Detik pertama video yang diproses (default 300 = 5 menit).",
    )
    parser.add_argument(
        "--langkah", type=int, default=5,
        help=(
            "Proses tiap frame ke-N (default 5, artinya ~6 fps). Aman "
            "dinaikkan untuk cacah ZONA (tidak bergantung kesinambungan "
            "track). Untuk CROSSING beda cerita: dinaikkan artinya "
            "posisi 'sebelumnya' yang dibandingkan makin renggang, jadi "
            "kendaraan cepat/dekat garis bisa lompat sisi tanpa "
            "terdeteksi. Turunkan ke 1 kalau angka crossing perlu akurat."
        ),
    )
    parser.add_argument(
        "--frame-visual", type=int, default=900,
        help="Nomor frame untuk gambar bukti (default 900 = detik ke-30).",
    )
    parser.add_argument(
        "--imgsz", type=int, default=IMGSZ,
        help=(
            f"Resolusi inferensi YOLO (default {IMGSZ}). Turunkan ke "
            f"640 kalau butuh cepat, tapi motor di ujung jauh frame "
            f"akan banyak yang lolos."
        ),
    )
    parser.add_argument(
        "--kamera", default=None,
        help=(
            "Proses SATU kamera saja, misal CCTV_1. Default: semua. "
            "Perlu diingat CSV ditulis ulang dari nol tiap run, jadi "
            "run satu-kamera menghasilkan CSV berisi kamera itu saja."
        ),
    )
    parser.add_argument(
        "--tanpa-tampilan", action="store_true",
        help=(
            "Matikan popup cv2.imshow (mis. dijalankan lewat SSH "
            "tanpa display). Default: popup nyala."
        ),
    )
    args = parser.parse_args()

    if args.kamera is not None and args.kamera not in ZONA_KEPADATAN:
        parser.error(
            f"kamera '{args.kamera}' tidak punya zona. "
            f"Pilihan: {', '.join(ZONA_KEPADATAN)}"
        )

    dipilih = {
        nama: zona
        for nama, zona in ZONA_KEPADATAN.items()
        if args.kamera is None or nama == args.kamera
    }

    # Direktori output dijamin ada TEPAT sebelum CSV dibuka.
    # Sudah dipanggil sekali di level modul, diulang di sini
    # supaya tetap benar kalau foldernya terhapus di antara impor
    # dan pemanggilan main() (mis. saat dipakai sebagai library).
    #
    # Pakai OUTPUT_DIR yang absolut, BUKAN string "cv/output":
    # skrip ini dijalankan dari dalam folder cv/, jadi path relatif
    # itu akan membuat cv/cv/output.
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 68)
    print("PERCOBAAN LOGIKA ZONA — kepadatan, bukan crossing")
    print("=" * 68)
    print(
        f"Model    : {os.path.basename(MODEL_PATH)} "
        f"(conf={CONFIDENCE}, imgsz={args.imgsz})"
    )
    print(f"Acuan    : TEPI BAWAH bbox (posisi roda), bukan centroid")
    print(f"Durasi   : {args.durasi} detik pertama tiap video")
    print(f"Langkah  : tiap frame ke-{args.langkah}")
    print(f"Jendela  : {WINDOW_DETIK} detik (rata-rata, bukan jumlah)")
    print(f"Kamera   : {', '.join(dipilih)}")
    print(f"CSV zona    : {CSV_PATH}")
    print(f"CSV cross   : {CROSSING_CSV_PATH}")
    print(f"CSV snapshot: {SNAPSHOT_CSV_PATH}")

    # Kredensial HF/Supabase disuntik SEKALI di sini, sebelum kamera
    # manapun sempat selesai merekam dan memicu upload_dan_update()
    # dari thread lain -- lihat _muat_kredensial_backend().
    _muat_kredensial_backend()

    statistik = []
    tampilkan_live = not args.tanpa_tampilan

    try:
        # Context manager: berkasnya dijamin ter-flush dan tertutup
        # walau jalankan_gabungan() melempar exception di tengah
        # jalan, jadi baris yang sudah ditulis tidak hilang. Tiga CSV
        # (zona + crossing + snapshot) dibuka bersarang supaya
        # sama-sama dijamin ter-flush lewat context manager yang sama.
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f, \
                open(CROSSING_CSV_PATH, "w", encoding="utf-8", newline="") as f_crossing, \
                open(SNAPSHOT_CSV_PATH, "w", encoding="utf-8", newline="") as f_snapshot:
            penulis = csv.DictWriter(f, fieldnames=KOLOM)
            penulis.writeheader()

            penulis_crossing = csv.DictWriter(f_crossing, fieldnames=KOLOM_CROSSING)
            penulis_crossing.writeheader()

            penulis_snapshot = csv.DictWriter(f_snapshot, fieldnames=KOLOM_SNAPSHOT)
            penulis_snapshot.writeheader()

            # Semua kamera terpilih dibaca round-robin dalam satu loop
            # dan (kalau tampilkan_live) tiap kamera dapat window
            # sendiri -- lihat jalankan_gabungan(). Q ditekan
            # menghentikan semua kamera bersamaan di dalamnya, tapi
            # baris yang sudah terkumpul tetap dikembalikan.
            statistik = jalankan_gabungan(
                dipilih,
                args.durasi,
                args.langkah,
                args.frame_visual,
                args.imgsz,
                penulis,
                penulis_crossing,
                penulis_snapshot,
                tampilkan_live,
            )
    finally:
        # Selalu dipanggil -- baik selesai normal, ditekan Q, maupun
        # kalau ada error lain di tengah jalan. Popup yang lupa
        # ditutup bisa bikin proses OpenCV nyangkut di background.
        if tampilkan_live:
            cv2.destroyAllWindows()

    cetak_cuplikan_csv(20, CSV_PATH)
    cetak_cuplikan_csv(20, CROSSING_CSV_PATH)
    cetak_cuplikan_csv(20, SNAPSHOT_CSV_PATH)
    cetak_statistik(statistik)

    print()
    print("Gambar bukti:")
    for nama_kamera in dipilih:
        p = os.path.join(
            OUTPUT_DIR,
            f"zona_test_{nama_kamera.replace('_', '')}.jpg",
        )
        if os.path.exists(p):
            print(f"  {p}")

    # Upload HF/Supabase jalan di background sejak tiap kamera
    # selesai merekam (lihat KameraState.tutup()) -- ditunggu di sini
    # supaya program tidak exit sebelum semuanya benar-benar beres.
    if _UPLOAD_FUTURES:
        print()
        print(f"Menunggu {len(_UPLOAD_FUTURES)} upload HuggingFace selesai...")
        concurrent.futures.wait(_UPLOAD_FUTURES)
        print("Semua upload selesai.")

    _UPLOAD_EXECUTOR.shutdown(wait=True)


if __name__ == "__main__":
    main()
