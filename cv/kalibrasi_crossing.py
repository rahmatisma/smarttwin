"""
Tool kalibrasi interaktif untuk menentukan garis crossing (bukan
polygon zona -- lihat kalibrasi_zona.py untuk itu) dengan cara klik
langsung di frame video.

Dipakai antara lain untuk kamera yang framenya memotret DUA lengan
sekaligus (mis. CCTV_2 yang melihat Jl. Magelang dan Jl. Diponegoro
dalam satu frame): satu sesi kalibrasi bisa menyimpan BEBERAPA garis
crossing berbeda, masing-masing dengan label sendiri, supaya counting
di vehicle_counter_pingit.py bisa dibedakan per lengan.

Alur per garis (bisa diulang beberapa kali dalam satu run):
    1. Klik 2 titik di frame -- titik 1 lalu titik 2, garis hijau
       digambar begitu titik ke-2 diklik.
    2. Tekan S -- tool menanyakan label garis ini (mis. MAGELANG)
       lewat terminal, lalu mencetak:
           CROSSING_LINE_MAGELANG = {"x1": .., "y1": .., "x2": .., "y2": ..}
       Garis yang sudah disimpan tetap digambar (kuning) di frame
       sebagai referensi visual sesi berikutnya.
    3. Tekan R -- reset 2 titik yang lagi aktif (garis yang SUDAH
       disimpan lewat S tidak ikut terhapus), lalu ulangi dari
       langkah 1 untuk garis berikutnya.

Tombol:
    R   reset titik aktif (garis yang sudah tersimpan tetap ada).
    S   simpan garis aktif (butuh 2 titik) -- minta label di
        terminal, cetak CROSSING_LINE_<LABEL>.
    Q   keluar.

Jalankan:
    python cv/kalibrasi_crossing.py --kamera CCTV_2

    Contoh sesi CCTV_2 (dua lengan dalam satu frame):
        Sesi 1: klik 2 titik utk Jl. Magelang -> S -> label "MAGELANG"
        Sesi 2: R -> klik 2 titik utk Jl. Diponegoro -> S -> label "DIPONEGORO"
"""

import argparse
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# VIDEO_DIR diwarisi dari file asli — path video kamera tidak
# didefinisikan ulang di sini.
from vehicle_counter import VIDEO_DIR  # noqa: E402


TITIK_MAKS = 2
WARNA_TITIK = (0, 0, 255)              # merah -- titik aktif
WARNA_GARIS_AKTIF = (0, 255, 0)        # hijau -- garis belum disimpan
WARNA_GARIS_TERSIMPAN = (0, 255, 255)  # kuning -- garis sudah disimpan
WARNA_TEKS = (255, 255, 255)           # putih


def gambar_ulang(frame_asli, titik_aktif, garis_tersimpan):
    """Kembalikan salinan frame_asli dengan garis-garis yang sudah
    tersimpan (kuning, permanen sepanjang sesi run ini) plus
    titik/garis aktif yang sedang diklik (merah/hijau) -- digambar
    ulang dari nol tiap frame supaya reset tidak menumpuk gambar
    lama."""

    frame = frame_asli.copy()

    for garis in garis_tersimpan:
        p1, p2 = garis["p1"], garis["p2"]
        cv2.line(frame, p1, p2, WARNA_GARIS_TERSIMPAN, 2)

        tengah = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
        cv2.putText(
            frame, garis["label"], tengah,
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, WARNA_GARIS_TERSIMPAN, 2,
        )

    for i, (x, y) in enumerate(titik_aktif, start=1):
        cv2.circle(frame, (x, y), 6, WARNA_TITIK, -1)
        cv2.putText(
            frame, str(i), (x + 10, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, WARNA_TEKS, 2,
        )

    if len(titik_aktif) == TITIK_MAKS:
        cv2.line(frame, titik_aktif[0], titik_aktif[1], WARNA_GARIS_AKTIF, 2)

    cv2.putText(
        frame,
        f"Titik: {len(titik_aktif)}/{TITIK_MAKS}  "
        f"tersimpan: {len(garis_tersimpan)}  "
        f"(klik kiri, R reset, S simpan, Q keluar)",
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WARNA_TEKS, 2,
    )

    return frame


def simpan_garis(titik_aktif, width, height, garis_tersimpan):
    """Minta label lewat terminal lalu cetak CROSSING_LINE_<LABEL>.
    Balikannya True kalau berhasil disimpan (dipakai caller buat tahu
    apakah perlu redraw), False kalau dibatalkan/gagal."""

    if len(titik_aktif) != TITIK_MAKS:
        print(
            f"  [!] Butuh {TITIK_MAKS} titik dulu sebelum simpan "
            f"(baru ada {len(titik_aktif)})."
        )
        return False

    label = input("  Label crossing line ini (mis. MAGELANG): ").strip().upper()

    if not label:
        print("  [!] Label kosong, dibatalkan.")
        return False

    (x1, y1), (x2, y2) = titik_aktif

    koord = {
        "x1": round(x1 / width, 2),
        "y1": round(y1 / height, 2),
        "x2": round(x2 / width, 2),
        "y2": round(y2 / height, 2),
    }

    print(
        f'\nCROSSING_LINE_{label} = '
        f'{{"x1": {koord["x1"]:.2f}, "y1": {koord["y1"]:.2f}, '
        f'"x2": {koord["x2"]:.2f}, "y2": {koord["y2"]:.2f}}}\n'
    )

    garis_tersimpan.append({
        "label": label,
        "p1": titik_aktif[0],
        "p2": titik_aktif[1],
    })

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Kalibrasi garis crossing dengan klik interaktif.",
    )
    parser.add_argument(
        "--kamera", required=True,
        help="Nama file video tanpa ekstensi, mis. CCTV_2",
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

    titik_aktif = []
    garis_tersimpan = []

    def klik(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(titik_aktif) < TITIK_MAKS:
            titik_aktif.append((x, y))
            print(f"  Titik {len(titik_aktif)}: piksel ({x}, {y})")

    nama_window = f"Kalibrasi Crossing - {args.kamera}"
    cv2.namedWindow(nama_window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(nama_window, klik)

    print("=" * 68)
    print(f"KALIBRASI CROSSING — {args.kamera} ({width}x{height})")
    print("=" * 68)
    print(f"Klik {TITIK_MAKS} titik di window untuk membentuk satu garis crossing.")
    print("S = simpan (minta label), R = reset titik aktif, Q = keluar.")
    print("Ulangi klik + S untuk tiap lengan yang perlu garis terpisah.\n")

    try:
        while True:
            cv2.imshow(
                nama_window, gambar_ulang(frame_asli, titik_aktif, garis_tersimpan)
            )

            tombol = cv2.waitKey(20) & 0xFF

            if tombol == ord("q"):
                break
            elif tombol == ord("r"):
                titik_aktif.clear()
                print("  [R] Titik aktif direset, silakan klik ulang.")
            elif tombol == ord("s"):
                # Tidak auto-clear -- user menekan R secara eksplisit
                # sebelum sesi berikutnya, sesuai alur "klik -> S ->
                # simpan, lalu R -> klik lagi" yang dijanjikan di atas.
                simpan_garis(titik_aktif, width, height, garis_tersimpan)
    finally:
        cv2.destroyAllWindows()

    if garis_tersimpan:
        print("=" * 68)
        print(f"Ringkasan {len(garis_tersimpan)} garis tersimpan sesi ini:")
        for garis in garis_tersimpan:
            print(f"  - {garis['label']}")


if __name__ == "__main__":
    main()
