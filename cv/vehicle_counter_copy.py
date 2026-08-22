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
import csv
import os
import sys

import cv2
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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CSV_PATH = os.path.join(
    OUTPUT_DIR,
    "percobaan_logic_simpang.csv"
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
        #   v4 SEKARANG — pita dilebarkan ke bawah-kanan sampai
        #               memeluk seluruh lajur menuju stop line,
        #               termasuk deretan motor di tepi kerb.
        #               Dibaca dari coretan dua garis biru pada
        #               frame 22 Agustus 2026 (17:41), sejajar
        #               sumbu jalan dan menyempit ke titik hilang
        #               di kanan atas.
        "polygon": [
            (0.00, 0.80),
            (0.84, 0.13),
            (0.90, 0.21),
            (0.38, 1.00),
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
        #   v3 SEKARANG — baji mengikuti coretan biru: sisi kiri
        #                 menyusuri mulut koridor Magelang, sisi
        #                 kanan melengkung mengikuti arus yang
        #                 membelok ke timur. Bentuk ini memeluk
        #                 badan simpang dan mulut lengan, dan
        #                 membuang aspal kosong di kuadran
        #                 kanan-bawah yang tidak pernah dilewati.
        "polygon": [
            (0.29, 0.21),
            (0.37, 0.21),
            (0.50, 0.35),
            (0.62, 0.43),
            (0.73, 0.47),
            (0.60, 0.52),
            (0.45, 0.58),
            (0.39, 0.60),
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
        #   v3 SEKARANG — pita sejajar sumbu jalan, dibaca dari
        #                 coretan dua garis biru. Menipis di kiri
        #                 (jauh) dan menebal di kanan (dekat
        #                 kamera), sesuai perspektif lajur berlebar
        #                 tetap.
        "polygon": [
            (0.19, 0.29),
            (0.92, 0.55),
            (0.89, 0.78),
            (0.09, 0.35),
        ],
        "nama_lengan": "barat",
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

        if point_in_polygon(cx, cy, zona_polygon):
            hasil["total"] += 1
            hasil[nama_kelas] += 1
            hasil["titik_dalam"].append((cx, cy))
        else:
            hasil["titik_luar"].append((cx, cy))

    return hasil


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
# PROSES SATU KAMERA
# ============================================================

def proses_kamera(
    nama_kamera,
    zona,
    durasi_detik,
    langkah,
    frame_visual,
    imgsz,
    penulis_csv,
):
    """
    Proses satu video, tulis satu baris CSV per jendela 5 detik.

    Balikannya daftar total_di_zona tiap jendela, untuk statistik.
    """
    video_path = os.path.join(VIDEO_DIR, f"{nama_kamera}.mp4")

    if not os.path.exists(video_path):
        print(f"[LEWAT] {video_path} tidak ada.")
        return []

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"[LEWAT] {video_path} gagal dibuka.")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Jam dinding dari posisi frame. GAGAL KERAS kalau videonya
    # tidak tercatat di sync_report.json — sama seperti file asli,
    # supaya jam laptop tidak pernah menyamar jadi jam rekaman.
    peta = muat_peta_jam(video_path, fps)

    # Model dibuat baru per kamera: state ByteTrack tidak boleh
    # bocor antar-video.
    model = YOLO(MODEL_PATH)

    poligon = zona["polygon"]
    lengan = zona["nama_lengan"]

    print(
        f"\n[{nama_kamera}] {width}x{height} @ {fps:.2f} fps "
        f"-> lengan '{lengan}', {len(poligon)} titik zona, "
        f"imgsz={imgsz}"
    )

    idx = -1
    window_aktif = None
    akumulasi = []
    frame_terakhir = 0
    totals = []
    path_bukti = None
    n_proses = 0

    batas_frame = int(durasi_detik * fps)

    def tutup_window():
        """Tulis satu baris CSV dari jendela yang baru selesai."""
        if not akumulasi:
            return

        n = len(akumulasi)

        rata = {
            k: sum(a[k] for a in akumulasi) / n
            for k in ("total", "motor", "mobil", "truk", "bus")
        }

        penulis_csv.writerow({
            "timestamp": peta.waktu(window_aktif).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "kamera": nama_kamera,
            "lengan": lengan,
            "total_di_zona": round(rata["total"], 2),
            "motor_di_zona": round(rata["motor"], 2),
            "mobil_di_zona": round(rata["mobil"], 2),
            "truk_di_zona": round(rata["truk"], 2),
            "bus_di_zona": round(rata["bus"], 2),
            "frame_number": frame_terakhir,
        })

        totals.append(rata["total"])

    while True:
        ok, frame = cap.read()

        if not ok:
            break

        idx += 1

        if idx >= batas_frame:
            break

        if idx % langkah != 0:
            continue

        detik = peta.detik_dinding(idx)

        # Frame di luar peta keping: lebih baik dilewati daripada
        # ditulis dengan jam karangan.
        if detik is None:
            continue

        awal_window = int(detik // WINDOW_DETIK) * WINDOW_DETIK

        if window_aktif is None:
            window_aktif = awal_window

        if awal_window != window_aktif:
            tutup_window()
            akumulasi = []
            window_aktif = awal_window

        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=TRACK_CLASSES,
            conf=CONFIDENCE,
            imgsz=imgsz,
            verbose=False,
        )

        hasil = hitung_kendaraan_di_zona(
            ekstrak_deteksi(results[0]),
            poligon,
            width,
            height,
        )

        akumulasi.append(hasil)
        frame_terakhir = idx
        n_proses += 1

        # Laporan tiap 30 frame yang DIPROSES — untuk memastikan
        # angkanya masuk akal sambil run masih jalan, bukan baru
        # ketahuan di akhir.
        if n_proses % 30 == 0:
            print(
                f"  {nama_kamera} f{idx:>6} ({idx / fps:>5.0f}s)"
                f"  zona={hasil['total']:>3}"
                f"  (motor {hasil['motor']}, mobil {hasil['mobil']}, "
                f"truk {hasil['truk']}, bus {hasil['bus']})"
                f"  luar={len(hasil['titik_luar'])}"
            )

        # Gambar bukti diambil dari frame yang sama sekali ini,
        # jadi angkanya dijamin hasil perhitungan yang sama.
        if path_bukti is None and idx >= frame_visual:
            path_bukti = gambar_bukti(
                frame,
                poligon,
                hasil,
                nama_kamera,
                lengan,
                os.path.join(
                    OUTPUT_DIR,
                    f"zona_test_{nama_kamera.replace('_', '')}.jpg",
                ),
            )

    tutup_window()
    cap.release()

    # Kalau videonya lebih pendek dari frame_visual, ambil apa pun
    # yang sempat terbaca supaya gambar buktinya tetap ada.
    if path_bukti is None and akumulasi:
        print(
            f"  [!] {nama_kamera}: frame visual {frame_visual} "
            f"tidak tercapai, gambar bukti dilewati."
        )

    print(
        f"  {nama_kamera}: {len(totals)} jendela ditulis"
        + (f", bukti -> {os.path.basename(path_bukti)}"
           if path_bukti else "")
    )

    return totals


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


def cetak_cuplikan_csv(n=20):
    print()
    print("=" * 68)
    print(f"{n} BARIS PERTAMA — {os.path.basename(CSV_PATH)}")
    print("=" * 68)

    with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
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
            "Proses tiap frame ke-N (default 5, artinya ~6 fps). "
            "Aman dinaikkan karena cacah zona per frame tidak "
            "bergantung pada kesinambungan track — beda dengan "
            "crossing di file asli, yang jejaknya pecah kalau "
            "frame-nya dilompati."
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
    print(f"CSV      : {CSV_PATH}")

    statistik = []

    # Context manager: berkasnya dijamin ter-flush dan tertutup
    # walau proses_kamera() melempar exception di tengah jalan,
    # jadi baris yang sudah ditulis tidak hilang.
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        penulis = csv.DictWriter(f, fieldnames=KOLOM)
        penulis.writeheader()

        for nama_kamera, zona in dipilih.items():
            totals = proses_kamera(
                nama_kamera,
                zona,
                args.durasi,
                args.langkah,
                args.frame_visual,
                args.imgsz,
                penulis,
            )

            statistik.append(
                (nama_kamera, zona["nama_lengan"], totals)
            )

    cetak_cuplikan_csv(20)
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


if __name__ == "__main__":
    main()
