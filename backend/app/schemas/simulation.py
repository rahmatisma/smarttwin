from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

# ============================================================
# SUMO ENVIRONMENT
# ============================================================

SUMO_HOME = os.environ.get("SUMO_HOME")

if not SUMO_HOME:
    print("ERROR: SUMO_HOME belum diset.")
    sys.exit(1)

SUMO_TOOLS = Path(SUMO_HOME) / "tools"

if str(SUMO_TOOLS) not in sys.path:
    sys.path.insert(0, str(SUMO_TOOLS))

import sumolib
import traci


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
# HELPERS
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


def vehicle_count_from_approach(approach_state) -> dict[str, int]:

    volume = int(approach_state.volume)

    if volume <= 0:
        return {
            "motorcycle": 0,
            "car": 0,
            "bus": 0,
            "truck": 0,
        }

    # TrafficState saat ini menyimpan total volume,
    # bukan breakdown tipe kendaraan.
    #
    # Untuk simulasi awal:
    # 60% motor
    # 30% mobil
    # 5% bus
    # 5% truck

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
# SUMO VEHICLE TYPES
# ============================================================

def create_vehicle_types() -> None:

    for config in VEHICLE_TYPES.values():

        try:
            traci.vehicletype.getIDList().index(config["id"])
            continue
        except ValueError:
            pass

        traci.vehicletype.copy(
            "DEFAULT_VEHTYPE",
            config["id"],
        )

        traci.vehicletype.setVehicleClass(
            config["id"],
            config["vclass"],
        )

        traci.vehicletype.setLength(
            config["id"],
            config["length"],
        )

        traci.vehicletype.setWidth(
            config["id"],
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

    except traci.TraCIException:

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

    binary = sumolib.checkBinary(
        "sumo-gui" if gui else "sumo"
    )

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

    print()
    print("=" * 70)
    print("SMARTTWIN SUMO SIMULATION")
    print("=" * 70)
    print(f"Network  : {net_file}")
    print(f"Duration : {duration} seconds")
    print(f"GUI      : {gui}")
    print()

    traci.start(command)

    try:

        create_vehicle_types()

        approaches = traffic_state.get(
            "approaches",
            [],
        )

        # ----------------------------------------------------
        # TARGET VEHICLES
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
            f"  ID         : "
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
        delays = defaultdict(list)

        spawned = 0

        # ----------------------------------------------------
        # SIMULATION LOOP
        # ----------------------------------------------------

        for second in range(duration):

            # -----------------------------------------------
            # Inject vehicles progressively.
            #
            # Volume adalah jumlah kendaraan dalam TrafficState.
            # Kita distribusikan sepanjang durasi state.
            # -----------------------------------------------

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

            # -----------------------------------------------
            # STEP SUMO
            # -----------------------------------------------

            traci.simulationStep()

            # -----------------------------------------------
            # DEPARTED
            # -----------------------------------------------

            for vehicle_id in (
                traci.simulation.getDepartedIDList()
            ):

                try:
                    approach = vehicle_id.split("_")[1]
                except IndexError:
                    approach = "unknown"

                departed[approach] += 1

            # -----------------------------------------------
            # ARRIVED
            # -----------------------------------------------

            for vehicle_id in (
                traci.simulation.getArrivedIDList()
            ):

                try:
                    approach = vehicle_id.split("_")[1]
                except IndexError:
                    approach = "unknown"

                arrived[approach] += 1

            # -----------------------------------------------
            # CURRENT VEHICLES
            # -----------------------------------------------

            for vehicle_id in traci.vehicle.getIDList():

                try:
                    approach = vehicle_id.split("_")[1]
                except IndexError:
                    continue

                waiting = traci.vehicle.getAccumulatedWaitingTime(
                    vehicle_id
                )

                waiting_times[approach].append(
                    waiting
                )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        total_waiting = []

        for values in waiting_times.values():
            total_waiting.extend(values)

        average_waiting = (
            sum(total_waiting) / len(total_waiting)
            if total_waiting
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
            "trafficStateId": traffic_state.get(
                "trafficStateId"
            ),
            "intersectionId": traffic_state.get(
                "intersectionId"
            ),
            "durationSeconds": duration,
            "spawnedVehicles": spawned,
            "departedVehicles": total_departed,
            "arrivedVehicles": total_arrived,
            "activeVehicles": active,
            "averageWaitingTimeSeconds": round(
                average_waiting,
                2,
            ),
            "departedByApproach": dict(
                departed
            ),
            "arrivedByApproach": dict(
                arrived
            ),
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