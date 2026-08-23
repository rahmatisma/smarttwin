from __future__ import annotations

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Any


# ============================================================
# PATH
# ============================================================

SIMULATION_ROOT = Path(__file__).resolve().parent

PROJECT_ROOT = SIMULATION_ROOT.parent

BACKEND_ROOT = PROJECT_ROOT / "backend"

ENV_FILE = BACKEND_ROOT / ".env"


# ============================================================
# PYTHON PATH
# ============================================================

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ============================================================
# ENVIRONMENT
# ============================================================

if not ENV_FILE.exists():
    raise RuntimeError(
        "\n"
        "============================================================\n"
        "BACKEND .env TIDAK DITEMUKAN\n"
        "============================================================\n"
        f"Expected:\n{ENV_FILE}\n"
    )


from dotenv import load_dotenv


load_dotenv(
    dotenv_path=ENV_FILE,
    override=False,
)


# ============================================================
# SUMO
# ============================================================

def find_sumo() -> tuple[Path, Path]:
    """
    Mencari SUMO executable.

    Prioritas:

    1. simulation/.venv/Scripts/sumo.exe
    2. SUMO_HOME/bin/sumo.exe
    3. PATH
    """

    # --------------------------------------------------------
    # 1. SUMO dari simulation virtual environment
    # --------------------------------------------------------

    candidates = [
        SIMULATION_ROOT
        / ".venv"
        / "Scripts"
        / "sumo.exe",

        SIMULATION_ROOT
        / ".venv"
        / "Scripts"
        / "sumo",
    ]

    for candidate in candidates:

        if candidate.exists():

            sumo_executable = candidate

            tools_dir = (
                SIMULATION_ROOT
                / ".venv"
                / "Lib"
                / "site-packages"
                / "sumolib"
            )

            # biasanya TraCI tersedia melalui SUMO_HOME/tools.
            # Jika tidak ada, cari tools dari package.
            if not tools_dir.exists():
                tools_dir = (
                    SIMULATION_ROOT
                    / ".venv"
                    / "Lib"
                    / "site-packages"
                )

            return (
                sumo_executable,
                tools_dir,
            )

    # --------------------------------------------------------
    # 2. SUMO_HOME
    # --------------------------------------------------------

    sumo_home = os.environ.get(
        "SUMO_HOME"
    )

    if sumo_home:

        home = Path(sumo_home)

        executable = (
            home
            / "bin"
            / "sumo.exe"
        )

        tools = (
            home
            / "tools"
        )

        if executable.exists():

            return (
                executable,
                tools,
            )

    # --------------------------------------------------------
    # 3. PATH
    # --------------------------------------------------------

    try:

        result = subprocess.run(
            [
                "where",
                "sumo",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        first_line = (
            result.stdout
            .strip()
            .splitlines()[0]
        )

        executable = Path(
            first_line
        )

        # Kalau ditemukan dari PATH,
        # coba cari SUMO_HOME dari parent.
        possible_home = executable.parent.parent

        possible_tools = (
            possible_home
            / "tools"
        )

        return (
            executable,
            possible_tools,
        )

    except Exception:

        pass

    raise RuntimeError(
        "\n"
        "============================================================\n"
        "SUMO TIDAK DITEMUKAN\n"
        "============================================================\n"
        "\n"
        "Sudah dicoba:\n"
        f"- {SIMULATION_ROOT / '.venv' / 'Scripts' / 'sumo.exe'}\n"
        "- SUMO_HOME\n"
        "- PATH\n"
    )


SUMO_BINARY, SUMO_TOOLS = find_sumo()


# ============================================================
# TRAFFIC / BACKEND IMPORT
# ============================================================

from app.pipeline.traffic_state_builder import (
    TrafficStateBuilder,
    TrafficStateBuilderConfig,
)

from app.services.simulation_result_writer import (
    SimulationResultWriter,
)


# ============================================================
# TRACI
# ============================================================

# SUMO_HOME biasanya dibutuhkan oleh traci.
#
# Karena SUMO kita berasal dari venv, cari lokasi
# package traci secara langsung.

try:

    import traci

except ModuleNotFoundError:

    # --------------------------------------------------------
    # fallback: coba tools path
    # --------------------------------------------------------

    if SUMO_TOOLS.exists():

        if str(SUMO_TOOLS) not in sys.path:

            sys.path.insert(
                0,
                str(SUMO_TOOLS),
            )

    import traci


# ============================================================
# CONFIG
# ============================================================

INTERSECTION_ID = "simpang4-pingit"

SUMO_CONFIG = (
    SIMULATION_ROOT
    / "network"
    / "simpang4_pingit.sumocfg"
)

TLS_ID = "SIMPANG_CENTER"

SIMULATION_STEP_LIMIT = 300


# ============================================================
# HEADER
# ============================================================

def print_header(
    title: str,
) -> None:

    print()

    print("=" * 70)

    print(title)

    print("=" * 70)


# ============================================================
# ENVIRONMENT INFO
# ============================================================

def print_environment() -> None:

    print_header(
        "ENVIRONMENT"
    )

    print(
        f"Simulation root : "
        f"{SIMULATION_ROOT}"
    )

    print(
        f"Backend root    : "
        f"{BACKEND_ROOT}"
    )

    print(
        f".env            : "
        f"{ENV_FILE}"
    )

    print(
        f"SUMO binary     : "
        f"{SUMO_BINARY}"
    )

    print(
        f"SUMO tools      : "
        f"{SUMO_TOOLS}"
    )

    print(
        "SUPABASE_URL    : OK"
        if os.getenv("SUPABASE_URL")
        else "SUPABASE_URL    : MISSING"
    )

    print(
        "SUPABASE_KEY    : OK"
        if os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY"
        )
        else "SUPABASE_KEY    : MISSING"
    )

    print(
        "HF_TOKEN        : OK"
        if os.getenv("HF_TOKEN")
        else "HF_TOKEN        : MISSING"
    )

    print(
        "HF_REPO_ID      : OK"
        if os.getenv("HF_REPO_ID")
        else "HF_REPO_ID      : MISSING"
    )


# ============================================================
# TRAFFIC STATE
# ============================================================

def load_traffic_state():

    print_header(
        "LOADING TRAFFIC STATE"
    )

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            windowSeconds=5
        )
    )

    state = (
        builder
        .build_latest_state_for_intersection(
            intersection_id=INTERSECTION_ID,
            save=False,
        )
    )

    if state is None:

        raise RuntimeError(
            "TrafficState tidak ditemukan "
            "di Supabase."
        )

    print()

    print(
        "TrafficState berhasil dimuat."
    )

    builder.print_state(
        state
    )

    return state


