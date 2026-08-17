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
            intersection_id=update.intersection_id,
            timestamp=datetime.now(timezone.utc),
            current_phase=update.current_phase,
            phase_name=update.phase_name,
            remaining_seconds=update.remaining_seconds,
            cycle_time_seconds=update.cycle_time_seconds,
            phases=update.phases,
            source="backend",
        )

        self._status = status

        return status

    def get_status(self) -> Optional[SignalStatus]:
        return self._status

    def get_demo_status(self) -> SignalStatus:
        return SignalStatus(
            intersection_id="intersection_01",
            timestamp=datetime.now(timezone.utc),
            current_phase="NS_GREEN",
            phase_name="North-South Green",
            remaining_seconds=24,
            cycle_time_seconds=90,
            phases={
                "NS_GREEN": SignalPhase(
                    phase_id="NS_GREEN",
                    state="green",
                    duration_seconds=35,
                    remaining_seconds=24,
                ),
                "NS_YELLOW": SignalPhase(
                    phase_id="NS_YELLOW",
                    state="yellow",
                    duration_seconds=4,
                    remaining_seconds=0,
                ),
                "EW_GREEN": SignalPhase(
                    phase_id="EW_GREEN",
                    state="green",
                    duration_seconds=35,
                    remaining_seconds=0,
                ),
                "EW_YELLOW": SignalPhase(
                    phase_id="EW_YELLOW",
                    state="yellow",
                    duration_seconds=4,
                    remaining_seconds=0,
                ),
            },
            source="demo",
        )


signal_service = SignalService()