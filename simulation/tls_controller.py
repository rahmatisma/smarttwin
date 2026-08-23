from __future__ import annotations

from dataclasses import dataclass


# ============================================================
# TLS CONFIGURATION
# ============================================================

TLS_ID = "SIMPANG_CENTER"

PHASE_NS = 0
PHASE_YELLOW = 1
PHASE_EW = 2


# ============================================================
# PHASE PLAN
# ============================================================

@dataclass
class PhasePlan:
    phase: int
    duration: int
    reason: str


# ============================================================
# TLS CONTROLLER
# ============================================================

class TLSController:

    def __init__(
        self,
        tls_id: str = TLS_ID,
    ):
        self.tls_id = tls_id

    # ========================================================
    # CALCULATE PHASE PLAN
    # ========================================================

    def calculate_phase_plan(
        self,
        north_volume: int,
        south_volume: int,
        east_volume: int,
        west_volume: int,
    ) -> PhasePlan:

        ns_volume = (
            north_volume
            + south_volume
        )

        ew_volume = (
            east_volume
            + west_volume
        )

        # ----------------------------------------------------
        # NS lebih padat
        # ----------------------------------------------------

        if ns_volume >= ew_volume:

            duration = self._calculate_green_duration(
                ns_volume
            )

            return PhasePlan(
                phase=PHASE_NS,
                duration=duration,
                reason=(
                    "North + South memiliki "
                    "volume lebih tinggi."
                ),
            )

        # ----------------------------------------------------
        # EW lebih padat
        # ----------------------------------------------------

        duration = self._calculate_green_duration(
            ew_volume
        )

        return PhasePlan(
            phase=PHASE_EW,
            duration=duration,
            reason=(
                "East + West memiliki "
                "volume lebih tinggi."
            ),
        )

    # ========================================================
    # GREEN DURATION
    # ========================================================

    def _calculate_green_duration(
        self,
        volume: int,
    ) -> int:

        # Minimum green
        if volume <= 5:
            return 20

        # Normal
        if volume <= 15:
            return 30

        # Padat
        if volume <= 30:
            return 40

        # Sangat padat
        return 50

    # ========================================================
    # PRINT PLAN
    # ========================================================

    def print_plan(
        self,
        plan: PhasePlan,
    ):

        print()
        print("=" * 70)
        print("TLS PHASE PLAN")
        print("=" * 70)

        print(
            f"TLS      : {self.tls_id}"
        )

        print(
            f"Phase    : {plan.phase}"
        )

        print(
            f"Duration : {plan.duration}s"
        )

        print(
            f"Reason   : {plan.reason}"
        )