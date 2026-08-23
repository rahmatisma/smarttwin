from __future__ import annotations

from pathlib import Path

import traci


# ============================================================
# CONFIG
# ============================================================

SIMULATION_ROOT = Path(__file__).resolve().parent

NET_FILE = (
    SIMULATION_ROOT
    / "network"
    / "simpang4_pingit.net.xml.gz"
)

TLS_ID = "SIMPANG_CENTER"

SUMO_BINARY = (
    SIMULATION_ROOT
    / ".venv"
    / "Lib"
    / "site-packages"
    / "sumo"
    / "bin"
    / "sumo-gui.exe"
)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("SMARTTWIN TLS RUNTIME DIAGNOSTIC")
    print("=" * 70)

    if not NET_FILE.exists():
        raise FileNotFoundError(
            f"Network tidak ditemukan:\n{NET_FILE}"
        )

    if not SUMO_BINARY.exists():
        raise FileNotFoundError(
            f"SUMO tidak ditemukan:\n{SUMO_BINARY}"
        )

    # --------------------------------------------------------
    # START SUMO
    # --------------------------------------------------------

    command = [
        str(SUMO_BINARY),

        "--net-file",
        str(NET_FILE),

        "--begin",
        "0",

        "--end",
        "60",

        "--step-length",
        "1",

        "--quit-on-end",
    ]

    print()
    print("Starting SUMO...")

    traci.start(command)

    try:

        # ----------------------------------------------------
        # CHECK TLS
        # ----------------------------------------------------

        tls_ids = traci.trafficlight.getIDList()

        print()
        print("=" * 70)
        print("TRAFFIC LIGHTS")
        print("=" * 70)

        print(tls_ids)

        if TLS_ID not in tls_ids:

            raise RuntimeError(
                f"TLS '{TLS_ID}' tidak ditemukan di TraCI."
            )

        # ----------------------------------------------------
        # TLS INFORMATION
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("TLS INFORMATION")
        print("=" * 70)

        print(
            "TLS ID:",
            TLS_ID,
        )

        print(
            "Program:",
            traci.trafficlight.getProgram(
                TLS_ID
            ),
        )

        print(
            "Phase:",
            traci.trafficlight.getPhase(
                TLS_ID
            ),
        )

        print(
            "Phase Duration:",
            traci.trafficlight.getPhaseDuration(
                TLS_ID
            ),
        )

        print(
            "State:",
            traci.trafficlight.getRedYellowGreenState(
                TLS_ID
            ),
        )

        # ----------------------------------------------------
        # RUN
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("TLS STATE OVER TIME")
        print("=" * 70)

        last_state = None

        for _ in range(60):

            traci.simulationStep()

            current_time = (
                traci.simulation.getTime()
            )

            phase = (
                traci.trafficlight.getPhase(
                    TLS_ID
                )
            )

            state = (
                traci.trafficlight
                .getRedYellowGreenState(
                    TLS_ID
                )
            )

            duration = (
                traci.trafficlight
                .getPhaseDuration(
                    TLS_ID
                )
            )

            if state != last_state:

                print(
                    f"[t={current_time:>5.0f}s] "
                    f"phase={phase:<3} "
                    f"duration={duration:<5.1f} "
                    f"state={state}"
                )

                last_state = state

        print()
        print("=" * 70)
        print("SELESAI")
        print("=" * 70)

    finally:

        traci.close()


if __name__ == "__main__":
    main()