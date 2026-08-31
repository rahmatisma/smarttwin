"""
Jalankan CV (deteksi kendaraan + gambar kotak + garis hitung merah)
untuk SEMUA video CCTV yang sudah diupload lewat halaman web tapi
belum pernah diproses -- tanpa argumen, tanpa export env var manual,
tanpa perlu tahu video-id/camera-id/job-id satu-satu.

Cukup:

    python reprocess_all.py

(pakai venv CUDA di luar repo kalau ada, biar cepat -- lihat pesan
"[INFO] pakai ..." di baris pertama output buat konfirmasi venv mana
yang aktif kepakai)

Cara kerja
----------
1. Baca kredensial (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, HF_TOKEN,
   HF_REPO_ID) langsung dari ../.env (root repo), taruh ke os.environ --
   ini sebabnya kamu TIDAK perlu export manual seperti kalau
   menjalankan process_uploaded_video.py sendirian.
2. Cari semua kamera milik intersection "simpang4-pingit" di
   Supabase, lalu untuk tiap kamera cek cameraVideos-nya:
     - video ASLI = storageProvider "huggingface" dan namanya TIDAK
       mengandung "_annotated_"
     - kamera dianggap SUDAH diproses kalau sudah punya video lain
       dengan "_annotated_" di namanya
   Kamera yang punya video asli tapi belum punya video anotasi ->
   masuk antrian.
3. Untuk tiap video di antrian: cari file lokalnya dulu di cv/videos/
   (video kalibrasi asli CCTV_1..4.mp4 kalau namanya cocok), atau
   download dari Hugging Face kalau tidak ketemu lokal.
4. Panggil process_uploaded_video.run() -- fungsi yang SAMA PERSIS
   dipakai backend saat upload otomatis, jadi hasilnya identik:
   trafficStates + trafficApproachStates ke Supabase per 5 detik, dan
   video anotasi (kotak + garis merah) diupload sebagai cameraVideos
   baru.

Aman dipanggil berkali-kali: video yang sudah punya hasil anotasi
otomatis dilewati (tidak diproses dobel).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from types import SimpleNamespace

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

INTERSECTION_SLUG = "simpang4-pingit"


def load_backend_env() -> None:
    """
    Baca ../.env (root repo) dan isi ke os.environ (tidak menimpa kalau
    variabelnya sudah di-set manual di shell).
    """
    env_path = os.path.join(BASE_DIR, "..", ".env")

    if not os.path.exists(env_path):
        raise RuntimeError(
            f"{env_path} tidak ditemukan -- tidak bisa membaca kredensial "
            "Supabase/Hugging Face secara otomatis."
        )

    with open(env_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, _, value = line.partition("=")

            os.environ.setdefault(key.strip(), value.strip())


def find_local_video(video_name: str) -> str | None:
    """
    Cek apakah video_name cocok dengan salah satu file di cv/videos/
    (video kalibrasi asli). None kalau tidak ada.
    """
    candidate = os.path.join(BASE_DIR, "videos", video_name)

    return candidate if os.path.exists(candidate) else None


def download_from_hf(repository_id: str, file_path: str, dest_path: str) -> None:
    from huggingface_hub import hf_hub_download

    cached_path = hf_hub_download(
        repo_id=repository_id,
        repo_type="dataset",
        filename=file_path,
        token=os.environ["HF_TOKEN"],
    )

    shutil.copyfile(cached_path, dest_path)


def find_pending_videos(sw) -> list[dict]:
    """
    Balikin daftar dict {camera_id, camera_row_id, name, approach,
    video_id, video_name, repository_id, file_path} untuk tiap kamera
    yang punya video asli tapi belum punya video anotasi.
    """
    supabase = sw.get_client()

    intersection = (
        supabase.table("intersections")
        .select("id")
        .eq("intersectionId", INTERSECTION_SLUG)
        .maybe_single()
        .execute()
    )

    if intersection is None or not intersection.data:
        raise RuntimeError(f"Intersection '{INTERSECTION_SLUG}' tidak ditemukan.")

    intersection_row_id = intersection.data["id"]

    cameras = (
        supabase.table("cameras")
        .select("id, cameraId, name, approachId")
        .eq("intersectionId", intersection_row_id)
        .execute()
    )

    approaches = (
        supabase.table("approaches")
        .select("id, approach")
        .eq("intersectionId", intersection_row_id)
        .execute()
    )
    approach_by_id = {row["id"]: row["approach"] for row in approaches.data}

    pending = []

    for camera in cameras.data:
        videos = (
            supabase.table("cameraVideos")
            .select("id, videoName, storageProvider, repositoryId, filePath, uploadedAt")
            .eq("cameraId", camera["id"])
            .order("uploadedAt")
            .execute()
        )

        has_annotated = any(
            "_annotated_" in (v["videoName"] or "") for v in videos.data
        )

        if has_annotated:
            continue

        original = next(
            (
                v
                for v in videos.data
                if v["storageProvider"] == "huggingface"
                and "_annotated_" not in (v["videoName"] or "")
            ),
            None,
        )

        if original is None:
            continue

        approach = approach_by_id.get(camera["approachId"])

        if approach is None:
            print(
                f"[SKIP] {camera['name']}: approach tidak diketahui "
                f"(approachId={camera['approachId']})"
            )
            continue

        pending.append(
            {
                "camera_row_id": camera["id"],
                "camera_name": camera["name"],
                "approach": approach,
                "video_id": original["id"],
                "video_name": original["videoName"],
                "repository_id": original["repositoryId"],
                "file_path": original["filePath"],
            }
        )

    return pending, intersection_row_id


def process_one(sw, item: dict, intersection_row_id: int) -> None:
    import process_uploaded_video as pv

    print(f"\n=== {item['camera_name']} ({item['approach']}) ===")

    local_path = find_local_video(item["video_name"])

    temp_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name

    if local_path:
        print(f"[INFO] Pakai file lokal: {local_path}")
        shutil.copyfile(local_path, temp_path)
    else:
        print(
            f"[INFO] File lokal tidak ada, download dari Hugging Face: "
            f"{item['repository_id']}/{item['file_path']}"
        )
        download_from_hf(item["repository_id"], item["file_path"], temp_path)

    job = (
        sw.get_client()
        .table("cvProcessingJobs")
        .insert(
            {
                "videoId": item["video_id"],
                "modelName": "YOLO26s-ByteTrack",
                "modelVersion": "ultralytics-track",
                "status": "running",
                "startedAt": __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat(),
            }
        )
        .execute()
    )
    job_id = job.data[0]["id"]

    args = SimpleNamespace(
        video=temp_path,
        approach=item["approach"],
        camera_id=item["camera_row_id"],
        video_id=item["video_id"],
        intersection_id=intersection_row_id,
        intersection_slug=INTERSECTION_SLUG,
        job_id=job_id,
    )

    try:
        pv.run(args)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        sw.update_job_status(job_id, "failed", error_message=str(exc))
    else:
        sw.update_job_status(job_id, "completed")
        sw.mark_video_processed(item["video_id"])
    finally:
        if os.path.exists(args.video):
            try:
                os.remove(args.video)
            except OSError:
                pass


def main() -> None:
    load_backend_env()

    os.environ.setdefault("BACKEND_URL", "http://127.0.0.1:8001")

    import supabase_writer as sw

    pending, intersection_row_id = find_pending_videos(sw)

    if not pending:
        print("Tidak ada video yang perlu diproses -- semua sudah punya hasil deteksi.")
        return

    # Video yang punya salinan lokal (cepat, pasti bisa dibuka) duluan;
    # yang harus didownload dari HF (lebih rawan gagal -- termasuk
    # kemungkinan video lama yang metadatanya ada tapi filenya sendiri
    # tidak pernah benar-benar terupload) belakangan.
    pending.sort(key=lambda item: find_local_video(item["video_name"]) is None)

    print(f"Ditemukan {len(pending)} video yang belum diproses:")

    for item in pending:
        print(f"  - {item['camera_name']} ({item['approach']}) : {item['video_name']}")

    failures = []

    for item in pending:
        try:
            process_one(sw, item, intersection_row_id)
        except Exception as exc:  # noqa: BLE001
            # SATU video gagal (mis. file-nya cuma metadata lama yang
            # tidak pernah benar-benar terupload ke HF) TIDAK BOLEH
            # menghentikan antrian video lain di belakangnya.
            traceback.print_exc()
            print(f"[GAGAL] {item['camera_name']}: {exc} -- lanjut ke video berikutnya.")
            failures.append(item["camera_name"])

    if failures:
        print(f"\nSelesai dengan {len(failures)} gagal: {', '.join(failures)}")
    else:
        print("\nSelesai semua.")


if __name__ == "__main__":
    main()
