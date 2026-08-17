"""
SMARTTWIN
Real-Time Multi-Camera Vehicle Detection & Counting

Input:
    4 video (.mp4) — 4 LENGAN dari SATU simpang (Simpang Pingit),
    bukan 4 persimpangan berbeda. Lihat CAMERAS di bagian 2.

Pipeline:
    Video
      ↓
    YOLO26s
      ↓
    ByteTrack
      ↓
    Vehicle Tracking (person/bicycle dilacak hanya untuk logika rider)
      ↓
    Centroid
      ↓
    Counting Line
      ↓
    Per-second crossing volume
      ↓
    Queue estimation
      ↓
    Density estimation
      ↓
    CSV

CSV output:
    timestamp
    intersection_id
    approach
    lane_id
    vehicle_count
    car_count
    motorcycle_count
    bus_count
    truck_count
    queue_length_veh
    queue_length_m_est
    density_index

NOTE:
- timestamp = JAM REKAMAN, diturunkan dari posisi frame lewat peta
  keping di sync_report.json — bukan jam laptop saat diproses.
  Karena itu keempat lengan memakai detik yang sama persis, dan
  hasilnya tidak berubah walau videonya diproses ulang di mesin
  lain. Detiknya melompat di sambungan keping: rentang yang
  dibuang saat sinkronisasi memang tidak punya rekaman. Lihat
  bagian 4B.
- intersection_id konstan (INTERSECTION_ID) karena seluruh kamera
  memantau simpang yang sama. Yang membedakan baris adalah approach.
- approach = north/south/east/west, mengikuti Approach di
  docs/data-contract.md. lane_id adalah lajur DI DALAM satu lengan.
- vehicle_count = car + motorcycle + bus + truck crossing the counting line
  during the current one-second interval, DIPECAH PER LAJUR: crossing
  dicatat pada lajur tempat kendaraan berada saat memotong garis.
  car_count/motorcycle_count/bus_count/truck_count adalah rincian kelas
  dari populasi yang sama, jadi keempatnya selalu berjumlah
  vehicle_count.
- DUA POPULASI dalam satu baris — jangan dicampur:
      ALIRAN    (memotong garis)  -> vehicle_count + *_count
      KEHADIRAN (terlihat di frame) -> queue_length_veh,
                                       queue_length_m_est,
                                       density_index
  Konsekuensinya vehicle_count wajar jauh lebih kecil daripada jumlah
  kendaraan yang terlihat di layar, dan kendaraan yang berhenti
  mengantre menyumbang ke kolom queue TAPI tidak ke vehicle_count
  selama ia belum bergerak melewati garis.
  Sampai 17 Agustus 2026 kolom volume keliru diambil dari KEHADIRAN,
  sehingga COUNTING_LINES/ARAH_MASUK tidak berpengaruh sama sekali
  terhadap CSV. Angka volume sebelum tanggal itu tidak sebanding
  dengan angka sesudahnya.
- person and bicycle are still detected and tracked, but deliberately NOT
  written to the CSV: docs/data-contract.md limits VehicleClass to
  motorcycle/car/bus/truck. Person detection is kept because it is what
  lets person_is_rider() suppress motorcycle riders from being counted
  twice — dropping it would break motorcycle counts.
- queue_length_veh = JUMLAH KENDARAAN yang hampir tidak bergerak di area
  antrean. Ini angka mentah hasil pengamatan, bukan panjang.
- queue_length_m_est = turunan queue dalam METER, dihitung per jenis
  kendaraan lewat QUEUE_SPACE_M (motor 2 m, mobil 5 m, bus/truk 10 m).
  Angka-angka itu ESTIMASI KESEPAKATAN TIM, bukan kutipan PKJI 2023 —
  lihat catatan lengkap di bagian 9. Namanya berakhiran _est justru
  supaya tidak pernah tertukar dengan hasil pengukuran.
  Dihitung dari kendaraan yang BERSTATUS ANTRE saja (penghitung
  queue_* per kelas), populasi yang sama persis dengan
  queue_length_veh — bukan dari *_count, yang sejak 17 Agustus 2026
  berisi crossing (aliran) dan justru populasi yang berlawanan.
  Jadi kedua kolom queue itu selalu sepadan satu sama lain, tapi
  TIDAK sepadan dengan kolom volume.
- density_index = indeks kepadatan ternormalisasi:
      jumlah kendaraan terdeteksi / fraksi luas jalan
  BUKAN veh/km. Butuh kalibrasi kamera terhadap ukuran dunia nyata
  sebelum boleh disebut density fisik.
- lane_id is currently assigned from the centroid's horizontal position:
      lane_1 = left third
      lane_2 = middle third
      lane_3 = right third
  For a real intersection, adjust LANE_REGIONS to match the actual lanes.
"""

import bisect
import csv
import json
import os
import re
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta

import cv2
from ultralytics import YOLO


# ============================================================
# 0. BASE PATH
# ============================================================
#
# Semua path di bawah relatif terhadap folder cv/ ini, supaya
# modulnya jalan di laptop siapa pun tanpa perlu diedit dulu.
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 1. PATH MODEL
# ============================================================
#
# Bobot tidak ikut di repo (cv/models/ di-gitignore). Ambil dengan
# salah satu cara di cv/requirements.txt.
# ============================================================

MODEL_PATH = os.path.join(BASE_DIR, "models", "yolo26s.pt")


# ============================================================
# 2. VIDEO INPUT — 4 LENGAN DARI SATU SIMPANG
# ============================================================
#
# Key = approach sesuai docs/data-contract.md:
#     Approach = Literal["north", "south", "east", "west"]
#
# Ini BUKAN 4 persimpangan berbeda. Keempatnya adalah 4 lengan
# dari SATU simpang (Simpang Pingit), masing-masing punya kamera
# sendiri. Karena itu intersection_id-nya satu dan sama untuk
# seluruh baris CSV; yang membedakan baris adalah approach.
# ============================================================

INTERSECTION_ID = "simpang4-pingit"

VIDEO_DIR = os.path.join(BASE_DIR, "videos")

# PEMETAAN KAMERA → ARAH MATA ANGIN
# ---------------------------------
# Dikonfirmasi dari screenshot CCTV asli + peta lokasi
# (15 Agustus 2026). JANGAN ditebak dari nomor kameranya:
#
#   CCTV "SIMPANG PINGIT 1" — Jl. Tentara Pelajar     → south
#   CCTV "SIMPANG PINGIT 2" — Jl. Magelang            → north
#   CCTV "SIMPANG PINGIT 3" — Jl. Kyai Mojo           → west
#   CCTV "SIMPANG PINGIT 4" — Jl. Pangeran Diponegoro → east
#
# Nomor kamera dan arah mata angin TIDAK berurutan — Pingit 1
# itu lengan selatan, Pingit 2 lengan utara. Versi sebelumnya
# tertukar persis di dua lengan ini.
#
# Keempat lengan sekarang aktif (16 Agustus 2026).
#
# Yang dibaca adalah video HASIL SINKRONISASI, bukan rekaman
# mentah: keempatnya sudah dipotong ke jendela waktu bersama
# lewat sync_videos.py, jadi frame ke-N di keempat file itu
# jam dindingnya sama. Rekaman mentahnya dulu bernama
# "CCTV 1.mp4" (pakai spasi); nama sekarang pakai garis bawah.
#
# Catatan dari proses sinkronisasi yang masih berlaku di sini:
# laju jam tiap channel DVR tidak sama persis (selisih ~0,3%
# antara Pingit 3 dan Pingit 4), jadi di ujung rekaman ~56 menit
# keempatnya bisa hanyut ~10 detik satu sama lain. Aman untuk
# agregasi per jendela 5 menit; tidak aman untuk mencocokkan
# kejadian antar-lengan frame demi frame.

CAMERAS = {
    # Pingit 1 (Jl. Tentara Pelajar) — lengan selatan
    "south": os.path.join(VIDEO_DIR, "CCTV_1.mp4"),

    # Pingit 2 (Jl. Magelang) — lengan utara
    "north": os.path.join(VIDEO_DIR, "CCTV_2.mp4"),

    # Pingit 3 (Jl. Kyai Mojo) — lengan barat
    "west": os.path.join(VIDEO_DIR, "CCTV_3.mp4"),

    # Pingit 4 (Jl. Pangeran Diponegoro) — lengan timur
    #
    # Sumbernya CCTV_2.mp4 — VIDEO YANG SAMA dengan north. Itu
    # bukan salah ketik.
    #
    # CCTV 4 sempat jadi sumber east lalu ditinggalkan (lihat 6C).
    # Penggantinya: menarik lengan Diponegoro dari koridor jalan
    # yang terlihat di frame CCTV 2 — dua lengan dari satu kamera,
    # dibedakan oleh garis hitungnya masing-masing. Garis east
    # digambar dari analisa langsung frame CCTV 2, jadi ia memang
    # dikalibrasi untuk video ini.
    #
    # Sampai 16 Agustus 2026 pengaturan ini tidak ada gunanya:
    # kolom volume CSV diambil dari kendaraan yang terlihat di
    # frame, bukan dari crossing, sehingga east dan north — video
    # sama, garis beda — menghasilkan 7.578 baris yang identik
    # byte demi byte. Sejak kolom volume benar-benar bersumber
    # dari crossing (17 Agustus 2026), garis yang berbeda baru
    # menghasilkan angka yang berbeda.
    #
    # YANG MASIH TERBUKA — bukan soal garisnya, tapi soal koridor
    # tempat garis itu dipasang: koridor tersebut Diponegoro atau
    # Magelang? Belum diuji dengan bearing terhadap network SUMO
    # maupun uji silang kendaraan antar-kamera. Kalau ternyata
    # Magelang, east dan north menghitung lengan yang sama dua
    # kali — kesalahan yang jauh lebih halus daripada baris
    # identik kemarin, karena angkanya akan kelihatan wajar.
    #
    # Cara menonaktifkan kalau pertanyaan itu nanti terjawab
    # buruk: komentari baris di bawah dan hidupkan kembali entri
    # "east" di LENGAN_TIDAK_TERUKUR (bagian 6C).
    "east": os.path.join(VIDEO_DIR, "CCTV_2.mp4"),
    #
    # CCTV 4 sebagai sumber east — DITINGGALKAN, bukan sekadar
    # dimatikan. Kameranya tidak mencakup mulut lengan Diponegoro
    # (bukti dan angkanya di bagian 6C), dan ia butuh imgsz=1920
    # supaya kendaraannya terdeteksi — jauh lebih lambat dari
    # lengan lain.
    # "east": os.path.join(VIDEO_DIR, "CCTV_4.mp4"),
}


