"""
Penyimpanan video CCTV ke Hugging Face Hub.

Lihat docs/database.md #13 — Video Storage Architecture:

    PostgreSQL (Supabase)  -> metadata (cameraVideos)
    Hugging Face Hub       -> file video asli (.mp4)

Repo dataset dibuat otomatis (private) saat upload pertama kali
kalau belum ada.
"""

from __future__ import annotations

from dataclasses import dataclass

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

from app.core.config import settings


@dataclass
class HfUploadResult:
    repository_id: str
    file_path: str
    file_url: str


def _get_api() -> HfApi:
    if not settings.hf_token:
        raise RuntimeError("HF_TOKEN belum diset di .env")

    return HfApi(token=settings.hf_token)


def ensure_dataset_repo() -> None:
    api = _get_api()

    try:
        api.repo_info(repo_id=settings.hf_repo_id, repo_type="dataset")
    except RepositoryNotFoundError:
        api.create_repo(
            repo_id=settings.hf_repo_id,
            repo_type="dataset",
            private=True,
            exist_ok=True,
        )


def upload_video(
    *,
    file_bytes: bytes,
    filename: str,
    intersection_id: str,
) -> HfUploadResult:
    """
    Upload satu file video ke dataset repo.

    Path di repo: videos/{intersection_id}/{filename}
    """

    ensure_dataset_repo()

    api = _get_api()

    path_in_repo = f"videos/{intersection_id}/{filename}"

    api.upload_file(
        path_or_fileobj=file_bytes,
        path_in_repo=path_in_repo,
        repo_id=settings.hf_repo_id,
        repo_type="dataset",
    )

    file_url = (
        f"https://huggingface.co/datasets/{settings.hf_repo_id}"
        f"/resolve/main/{path_in_repo}"
    )

    return HfUploadResult(
        repository_id=settings.hf_repo_id,
        file_path=path_in_repo,
        file_url=file_url,
    )
