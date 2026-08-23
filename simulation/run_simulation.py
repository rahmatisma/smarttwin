from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path


# ============================================================
# PATH
# ============================================================

SIMULATION_ROOT = Path(__file__).resolve().parent


# ============================================================
# SUMO ENVIRONMENT
# ============================================================

def setup_sumo() -> None:
    """
    Setup SUMO dari virtual environment simulation.

    SUMO Python package dan executable diasumsikan berada
    di simulation/.venv.
    """

    venv_root = SIMULATION_ROOT / ".venv"

    scripts_dir = venv_root / "Scripts"
    site_packages = venv_root / "Lib" / "site-packages"

    # --------------------------------------------------------
    # Python SUMO tools
    # --------------------------------------------------------

    sumo_tools_candidates = [
        site_packages / "sumo" / "tools",
        site_packages / "sumo" / "share" / "sumo" / "tools",
        venv_root / "tools",
    ]

    sumo_tools = None

    for candidate in sumo_tools_candidates:
        if candidate.exists():
            sumo_tools = candidate
            break

    if sumo_tools is None:
        raise RuntimeError(
            "SUMO tools tidak ditemukan.\n"
            f"Checked:\n"
            + "\n".join(str(x) for x in sumo_tools_candidates)
        )

    if str(sumo_tools) not in sys.path:
        sys.path.insert(0, str(sumo_tools))

    # --------------------------------------------------------
    # Executable
    # --------------------------------------------------------

    sumo_exe = scripts_dir / "sumo.exe"
    sumo_gui_exe = scripts_dir / "sumo-gui.exe"

    if not sumo_exe.exists():
        found = shutil.which("sumo")

        if not found:
            raise RuntimeError(
                "SUMO executable tidak ditemukan.\n"
                f"Expected: {sumo_exe}"
            )

    # --------------------------------------------------------
    # SUMO_HOME
    #
    # Untuk pip installation, kita arahkan ke package SUMO.
    # Jangan mengasumsikan C:\\Program Files.
    # --------------------------------------------------------

    sumo_package = site_packages / "sumo"

    if sumo_package.exists():
        os.environ["SUMO_HOME"] = str(sumo_package)

    # --------------------------------------------------------
    # Import setelah sys.path siap
    # --------------------------------------------------------

    global sumolib
    global traci

    import sumolib
    import traci


setup_sumo()


# ============================================================
# VEHICLE CONFIGURATION
# ============================================================

VEHICLE_TYPES = {
    "motorcycle": {
        "id": "motorcycle",
        "vclass": "motorcycle",
        "length": 2.2,
        "width": 0.9,
    },
    "car": {
        "id": "car",
        "vclass": "passenger",
        "length": 5.0,
        "width": 1.8,
    },
    "bus": {
        "id": "bus",
        "vclass": "bus",
        "length": 12.0,
        "width": 2.5,
    },
    "truck": {
        "id": "truck",
        "vclass": "truck",
        "length": 10.0,
        "width": 2.5,
    },
}


# ============================================================
# APPROACH -> SUMO EDGE
# ============================================================

EDGE_HULU = {
    "north": "484349908#0",
    "south": "134603786#0",
    "east": "153857851#2",
    "west": "590064461#0",
}

EDGE_MASUK = {
    "north": "484349908#2",
    "south": "134603786#2",
    "east": "153857851#4",
    "west": "590064461#2",
}

EDGE_KELUAR = {
    "north": "201299423#0",
    "south": "153857907#0",
    "east": "590386082#0",
    "west": "25006154#0",
}


# ============================================================
# TURN DISTRIBUTION
# ============================================================

TURN_DISTRIBUTION = {
    "lurus": 0.50,
    "kiri": 0.25,
    "kanan": 0.25,
}


TURN_MAPPING = {
    "north": {
        "lurus": "south",
        "kiri": "east",
        "kanan": "west",
    },
    "south": {
        "lurus": "north",
        "kiri": "west",
        "kanan": "east",
    },
    "east": {
        "lurus": "west",
        "kiri": "north",
        "kanan": "south",
    },
    "west": {
        "lurus": "east",
        "kiri": "south",
        "kanan": "north",
    },
}


# ============================================================
# ROUTE
# ============================================================

def build_route(
    approach: str,
    rng: random.Random,
) -> list[str]:

    turn = rng.choices(
        list(TURN_DISTRIBUTION.keys()),
        weights=list(TURN_DISTRIBUTION.values()),
        k=1,
    )[0]

    destination = TURN_MAPPING[approach][turn]

    return [
        EDGE_HULU[approach],
        EDGE_MASUK[approach],
        EDGE_KELUAR[destination],
    ]


