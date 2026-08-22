"""
Tool kalibrasi interaktif untuk menentukan koordinat polygon zona
kepadatan (ZONA_KEPADATAN di vehicle_counter_copy.py) dengan cara
klik langsung di frame video, bukan tebak-tebakan angka rasio.

Alur:
    1. Ambil frame PERTAMA video CCTV yang dipilih.
    2. Tampilkan di window OpenCV.
    3. User klik 4 titik (urutan klik = urutan polygon).
    4. Tiap klik: titik merah + nomor urut digambar di frame.
    5. Setelah titik ke-4: polygon biru digambar (tertutup), dan
       koordinat ternormalisasi (dibagi width/height) dicetak ke
       terminal, siap tempel ke ZONA_KEPADATAN["polygon"].

Tombol:
    R   reset -- hapus semua titik, mulai ulang dari frame bersih.
    S   cetak ulang koordinat titik yang sudah diklik ke terminal
        (berguna kalau output awal ke-scroll lewat).
    Q   keluar.

Jalankan:
    python cv/kalibrasi_zona.py --kamera CCTV_1
"""

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# VIDEO_DIR diwarisi dari file asli — path video kamera tidak
# didefinisikan ulang di sini.
from vehicle_counter import VIDEO_DIR  # noqa: E402


TITIK_MAKS = 4
WARNA_TITIK = (0, 0, 255)      # merah
WARNA_POLYGON = (255, 0, 0)    # biru
WARNA_TEKS = (255, 255, 255)   # putih


def gambar_ulang(frame_asli, titik):
    """Kembalikan salinan frame_asli dengan semua titik (+ polygon
    kalau sudah 4) digambar ulang dari nol -- supaya reset/redraw
    tidak menumpuk gambar lama."""

    frame = frame_asli.copy()

    for i, (x, y) in enumerate(titik, start=1):
        cv2.circle(frame, (x, y), 6, WARNA_TITIK, -1)
        cv2.putText(
            frame, str(i), (x + 10, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, WARNA_TEKS, 2,
        )

    if len(titik) == TITIK_MAKS:
        cv2.polylines(
            frame, [np.array(titik, dtype=np.int32)],
            isClosed=True, color=WARNA_POLYGON, thickness=2,
        )

    cv2.putText(
        frame,
        f"Titik: {len(titik)}/{TITIK_MAKS}  "
        f"(klik kiri buat nambah, R reset, S cetak, Q keluar)",
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WARNA_TEKS, 2,
    )

    return frame


def cetak_koordinat(titik, width, height):
    if not titik:
        print("  (belum ada titik yang diklik)")
        return

    ternormalisasi = [
        (round(x / width, 2), round(y / height, 2)) for x, y in titik
    ]

    print("\nKoordinat ternormalisasi (tempel ke ZONA_KEPADATAN):")
    print("[" + ", ".join(f"({x:.2f}, {y:.2f})" for x, y in ternormalisasi) + "]")


def main():
    parser = argparse.ArgumentParser(
        description="Kalibrasi zona kepadatan dengan klik interaktif.",
    )
    parser.add_argument(
        "--kamera", required=True,
        help="Nama file video tanpa ekstensi, mis. CCTV_1",
    )
    args = parser.parse_args()

    video_path = os.path.join(VIDEO_DIR, f"{args.kamera}.mp4")

    if not os.path.exists(video_path):
        parser.error(f"Video '{video_path}' tidak ada.")

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        parser.error(f"Video '{video_path}' gagal dibuka.")

    ok, frame_asli = cap.read()
    cap.release()

    if not ok:
        parser.error(f"Frame pertama '{video_path}' gagal dibaca.")

    height, width = frame_asli.shape[:2]

    titik = []

    def klik(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(titik) < TITIK_MAKS:
            titik.append((x, y))
            print(f"  Titik {len(titik)}: piksel ({x}, {y})")

            if len(titik) == TITIK_MAKS:
                cetak_koordinat(titik, width, height)

    nama_window = f"Kalibrasi Zona - {args.kamera}"
    cv2.namedWindow(nama_window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(nama_window, klik)

    print("=" * 68)
    print(f"KALIBRASI ZONA — {args.kamera} ({width}x{height})")
    print("=" * 68)
    print("Klik 4 titik di window untuk membentuk polygon zona.")
    print("R = reset, S = cetak koordinat, Q = keluar.\n")

    try:
        while True:
            cv2.imshow(nama_window, gambar_ulang(frame_asli, titik))

            tombol = cv2.waitKey(20) & 0xFF

            if tombol == ord("q"):
                break
            elif tombol == ord("r"):
                titik.clear()
                print("  [R] Direset, silakan klik ulang.")
            elif tombol == ord("s"):
                cetak_koordinat(titik, width, height)
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