# ============================================================
# 3. YOLO CONFIDENCE
# ============================================================

CONFIDENCE = 0.35


# ============================================================
# 4. OUTPUT CSV
# ============================================================

OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CSV_PATH = os.path.join(
    OUTPUT_DIR,
    "smarttwin_traffic_data.csv"
)


# ============================================================
# 4B. JAM DINDING DARI POSISI FRAME
# ============================================================
#
# Diberi nomor 4B, bukan 5, supaya penomoran bagian sesudahnya
# tidak bergeser — beberapa komentar di file ini menunjuk ke
# "bagian 9" dan seterusnya.
#
# MASALAH YANG DIPERBAIKI
# -----------------------
# Versi sebelumnya menulis timestamp CSV dengan datetime.now(),
# yaitu jam LAPTOP saat frame itu selesai diproses. Empat thread
# YOLO tidak jalan dengan kecepatan yang sama, jadi detik yang
# sama di dunia nyata muncul dengan timestamp berbeda-beda di
# tiap lengan — persis hal yang bikin sinkronisasi videonya
# jadi sia-sia begitu masuk CSV.
#
# Sekarang timestamp diturunkan dari POSISI FRAME di video, jadi
# hasilnya sama saja mau diproses di laptop cepat atau lambat,
# mau realtime atau ditinggal semalaman.
#
# KENAPA TIDAK CUKUP (idx / fps) + jam mulai
# ------------------------------------------
# Video hasil sinkronisasi BUKAN rekaman utuh. Isinya 18 keping
# yang disambung; di antaranya ada 15 jeda yang dibuang (1 di
# depan + 14 di tengah). Kalau waktunya dianggap berjalan linear
# dari awal sampai akhir, di ujung video meleset **342 detik
# (5 menit 42 detik)** — bukan urusan pembulatan, tapi salah
# menit. Karena itu peta di bawah memetakan per keping.
#
# Di DALAM satu keping, (idx / fps) memang cukup: selisih antara
# n_frame/fps dan durasi yang dilaporkan sync_report.json paling
# besar 0,0153 detik, jauh di bawah resolusi CSV yang 1 detik.
#
# SUMBER ANGKA
# ------------
# cv/output/sync_report.json:
#   videos[].potongan[].w0       jam dinding awal keping
#                                (detik sejak tengah malam)
#   videos[].potongan[].n_frame  jumlah frame keping itu di
#                                video keluaran
#
# Dipakai w0 milik VIDEO MASING-MASING, bukan dipakai[].mulai
# yang global, supaya tiap kamera memakai angka hasil fit-nya
# sendiri. (Sudah dicek: keduanya sama sampai <0,002 detik, dan
# keempat video punya n_frame yang identik keping demi keping —
# 78.046 frame @30 fps. Jadi baris CSV keempat lengan memang
# akan jatuh pada detik yang sama.)
#
# Nomor frame dihitung SENDIRI dari pembacaan berurutan, tidak
# pernah dari CAP_PROP_POS_FRAMES. Itu pelajaran dari investigasi
# CCTV 1: pada MP4 terfragmentasi, posisi hasil seek bisa
# berbohong walau jam di layarnya terbaca sempurna.
# ============================================================

SYNC_REPORT_PATH = os.path.join(
    OUTPUT_DIR,
    "sync_report.json"
)

# TANGGAL REKAMAN — SATU-SATUNYA ANGKA DI SINI YANG TIDAK TERBACA
# DARI DATA, TOLONG DIKONFIRMASI.
#
# Jam burned-in di CCTV cuma memuat HH:MM:SS, tanpa tanggal, jadi
# sync_report.json juga tidak menyimpan tanggal. Nilai di bawah
# disimpulkan dari mtime video sumber yang tercatat di clockmap:
# CCTV 3 dan CCTV 4 selesai ditulis 2026-08-15 17:27:1x, sementara
# jam di layarnya berhenti 17:26:3x — selisih kurang dari satu
# menit. Kalau rekamannya ternyata hari lain, ganti baris ini saja;
# tidak ada tempat lain yang perlu diubah.
TANGGAL_REKAMAN = "2026-08-15"


class PetaJamVideo:
    """
    Peta nomor frame -> jam dinding untuk SATU video hasil
    sinkronisasi.

    Dibangun dari daftar potongan: tiap keping menyumbang
    (frame_awal_kumulatif, jumlah frame, jam dinding awal).
    Pencarian pakai bisect, jadi biayanya tetap sama walau
    kepingnya nanti jadi ratusan.
    """

    def __init__(
        self,
        potongan,
        tanggal_rekaman,
        fps
    ):
        self.fps = fps

        self.tengah_malam = datetime.strptime(
            tanggal_rekaman,
            "%Y-%m-%d"
        )

        # Indeks frame awal tiap keping, untuk bisect
        self.frame_awal = []

        # (jumlah_frame, jam_dinding_awal_detik) sejajar dengan
        # self.frame_awal
        self.keping = []

        kumulatif = 0

        for p in potongan:
            self.frame_awal.append(kumulatif)

            self.keping.append(
                (p["n_frame"], p["w0"])
            )

            kumulatif += p["n_frame"]

        self.total_frame = kumulatif


    def detik_dinding(self, frame_idx):
        """
        Jam dinding frame ke-`frame_idx` dalam detik sejak tengah
        malam.

        Balikannya None kalau frame-nya di luar peta — itu berarti
        videonya tidak cocok dengan laporannya, dan lebih baik
        baris CSV-nya TIDAK ditulis daripada ditulis dengan jam
        karangan.
        """
        if frame_idx < 0 or frame_idx >= self.total_frame:
            return None

        i = bisect.bisect_right(
            self.frame_awal,
            frame_idx
        ) - 1

        n_frame, wall_mulai = self.keping[i]

        offset = frame_idx - self.frame_awal[i]

        return wall_mulai + (offset / self.fps)


    def waktu(self, detik_dinding):
        """
        Detik sejak tengah malam -> objek datetime bertanggal.
        """
        return self.tengah_malam + timedelta(
            seconds=detik_dinding
        )


def nomor_kamera(path):
    """
    Menarik nomor kamera dari nama berkas: "CCTV_2.mp4" -> 2.

    Sengaja lewat angka, bukan cocokkan nama mentah-mentah:
    nama di sync_report.json masih nama rekaman asli ("CCTV 2.mp4",
    pakai spasi), sedangkan berkas hasil sinkronisasi memakai
    garis bawah.
    """
    cocok = re.search(
        r"(\d+)",
        os.path.basename(path)
    )

    return int(cocok.group(1)) if cocok else None


def muat_peta_jam(video_path, fps):
    """
    Membangun PetaJamVideo untuk satu video dari sync_report.json.

    Melempar RuntimeError kalau laporannya tidak ada atau videonya
    tidak tercatat di situ. Sengaja GAGAL KERAS, tidak diam-diam
    balik ke datetime.now() — jam laptop yang menyamar jadi jam
    rekaman itu justru bug yang sedang diperbaiki di sini, dan
    kalau ia kembali secara diam-diam tidak akan ketahuan dari
    isi CSV-nya.
    """
    if not os.path.exists(SYNC_REPORT_PATH):
        raise RuntimeError(
            f"sync_report.json tidak ditemukan di "
            f"{SYNC_REPORT_PATH}. Berkas itu satu-satunya sumber "
            f"jam mulai tiap keping video hasil sinkronisasi."
        )

    with open(
        SYNC_REPORT_PATH,
        "r",
        encoding="utf-8"
    ) as file:
        laporan = json.load(file)

    nomor = nomor_kamera(video_path)

    for v in laporan.get("videos", []):

        if nomor_kamera(v["nama"]) != nomor:
            continue

        potongan = v.get("potongan", [])

        if not potongan:
            raise RuntimeError(
                f"{v['nama']} tercatat di sync_report.json tapi "
                f"tidak punya daftar potongan."
            )

        return PetaJamVideo(
            potongan,
            TANGGAL_REKAMAN,
            fps
        )

    raise RuntimeError(
        f"{os.path.basename(video_path)} tidak ada di "
        f"sync_report.json. Video ini bukan keluaran "
        f"sync_videos.py, jadi jam dindingnya tidak diketahui."
    )


# ============================================================
# 5. YOLO CLASSES
# ============================================================

YOLO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

TRACK_CLASSES = list(YOLO_CLASSES.keys())


# ============================================================
# 6. COUNTING LINE
# ============================================================
#
# Format:
# (x1_ratio, y1_ratio, x2_ratio, y2_ratio)
#
# Example:
# (0.10, 0.65, 0.90, 0.65)
#
# berarti garis horizontal pada 65% tinggi video.
# ============================================================