# ============================================================
# VEHICLE COUNT
# ============================================================

def vehicle_count_from_approach(
    approach_state: dict,
) -> dict[str, int]:

    volume = int(approach_state.get("volume", 0))

    if volume <= 0:
        return {
            "motorcycle": 0,
            "car": 0,
            "bus": 0,
            "truck": 0,
        }

    # --------------------------------------------------------
    # Temporary distribution.
    #
    # Nanti bisa diganti langsung dengan:
    # motorcycleCount
    # carCount
    # busCount
    # truckCount
    #
    # jika schema TrafficState sudah menyediakan semuanya.
    # --------------------------------------------------------

    motorcycle = round(volume * 0.60)
    car = round(volume * 0.30)
    bus = round(volume * 0.05)
    truck = volume - motorcycle - car - bus

    return {
        "motorcycle": motorcycle,
        "car": car,
        "bus": bus,
        "truck": truck,
    }


# ============================================================
# CREATE VEHICLE TYPES
# ============================================================

def create_vehicle_types() -> None:

    existing = set(
        traci.vehicletype.getIDList()
    )

    for config in VEHICLE_TYPES.values():

        vehicle_type_id = config["id"]

        if vehicle_type_id in existing:
            continue

        traci.vehicletype.copy(
            "DEFAULT_VEHTYPE",
            vehicle_type_id,
        )

        traci.vehicletype.setVehicleClass(
            vehicle_type_id,
            config["vclass"],
        )

        traci.vehicletype.setLength(
            vehicle_type_id,
            config["length"],
        )

        traci.vehicletype.setWidth(
            vehicle_type_id,
            config["width"],
        )


# ============================================================
# ADD VEHICLE
# ============================================================

def add_vehicle(
    vehicle_id: str,
    vehicle_type: str,
    approach: str,
    rng: random.Random,
) -> bool:

    route_id = f"route_{vehicle_id}"

    edges = build_route(
        approach,
        rng,
    )

    try:

        traci.route.add(
            route_id,
            edges,
        )

        traci.vehicle.add(
            vehID=vehicle_id,
            routeID=route_id,
            typeID=vehicle_type,
            depart="now",
        )

        return True

    except traci.TraCIException as exc:

        print(
            f"[WARNING] vehicle {vehicle_id} gagal dibuat: {exc}"
        )

        return False


# ============================================================
# SIMULATION
# ============================================================

