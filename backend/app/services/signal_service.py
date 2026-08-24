from datetime import datetime, timezone
from typing import Optional

from app.schemas.signal import (
    SignalPhase,
    SignalStatus,
    SignalUpdate,
)


class SignalService:
    def __init__(self) -> None:
        self._status: Optional[SignalStatus] = None

    def update_status(
        self,
        update: SignalUpdate,
    ) -> SignalStatus:

        status = SignalStatus(
            intersectionId=update.intersectionId,
            timestamp=datetime.now(timezone.utc),
            currentPhase=update.currentPhase,
            phaseName=update.phaseName,
            remainingSeconds=update.remainingSeconds,
            cycleTimeSeconds=update.cycleTimeSeconds,
            phases=update.phases,
            source="backend",
        )

        self._status = status

        return status

    def get_status(self) -> Optional[SignalStatus]:
        return self._status

    def get_demo_status(self) -> SignalStatus:
        return SignalStatus(
            intersectionId="intersection_01",
            timestamp=datetime.now(timezone.utc),
            currentPhase="NS_GREEN",
            phaseName="North-South Green",
            remainingSeconds=24,
            cycleTimeSeconds=90,
            phases={
                "NS_GREEN": SignalPhase(
                    phaseId="NS_GREEN",
                    state="green",
                    durationSeconds=35,
                    remainingSeconds=24,
                ),
                "NS_YELLOW": SignalPhase(
                    phaseId="NS_YELLOW",
                    state="yellow",
                    durationSeconds=4,
                    remainingSeconds=0,
                ),
                "EW_GREEN": SignalPhase(
                    phaseId="EW_GREEN",
                    state="green",
                    durationSeconds=35,
                    remainingSeconds=0,
                ),
                "EW_YELLOW": SignalPhase(
                    phaseId="EW_YELLOW",
                    state="yellow",
                    durationSeconds=4,
                    remainingSeconds=0,
                ),
            },
            source="demo",
        )


signal_service = SignalService()