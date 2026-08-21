"""
Orkestrasi upload CCTV: Supabase (metadata) + Hugging Face (file video).

Alur (docs/database.md #13):

    Frontend
       |  multipart/form-data
       v
    FastAPI  --insert-->  Supabase (cameras, cameraVideos)
       |
       +--upload-->  Hugging Face Hub (dataset repo, private)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.services.hf_storage_service import upload_video
from app.services.supabase_client import get_supabase

APPROACHES = {"north", "south", "east", "west"}


class CctvServiceError(Exception):
    pass


@dataclass
class UploadedCamera:
    camera_id: int
    video_id: int
    stream_path: str


def _get_intersection_row_id(intersection_id: str) -> int:
    supabase = get_supabase()

    result = (
        supabase.table("intersections")
        .select("id")
        .eq("intersectionId", intersection_id)
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise CctvServiceError(
            f"Intersection '{intersection_id}' tidak ditemukan."
        )

    return result.data["id"]


def _get_approach_row_id(intersection_row_id: int, approach: str) -> int:
    supabase = get_supabase()

    result = (
        supabase.table("approaches")
        .select("id")
        .eq("intersectionId", intersection_row_id)
        .eq("approach", approach)
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise CctvServiceError(f"Approach '{approach}' tidak ditemukan.")

    return result.data["id"]


def upload_camera_video(
    *,
    intersection_id: str,
    approach: str,
    name: str,
    filename: str,
    file_bytes: bytes,
) -> UploadedCamera:
    if approach not in APPROACHES:
        raise CctvServiceError(f"Approach tidak valid: {approach}")

    if not name.strip():
        raise CctvServiceError("Nama CCTV wajib diisi.")

    supabase = get_supabase()

    intersection_row_id = _get_intersection_row_id(intersection_id)
    approach_row_id = _get_approach_row_id(intersection_row_id, approach)

    camera_id = f"cam-{uuid.uuid4()}"

    camera_insert = (
        supabase.table("cameras")
        .insert(
            {
                "intersectionId": intersection_row_id,
                "cameraId": camera_id,
                "name": name.strip(),
                "approachId": approach_row_id,
                "sourceType": "uploaded",
                "sourceUrl": None,
                "status": "active",
            }
        )
        .execute()
    )

    camera_row = camera_insert.data[0]

    hf_result = upload_video(
        file_bytes=file_bytes,
        filename=f"{camera_id}_{filename}",
        intersection_id=intersection_id,
    )

    video_format = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp4"

    video_insert = (
        supabase.table("cameraVideos")
        .insert(
            {
                "cameraId": camera_row["id"],
                "videoName": filename,
                "videoFormat": video_format,
                "storageProvider": "huggingface",
                "repositoryId": hf_result.repository_id,
                "filePath": hf_result.file_path,
                "fileUrl": None,
                "fileSizeBytes": len(file_bytes),
                "status": "uploaded",
            }
        )
        .execute()
    )

    video_row = video_insert.data[0]

    stream_path = f"/api/v1/cctv/videos/{video_row['id']}/stream"

    supabase.table("cameraVideos").update({"fileUrl": stream_path}).eq(
        "id", video_row["id"]
    ).execute()

    return UploadedCamera(
        camera_id=camera_row["id"],
        video_id=video_row["id"],
        stream_path=stream_path,
    )


def get_video_hf_location(video_id: int) -> tuple[str, str]:
    """Return (repository_id, file_path) untuk satu cameraVideos row."""

    supabase = get_supabase()

    result = (
        supabase.table("cameraVideos")
        .select("repositoryId, filePath, storageProvider")
        .eq("id", video_id)
        .maybe_single()
        .execute()
    )

    if not result.data or result.data.get("storageProvider") != "huggingface":
        raise CctvServiceError("Video tidak ditemukan di Hugging Face.")

    return result.data["repositoryId"], result.data["filePath"]
