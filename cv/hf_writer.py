"""
Upload video hasil anotasi (kotak deteksi dibakar ke frame) ke
Hugging Face Hub.

Mirror dari backend/app/services/hf_storage_service.py, tapi baca
HF_TOKEN/HF_REPO_ID dari environment variable (di-inject backend saat
men-spawn subprocess ini), bukan dari app.core.config.settings --
cv/ tidak mengimpor backend/ (venv terpisah).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError


@dataclass
class HfUploadResult:
    repository_id: str
    file_path: str


def _get_api() -> HfApi:
    token = os.environ.get("HF_TOKEN")

    if not token:
        raise RuntimeError("HF_TOKEN tidak ada di environment.")

    return HfApi(token=token)


def upload_annotated_video(
    *,
    local_path: str,
    intersection_id: str,
    filename: str,
) -> HfUploadResult:
    """
    Upload satu file video ke dataset repo, path:
    videos/{intersection_id}/annotated/{filename}
    """

    repo_id = os.environ.get("HF_REPO_ID")

    if not repo_id:
        raise RuntimeError("HF_REPO_ID tidak ada di environment.")

    api = _get_api()

    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
    except RepositoryNotFoundError:
        api.create_repo(repo_id=repo_id, repo_type="dataset", private=True, exist_ok=True)

    path_in_repo = f"videos/{intersection_id}/annotated/{filename}"

    api.upload_file(
        path_or_fileobj=local_path,
        path_in_repo=path_in_repo,
        repo_id=repo_id,
        repo_type="dataset",
    )

    return HfUploadResult(repository_id=repo_id, file_path=path_in_repo)
