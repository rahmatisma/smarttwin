from fastapi import APIRouter

from app.schemas.signal import SignalStatus, SignalUpdate
from app.services.signal_service import signal_service


router = APIRouter(
    prefix="/signal",
    tags=["Signal"],
)


@router.get(
    "/status",
    response_model=SignalStatus,
)
def get_signal_status():
    status = signal_service.get_status()

    if status is None:
        status = signal_service.get_demo_status()

    return status


@router.post(
    "/status",
    response_model=SignalStatus,
)
def update_signal_status(
    update: SignalUpdate,
):
    return signal_service.update_status(update)