# Nilainya ruang-gambar (posisi di dalam frame), bukan arah mata
# angin. Jadi kalibrasinya mengikuti VIDEO yang dipetakan ke key
# itu di CAMERAS, bukan kompasnya. Kalau pemetaan kamera→key
# berubah lagi, geometri di sini harus ikut pindah bersama
# videonya.
#
# PENTING — sejak batas ruas ditegakkan (lihat potongan_dalam_ruas
# di bagian 9), angka x DI SINI BENAR-BENAR BERLAKU. Sebelumnya
# untuk garis mendatar (y1 == y2) suku x hilang dari perhitungan
# side_of_line, jadi 0.10..0.90 cuma hiasan gambar sementara
# hitungannya memakai garis mendatar TAK HINGGA selebar frame.
COUNTING_LINES = {
    # BELUM DIKALIBRASI — masih default, dan kameranya memotret
    # badan simpang (bukan ruas lurus), jadi butuh pendekatan
    # tersendiri yang belum diputuskan.
    "north": (0.10, 0.65, 0.90, 0.65),

    # Pingit 4 (Jl. Pangeran Diponegoro) — lengan timur.
    #
    # PENTING: garis ini ditentukan dari analisa langsung frame
    # CCTV_2.mp4, yaitu video yang MEMANG dipakai east sekarang
    # (lihat CAMERAS). Jadi ia sudah menunjuk ke posisi yang
    # dimaksud di frame yang benar — bukan sisa kalibrasi CCTV 4.
    #
    # Sejak 17 Agustus 2026 garis ini BENAR-BENAR menentukan kolom
    # volume east di CSV. Sebelumnya kolom volume diambil dari
    # kendaraan yang terlihat di frame, jadi garis ini — dan
    # seluruh kalibrasi di bagian 6 — tidak berpengaruh sama
    # sekali. Menggeser angka di sini sekarang langsung menggeser
    # angka di CSV.
    #
    # Yang MASIH terbuka bukan posisi garisnya, melainkan
    # identitas koridor tempat ia dipasang: koridor jalan yang
    # terlihat di frame CCTV 2 itu Diponegoro atau Magelang?
    # Belum pernah diuji dengan bearing terhadap network SUMO
    # maupun uji silang kendaraan antar-kamera. Kalau ternyata
    # Magelang, east dan north menghitung lengan yang sama dua
    # kali. Lihat bagian 6C.
    #
    # RIWAYAT — dua kandidat garis untuk CCTV 4 (sumber east yang
    # LAMA, sudah ditinggalkan) sempat diuji berdampingan pada
    # lintasan yang sama, t=960..1020 s, setiap frame, imgsz=1920.
    # Angka di bawah bukan salah satunya, dan tidak sebanding
    # dengannya — beda kamera, beda frame:
    #
    #                                     mentah  terpakai  murni
    #   (0.651,0.419,0.865,0.378)  -6 deg    54      35     18,5 %
    #   (0.793,0.536,0.807,0.334)  86 deg    28       0      0,0 %
    #
    # Yang pertama menghasilkan angka tapi kemurnian arahnya cuma
    # 18,5 % — campuran beberapa pergerakan, bukan volume satu
    # lengan. Yang kedua habis disaring karena seluruh crossingnya
    # bergerak KELUAR simpang. Keduanya ditolak, dan CCTV 4 ikut
    # ditinggalkan sebagai sumber east.
    #
    # Angka di bawah adalah penggantinya, digambar di frame CCTV 2.
    "east":  (0.964, 0.659, 0.745, 0.461),

    # Pingit 1 / CCTV 1 — TERVERIFIKASI 16 Agustus 2026.
    # Median jalan ada di ATAS garis, jadi jalur berlawanan tidak
    # pernah menyentuhnya: 67 dari 67 crossing pada uji 60 detik
    # bergerak turun (menuju stop line). Dibiarkan apa adanya.
    #
    # BELUM DIPERIKSA — kontradiksi yang masih menggantung:
    # uji_estimasi_east.py melaporkan south cuma 1 crossing dalam
    # 3x40 detik (0,5/menit), padahal verifikasi di atas memberi
    # 67/67. Dugaan: artefak harness uji, bukan regresi logika
    # south — harness itu memproses hanya setiap frame ke-2
    # (LANGKAH=2) pada imgsz=960, jadi jejak terpecah dan sebagian
    # besar perpotongan jatuh di antara frame yang disampel.
    # Cara mengecek: jalankan ulang jendela yang sama dengan
    # LANGKAH=1 dan imgsz penuh.
    "south": (0.10, 0.65, 0.90, 0.65),

    # Pingit 3 / CCTV 3 — DIGANTI 16 Agustus 2026.
    #
    # Garis lama (0.10, 0.65, 0.90, 0.65) jatuh di bawah median,
    # nyaris SEJAJAR arah lalu lintas, jadi mayoritas kendaraan
    # tidak pernah memotongnya: cuma 14 crossing dari 174 track
    # pada uji 60 detik yang sama.
    #
    # Garis baru memotong TEGAK LURUS jalur yang menuju simpang.
    # Arah jalur diukur dengan optical flow per kotak uji:
    #   jalur ATAS median  vx=+5,6..+7,8  -> MENUJU simpang (kanan)
    #   jalur BAWAH median vx=-12..-18    -> MENJAUH
    # Sumbu jalannya +11 derajat, jadi garis ini dipasang pada
    # +101 derajat. Ujung bawah menempel di median, ujung atas
    # menyeberangi kedua lajur sampai deretan kendaraan di tepi.
    "west": (0.830, 0.753, 0.956, 0.345),
}


# ARAH MASUK SIMPANG — vektor di ruang-gambar (x ke kanan, y ke
# bawah) yang menunjuk ke arah simpang.
#
# Dipakai untuk menolak kendaraan yang MENJAUHI simpang. Tanpa ini
# crossing dihitung ke arah mana pun: pada CCTV 3, 3 dari 14
# crossing (21 %) datang dari jalur arah berlawanan.
#
# None = tidak disaring. Sengaja untuk north: kameranya memotret
# BADAN SIMPANG, kendaraannya berbelok ke segala arah, jadi "satu
# arah masuk" belum punya arti di sana. Menebak angkanya lebih
# berbahaya daripada membiarkannya terbuka.
#
# east dulu juga None dengan alasan yang sama. Sekarang ia punya
# nilai, sepasang dengan garis hitung east yang digambar di frame
# CCTV 2 (lihat COUNTING_LINES). Arah itu BELUM diadu dengan
# crossing nyata seperti yang sudah dilakukan untuk south (67/67)
# dan west (optical flow per kotak uji) — jadi kalau angka east
# nanti terasa terlalu kecil, tersangka pertamanya di sini:
# filter arah yang terlalu ketat akan membuang crossing yang
# sebenarnya sah.
ARAH_MASUK = {
    # Turun = menuju stop line. Terverifikasi: seluruh 67 crossing
    # CCTV 1 pada uji 60 detik searah ini.
    "south": (0.0, 1.0),

    # Sumbu jalan +11 derajat dari hasil optical flow di atas.
    "west": (0.98, 0.19),

    "north": None,
    "east": (-1.00, 0.05),
}


# ============================================================
# 6C. LENGAN YANG TIDAK DIUKUR LANGSUNG
# ============================================================
#
# STATUS SEKARANG: KOSONG — tidak ada lengan yang ditandai
# "tidak terukur". Keempat lengan diproses, termasuk east.
#
# Mekanismenya sendiri dipertahankan utuh karena east masih bisa
# jatuh kembali ke sini; cara menghidupkannya ada di bawah.
#
# RIWAYAT — kenapa east pernah ada di daftar ini:
# east semula diukur dari CCTV 4, dan kamera itu tidak mencakup
# mulut lengan Diponegoro. Rincian investigasinya ada di
# cv/_arsip/ (BUKTI_pita_atas_CCTV4_vs_CCTV2.jpg dan
# CATATAN-sync-cctv1.md); ringkasnya:
#
#   - Pada y < 0,28H frame CCTV 4 tidak ada badan jalan sama
#     sekali, hanya atap, baliho, dan kabel. YOLO imgsz=1920
#     conf=0,25 memberi 0 deteksi di seluruh pita itu dari 150
#     frame, dan 0 dari 289 lintasan berawal/berakhir di sana.
#   - Dua kandidat garis pengganti sudah diuji dan dua-duanya
#     ditolak (angkanya ada di COUNTING_LINES["east"]).
#   - Estimasi dari arus keluar TIDAK dipakai: belum tervalidasi,
#     dan harness pengukurnya sendiri bermasalah.
#
# Bukti yang sama mencatat sesuatu tentang CCTV 2 yang belakangan
# jadi dasar pengaturan sekarang: di frame CCTV 2 koridor jalan
# MENERUS melewati y=0,28H — 74 deteksi lolos di atas garis itu,
# terjauh y≈279 px (y/H 0,259). Jadi CCTV 2 memang memuat sebuah
# koridor jalan yang memanjang, dan di koridor itulah garis east
# sekarang dipasang (COUNTING_LINES["east"]).
#
# YANG BELUM DIBUKTIKAN: koridor itu Diponegoro atau Magelang.
# Bukti tersebut dibuat untuk menjawab pertanyaan lain (isi pita
# atas CCTV 4), jadi ia menunjukkan ADA koridor di sana, bukan
# koridor itu lengan yang mana. Menjawabnya perlu bearing garis
# terhadap network SUMO (TLS SIMPANG_CENTER) atau uji silang:
# satu kendaraan yang sama terlihat di dua kamera pada detik yang
# sama, lalu ditelusuri masuk dari lengan mana.
#
# Kalau east dikembalikan ke sini, barisnya tetap ditulis ke CSV
# supaya keempat lengan hadir dan jumlah barisnya konsisten, TAPI
# seluruh kolom angka dikosongkan.
#
# KENAPA KOSONG, BUKAN 0
# ----------------------
# 0 terbaca sebagai "terukur, hasilnya nol kendaraan" — itu klaim
# yang tidak kita punya buktinya. String kosong terbaca sebagai
# NULL/NaN oleh pandas dan sebagian besar pembaca CSV, jadi tidak
# bisa disalahartikan sebagai hasil deteksi.
#
# PERHATIAN UNTUK KONSUMEN HILIR: kalau ada yang menjumlahkan
# volume per lengan, sel kosong ini harus di-skip secara sadar
# (mis. .sum(skipna=True) atau .dropna()), bukan di-fillna(0).
# Meng-nol-kannya mengembalikan persis kesalahan yang dihindari
# di sini.
LENGAN_TIDAK_TERUKUR = {
    # "east": (
    #     "east tidak diukur langsung dari CCTV 4 - kamera tidak "
    #     "mencakup mulut lengan Diponegoro"
    # ),
}


