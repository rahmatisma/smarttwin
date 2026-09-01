"""Endpoint Riwayat Keputusan.

File ini sebelumnya KOSONG (0 baris) dan tidak pernah didaftarkan di
main.py — halaman /history di frontend memakai data contoh. Sekarang diisi
dan disambungkan ke riwayat asli yang ditulis simulation/scenario_worker.py.
"""

from fastapi import APIRouter, HTTPException, Query

from app.services.history_service import history_service

router = APIRouter(prefix="/api/v1/history", tags=["History"])


@router.get("/recommendations")
def list_recommendation_history(
    intersectionId: str = Query(default="simpang4-pingit"),
    page: int = Query(default=1, ge=1),
    # Dibatasi 100 supaya satu permintaan tidak pernah mendekati ambang
    # pemotongan senyap PostgREST (1000 baris = 250 siklus).
    pageSize: int = Query(default=20, ge=1, le=100),
):
    """Daftar siklus keputusan, terbaru dulu, dipaginasi per siklus.

    Satu item = satu siklus worker, berisi durasi hijau per lengan, kandidat
    yang diuji beserta metriknya, dan kondisi lalu lintas yang memicunya.
    """
    try:
        return history_service.list_cycles(
            intersection_id=intersectionId,
            page=page,
            page_size=pageSize,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
