"""
Proses SATU video hasil upload lewat halaman CCTV -> Supabase.

Beda dengan vehicle_counter.py (yang memproses 4 kamera Pingit asli
yang sudah dikalibrasi lewat sync_report.json dan menulis ke CSV
bersama cv/output/smarttwin_traffic_data.csv), script ini:

    - memproses SATU video ad-hoc untuk SATU approach
    - tidak menyentuh sync_report.json / jam rekaman -> timestamp
      window pakai wall-clock (datetime.now()) saat window ditutup,
      supaya dashboard terasa "baru saja terdeteksi"
    - tidak menulis CSV sama sekali -> setiap window 5 detik langsung
      di-upsert ke Supabase (trafficStates + trafficApproachStates)
      lewat supabase_writer.py, supaya dashboard ter-update sambil
      video masih diproses
    - selain menghitung, tiap frame juga digambari kotak deteksi
      (TANPA garis hitung -- itu cuma alat bantu hitung, bukan buat
      ditonton) lalu ditulis ke video baru supaya halaman CCTV bisa
      menampilkan hasil deteksinya secara visual. Video anotasi ini
      diupload sebagai baris cameraVideos BARU (bukan menimpa video
      asli), lihat supabase_writer.insert_annotated_video().

Konstanta & fungsi murni diimpor dari vehicle_counter.py (aman,
file itu dijaga `if __name__ == "__main__":` jadi tidak ada proses
4-kamera yang otomatis jalan saat diimpor). Logika hitungnya SAMA
PERSIS dengan CameraProcessor di vehicle_counter.py, cuma versi
satu-video tanpa cv2.imshow/threading/multi-kamera.

Video anotasi di-encode H.264 lewat imageio-ffmpeg (bukan
cv2.VideoWriter): encoder H.264 bawaan OpenCV di Windows butuh DLL
openh264 eksternal yang gagal dimuat plugin FFmpeg internal OpenCV
di lingkungan ini, sementara imageio-ffmpeg bawa binary ffmpeg
sendiri lewat pip sehingga selalu bisa encode avc1/yuv420p yang
didukung <video> browser.

Dipanggil oleh backend/app/services/cv_trigger_service.py sebagai
subprocess terpisah (venv cv/.venv sendiri, bukan venv backend).

Setiap window 5 detik juga memanggil POST {BACKEND_URL}/api/v1/traffic/notify
supaya dashboard ter-update SAAT ITU JUGA lewat WebSocket backend --
BUKAN Supabase Realtime (terbukti tidak mem-broadcast event di
project ini walau publication/RLS sudah benar) dan BUKAN polling.
Kalau backend sedang tidak jalan, panggilan ini gagal diam-diam --
data di Supabase tetap tersimpan, cuma dashboard tidak ter-update
otomatis sampai halaman di-refresh manual.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import cv2
import imageio_ffmpeg
import requests
import ultralytics
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vehicle_counter import (  # noqa: E402
    COUNTING_LINES,
    LANE_REGIONS,
    MIN_STOPPED_FRAMES,
    MODEL_PATH,
    QUEUE_SPACE_M,
    QUEUE_ZONE_Y_RATIO,
    STOPPED_PIXEL_THRESHOLD,
    TRACK_CLASSES,
    VEHICLE_CLASSES,
    YOLO_CLASSES,
    get_lane_id,
    get_line,
    is_in_pedestrian_zone,
    menuju_simpang,
    person_is_rider,
    potongan_dalam_ruas,
    side_of_line,
)

import hf_writer as hw  # noqa: E402
import supabase_writer as sw  # noqa: E402

WINDOW_SECONDS = 5

CONFIDENCE = 0.35

BOX_COLOR = (0, 255, 0)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8001")


def notify_backend(payload: dict) -> None:
    """
    Best-effort: dashboard update lewat jalur ini bukan hal yang
    boleh menggagalkan job CV kalau backend kebetulan mati/lambat.
    Data traffic-nya sendiri sudah aman di Supabase sebelum fungsi
    ini dipanggil.
    """

    try:
        requests.post(
            f"{BACKEND_URL}/api/v1/traffic/notify",
            json=payload,
            timeout=2,
        )
    except requests.RequestException:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("--video", required=True)
    parser.add_argument("--approach", required=True, choices=list(COUNTING_LINES.keys()))
    parser.add_argument("--camera-id", required=True, type=int)
    parser.add_argument("--video-id", required=True, type=int)
    parser.add_argument("--intersection-id", required=True, type=int, help="ROW ID intersections.id, bukan intersectionId text")
    parser.add_argument("--intersection-slug", required=True, help="intersectionId text, mis. simpang4-pingit -- dipakai buat path penyimpanan HF")
    parser.add_argument("--job-id", required=True, type=int)

    return parser.parse_args()


def empty_lane_bucket() -> dict:
    return {
        "car_count": 0,
        "motorcycle_count": 0,
        "bus_count": 0,
        "truck_count": 0,
        "queue_length": 0,
        "queue_car": 0,
        "queue_motorcycle": 0,
        "queue_bus": 0,
        "queue_truck": 0,
    }


class WindowAccumulator:
    """
    Menampung crossing + kehadiran selama WINDOW_SECONDS, lalu
    di-flush jadi satu upsert Supabase.

    Ini versi sederhana dari PerSecondCounter+TrafficStateBuilder di
    vehicle_counter.py/backend, digabung jadi satu langkah karena di
    sini tidak ada CSV perantara.
    """

    def __init__(self, approach: str, approach_id: int, intersection_row_id: int, job_id: int):
        self.approach = approach
        self.approach_id = approach_id
        self.intersection_row_id = intersection_row_id
        self.job_id = job_id

        self.window_start: datetime | None = None
        self.crossing: dict[str, defaultdict] = {}
        self.presence_snapshot: dict[str, dict] = {}

    def add_crossing(self, lane_id: str, object_type: str) -> None:
        lane = self.crossing.setdefault(lane_id, defaultdict(int))
        lane[object_type] += 1

    def update_presence(self, lane_counts: dict[str, dict]) -> None:
        self.presence_snapshot = lane_counts

    def maybe_flush(self, now: datetime) -> None:
        if self.window_start is None:
            self.window_start = now
            return

        elapsed = (now - self.window_start).total_seconds()

        if elapsed < WINDOW_SECONDS:
            return

        self._flush(self.window_start + timedelta(seconds=WINDOW_SECONDS))
        self.window_start = self.window_start + timedelta(seconds=WINDOW_SECONDS)

    def flush_final(self, now: datetime) -> None:
        if self.window_start is None:
            return

        self._flush(now)

    def _flush(self, window_end: datetime) -> None:
        window_start = self.window_start

        car = sum(lane.get("car", 0) for lane in self.crossing.values())
        motorcycle = sum(lane.get("motorcycle", 0) for lane in self.crossing.values())
        bus = sum(lane.get("bus", 0) for lane in self.crossing.values())
        truck = sum(lane.get("truck", 0) for lane in self.crossing.values())
        volume = car + motorcycle + bus + truck

        queue_length_veh = sum(
            lane.get("queue_length", 0) for lane in self.presence_snapshot.values()
        )

        queue_length_m_est = sum(
            lane.get(f"queue_{kelas}", 0) * meter
            for lane in self.presence_snapshot.values()
            for kelas, meter in QUEUE_SPACE_M.items()
        )

        densities = [
            lane.get("density", 0.0) for lane in self.presence_snapshot.values()
        ]
        density_index = (sum(densities) / len(densities)) if densities else 0.0

        metrics = {
            "volume": volume,
            "carCount": car,
            "motorcycleCount": motorcycle,
            "busCount": bus,
            "truckCount": truck,
            "queueLengthVeh": queue_length_veh,
            "queueLengthMEst": round(queue_length_m_est, 2),
            "densityIndex": round(density_index, 6),
            "avgSpeedKmh": None,
        }

        sw.upsert_traffic_window(
            intersection_row_id=self.intersection_row_id,
            window_start=window_start,
            window_end=window_end,
            processing_job_id=self.job_id,
            approach=self.approach,
            approach_id=self.approach_id,
            metrics=metrics,
        )

        # Data sudah aman di Supabase di atas -- notify ini cuma
        # supaya dashboard yang lagi terbuka ikut update SAAT INI
        # JUGA, bukan lain kali di-refresh manual.
        notify_backend(
            {
                "approach": self.approach,
                "windowStart": window_start.isoformat(),
                "windowEnd": window_end.isoformat(),
                **metrics,
            }
        )

        print(
            f"[{window_start.strftime('%H:%M:%S')}-{window_end.strftime('%H:%M:%S')}] "
            f"{self.approach} | volume={volume} queue={queue_length_veh} "
            f"density={density_index:.3f}"
        )

        self.crossing = {}


def upload_annotated_video(
    *,
    local_path: str,
    camera_id: int,
    intersection_slug: str,
) -> None:
    """
    Upload video anotasi ke HF, lalu simpan sebagai baris cameraVideos
    BARU (uploadedAt lebih baru dari video asli, lihat catatan di
    supabase_writer.insert_annotated_video()).
    """

    filename = f"cam-{camera_id}_annotated_{int(datetime.now(timezone.utc).timestamp())}.mp4"

    result = hw.upload_annotated_video(
        local_path=local_path,
        intersection_id=intersection_slug,
        filename=filename,
    )

    file_size_bytes = os.path.getsize(local_path)

    video_id = sw.insert_annotated_video(
        camera_id=camera_id,
        video_name=filename,
        repository_id=result.repository_id,
        file_path=result.file_path,
        file_size_bytes=file_size_bytes,
    )

    sw.set_video_file_url(
        video_id, f"/api/v1/cctv/videos/{video_id}/stream"
    )

    print(f"[INFO] Video anotasi terupload, videoId={video_id}")


def run(args: argparse.Namespace) -> None:
    approach = args.approach

    approach_id = sw.get_approach_row_id(args.intersection_id, approach)

    accumulator = WindowAccumulator(
        approach=approach,
        approach_id=approach_id,
        intersection_row_id=args.intersection_id,
        job_id=args.job_id,
    )

    print(f"[INFO] Membuka video: {args.video}")

    cap = cv2.VideoCapture(args.video)

    if not cap.isOpened():
        raise RuntimeError(f"Tidak dapat membuka video: {args.video}")

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = 25

    print(f"[INFO] Loading model: {MODEL_PATH}")

    model = YOLO(MODEL_PATH)

    counted_ids: set[int] = set()
    last_side: dict[int, float] = {}
    last_centroids: dict[int, tuple[float, float]] = {}
    stopped_frames: dict[int, int] = defaultdict(int)

    frame_idx = -1

    job_start = datetime.now(timezone.utc)

    # Video anotasi (kotak deteksi dibakar ke frame, TANPA garis
    # hitung) -- dibuka lazy di frame pertama begitu ukuran frame
    # sungguhan diketahui. Lihat docstring header soal kenapa
    # imageio-ffmpeg, bukan cv2.VideoWriter.
    annotated_path = tempfile.NamedTemporaryFile(
        suffix="_annotated.mp4", delete=False
    ).name

    annotated_writer = None

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        frame_idx += 1

        height, width = frame.shape[:2]

        line_p1, line_p2 = get_line(width, height, approach)

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

        lane_current: dict[str, dict] = defaultdict(empty_lane_bucket)

        if boxes is not None and boxes.id is not None:
            track_ids = boxes.id.int().cpu().tolist()
            classes = boxes.cls.int().cpu().tolist()
            coordinates = boxes.xyxy.cpu().tolist()

            motorcycle_boxes = [
                box for cls_id, box in zip(classes, coordinates) if cls_id == 3
            ]

            for track_id, cls_id, box in zip(track_ids, classes, coordinates):
                x1, y1, x2, y2 = box

                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                object_type = YOLO_CLASSES.get(cls_id, "unknown")

                if object_type == "unknown":
                    continue

                if object_type == "person":
                    is_rider = person_is_rider(
                        person_box=(x1, y1, x2, y2),
                        motorcycle_boxes=motorcycle_boxes,
                        width=width,
                        height=height,
                    )

                    if is_rider:
                        object_type = "motorcycle"
                    elif not is_in_pedestrian_zone(approach, cx, cy, width, height):
                        continue

                lane_id = get_lane_id(approach, cx, width)

                if object_type in VEHICLE_CLASSES.values():
                    lane_current[lane_id][f"{object_type}_count"] += 1

                    cv2.rectangle(
                        frame,
                        (int(x1), int(y1)),
                        (int(x2), int(y2)),
                        BOX_COLOR,
                        2,
                    )

                    cv2.putText(
                        frame,
                        object_type,
                        (int(x1), max(15, int(y1) - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        BOX_COLOR,
                        2,
                    )

                previous_centroid = last_centroids.get(track_id)

                if previous_centroid is not None:
                    dx = cx - previous_centroid[0]
                    dy = cy - previous_centroid[1]
                    movement = (dx * dx + dy * dy) ** 0.5

                    if movement <= STOPPED_PIXEL_THRESHOLD:
                        stopped_frames[track_id] += 1
                    else:
                        stopped_frames[track_id] = 0

                last_centroids[track_id] = (cx, cy)

                queue_zone_y = height * QUEUE_ZONE_Y_RATIO

                is_queue_vehicle = (
                    object_type in VEHICLE_CLASSES.values()
                    and cy >= queue_zone_y
                    and stopped_frames[track_id] >= MIN_STOPPED_FRAMES
                )

                if is_queue_vehicle:
                    lane_current[lane_id]["queue_length"] += 1
                    lane_current[lane_id][f"queue_{object_type}"] += 1

                current_side = side_of_line((cx, cy), line_p1, line_p2)
                previous_side = last_side.get(track_id)

                if (
                    previous_side is not None
                    and previous_side * current_side < 0
                    and previous_centroid is not None
                    and potongan_dalam_ruas(previous_centroid, (cx, cy), line_p1, line_p2)
                    and menuju_simpang(approach, cx - previous_centroid[0], cy - previous_centroid[1])
                    and track_id not in counted_ids
                ):
                    accumulator.add_crossing(lane_id, object_type)
                    counted_ids.add(track_id)

                last_side[track_id] = current_side

        for lane_id, lane_info in lane_current.items():
            lane_def = next(
                (d for d in LANE_REGIONS[approach] if d[0] == lane_id), None
            )

            lane_width_fraction = (lane_def[2] - lane_def[1]) if lane_def else 1.0
            area_fraction = max(lane_width_fraction, 0.001)

            vehicle_now = (
                lane_info["car_count"]
                + lane_info["motorcycle_count"]
                + lane_info["bus_count"]
                + lane_info["truck_count"]
            )

            lane_info["density"] = vehicle_now / area_fraction

        accumulator.update_presence(lane_current)
        accumulator.maybe_flush(datetime.now(timezone.utc))

        if annotated_writer is None:
            annotated_writer = imageio_ffmpeg.write_frames(
                annotated_path,
                (width, height),
                fps=fps,
                codec="libx264",
                pix_fmt_in="bgr24",
                pix_fmt_out="yuv420p",
            )
            annotated_writer.send(None)

        annotated_writer.send(frame.tobytes())

    cap.release()

    accumulator.flush_final(datetime.now(timezone.utc))

    elapsed = (datetime.now(timezone.utc) - job_start).total_seconds()

    print(f"[INFO] Selesai. {frame_idx + 1} frame diproses dalam {elapsed:.1f} detik.")

    if annotated_writer is not None:
        annotated_writer.close()

        try:
            upload_annotated_video(
                local_path=annotated_path,
                camera_id=args.camera_id,
                intersection_slug=args.intersection_slug,
            )
        except Exception as exc:  # noqa: BLE001
            # Video anotasi cuma pelengkap visual -- kalau upload-nya
            # gagal, data traffic yang sudah masuk Supabase tetap sah.
            # Jangan sampai job berstatus "failed" gara-gara ini.
            print(f"[WARNING] Gagal upload video anotasi: {exc}")

    if os.path.exists(annotated_path):
        try:
            os.remove(annotated_path)
        except OSError:
            pass


def main() -> None:
    args = parse_args()  # exit di sini kalau argumen tidak valid, sebelum job_id diketahui

    try:
        run(args)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()

        sw.update_job_status(args.job_id, "failed", error_message=str(exc))

        sys.exit(1)
    else:
        sw.update_job_status(args.job_id, "completed")
        sw.mark_video_processed(args.video_id)
    finally:
        if os.path.exists(args.video):
            try:
                os.remove(args.video)
            except OSError:
                pass


if __name__ == "__main__":
    print(f"[INFO] ultralytics {ultralytics.__version__}")
    main()