# ============================================================
# 7. LANE REGIONS
# ============================================================
#
# Default:
#   lane_1 = 0% - 33%
#   lane_2 = 33% - 66%
#   lane_3 = 66% - 100%
#
# Ini adalah pembagian berdasarkan posisi X centroid.
# Untuk penelitian sebenarnya, sesuaikan dengan posisi lajur
# pada video masing-masing kamera.
# ============================================================

# BELUM DIKALIBRASI: masih pembagian sepertiga default di keempat
# lengan. Sesuaikan dengan posisi lajur asli tiap kamera Pingit.
# Sama seperti COUNTING_LINES: ini posisi di dalam frame, jadi
# ikut videonya — bukan arah mata anginnya.
LANE_REGIONS = {
    "north": [
        ("lane_1", 0.00, 0.33),
        ("lane_2", 0.33, 0.66),
        ("lane_3", 0.66, 1.00),
    ],
    "south": [
        ("lane_1", 0.00, 0.33),
        ("lane_2", 0.33, 0.66),
        ("lane_3", 0.66, 1.00),
    ],
    "east": [
        ("lane_1", 0.00, 0.33),
        ("lane_2", 0.33, 0.66),
        ("lane_3", 0.66, 1.00),
    ],
    "west": [
        ("lane_1", 0.00, 0.33),
        ("lane_2", 0.33, 0.66),
        ("lane_3", 0.66, 1.00),
    ],
}


# ============================================================
# 8. PEDESTRIAN / RIDER FILTER
# ============================================================

# Person hanya dihitung sebagai pedestrian jika centroid-nya
# berada di area pedestrian.
#
# Format:
#   (x1_ratio, y1_ratio, x2_ratio, y2_ratio)
#
# DEFAULT:
# seluruh frame dianggap area pedestrian, KECUALI person yang
# berada di area kendaraan akan difilter menggunakan hubungan
# spasial dengan bounding box kendaraan.
#
# Untuk hasil terbaik pada CCTV masing-masing simpang, isi
# PEDESTRIAN_ZONES dengan area trotoar/zebra crossing.
PEDESTRIAN_ZONES = {
    "north": [],
    "south": [],
    "east": [],
    "west": [],
}

# Jarak maksimum person ke bounding box motorcycle agar dianggap
# sebagai pengendara motor. Nilai dalam rasio terhadap tinggi frame.
RIDER_DISTANCE_RATIO = 0.12

# Person yang berada di bagian bawah/atas bounding box motorcycle
# dengan jarak dekat akan dianggap rider, bukan pedestrian.
RIDER_VERTICAL_OVERLAP_RATIO = 0.35


def point_in_zone(cx, cy, width, height, zone):
    """
    Mengecek apakah titik centroid berada di pedestrian zone.
    """
    x1_ratio, y1_ratio, x2_ratio, y2_ratio = zone

    x1 = width * x1_ratio
    y1 = height * y1_ratio
    x2 = width * x2_ratio
    y2 = height * y2_ratio

    return x1 <= cx <= x2 and y1 <= cy <= y2


def is_in_pedestrian_zone(camera_name, cx, cy, width, height):
    """
    Jika PEDESTRIAN_ZONES belum dikonfigurasi, return True.
    Dengan begitu sistem tetap mempertahankan deteksi person,
    tetapi rider filter tetap bekerja.
    """
    zones = PEDESTRIAN_ZONES.get(camera_name, [])

    if not zones:
        return True

    return any(
        point_in_zone(cx, cy, width, height, zone)
        for zone in zones
    )


def person_is_rider(
    person_box,
    motorcycle_boxes,
    width,
    height
):
    """
    Menentukan apakah deteksi person kemungkinan merupakan
    pengendara motorcycle.

    Logika:
    1. Cari motorcycle yang dekat dengan person.
    2. Cek overlap horizontal.
    3. Cek jarak vertikal person terhadap motorcycle.
    """
    px1, py1, px2, py2 = person_box

    person_cx = (px1 + px2) / 2
    person_cy = (py1 + py2) / 2

    max_distance = height * RIDER_DISTANCE_RATIO

    for mx1, my1, mx2, my2 in motorcycle_boxes:
        motorcycle_cx = (mx1 + mx2) / 2

        # Overlap horizontal antara person dan motorcycle.
        horizontal_overlap = (
            min(px2, mx2) - max(px1, mx1)
        )

        person_width = max(px2 - px1, 1)
        motorcycle_width = max(mx2 - mx1, 1)

        overlap_ratio = horizontal_overlap / min(
            person_width,
            motorcycle_width
        )

        if overlap_ratio < RIDER_VERTICAL_OVERLAP_RATIO:
            # Jika tidak overlap cukup baik, cek kedekatan centroid.
            if abs(person_cx - motorcycle_cx) > (
                max(person_width, motorcycle_width) * 0.75
            ):
                continue

        # Motorcycle biasanya berada di bawah person.
        vertical_distance = my1 - py2

        # Person sedikit masuk/menempel dengan bbox motorcycle.
        if (
            vertical_distance <= max_distance
            and py2 >= my1 - max_distance
            and person_cy <= my2 + max_distance
        ):
            return True

    return False


# ============================================================
# 9. QUEUE PARAMETERS
# ============================================================

# Kendaraan dianggap berada di area antrean jika berada di
# sekitar / sebelum counting line.
QUEUE_ZONE_Y_RATIO = 0.65

# Perubahan centroid maksimum antar-frame agar dianggap
# "hampir berhenti".
STOPPED_PIXEL_THRESHOLD = 3.0

# Minimal jumlah frame berturut-turut dengan gerakan kecil
# sebelum kendaraan dianggap masuk antrean.
MIN_STOPPED_FRAMES = 5


# ------------------------------------------------------------
# Panjang ruang antrean per jenis kendaraan (meter)
# ------------------------------------------------------------
#
# Dipakai untuk menurunkan queue_length_m_est dari hitungan
# kendaraan. Tiap angka mewakili panjang badan kendaraan DITAMBAH
# jarak antar-kendaraan saat mengantre — jadi bukan panjang
# kendaraan saja.
#
# PENTING — dari mana angkanya:
# 2 / 5 / 10 meter ini ESTIMASI KESEPAKATAN TIM, BUKAN kutipan
# dari tabel resmi PKJI 2023. Jangan dipresentasikan sebagai
# angka standar.
#
# Kenapa dibedakan per jenis: motor, mobil, dan kendaraan besar
# menempati ruang antrean yang jauh berbeda, jadi satu angka flat
# untuk semua jenis akan bias — terlalu panjang di lengan yang
# didominasi motor, terlalu pendek di lengan yang banyak truk.
#
# TINDAK LANJUT kalau sempat: cek ulang terhadap tabel SMP
# (Satuan Mobil Penumpang) di PKJI 2023 untuk memperkuat
# validasi. Kalau angkanya diganti, perbarui juga catatan ini.
# ------------------------------------------------------------

QUEUE_SPACE_M = {
    "motorcycle": 2,
    "car": 5,
    "bus": 10,
    "truck": 10,
}


# ============================================================
# 9. HELPER
# ============================================================

def get_line(frame_width, frame_height, camera_name):
    x1_ratio, y1_ratio, x2_ratio, y2_ratio = COUNTING_LINES[
        camera_name
    ]

    x1 = int(frame_width * x1_ratio)
    y1 = int(frame_height * y1_ratio)

    x2 = int(frame_width * x2_ratio)
    y2 = int(frame_height * y2_ratio)

    return (x1, y1), (x2, y2)


def side_of_line(point, line_p1, line_p2):
    """
    Di sisi mana titik ini terhadap GARIS TAK HINGGA line_p1-line_p2.

    Fungsi ini sengaja dibiarkan tak hingga — itu memang definisi
    "sisi". Yang dulu keliru bukan fungsinya, melainkan memakai
    dia SENDIRIAN sebagai uji penyeberangan: untuk garis mendatar
    (y1 == y2) suku (y2-y1)*(x-x1) jadi nol, sehingga hasilnya
    hanya bergantung pada y dan panjang ruas x-nya tidak berarti
    apa-apa. Pembatas ruasnya ada di potongan_dalam_ruas().
    """
    x, y = point
    x1, y1 = line_p1
    x2, y2 = line_p2

    return (
        (x2 - x1) * (y - y1)
        -
        (y2 - y1) * (x - x1)
    )


def potongan_dalam_ruas(
    titik_lama,
    titik_baru,
    line_p1,
    line_p2
):
    """
    True kalau perpindahan titik_lama -> titik_baru memotong RUAS
    garis (line_p1..line_p2), bukan perpanjangannya.

    Dihitung dari titik potong sebenarnya, bukan sekadar mengecek
    x centroid ada di antara x1 dan x2. Bedanya baru terasa pada
    garis miring seperti "west", dan biayanya sama-sama beberapa
    perkalian.

    Parameter t adalah posisi titik potong di sepanjang garis:
    t=0 di line_p1, t=1 di line_p2. Jadi syaratnya 0 <= t <= 1.
    """
    rx = titik_baru[0] - titik_lama[0]
    ry = titik_baru[1] - titik_lama[1]

    sx = line_p2[0] - line_p1[0]
    sy = line_p2[1] - line_p1[1]

    penyebut = rx * sy - ry * sx

    # Gerakannya sejajar garis — tidak ada titik potong tunggal.
    if abs(penyebut) < 1e-9:
        return False

    qx = line_p1[0] - titik_lama[0]
    qy = line_p1[1] - titik_lama[1]

    t = (qx * ry - qy * rx) / penyebut

    return 0.0 <= t <= 1.0


