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
- intersection_id konstan (INTERSECTION_ID) karena seluruh kamera
  memantau simpang yang sama. Yang membedakan baris adalah approach.
- approach = north/south/east/west, mengikuti Approach di
  docs/data-contract.md. lane_id adalah lajur DI DALAM satu lengan.
- vehicle_count = car + motorcycle + bus + truck crossing the counting line
  during the current one-second interval.
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
  queue_length_veh — bukan dari *_count yang berisi seluruh kendaraan
  terdeteksi. Jadi kedua kolom queue itu selalu sepadan.
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

import csv
import os
import time
import threading
from collections import defaultdict
from datetime import datetime

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

CAMERAS = {
    "north": os.path.join(VIDEO_DIR, "pingit_north.mp4"),
    "south": os.path.join(VIDEO_DIR, "pingit_south.mp4"),
    "east": os.path.join(VIDEO_DIR, "pingit_east.mp4"),
    "west": os.path.join(VIDEO_DIR, "pingit_west.mp4"),
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

# BELUM DIKALIBRASI: keempat lengan masih memakai nilai default yang
# sama. Sesuaikan per lengan begitu footage Simpang Pingit tersedia.
COUNTING_LINES = {
    "north": (0.10, 0.65, 0.90, 0.65),
    "south": (0.10, 0.65, 0.90, 0.65),
    "east": (0.10, 0.65, 0.90, 0.65),
    "west": (0.10, 0.65, 0.90, 0.65),
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
    x, y = point
    x1, y1 = line_p1
    x2, y2 = line_p2

    return (
        (x2 - x1) * (y - y1)
        -
        (y2 - y1) * (x - x1)
    )


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

    def __init__(self, camera_name):
        self.camera_name = camera_name

        self.counts = defaultdict(int)

        self.second_start = time.time()

        self.lock = threading.Lock()

        # Statistik realtime terakhir
        self.latest_stats = {}


    def add(self, object_type):
        with self.lock:
            self.counts[object_type] += 1


    def update(
        self,
        current_counts,
        queue_length,
        density,
        lane_counts
    ):
        now = time.time()

        with self.lock:
            elapsed = now - self.second_start

            if elapsed >= 1.0:

                self.write_csv(
                    current_counts=current_counts,
                    queue_length=queue_length,
                    density=density,
                    lane_counts=lane_counts
                )

                self.counts = defaultdict(int)

                self.second_start = now


    def write_csv(
        self,
        current_counts,
        queue_length,
        density,
        lane_counts
    ):
        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # ----------------------------------------------------
        # Volume per second
        # ----------------------------------------------------

        car_count = self.counts["car"]
        motorcycle_count = self.counts["motorcycle"]
        bus_count = self.counts["bus"]
        truck_count = self.counts["truck"]

        vehicle_count = (
            car_count
            + motorcycle_count
            + bus_count
            + truck_count
        )

        # ----------------------------------------------------
        # Satu baris per lane
        # ----------------------------------------------------
        #
        # Untuk lane yang tidak memiliki crossing pada detik
        # tersebut, volume tetap 0.
        #
        # queue_length dan density dibagi berdasarkan lane.
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

            # Jika belum ada lane yang terdeteksi,
            # tetap tulis lane_1.
            lanes = lane_counts.keys()

            if not lanes:
                lanes = ["lane_1"]

            for lane_id in lanes:

                lane = lane_counts.get(
                    lane_id,
                    {}
                )

                car = lane.get("car_count", 0)
                motorcycle = lane.get("motorcycle_count", 0)
                bus = lane.get("bus_count", 0)
                truck = lane.get("truck_count", 0)

                # Estimasi panjang antrean dalam meter.
                #
                # Sumbernya queue_* — kendaraan yang benar-benar
                # berstatus antre — BUKAN *_count di atas yang berisi
                # semua kendaraan terdeteksi termasuk yang melaju.
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

                    # Volume kendaraan per detik
                    lane.get("vehicle_count", 0),

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
        video_path
    ):
        self.camera_name = camera_name

        self.video_path = video_path

        self.running = True

        self.frame = None

        self.lock = threading.Lock()

        self.counter = PerSecondCounter(
            camera_name
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

                    if (
                        previous_side is not None
                        and previous_side
                        * current_side < 0
                        and track_id
                        not in self.counted_ids
                    ):

                        self.counter.add(
                            object_type
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

                lane_counts=lane_current
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

        self.running = False


# ============================================================
# 12. MAIN
# ============================================================

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


        processors[
            camera_name
        ] = CameraProcessor(

            camera_name,

            video_path
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

    WINDOW_WIDTH = 640
    WINDOW_HEIGHT = 360


    cv2.namedWindow(

        "SMARTTWIN - 4 CCTV",

        cv2.WINDOW_NORMAL
    )


    cv2.resizeWindow(

        "SMARTTWIN - 4 CCTV",

        WINDOW_WIDTH * 2,

        WINDOW_HEIGHT * 2
    )


    # ========================================================
    # DISPLAY LOOP
    # ========================================================

    while True:

        frames = []


        # ----------------------------------------------------
        # Ambil frame masing-masing kamera
        # ----------------------------------------------------

        for camera_name in CAMERAS:

            processor = processors.get(
                camera_name
            )


            if processor is None:

                blank = (
                    cv2.UMat(
                        WINDOW_HEIGHT,
                        WINDOW_WIDTH,
                        cv2.CV_8UC3
                    ).get()
                )

                cv2.putText(

                    blank,

                    f"{camera_name} - NO VIDEO",

                    (50, 180),

                    cv2.FONT_HERSHEY_SIMPLEX,

                    0.8,

                    (255, 255, 255),

                    2
                )

                frames.append(
                    blank
                )

                continue


            with processor.lock:

                if processor.frame is not None:

                    frame = (
                        processor.frame.copy()
                    )

                else:

                    frame = (
                        cv2.UMat(
                            WINDOW_HEIGHT,
                            WINDOW_WIDTH,
                            cv2.CV_8UC3
                        ).get()
                    )


            frame = cv2.resize(

                frame,

                (
                    WINDOW_WIDTH,
                    WINDOW_HEIGHT
                )
            )


            frames.append(
                frame
            )


        # ----------------------------------------------------
        # Pastikan 4 frame
        # ----------------------------------------------------

        while len(frames) < 4:

            frames.append(

                cv2.UMat(

                    WINDOW_HEIGHT,

                    WINDOW_WIDTH,

                    cv2.CV_8UC3

                ).get()
            )


        # ----------------------------------------------------
        # GRID 2 x 2
        # ----------------------------------------------------

        top = cv2.hconcat(
            [
                frames[0],
                frames[1]
            ]
        )


        bottom = cv2.hconcat(
            [
                frames[2],
                frames[3]
            ]
        )


        dashboard = cv2.vconcat(
            [
                top,
                bottom
            ]
        )


        cv2.imshow(

            "SMARTTWIN - 4 CCTV",

            dashboard
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
