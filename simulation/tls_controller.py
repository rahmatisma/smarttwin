from __future__ import annotations

from dataclasses import dataclass


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_GREEN_DURATION = 30
MIN_GREEN_DURATION = 10
MAX_GREEN_DURATION = 60
YELLOW_DURATION = 6

NORTH_SOUTH_PHASE = 0
YELLOW_NS_PHASE = 1
EAST_WEST_PHASE = 2


# ============================================================
# PHASE PLAN
# ============================================================

@dataclass(frozen=True)
class PhasePlan:
    """
    Rencana phase TLS yang akan diberikan ke SUMO.
    """

    phase: int
    duration: int
    reason: str


# ============================================================
# TLS CONTROLLER
# ============================================================

class TLSController:

    def __init__(
        self,
        tls_id: str = "SIMPANG_CENTER",
    ) -> None:

        self.tls_id = tls_id

        self.current_phase = None

        print("TLS Controller berhasil dibuat.")

    # ========================================================
    # TRAFFIC STATE → PHASE PLAN
    # ========================================================

    def create_phase_plan(
        self,
        traffic_state,
    ) -> PhasePlan:

        north = self._get_approach(
            traffic_state,
            "north",
        )

        south = self._get_approach(
            traffic_state,
            "south",
        )

        east = self._get_approach(
            traffic_state,
            "east",
        )

        west = self._get_approach(
            traffic_state,
            "west",
        )

        # ----------------------------------------------------
        # Hitung demand
        # ----------------------------------------------------

        ns_demand = (
            north.queueLengthVeh
            + south.queueLengthVeh
        )

        ew_demand = (
            east.queueLengthVeh
            + west.queueLengthVeh
        )

        # ----------------------------------------------------
        # Jika North/South lebih padat
        # ----------------------------------------------------

        if ns_demand > ew_demand:

            duration = self._calculate_green_duration(
                ns_demand
            )

            return PhasePlan(
                phase=NORTH_SOUTH_PHASE,
                duration=duration,
                reason=(
                    "North/South memiliki "
                    "queue lebih tinggi."
                ),
            )

        # ----------------------------------------------------
        # Jika East/West lebih padat
        # ----------------------------------------------------

        if ew_demand > ns_demand:

            duration = self._calculate_green_duration(
                ew_demand
            )

            return PhasePlan(
                phase=EAST_WEST_PHASE,
                duration=duration,
                reason=(
                    "East/West memiliki "
                    "queue lebih tinggi."
                ),
            )

        # ----------------------------------------------------
        # Jika sama
        # ----------------------------------------------------

        return PhasePlan(
            phase=NORTH_SOUTH_PHASE,
            duration=DEFAULT_GREEN_DURATION,
            reason=(
                "Demand seimbang. "
                "Menggunakan phase default."
            ),
        )

    # ========================================================
    # APPLY TO TRAFFIC LIGHT
    # ========================================================

    def apply_phase(
        self,
        traci,
        phase_plan: PhasePlan,
    ) -> None:

        traci.trafficlight.setPhase(
            self.tls_id,
            phase_plan.phase,
        )

        traci.trafficlight.setPhaseDuration(
            self.tls_id,
            phase_plan.duration,
        )

        self.current_phase = phase_plan.phase

        print()
        print("=" * 70)
        print("TLS PHASE APPLIED")
        print("=" * 70)

        print(
            f"TLS      : {self.tls_id}"
        )

        print(
            f"Phase    : {phase_plan.phase}"
        )

        print(
            f"Duration : {phase_plan.duration}s"
        )

        print(
            f"Reason   : {phase_plan.reason}"
        )

        print("=" * 70)

    # ========================================================
    # HELPER
    # ========================================================

    @staticmethod
    def _get_approach(
        traffic_state,
        approach_name: str,
    ):

        for approach in traffic_state.approaches:

            if (
                approach.approach.lower()
                == approach_name
            ):
                return approach

        raise ValueError(
            f"Approach '{approach_name}' "
            "tidak ditemukan."
        )

    # ========================================================
    # GREEN DURATION
    # ========================================================

    @staticmethod
    def _calculate_green_duration(
        queue: int,
    ) -> int:

        duration = (
            DEFAULT_GREEN_DURATION
            + queue
        )

        duration = max(
            MIN_GREEN_DURATION,
            duration,
        )

        duration = min(
            MAX_GREEN_DURATION,
            duration,
        )

        return int(duration)

    # ========================================================
    # INFO
    # ========================================================

    def get_current_phase(self) -> int | None:

        return self.current_phase