def menuju_simpang(camera_name, dx, dy):
    """
    True kalau perpindahan (dx, dy) mengarah ke simpang.

    Dipakai untuk membuang kendaraan yang MENJAUHI simpang, yang
    seharusnya tidak masuk volume approach.

    Uji yang dipakai: hasil kali titik antara vektor gerak dan
    vektor ARAH_MASUK. Positif = komponen geraknya searah menuju
    simpang. Tanda dx/dy inilah yang selama ini sudah dihitung
    untuk deteksi berhenti tapi langsung dibuang (cuma
    magnitudonya yang dipakai).

    Lengan tanpa ARAH_MASUK (north/east) mengembalikan True —
    perilakunya persis seperti sebelumnya, tidak ada yang disaring.
    """
    arah = ARAH_MASUK.get(camera_name)

    if arah is None:
        return True

    return (dx * arah[0] + dy * arah[1]) > 0


def get_lane_id(camera_name, cx, frame_width):
    """
    Menentukan lane berdasarkan posisi X centroid.
    """
    x_ratio = cx / max(frame_width, 1)

    for lane_id, start_ratio, end_ratio in LANE_REGIONS[camera_name]:
        if start_ratio <= x_ratio < end_ratio:
            return lane_id

    return "unknown"


# Satu sumber kebenaran untuk header CSV, dipakai initialize_csv()
# maupun penulisan baris — supaya urutan kolom tidak bisa lagi
# menyimpang antara keduanya.
CSV_HEADER = [
    "timestamp",
    "intersection_id",
    "approach",
    "lane_id",
    "vehicle_count",
    "car_count",
    "motorcycle_count",
    "bus_count",
    "truck_count",
    "queue_length_veh",
    "queue_length_m_est",
    "density_index",
]


# Detik-detik yang benar-benar ditulis pada RUN INI. Dipakai
# untuk membangkitkan baris lengan yang tidak diukur pada detik
# yang sama persis, tanpa membaca ulang CSV lama yang mungkin
# sudah berisi hasil run sebelumnya (file ini ditulis mode append).
TIMESTAMP_TERTULIS = set()

_KUNCI_TIMESTAMP = threading.Lock()


