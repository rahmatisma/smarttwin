from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any


# ============================================================
# SUMO IMPORT
# ============================================================

try:
    import traci
except ImportError:
    print(
        "ERROR: traci tidak ditemukan.",
        file=sys.stderr,
    )
    print(
        "Install dengan:",
        file=sys.stderr,
    )
    print(
        "pip install traci",
        file=sys.stderr,
    )
    raise


# ============================================================
# DEFAULT CONFIG
# ============================================================

DEFAULT_DURATION = 60
DEFAULT_GUI_DELAY_MS = 100


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "SmartTwin SUMO Traffic Simulation Runner"
        )
    )

    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="JSON TrafficState input.",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="JSON hasil simulasi.",
    )

    parser.add_argument(
        "--net-file",
        type=str,
        required=True,
        help="SUMO network file.",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_DURATION,
        help="Durasi simulasi dalam detik.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed.",
    )

    parser.add_argument(
        "--gui",
        action="store_true",
        help="Jalankan SUMO-GUI.",
    )

    parser.add_argument(
        "--gui-delay",
        type=int,
        default=DEFAULT_GUI_DELAY_MS,
        help="Delay GUI dalam milidetik.",
    )

    return parser.parse_args()


# ============================================================
# INPUT
# ============================================================

def load_input(
    input_path: str | None,
) -> dict[str, Any]:

    if input_path is None:

        return {
            "trafficStateId": None,
            "intersectionId": "simpang4_pingit",
            "windowStart": None,
            "windowEnd": None,
            "approaches": [
                {
                    "approach": "north",
                    "volume": 20,
                    "carCount": 10,
                    "motorcycleCount": 8,
                    "busCount": 1,
                    "truckCount": 1,
                    "queueLengthVeh": 5,
                    "queueLengthMEst": 25.0,
                    "densityIndex": 0.4,
                    "avgSpeedKmh": None,
                },
                {
                    "approach": "south",
                    "volume": 15,
                    "carCount": 8,
                    "motorcycleCount": 6,
                    "busCount": 1,
                    "truckCount": 0,
                    "queueLengthVeh": 3,
                    "queueLengthMEst": 15.0,
                    "densityIndex": 0.3,
                    "avgSpeedKmh": None,
                },
                {
                    "approach": "east",
                    "volume": 18,
                    "carCount": 9,
                    "motorcycleCount": 7,
                    "busCount": 1,
                    "truckCount": 1,
                    "queueLengthVeh": 4,
                    "queueLengthMEst": 20.0,
                    "densityIndex": 0.35,
                    "avgSpeedKmh": None,
                },
                {
                    "approach": "west",
                    "volume": 12,
                    "carCount": 6,
                    "motorcycleCount": 5,
                    "busCount": 1,
                    "truckCount": 0,
                    "queueLengthVeh": 2,
                    "queueLengthMEst": 10.0,
                    "densityIndex": 0.2,
                    "avgSpeedKmh": None,
                },
            ],
        }

    path = Path(input_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Input JSON tidak ditemukan: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# SUMO START
# ============================================================

def start_sumo(
    net_file: Path,
    gui: bool,
    seed: int | None,
) -> None:

    sumo_binary = (
        "sumo-gui"
        if gui
        else "sumo"
    )

    command = [
        sumo_binary,
        "--net-file",
        str(net_file),
        "--step-length",
        "1",
        "--begin",
        "0",
        "--no-step-log",
        "true",
    ]

    if gui:
        command.extend(
            [
                "--start",
                "true",
            ]
        )

    if seed is not None:
        command.extend(
            [
                "--seed",
                str(seed),
            ]
        )

    print()
    print("=" * 60)
    print("SMARTTWIN SUMO")
    print("=" * 60)
    print(
        f"Mode       : "
        f"{'SUMO-GUI' if gui else 'SUMO'}"
    )
    print(
        f"Network    : {net_file}"
    )
    print(
        f"Seed       : {seed}"
    )
    print("=" * 60)
    print()

    traci.start(
        command
    )


# ============================================================
# ROUTE / VEHICLE GENERATION
# ============================================================

def get_edges() -> list[str]:

    edges = traci.edge.getIDList()

    return [
        edge
        for edge in edges
        if not edge.startswith(":")
    ]


def generate_traffic(
    traffic_state: dict[str, Any],
) -> int:

    edges = get_edges()

    if not edges:
        print(
            "WARNING: Tidak ada edge yang dapat digunakan."
        )
        return 0

    total_volume = 0

    for approach in traffic_state.get(
        "approaches",
        [],
    ):

        total_volume += int(
            approach.get(
                "volume",
                0,
            )
        )

    if total_volume <= 0:
        total_volume = 20

    vehicle_count = max(
        1,
        min(
            total_volume,
            100,
        ),
    )

    generated = 0

    for index in range(
        vehicle_count
    ):

        edge = random.choice(
            edges
        )

        vehicle_id = (
            f"smarttwin_{index}"
        )

        try:

            traci.vehicle.add(
                vehID=vehicle_id,
                routeID="",
                typeID="DEFAULT_VEHTYPE",
                depart=traci.constants.DEPART_NOW,
            )

            generated += 1

        except Exception:
            continue

    return generated


# ============================================================
# SIMULATION
# ============================================================

def run_simulation(
    traffic_state: dict[str, Any],
    duration: int,
    gui_delay_ms: int,
) -> dict[str, Any]:

    start_time = time.perf_counter()

    generated_vehicles = 0

    arrived_total = 0
    departed_total = 0

    max_queue = 0
    total_waiting = 0.0

    for step in range(
        duration
    ):

        if step == 0:

            generated_vehicles = (
                generate_traffic(
                    traffic_state
                )
            )

        traci.simulationStep()

        departed_total = (
            traci.simulation.getDepartedNumber()
        )

        arrived_total = (
            traci.simulation.getArrivedNumber()
        )

        vehicle_ids = (
            traci.vehicle.getIDList()
        )

        current_queue = 0
        current_waiting = 0.0

        for vehicle_id in vehicle_ids:

            try:

                speed = (
                    traci.vehicle.getSpeed(
                        vehicle_id
                    )
                )

                waiting = (
                    traci.vehicle.getAccumulatedWaitingTime(
                        vehicle_id
                    )
                )

                if speed < 0.1:
                    current_queue += 1

                current_waiting += waiting

            except Exception:
                continue

        max_queue = max(
            max_queue,
            current_queue,
        )

        total_waiting = max(
            total_waiting,
            current_waiting,
        )

        if gui_delay_ms > 0:
            time.sleep(
                gui_delay_ms / 1000
            )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    return {
        "trafficStateId": traffic_state.get(
            "trafficStateId"
        ),
        "intersectionId": traffic_state.get(
            "intersectionId"
        ),
        "durationSeconds": duration,
        "generatedVehicles": generated_vehicles,
        "departedVehicles": departed_total,
        "arrivedVehicles": arrived_total,
        "maxQueueVehicles": max_queue,
        "totalWaitingSeconds": round(
            total_waiting,
            2,
        ),
        "simulationRuntimeSeconds": round(
            elapsed,
            3,
        ),
        "status": "completed",
    }


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    args = parse_args()

    if args.duration <= 0:
        raise ValueError(
            "duration harus lebih besar dari 0."
        )

    net_file = Path(
        args.net_file
    ).resolve()

    if not net_file.exists():
        raise FileNotFoundError(
            f"Network SUMO tidak ditemukan: "
            f"{net_file}"
        )

    traffic_state = load_input(
        args.input
    )

    if args.seed is not None:
        random.seed(
            args.seed
        )

    try:

        start_sumo(
            net_file=net_file,
            gui=args.gui,
            seed=args.seed,
        )

        result = run_simulation(
            traffic_state=traffic_state,
            duration=args.duration,
            gui_delay_ms=args.gui_delay,
        )

    finally:

        try:
            traci.close()
        except Exception:
            pass

    print()
    print("=" * 60)
    print("SIMULATION RESULT")
    print("=" * 60)
    print(
        json.dumps(
            result,
            indent=2,
        )
    )
    print("=" * 60)

    if args.output is not None:

        output_path = Path(
            args.output
        ).resolve()

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            json.dumps(
                result,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"\nResult disimpan ke: "
            f"{output_path}"
        )


if __name__ == "__main__":
    main()