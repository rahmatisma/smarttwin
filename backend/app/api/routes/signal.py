from fastapi import APIRouter, Depends

from app.schemas.signal import SignalStatus, SignalUpdate
from app.services.signal_service import signal_service
from app.core.auth import require_operator


router = APIRouter(
    prefix="/signal",
    tags=["Signal"],
)


@router.get(
    "/status",
    response_model=SignalStatus,
)
def get_signal_status():
    return signal_service.get_live_status()


@router.post(
    "/status",
    response_model=SignalStatus,
    dependencies=[Depends(require_operator)],
)
def update_signal_status(
    update: SignalUpdate,
):
    return signal_service.update_status(update)