def run_simulation(
    traffic_state: dict,
    net_file: Path,
    duration: int,
    gui: bool,
    gui_delay: int,
    seed: int,
) -> dict:

    rng = random.Random(seed)

    # --------------------------------------------------------
    # SUMO binary
    # --------------------------------------------------------

    if gui:
        binary = shutil.which("sumo-gui")

        if not binary:
            binary = (
                SIMULATION_ROOT
                / ".venv"
                / "Scripts"
                / "sumo-gui.exe"
            )

    else:
        binary = shutil.which("sumo")

        if not binary:
            binary = (
                SIMULATION_ROOT
                / ".venv"
                / "Scripts"
                / "sumo.exe"
            )

    binary = str(binary)

    if not Path(binary).exists():
        raise RuntimeError(
            f"SUMO binary tidak ditemukan: {binary}"
        )

    # --------------------------------------------------------
    # COMMAND
    # --------------------------------------------------------

    command = [
        binary,
        "-n",
        str(net_file),
        "--step-length",
        "1",
        "--no-step-log",
        "--no-warnings",
    ]

    if gui:

        command.extend(
            [
                "--delay",
                str(gui_delay),
            ]
        )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SMARTTWIN SUMO SIMULATION")
    print("=" * 70)
    print(f"Network  : {net_file}")
    print(f"Duration : {duration} seconds")
    print(f"GUI      : {gui}")
    print(f"SUMO     : {binary}")
    print()

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    traci.start(command)

    try:

        create_vehicle_types()

        approaches = traffic_state.get(
            "approaches",
            [],
        )

        # ----------------------------------------------------
        # TARGET
        # ----------------------------------------------------

        target = {}

        for approach_state in approaches:

            approach = approach_state["approach"]

            counts = vehicle_count_from_approach(
                approach_state
            )

            target[approach] = counts

        print("TrafficState:")
        print(
            f"  ID          : "
            f"{traffic_state.get('trafficStateId', '-')}"
        )

        print(
            f"  Intersection: "
            f"{traffic_state.get('intersectionId', '-')}"
        )

        print()

        for approach, counts in target.items():

            print(
                f"  {approach:<7} "
                f"motor={counts['motorcycle']:<4} "
                f"car={counts['car']:<4} "
                f"bus={counts['bus']:<4} "
                f"truck={counts['truck']:<4}"
            )

        print()

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        departed = defaultdict(int)
        arrived = defaultdict(int)

        waiting_times = defaultdict(list)

        spawned = 0

        # ----------------------------------------------------
        # SIMULATION LOOP
        # ----------------------------------------------------

        for second in range(duration):

            # ------------------------------------------------
            # Inject vehicles
            # ------------------------------------------------

            for approach, counts in target.items():

                for vehicle_type, total in counts.items():

                    if total <= 0:
                        continue

                    interval = max(
                        1,
                        duration // total,
                    )

                    if second % interval != 0:
                        continue

                    index = second // interval

                    if index >= total:
                        continue

                    vehicle_id = (
                        f"{vehicle_type}_"
                        f"{approach}_"
                        f"{second}_"
                        f"{index}"
                    )

                    success = add_vehicle(
                        vehicle_id=vehicle_id,
                        vehicle_type=vehicle_type,
                        approach=approach,
                        rng=rng,
                    )

                    if success:
                        spawned += 1

            # ------------------------------------------------
            # STEP
            # ------------------------------------------------

            traci.simulationStep()

            # ------------------------------------------------
            # DEPARTED
            # ------------------------------------------------

            for vehicle_id in (
                traci.simulation.getDepartedIDList()
            ):

                parts = vehicle_id.split("_")

                approach = (
                    parts[1]
                    if len(parts) > 1
                    else "unknown"
                )

                departed[approach] += 1

            # ------------------------------------------------
            # ARRIVED
            # ------------------------------------------------

            for vehicle_id in (
                traci.simulation.getArrivedIDList()
            ):

                parts = vehicle_id.split("_")

                approach = (
                    parts[1]
                    if len(parts) > 1
                    else "unknown"
                )

                arrived[approach] += 1

            # ------------------------------------------------
            # WAITING
            # ------------------------------------------------

            for vehicle_id in traci.vehicle.getIDList():

                parts = vehicle_id.split("_")

                if len(parts) <= 1:
                    continue

                approach = parts[1]

                waiting = (
                    traci.vehicle
                    .getAccumulatedWaitingTime(
                        vehicle_id
                    )
                )

                waiting_times[approach].append(
                    waiting
                )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        all_waiting = []

        for values in waiting_times.values():
            all_waiting.extend(values)

        average_waiting = (
            sum(all_waiting) / len(all_waiting)
            if all_waiting
            else 0.0
        )

        total_departed = sum(
            departed.values()
        )

        total_arrived = sum(
            arrived.values()
        )

        active = traci.vehicle.getIDCount()

        result = {

            "trafficStateId":
                traffic_state.get(
                    "trafficStateId"
                ),

            "intersectionId":
                traffic_state.get(
                    "intersectionId"
                ),

            "durationSeconds":
                duration,

            "spawnedVehicles":
                spawned,

            "departedVehicles":
                total_departed,

            "arrivedVehicles":
                total_arrived,

            "activeVehicles":
                active,

            "averageWaitingTimeSeconds":
                round(
                    average_waiting,
                    2,
                ),

            "departedByApproach":
                dict(departed),

            "arrivedByApproach":
                dict(arrived),
        }

        return result

    finally:

        traci.close()


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="SmartTwin SUMO TrafficState Runner"
    )

    parser.add_argument(
        "--input",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    parser.add_argument(
        "--net-file",
        required=True,
    )

    parser.add_argument(
        "--duration",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--gui",
        action="store_true",
    )

    parser.add_argument(
        "--gui-delay",
        type=int,
        default=100,
    )

    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)
    net_file = Path(args.net_file)

    if not input_file.exists():
        raise RuntimeError(
            f"Input TrafficState tidak ditemukan: {input_file}"
        )

    if not net_file.exists():
        raise RuntimeError(
            f"Network SUMO tidak ditemukan: {net_file}"
        )

    traffic_state = json.loads(
        input_file.read_text(
            encoding="utf-8"
        )
    )

    result = run_simulation(
        traffic_state=traffic_state,
        net_file=net_file,
        duration=args.duration,
        gui=args.gui,
        gui_delay=args.gui_delay,
        seed=args.seed,
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print("SIMULATION SELESAI")
    print("=" * 70)

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()