def initialize_csv():
    """
    Membuat header CSV jika file belum ada.
    """
    if not os.path.exists(CSV_PATH):
        with open(
            CSV_PATH,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.writer(file)

            writer.writerow(CSV_HEADER)


# ============================================================
# 10. PER SECOND COUNTER
# ============================================================

class PerSecondCounter:

    def __init__(self, camera_name, peta_jam):
        self.camera_name = camera_name

        # Crossing yang terkumpul pada detik yang sedang berjalan,
        # DIPECAH PER LAJUR:
        #
        #     self.counts[lane_id][object_type] = jumlah crossing
        #
        # Dulu ini defaultdict(int) datar yang hanya di-key oleh
        # object_type, dan isinya cuma dipakai untuk print() ke
        # layar — kolom volume di CSV justru diambil dari kendaraan
        # yang TERLIHAT di frame. Akibatnya garis hitung tidak
        # berpengaruh sama sekali terhadap CSV; dua lengan yang
        # memakai video sama menghasilkan baris identik walau
        # garisnya beda. Lihat catatan "SEMANTIK KOLOM" di bagian 10.
        self.counts = defaultdict(
            lambda: defaultdict(int)
        )

        # Peta frame -> jam dinding (lihat bagian 4B). Batas detik
        # dibaca dari sini, BUKAN dari time.time(): satu baris CSV
        # harus mewakili satu detik VIDEO, bukan satu detik kerja
        # laptop. Kalau pakai jam laptop, thread yang kebetulan
        # lambat akan memadatkan beberapa detik video ke dalam
        # satu baris, dan volume/detik-nya jadi bohong.
        self.peta_jam = peta_jam

        # Detik dinding (bulat) yang sedang dikumpulkan
        self.detik_berjalan = None

        # Snapshot terakhir, dipakai flush_akhir() untuk menutup
        # detik terakhir saat videonya habis
        self.snapshot = None

        self.lock = threading.Lock()

        # Statistik realtime terakhir
        self.latest_stats = {}


    def add(self, object_type, lane_id):
        """
        Mencatat SATU crossing garis hitung.

        lane_id wajib: lajur tempat kendaraan berada pada frame
        saat ia memotong garis, hasil get_lane_id(). Tanpa itu
        volume tidak bisa dipecah per lajur dan kolom volume CSV
        terpaksa jatuh kembali ke hitungan kehadiran.
        """
        with self.lock:
            self.counts[lane_id][object_type] += 1


    def update(
        self,
        current_counts,
        queue_length,
        density,
        lane_counts,
        frame_idx
    ):
        detik = self.peta_jam.detik_dinding(
            frame_idx
        )

        # Frame di luar peta: tidak ada jam yang bisa
        # dipertanggungjawabkan, jadi tidak ada baris ditulis.
        if detik is None:
            return

        detik_bulat = int(detik)

        with self.lock:

            self.snapshot = (
                current_counts,
                queue_length,
                density,
                lane_counts
            )

            # Frame pertama: buka detik pertama, belum ada yang
            # bisa ditutup
            if self.detik_berjalan is None:
                self.detik_berjalan = detik_bulat

                return

            # Masih di detik yang sama -> terus kumpulkan
            if detik_bulat == self.detik_berjalan:
                return

            # Detik berganti -> tutup detik yang baru saja lewat.
            #
            # Di sambungan antar-keping, detik_bulat bisa melompat
            # puluhan detik sekaligus. Itu memang benar: rentang
            # yang dilompati tidak ada rekamannya, jadi CSV-nya
            # sengaja berlubang di situ. Jangan diisi baris kosong
            # supaya tidak terbaca sebagai "lalu lintas nol".
            self.write_csv(
                detik_dinding=self.detik_berjalan,
                current_counts=current_counts,
                queue_length=queue_length,
                density=density,
                lane_counts=lane_counts
            )

            self.counts = defaultdict(
                lambda: defaultdict(int)
            )

            self.detik_berjalan = detik_bulat


    def flush_akhir(self):
        """
        Menutup detik terakhir saat video habis.

        Tanpa ini, detik terakhir tiap video hilang tanpa suara —
        cacat lama yang ikut terbawa dari versi berbasis
        time.time().
        """
        with self.lock:

            if self.detik_berjalan is None or self.snapshot is None:
                return

            (
                current_counts,
                queue_length,
                density,
                lane_counts
            ) = self.snapshot

            self.write_csv(
                detik_dinding=self.detik_berjalan,
                current_counts=current_counts,
                queue_length=queue_length,
                density=density,
                lane_counts=lane_counts
            )

            self.counts = defaultdict(
                lambda: defaultdict(int)
            )

            self.detik_berjalan = None


    def write_csv(
        self,
        detik_dinding,
        current_counts,
        queue_length,
        density,
        lane_counts
    ):
        # Jam REKAMAN, diturunkan dari posisi frame — bukan
        # datetime.now(). Lihat bagian 4B.
        timestamp = self.peta_jam.waktu(
            detik_dinding
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # ----------------------------------------------------
        # SEMANTIK KOLOM — BACA SEBELUM MENGUBAH
        # ----------------------------------------------------
        #
        # Ada DUA populasi berbeda di satu baris CSV, dan keduanya
        # sengaja tidak dicampur:
        #
        #   ALIRAN (self.counts)     kendaraan yang MEMOTONG garis
        #                            hitung selama detik ini
        #     -> vehicle_count, car_count, motorcycle_count,
        #        bus_count, truck_count
        #
        #   KEHADIRAN (lane_counts)  kendaraan yang TERLIHAT di
        #                            frame pada detik ini
        #     -> queue_length_veh, queue_length_m_est,
        #        density_index
        #
        # Kenapa dipisah: volume/detik itu ukuran ALIRAN — satu
        # kendaraan boleh dihitung sekali seumur hidupnya (dijaga
        # counted_ids). Antrean dan kepadatan justru ukuran
        # KEHADIRAN — kendaraan yang berhenti mengantre harus tetap
        # terhitung di setiap detik ia masih ada di sana. Memakai
        # satu populasi untuk keduanya salah di dua arah sekaligus.
        #
        # RIWAYAT — kenapa catatan ini panjang:
        # sampai 17 Agustus 2026 kolom volume DIAMBIL DARI KEHADIRAN,
        # padahal docstring di kepala berkas sudah menjanjikan
        # crossing sejak awal. Akibatnya COUNTING_LINES dan
        # ARAH_MASUK tidak berpengaruh apa pun terhadap CSV: seluruh
        # kalibrasi garis di bagian 6 cuma menggambar garis di
        # layar. Ketahuan karena east dan north — yang membaca video
        # yang sama dengan garis berbeda — menghasilkan 7.578 baris
        # yang identik byte demi byte.
        #
        # Jadi kalau suatu saat kolom volume terasa "terlalu kecil"
        # dibanding yang terlihat di layar, ITU MEMANG BENAR: yang
        # di layar adalah kehadiran, yang di kolom adalah aliran.
        # Jangan diperbaiki dengan mengembalikannya ke lane_counts.
        # ----------------------------------------------------

        # ----------------------------------------------------
        # Satu baris per lane
        # ----------------------------------------------------
        #
        # Lajur yang ditulis = gabungan lajur yang PUNYA KEHADIRAN
        # dan lajur yang PUNYA CROSSING pada detik ini.
        #
        # Gabungan, bukan salah satu: crossing bisa terjadi di lajur
        # yang pada frame penutup detik sudah kosong (kendaraannya
        # keburu lewat), dan sebaliknya lajur yang macet total punya
        # antrean tanpa satu pun crossing. Kalau hanya salah satu
        # yang dipakai, salah satu jenis baris itu hilang diam-diam.
        # ----------------------------------------------------

        file_exists = os.path.exists(CSV_PATH)

        with open(
            CSV_PATH,
            "a",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            if not file_exists:
                writer.writerow(CSV_HEADER)

            # Detik ini dicatat supaya lengan yang tidak diukur
            # bisa diberi baris pada detik yang sama (bagian 6C).
            with _KUNCI_TIMESTAMP:
                TIMESTAMP_TERTULIS.add(timestamp)

            lanes = list(lane_counts.keys())

            # .keys() langsung, BUKAN self.counts[lane] — indexing
            # defaultdict akan membuat lajur kosong baru sambil
            # diiterasi.
            for lane_id in self.counts.keys():
                if lane_id not in lanes:
                    lanes.append(lane_id)

            # Jika belum ada lane yang terdeteksi,
            # tetap tulis lane_1.
            if not lanes:
                lanes = ["lane_1"]

            for lane_id in lanes:

                lane = lane_counts.get(
                    lane_id,
                    {}
                )

                # ALIRAN — crossing garis hitung pada lajur ini.
                # .get() supaya lajur yang cuma punya kehadiran
                # tidak ikut terbuat di self.counts.
                crossing = self.counts.get(
                    lane_id,
                    {}
                )

                car = crossing.get("car", 0)
                motorcycle = crossing.get("motorcycle", 0)
                bus = crossing.get("bus", 0)
                truck = crossing.get("truck", 0)

                vehicle_count_lane = (
                    car
                    + motorcycle
                    + bus
                    + truck
                )

                # Estimasi panjang antrean dalam meter.
                #
                # Sumbernya queue_* — kendaraan yang benar-benar
                # berstatus antre pada detik ini — BUKAN car/
                # motorcycle/bus/truck di atas, yang sekarang berisi
                # crossing (aliran) dan justru populasi yang
                # berlawanan: kendaraan yang antre malah TIDAK
                # memotong garis selama ia masih berhenti.
                # Dengan begitu queue_length_m_est dan
                # queue_length_veh menghitung populasi yang sama.
                #
                # Angka meternya dari QUEUE_SPACE_M; lihat catatan
                # di bagian 9 soal asal-usul angka tersebut.
                queue_length_m_est = sum(
                    lane.get(f"queue_{kelas}", 0) * meter
                    for kelas, meter in QUEUE_SPACE_M.items()
                )

                writer.writerow([
                    timestamp,

                    # Satu simpang, sama untuk semua lengan & lane
                    INTERSECTION_ID,

                    # Lengan asal kamera: north / south / east / west
                    self.camera_name,

                    lane_id,

                    # Volume kendaraan per detik — ALIRAN
                    # (crossing garis), bukan kehadiran di frame
                    vehicle_count_lane,

                    car,
                    motorcycle,
                    bus,
                    truck,

                    # Antrean sebagai JUMLAH KENDARAAN (mentah)
                    lane.get("queue_length", 0),

                    # Turunan dalam meter — estimasi, bukan ukuran
                    queue_length_m_est,

                    # Indeks kepadatan ternormalisasi, BUKAN veh/km
                    round(
                        lane.get("density", 0.0),
                        6
                    )
                ])


        # Total crossing seluruh lajur pada detik ini — angka yang
        # sama dengan jumlah kolom vehicle_count baris-baris di
        # atas, supaya yang terlihat di terminal bisa langsung
        # diadu dengan yang masuk CSV.
        vehicle_count = sum(
            per_kelas.get(kelas, 0)
            for per_kelas in self.counts.values()
            for kelas in ("car", "motorcycle", "bus", "truck")
        )

        print(
            f"[{timestamp}] "
            f"{self.camera_name} | "
            f"vehicle={vehicle_count}/detik | "
            f"queue={queue_length} | "
            f"density={density:.6f}"
        )


# ============================================================
# 11. CAMERA PROCESSOR
# ============================================================

class CameraProcessor:

    def __init__(
        self,
        camera_name,
        video_path,
        peta_jam
    ):
        self.camera_name = camera_name

        self.video_path = video_path

        self.peta_jam = peta_jam

        self.running = True

        self.frame = None

        self.lock = threading.Lock()

        self.counter = PerSecondCounter(
            camera_name,
            peta_jam
        )

        # ----------------------------------------------------
        # ID yang sudah dihitung
        # ----------------------------------------------------

        self.counted_ids = set()

        # ----------------------------------------------------
        # Posisi kendaraan sebelumnya
        # ----------------------------------------------------

        self.last_side = {}

        self.last_centroids = {}

        # Berapa frame kendaraan bergerak sangat sedikit
        self.stopped_frames = defaultdict(int)

        # ----------------------------------------------------
        # Statistik realtime
        # ----------------------------------------------------

        self.current_counts = {
            "person": 0,
            "bicycle": 0,
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0,
        }


    # ========================================================
    # RUN CAMERA
    # ========================================================

    def run(self):

        print(
            f"[INFO] Membuka {self.camera_name}: "
            f"{self.video_path}"
        )

        cap = cv2.VideoCapture(
            self.video_path
        )

        if not cap.isOpened():

            print(
                f"[ERROR] Tidak dapat membuka "
                f"{self.video_path}"
            )

            self.running = False

            return


        # ----------------------------------------------------
        # Load YOLO26s
        # ----------------------------------------------------

        print(
            f"[INFO] Loading YOLO26s "
            f"untuk {self.camera_name}"
        )

        model = YOLO(MODEL_PATH)


        # ----------------------------------------------------
        # FPS video
        # ----------------------------------------------------

        fps = cap.get(
            cv2.CAP_PROP_FPS
        )

        if fps <= 0:
            fps = 25

        frame_delay = 1.0 / fps


        # ----------------------------------------------------
        # Nomor frame
        # ----------------------------------------------------
        #
        # Dihitung sendiri dari pembacaan berurutan. TIDAK pakai
        # CAP_PROP_POS_FRAMES: pada MP4 terfragmentasi nilai itu
        # bisa meleset, dan seluruh timestamp CSV bergantung
        # padanya. Lihat bagian 4B.
        frame_idx = -1


        # ====================================================
        # LOOP
        # ====================================================

        while self.running:

            start_time = time.time()

            ret, frame = cap.read()

            if not ret:

                print(
                    f"[INFO] {self.camera_name} "
                    f"selesai."
                )

                break


            frame_idx += 1


            height, width = frame.shape[:2]


            # ------------------------------------------------
            # Counting line
            # ------------------------------------------------

            line_p1, line_p2 = get_line(
                width,
                height,
                self.camera_name
            )


            # ------------------------------------------------
            # YOLO + ByteTrack
            # ------------------------------------------------

            results = model.track(

                frame,

                persist=True,

                tracker="bytetrack.yaml",

                classes=TRACK_CLASSES,

                conf=CONFIDENCE,

                verbose=False,
            )


            result = results[0]

            boxes = result.boxes


            # ------------------------------------------------
            # Reset statistik realtime
            # ------------------------------------------------

            self.current_counts = {
                "person": 0,
                "bicycle": 0,
                "car": 0,
                "motorcycle": 0,
                "bus": 0,
                "truck": 0,
            }


            # ------------------------------------------------
            # Lane statistics
            # ------------------------------------------------

            lane_current = defaultdict(
                lambda: {
                    "vehicle_count": 0,
                    "car_count": 0,
                    "motorcycle_count": 0,
                    "bus_count": 0,
                    "truck_count": 0,

                    # Total kendaraan berstatus antre di lane ini.
                    "queue_length": 0,

                    # Pecahan per kelas dari queue_length di atas.
                    # HARUS berasal dari populasi yang sama persis
                    # (is_queue_vehicle), supaya queue_length_m_est
                    # konsisten dengan queue_length_veh. Jangan
                    # menurunkannya dari *_count di atas — itu semua
                    # kendaraan terdeteksi, termasuk yang melaju.
                    "queue_car": 0,
                    "queue_motorcycle": 0,
                    "queue_bus": 0,
                    "queue_truck": 0,

                    "density": 0.0,
                    "current_objects": 0,
                    "area_fraction": 0.0,
                }
            )


            # ------------------------------------------------
            # Tracking
            # ------------------------------------------------

            if (
                boxes is not None
                and boxes.id is not None
            ):

                track_ids = (
                    boxes.id
                    .int()
                    .cpu()
                    .tolist()
                )

                classes = (
                    boxes.cls
                    .int()
                    .cpu()
                    .tolist()
                )

                coordinates = (
                    boxes.xyxy
                    .cpu()
                    .tolist()
                )


                # ============================================
                # Siapkan daftar bounding box motorcycle
                # ============================================

                motorcycle_boxes = [
                    box
                    for cls_id, box in zip(classes, coordinates)
                    if cls_id == 3
                ]

                # ============================================
                # Setiap objek
                # ============================================

                for (
                    track_id,
                    cls_id,
                    box
                ) in zip(
                    track_ids,
                    classes,
                    coordinates
                ):

                    x1, y1, x2, y2 = box


                    # ----------------------------------------
                    # Centroid
                    # ----------------------------------------

                    cx = (
                        x1 + x2
                    ) / 2

                    cy = (
                        y1 + y2
                    ) / 2


                    object_type = (
                        YOLO_CLASSES.get(
                            cls_id,
                            "unknown"
                        )
                    )

                    if object_type == "unknown":
                        continue

                    # ------------------------------------------------
                    # FILTER RIDER
                    # ------------------------------------------------
                    # YOLO dapat mendeteksi pengendara sebagai person
                    # walaupun motorcycle juga terdeteksi.
                    #
                    # Jika person dekat dengan motorcycle, ubah
                    # klasifikasinya menjadi motorcycle agar:
                    # - tidak dihitung sebagai pejalan kaki
                    # - masuk vehicle_count
                    # - masuk motorcycle_count
                    # - dapat dihitung sebagai queue kendaraan
                    #
                    # Person yang tidak berhubungan dengan motorcycle
                    # tetap diproses sebagai person/pedestrian.
                    if object_type == "person":
                        is_rider = person_is_rider(
                            person_box=(x1, y1, x2, y2),
                            motorcycle_boxes=motorcycle_boxes,
                            width=width,
                            height=height
                        )

                        if is_rider:
                            object_type = "motorcycle"
                        elif not is_in_pedestrian_zone(
                            self.camera_name,
                            cx,
                            cy,
                            width,
                            height
                        ):
                            # Person di luar pedestrian zone dan tidak
                            # terhubung dengan motorcycle tidak dihitung
                            # sebagai pedestrian.
                            continue


                    # ----------------------------------------
                    # Lane
                    # ----------------------------------------

                    lane_id = get_lane_id(
                        self.camera_name,
                        cx,
                        width
                    )


                    # ----------------------------------------
                    # Current detection
                    # ----------------------------------------

                    self.current_counts[
                        object_type
                    ] += 1

                    lane_current[lane_id][
                        "current_objects"
                    ] += 1


                    # ----------------------------------------
                    # Kendaraan
                    # ----------------------------------------
                    #
                    # Hitungan per kelas hanya untuk kelas kendaraan.
                    # person/bicycle sengaja tidak punya kolom sendiri
                    # (lihat catatan CSV output di header file), jadi
                    # key f"{object_type}_count" untuk keduanya memang
                    # tidak ada di lane_current.
                    #
                    # PERHATIAN — ini hitungan KEHADIRAN (kendaraan
                    # yang terlihat di frame), BUKAN isi kolom
                    # car_count/motorcycle_count/... di CSV. Kolom
                    # CSV diambil dari crossing garis; lihat catatan
                    # "SEMANTIK KOLOM" di write_csv.
                    #
                    # Yang masih memakai angka kehadiran ini cuma
                    # perhitungan DENSITY di bawah. Key "vehicle_count"
                    # di lane_current sengaja dipertahankan sebagai
                    # subtotal kehadiran, tapi TIDAK ADA yang
                    # membacanya lagi untuk CSV — jangan disambungkan
                    # kembali ke kolom volume, itu persis cacat yang
                    # bikin east dan north keluar identik.
                    # ----------------------------------------

                    if object_type in VEHICLE_CLASSES.values():

                        lane_current[lane_id][
                            f"{object_type}_count"
                        ] += 1

                        lane_current[lane_id][
                            "vehicle_count"
                        ] += 1


                    # ----------------------------------------
                    # Movement / stopped detection
                    # ----------------------------------------

                    previous_centroid = (
                        self.last_centroids.get(
                            track_id
                        )
                    )

                    if previous_centroid is not None:

                        dx = (
                            cx
                            - previous_centroid[0]
                        )

                        dy = (
                            cy
                            - previous_centroid[1]
                        )

                        movement = (
                            dx * dx
                            + dy * dy
                        ) ** 0.5


                        if movement <= STOPPED_PIXEL_THRESHOLD:

                            self.stopped_frames[
                                track_id
                            ] += 1

                        else:

                            self.stopped_frames[
                                track_id
                            ] = 0


                    self.last_centroids[
                        track_id
                    ] = (cx, cy)


                    # ----------------------------------------
                    # Queue detection
                    # ----------------------------------------
                    #
                    # Hanya kendaraan yang:
                    # 1. berada di area antrean
                    # 2. bergerak sangat sedikit
                    # 3. sudah stabil beberapa frame
                    # ----------------------------------------

                    queue_zone_y = (
                        height
                        * QUEUE_ZONE_Y_RATIO
                    )

                    is_queue_vehicle = (
                        object_type in VEHICLE_CLASSES.values()
                        and cy >= queue_zone_y
                        and self.stopped_frames[
                            track_id
                        ] >= MIN_STOPPED_FRAMES
                    )

                    if is_queue_vehicle:

                        lane_current[lane_id][
                            "queue_length"
                        ] += 1

                        # Pecah per kelas dari populasi yang SAMA.
                        # Aman pakai key dinamis karena
                        # is_queue_vehicle sudah menjamin
                        # object_type ada di VEHICLE_CLASSES.
                        lane_current[lane_id][
                            f"queue_{object_type}"
                        ] += 1


                    # ----------------------------------------
                    # Counting line
                    # ----------------------------------------

                    current_side = side_of_line(
                        (cx, cy),
                        line_p1,
                        line_p2
                    )

                    previous_side = (
                        self.last_side.get(
                            track_id
                        )
                    )


                    # ----------------------------------------
                    # CROSSING
                    # ----------------------------------------

                    # Dua syarat BARU disisipkan di antara yang lama:
                    #
                    # 1. (lama) tanda sisi berubah -> memang
                    #    menyeberang garis tak hingga
                    # 2. BARU: titik potongnya jatuh di dalam ruas
                    #    yang digambar, bukan di perpanjangannya
                    # 3. BARU: geraknya menuju simpang, bukan
                    #    menjauh
                    # 4. (lama) belum pernah dihitung
                    if (
                        previous_side is not None
                        and previous_side
                        * current_side < 0
                        and previous_centroid is not None
                        and potongan_dalam_ruas(
                            previous_centroid,
                            (cx, cy),
                            line_p1,
                            line_p2
                        )
                        and menuju_simpang(
                            self.camera_name,
                            cx - previous_centroid[0],
                            cy - previous_centroid[1]
                        )
                        and track_id
                        not in self.counted_ids
                    ):

                        # lane_id = lajur pada frame saat garis
                        # dipotong (dihitung di atas dari centroid).
                        # Dipakai supaya volume CSV bisa dipecah per
                        # lajur, bukan cuma total per lengan.
                        self.counter.add(
                            object_type,
                            lane_id
                        )

                        self.counted_ids.add(
                            track_id
                        )


                    # ----------------------------------------
                    # Simpan posisi garis
                    # ----------------------------------------

                    self.last_side[
                        track_id
                    ] = current_side


                    # ----------------------------------------
                    # DRAW BOUNDING BOX
                    # ----------------------------------------

                    x1_int = int(x1)
                    y1_int = int(y1)

                    x2_int = int(x2)
                    y2_int = int(y2)


                    cv2.rectangle(

                        frame,

                        (
                            x1_int,
                            y1_int
                        ),

                        (
                            x2_int,
                            y2_int
                        ),

                        (0, 255, 0),

                        2
                    )


                    # ----------------------------------------
                    # LABEL
                    # ----------------------------------------

                    label = (
                        f"{object_type}"
                        f" #{track_id}"
                    )


                    cv2.putText(

                        frame,

                        label,

                        (
                            x1_int,
                            max(
                                20,
                                y1_int - 8
                            )
                        ),

                        cv2.FONT_HERSHEY_SIMPLEX,

                        0.55,

                        (0, 255, 0),

                        2
                    )


                    # ----------------------------------------
                    # CENTROID
                    # ----------------------------------------

                    cv2.circle(

                        frame,

                        (
                            int(cx),
                            int(cy)
                        ),

                        4,

                        (0, 0, 255),

                        -1
                    )


            # =================================================
            # DENSITY
            # =================================================
            #
            # Density normalized menggunakan luas relatif lane.
            #
            # density = jumlah kendaraan / area_fraction
            #
            # Untuk density fisik (veh/km), kamera perlu
            # dikalibrasi terhadap ukuran dunia nyata.
            # =================================================

            total_queue = 0
            total_density = 0.0

            for lane_id in lane_current:

                lane_info = lane_current[lane_id]

                # Ambil area horizontal lane.
                lane_def = None

                for definition in LANE_REGIONS[
                    self.camera_name
                ]:

                    if definition[0] == lane_id:
                        lane_def = definition
                        break

                if lane_def is not None:

                    _, x_start, x_end = lane_def

                    lane_width_fraction = (
                        x_end - x_start
                    )

                else:

                    lane_width_fraction = 1.0


                # Area relatif = lebar lane x tinggi frame
                area_fraction = (
                    lane_width_fraction
                    * 1.0
                )

                lane_info[
                    "area_fraction"
                ] = area_fraction


                vehicle_now = (
                    lane_info[
                        "car_count"
                    ]
                    +
                    lane_info[
                        "motorcycle_count"
                    ]
                    +
                    lane_info[
                        "bus_count"
                    ]
                    +
                    lane_info[
                        "truck_count"
                    ]
                )


                lane_info[
                    "density"
                ] = (
                    vehicle_now
                    / max(
                        area_fraction,
                        0.001
                    )
                )


                total_queue += lane_info[
                    "queue_length"
                ]

                total_density += lane_info[
                    "density"
                ]


            # =================================================
            # DRAW COUNTING LINE
            # =================================================

            cv2.line(

                frame,

                line_p1,

                line_p2,

                (0, 0, 255),

                3
            )


            # =================================================
            # CAMERA NAME
            # =================================================

            cv2.rectangle(

                frame,

                (0, 0),

                (330, 40),

                (0, 0, 0),

                -1
            )


            cv2.putText(

                frame,

                self.camera_name,

                (10, 28),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.8,

                (255, 255, 255),

                2
            )


            # =================================================
            # CURRENT DETECTION
            # =================================================

            y_offset = 65

            for object_type in [
                "person",
                "bicycle",
                "car",
                "motorcycle",
                "bus",
                "truck"
            ]:

                text = (
                    f"{object_type}: "
                    f"{self.current_counts[object_type]}"
                )


                cv2.putText(

                    frame,

                    text,

                    (10, y_offset),

                    cv2.FONT_HERSHEY_SIMPLEX,

                    0.55,

                    (255, 255, 255),

                    2
                )


                y_offset += 23


            # ------------------------------------------------
            # Queue / density display
            # ------------------------------------------------

            cv2.putText(

                frame,

                f"Queue: {total_queue}",

                (10, y_offset + 5),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (255, 255, 255),

                2
            )


            cv2.putText(

                frame,

                f"Density: {total_density:.3f}",

                (10, y_offset + 28),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (255, 255, 255),

                2
            )


            # =================================================
            # UPDATE CSV PER SECOND
            # =================================================

            self.counter.update(

                current_counts=self.current_counts,

                queue_length=total_queue,

                density=total_density,

                lane_counts=lane_current,

                frame_idx=frame_idx
            )


            # =================================================
            # SIMPAN FRAME
            # =================================================

            with self.lock:

                self.frame = frame.copy()


            # =================================================
            # FPS CONTROL
            # =================================================

            processing_time = (
                time.time()
                - start_time
            )

            sleep_time = (
                frame_delay
                - processing_time
            )

            if sleep_time > 0:

                time.sleep(
                    sleep_time
                )


        cap.release()

        # Tutup detik terakhir sebelum thread-nya mati
        self.counter.flush_akhir()

        self.running = False


# ============================================================
# 12. MAIN
# ============================================================

def tulis_lengan_tidak_terukur():
    """
    Menulis baris CSV untuk lengan di LENGAN_TIDAK_TERUKUR
    (bagian 6C), satu baris per detik yang benar-benar ditulis
    lengan lain pada run ini.

    Seluruh kolom angka dikosongkan — lihat catatan di bagian 6C
    soal kenapa kosong dan bukan 0.
    """
    if not LENGAN_TIDAK_TERUKUR:
        return

    with _KUNCI_TIMESTAMP:
        detik = sorted(TIMESTAMP_TERTULIS)

    if not detik:
        print(
            "[WARNING] Tidak ada baris terukur sama sekali, "
            "jadi baris lengan tidak-terukur juga dilewati."
        )
        return

    # timestamp, intersection_id, approach, lane_id, lalu 8 kolom
    # angka yang semuanya dikosongkan.
    kosong = [""] * (len(CSV_HEADER) - 4)

    with open(
        CSV_PATH,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        for approach in LENGAN_TIDAK_TERUKUR:
            for timestamp in detik:
                writer.writerow(
                    [
                        timestamp,
                        INTERSECTION_ID,
                        approach,
                        "lane_1",
                    ]
                    + kosong
                )

    for approach, alasan in LENGAN_TIDAK_TERUKUR.items():
        print(
            f"[INFO] {approach}: {len(detik)} baris ditulis "
            f"sebagai TIDAK TERUKUR (semua kolom angka kosong) - "
            f"{alasan}."
        )


def main():

    print("=" * 75)

    print(
        "SMARTTWIN - MULTI CAMERA "
        "TRAFFIC ANALYSIS"
    )

    print("=" * 75)

    print(
        f"Model : {MODEL_PATH}"
    )

    print(
        f"CSV   : {CSV_PATH}"
    )

    print("=" * 75)


    # --------------------------------------------------------
    # Cek model
    # --------------------------------------------------------

    if not os.path.exists(
        MODEL_PATH
    ):

        print(
            "[ERROR] Model tidak ditemukan:"
        )

        print(
            MODEL_PATH
        )

        return


    # --------------------------------------------------------
    # Initialize CSV
    # --------------------------------------------------------

    initialize_csv()


    # --------------------------------------------------------
    # Buat processor
    # --------------------------------------------------------

    processors = {}


    for (
        camera_name,
        video_path
    ) in CAMERAS.items():

        if not os.path.exists(
            video_path
        ):

            print(
                f"[WARNING] Video "
                f"{camera_name} tidak ditemukan:"
            )

            print(
                video_path
            )

            continue


        # ----------------------------------------------------
        # Peta jam dinding
        # ----------------------------------------------------
        #
        # Dibangun di sini, bukan di dalam thread, supaya
        # kegagalannya muncul SEBELUM YOLO dimuat dan sebelum
        # ada baris CSV yang tertulis. Kalau petanya tidak bisa
        # dibuat, seluruh proses dibatalkan — bukan dilanjutkan
        # dengan jam laptop.
        cek = cv2.VideoCapture(video_path)

        fps_video = cek.get(cv2.CAP_PROP_FPS)

        frame_video = int(
            cek.get(cv2.CAP_PROP_FRAME_COUNT)
        )

        cek.release()

        if fps_video <= 0:

            print(
                f"[ERROR] fps {camera_name} terbaca "
                f"{fps_video}; jam dinding tidak bisa dihitung."
            )

            return

        try:
            peta_jam = muat_peta_jam(
                video_path,
                fps_video
            )

        except RuntimeError as e:

            print(
                f"[ERROR] {camera_name}: {e}"
            )

            return

        # Jumlah frame video harus cocok dengan jumlah frame di
        # laporan. Kalau tidak, videonya bukan hasil run yang
        # sama dengan laporannya, dan setiap timestamp sesudah
        # keping pertama akan meleset.
        if peta_jam.total_frame != frame_video:

            print(
                f"[ERROR] {camera_name}: video punya "
                f"{frame_video} frame, sync_report.json "
                f"mencatat {peta_jam.total_frame}. "
                f"Laporannya bukan milik video ini."
            )

            return

        print(
            f"[INFO] {camera_name}: jam dinding "
            f"{peta_jam.waktu(peta_jam.detik_dinding(0)).strftime('%H:%M:%S')}"
            f" - "
            f"{peta_jam.waktu(peta_jam.detik_dinding(frame_video - 1)).strftime('%H:%M:%S')}"
            f" ({len(peta_jam.frame_awal)} keping)"
        )


        processors[
            camera_name
        ] = CameraProcessor(

            camera_name,

            video_path,

            peta_jam
        )


    if not processors:

        print(
            "[ERROR] Tidak ada video "
            "yang dapat dibuka."
        )

        return


    # --------------------------------------------------------
    # Thread masing-masing kamera
    # --------------------------------------------------------

    threads = []


    for processor in processors.values():

        thread = threading.Thread(

            target=processor.run,

            daemon=True
        )

        thread.start()

        threads.append(
            thread
        )


    # --------------------------------------------------------
    # Window
    # --------------------------------------------------------

    # Ukuran placeholder waktu video sebuah lengan belum ada.
    # Frame asli TIDAK dikecilkan ke ukuran ini — lihat catatan
    # di bawah.
    PLACEHOLDER_WIDTH = 640
    PLACEHOLDER_HEIGHT = 360

    # --------------------------------------------------------
    # Satu jendela per kamera, bukan grid 2x2
    # --------------------------------------------------------
    #
    # Versi lama menggabungkan semua kamera jadi satu gambar 2x2,
    # dan tiap frame dikecilkan dulu ke 640x360 sebelum digabung.
    # Pengecilan itu destruktif: resolusinya hilang di situ, jadi
    # memperbesar jendela cuma bikin gambar makin buram, bukan
    # makin jelas — padahal jendela ini dipakai buat memverifikasi
    # bounding box secara visual.
    #
    # Sekarang tiap kamera punya jendelanya sendiri dan ditampilkan
    # pada resolusi asli video. Jendelanya WINDOW_NORMAL, jadi bisa
    # di-resize/maximize satu-satu sesuai kebutuhan.
    #
    # Jumlah jendela mengikuti CAMERAS. Mau 2 lengan atau 4, tidak
    # ada yang perlu diubah di bagian ini.
    # --------------------------------------------------------

    def window_title(camera_name):
        return f"SMARTTWIN - {camera_name.upper()}"

    for camera_name in CAMERAS:
        cv2.namedWindow(
            window_title(camera_name),
            cv2.WINDOW_NORMAL
        )


    # ========================================================
    # DISPLAY LOOP
    # ========================================================

    while True:

        # ----------------------------------------------------
        # Tampilkan tiap kamera di jendelanya sendiri
        # ----------------------------------------------------

        for camera_name in CAMERAS:

            processor = processors.get(
                camera_name
            )


            if processor is None:

                frame = (
                    cv2.UMat(
                        PLACEHOLDER_HEIGHT,
                        PLACEHOLDER_WIDTH,
                        cv2.CV_8UC3
                    ).get()
                )

                cv2.putText(

                    frame,

                    f"{camera_name} - NO VIDEO",

                    (50, 180),

                    cv2.FONT_HERSHEY_SIMPLEX,

                    0.8,

                    (255, 255, 255),

                    2
                )

            else:

                with processor.lock:

                    if processor.frame is not None:

                        # Resolusi asli, TANPA cv2.resize —
                        # ini yang bikin bounding box kebaca jelas.
                        frame = (
                            processor.frame.copy()
                        )

                    else:

                        frame = (
                            cv2.UMat(
                                PLACEHOLDER_HEIGHT,
                                PLACEHOLDER_WIDTH,
                                cv2.CV_8UC3
                            ).get()
                        )


            cv2.imshow(

                window_title(camera_name),

                frame
            )


        # ----------------------------------------------------
        # Keyboard
        # q = quit
        # ESC = quit
        # ----------------------------------------------------

        key = cv2.waitKey(1) & 0xFF


        if key == ord("q"):

            print(
                "[INFO] Program dihentikan."
            )

            break


        if key == 27:

            break


    # --------------------------------------------------------
    # Stop semua processor
    # --------------------------------------------------------

    for processor in processors.values():

        processor.running = False


    for thread in threads:

        thread.join(
            timeout=2
        )


    cv2.destroyAllWindows()


    print("=" * 75)

    print(
        "PROGRAM SELESAI"
    )

    print(
        "CSV tersimpan di:"
    )

    print(
        CSV_PATH
    )

    print("=" * 75)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
