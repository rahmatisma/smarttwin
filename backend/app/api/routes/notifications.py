from fastapi import APIRouter, HTTPException

from app.schemas.notification import NotificationListResponse, NotificationMarkReadRequest
from app.services.notification_service import notification_service

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
)

@router.get("", response_model=NotificationListResponse)
def get_notifications():
    try:
        data = notification_service.get_notifications()
        return {
            "success": True,
            "data": data,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil notifikasi: {exc}",
        ) from exc


@router.patch("/{notification_id}/read")
def mark_notification_as_read(notification_id: str):
    try:
        data = notification_service.mark_as_read(notification_id)
        if not data:
            raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan")
        return {"success": True, "data": data[0]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengupdate notifikasi: {exc}",
        ) from exc