# ============================================================
# PHASE PLAN
# ============================================================

def create_phase_plan(
    state,
) -> dict[str, Any]:

    print_header(
        "CREATING PHASE PLAN"
    )

    north = next(
        x for x in state.approaches
        if x.approach == "north"
    )

    south = next(
        x for x in state.approaches
        if x.approach == "south"
    )

    east = next(
        x for x in state.approaches
        if x.approach == "east"
    )

    west = next(
        x for x in state.approaches
        if x.approach == "west"
    )

    queue_north = north.queueLengthVeh
    queue_south = south.queueLengthVeh
    queue_east = east.queueLengthVeh
    queue_west = west.queueLengthVeh

    # --------------------------------------------------------
    # Adaptive rule-based TLS (4 Phases)
    # --------------------------------------------------------

    queues = {
        0: ("South", queue_south),
        1: ("East", queue_east),
        2: ("North", queue_north),
        3: ("West", queue_west),
    }

    best_phase = max(queues.items(), key=lambda x: x[1][1])[0]
    best_name, best_queue = queues[best_phase]

    phase = best_phase
    duration = min(60, max(20, 30 + best_queue))
    reason = f"{best_name} memiliki queue tertinggi ({best_queue})."

    plan = {
        "phase": phase,
        "duration": float(duration),
        "reason": reason,
        "queueNorth": queue_north,
        "queueSouth": queue_south,
        "queueEast": queue_east,
        "queueWest": queue_west,
    }

    print(
        f"Selected phase : "
        f"{phase}"
    )

    print(
        f"Duration        : "
        f"{duration:.0f}s"
    )

    print(
        f"Reason          : "
        f"{reason}"
    )

    print()

    print(f"Queue South     : {queue_south}")
    print(f"Queue East      : {queue_east}")
    print(f"Queue North     : {queue_north}")
    print(f"Queue West      : {queue_west}")

    return plan


# ============================================================
# START SUMO
# ============================================================

def start_sumo():

    print_header(
        "STARTING SUMO"
    )

    if not SUMO_CONFIG.exists():

        raise FileNotFoundError(
            f"SUMO config tidak ditemukan:\n"
            f"{SUMO_CONFIG}"
        )

    command = [
        str(SUMO_BINARY),
        "-c",
        str(SUMO_CONFIG),
        "--start",
    ]

    print(
        "Command:",
        " ".join(command),
    )

    traci.start(
        command
    )

    print(
        "SUMO berhasil dimulai."
    )


# ============================================================
# APPLY TLS
# ============================================================

def apply_tls(
    plan: dict[str, Any],
) -> None:

    print_header(
        "TLS PHASE APPLIED"
    )

    traci.trafficlight.setPhase(
        TLS_ID,
        plan["phase"],
    )

    traci.trafficlight.setPhaseDuration(
        TLS_ID,
        plan["duration"],
    )

    print(
        f"TLS      : {TLS_ID}"
    )

    print(
        f"Phase    : "
        f"{plan['phase']}"
    )

    print(
        f"Duration : "
        f"{plan['duration']:.0f}s"
    )

    print(
        f"Reason   : "
        f"{plan['reason']}"
    )


# ============================================================
# RUN SIMULATION
# ============================================================

def run_simulation():

    print_header(
        "SIMULATION RUNNING"
    )

    steps = 0

    arrived = 0

    departed = 0

    while steps < SIMULATION_STEP_LIMIT:

        try:

            traci.simulationStep()

        except Exception as exc:

            print(
                "SUMO step error:",
                exc,
            )

            break

        steps += 1

        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        try:

            arrived = (
                traci.simulation
                .getArrivedNumber()
            )

            departed = (
                traci.simulation
                .getDepartedNumber()
            )

            active = (
                traci.vehicle
                .getIDCount()
            )

            expected = (
                traci.simulation
                .getMinExpectedNumber()
            )

        except Exception:

            active = 0

            expected = 0

        if (
            steps % 10 == 0
            or expected == 0
        ):

            print(
                f"[t={steps:4d}s] "
                f"active={active:<4} "
                f"expected={expected:<4}"
            )

        if expected == 0:

            break

    return {
        "steps": steps,
        "active": (
            traci.vehicle
            .getIDCount()
        ),
        "arrived": arrived,
        "departed": departed,
    }


# ============================================================
# GET TLS RESULT
# ============================================================

def get_tls_result(
    plan: dict[str, Any],
) -> dict[str, Any]:

    phase = traci.trafficlight.getPhase(
        TLS_ID
    )

    state = traci.trafficlight.getRedYellowGreenState(
        TLS_ID
    )

    return {
        "phase": phase,
        "duration": plan["duration"],
        "state": state,
    }


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(
    traffic_state,
    phase_plan,
    simulation_metrics,
    tls_result,
):

    print_header(
        "WRITING SIMULATION RESULT"
    )

    writer = SimulationResultWriter()

    result = writer.save_result(
        traffic_state=traffic_state,
        phase_plan=phase_plan,
        simulation_metrics={
            **simulation_metrics,
            "tlsPhase": tls_result["phase"],
            "tlsDuration": tls_result["duration"],
            "tlsState": tls_result["state"],
        },
    )

    print(
        "Simulation result berhasil "
        "disimpan ke Supabase."
    )

    print(
        f"Simulation ID : "
        f"{result}"
    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print("=" * 70)

    print(
        "SMARTTWIN ADAPTIVE TLS SIMULATION"
    )

    print("=" * 70)

    print_environment()

    # --------------------------------------------------------
    # 1. Traffic State dari Supabase
    # --------------------------------------------------------

    traffic_state = (
        load_traffic_state()
    )

    # --------------------------------------------------------
    # 2. Phase plan
    # --------------------------------------------------------

    phase_plan = (
        create_phase_plan(
            traffic_state
        )
    )

    # --------------------------------------------------------
    # 3. Start SUMO
    # --------------------------------------------------------

    start_sumo()

    try:

        # ----------------------------------------------------
        # 4. Apply TLS
        # ----------------------------------------------------

        apply_tls(
            phase_plan
        )

        # ----------------------------------------------------
        # 5. Run simulation
        # ----------------------------------------------------

        simulation_metrics = (
            run_simulation()
        )

        # ----------------------------------------------------
        # 6. TLS result
        # ----------------------------------------------------

        tls_result = (
            get_tls_result(
                phase_plan
            )
        )

        # ----------------------------------------------------
        # 7. Print result
        # ----------------------------------------------------

        print_header(
            "SIMULATION METRICS"
        )

        print(
            f"Simulation steps : "
            f"{simulation_metrics['steps']}"
        )

        print(
            f"Active vehicles  : "
            f"{simulation_metrics['active']}"
        )

        print(
            f"Arrived vehicles : "
            f"{simulation_metrics['arrived']}"
        )

        print(
            f"Departed         : "
            f"{simulation_metrics['departed']}"
        )

        print(
            f"TLS phase        : "
            f"{tls_result['phase']}"
        )

        print(
            f"TLS duration     : "
            f"{tls_result['duration']}"
        )

        print(
            f"TLS state        : "
            f"{tls_result['state']}"
        )

        # ----------------------------------------------------
        # 8. Save Supabase
        # ----------------------------------------------------

        save_result(
            traffic_state=traffic_state,
            phase_plan=phase_plan,
            simulation_metrics=simulation_metrics,
            tls_result=tls_result,
        )

    finally:

        try:

            traci.close()

            print()

            print(
                "SUMO connection ditutup."
            )

        except Exception:

            pass

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print_header(
        "SMARTTWIN TLS SIMULATION SELESAI"
    )

    print(
        "TrafficState"
    )

    print(
        "     ↓"
    )

    print(
        "Phase Plan"
    )

    print(
        "     ↓"
    )

    print(
        "TLS Controller"
    )

    print(
        "     ↓"
    )

    print(
        "SUMO"
    )

    print(
        "     ↓"
    )

    print(
        "Simulation Metrics"
    )

    print(
        "     ↓"
    )

    print(
        "Supabase"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()