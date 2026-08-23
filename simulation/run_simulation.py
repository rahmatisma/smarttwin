from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sumolib
import traci
from dotenv import load_dotenv


# ============================================================
# PATH CONFIGURATION
# ============================================================

SIMULATION_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SIMULATION_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"

DEFAULT_NET_FILE = (
    SIMULATION_ROOT
    / "network"
    / "simpang4_pingit.net.xml.gz"
)

DEFAULT_RESULT_FILE = (
    SIMULATION_ROOT
    / "simulation_result.json"
)

SUMO_HOME = (
    SIMULATION_ROOT
    / ".venv"
    / "Lib"
    / "site-packages"
    / "sumo"
)


# ============================================================
# PYTHON PATH
# ============================================================

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")


# ============================================================
# TRAFFIC STATE
# ============================================================

APPROACHES = (
    "north",
    "south",
    "east",
    "west",
)


@dataclass
class ApproachTraffic:
    approach: str
    volume: int
    carCount: int
    motorcycleCount: int
    busCount: int
    truckCount: int
    queueLengthVeh: int
    queueLengthMEst: float
    densityIndex: float


@dataclass
class TrafficStateData:
    trafficStateId: int
    intersectionId: str
    windowStart: str
    windowEnd: str
    source: str
    approaches: dict[str, ApproachTraffic]


# ============================================================
# SUMO PATH
# ============================================================

def get_sumo_binary(gui: bool) -> str:
    if gui:
        binary = SUMO_HOME / "bin" / "sumo-gui.exe"
    else:
        binary = SUMO_HOME / "bin" / "sumo.exe"

    if not binary.exists():
        raise RuntimeError(
            f"SUMO binary tidak ditemukan:\n{binary}"
        )

    return str(binary)


# ============================================================
# LOAD TRAFFIC STATE FROM SUPABASE
# ============================================================

def load_latest_traffic_state(
    intersection_id: str | None = None,
) -> TrafficStateData:

    from app.pipeline.traffic_state_builder import (
        TrafficStateBuilder,
        TrafficStateBuilderConfig,
    )

    builder = TrafficStateBuilder(
        TrafficStateBuilderConfig(
            windowSeconds=5
        )
    )

    # --------------------------------------------------------
    # BUILD TERBARU DARI SUPABASE
    # --------------------------------------------------------

    if intersection_id:
        built_state = builder.build_latest_state_for_intersection(
            intersection_id,
            save=False,
        )
        states = [built_state] if built_state is not None else []
    else:
        states = builder.build_latest_states(
            limit=1,
            save=False,
        )

    if not states:
        raise RuntimeError(
            "Tidak ada TrafficState yang tersedia dari Supabase."
        )

    state = states[0]

    # --------------------------------------------------------
    # AMBIL ID TRAFFIC STATE
    # --------------------------------------------------------

    from app.services.supabase_client import get_supabase

    supabase = get_supabase()

    query = (
        supabase
        .table("trafficStates")
        .select(
            "id, intersectionId, windowStart, "
            "windowEnd, source"
        )
        .order("id", desc=True)
        .limit(1)
    )

    if intersection_id:
        intersection_result = (
            supabase
            .table("intersections")
            .select("id")
            .eq("intersectionId", intersection_id)
            .limit(1)
            .execute()
        )

        rows = intersection_result.data or []

        if not rows:
            raise RuntimeError(
                f"Intersection '{intersection_id}' tidak ditemukan."
            )

        intersection_row_id = rows[0]["id"]

        query = (
            supabase
            .table("trafficStates")
            .select(
                "id, intersectionId, windowStart, "
                "windowEnd, source"
            )
            .eq(
                "intersectionId",
                intersection_row_id,
            )
            .order("id", desc=True)
            .limit(1)
        )

    result = query.execute()

    rows = result.data or []

    if not rows:
        raise RuntimeError(
            "TrafficState terbaru tidak ditemukan."
        )

    row = rows[0]

    # --------------------------------------------------------
    # CONVERT APPROACH
    # --------------------------------------------------------

    approach_map: dict[str, ApproachTraffic] = {}

    for approach_name in APPROACHES:

        approach_state = next(
            (
                item
                for item in state.approaches
                if item.approach == approach_name
            ),
            None,
        )

        if approach_state is None:
            approach_state = type(
                "EmptyApproach",
                (),
                {
                    "volume": 0,
                    "carCount": 0,
                    "motorcycleCount": 0,
                    "busCount": 0,
                    "truckCount": 0,
                    "queueLengthVeh": 0,
                    "queueLengthMEst": 0.0,
                    "densityIndex": 0.0,
                },
            )()

        approach_map[approach_name] = ApproachTraffic(
            approach=approach_name,
            volume=int(
                approach_state.volume
            ),
            carCount=int(
                approach_state.carCount
            ),
            motorcycleCount=int(
                approach_state.motorcycleCount
            ),
            busCount=int(
                approach_state.busCount
            ),
            truckCount=int(
                approach_state.truckCount
            ),
            queueLengthVeh=int(
                approach_state.queueLengthVeh
            ),
            queueLengthMEst=float(
                approach_state.queueLengthMEst
            ),
            densityIndex=float(
                approach_state.densityIndex
            ),
        )

    return TrafficStateData(
        trafficStateId=int(row["id"]),
        intersectionId=str(
            state.intersectionId
        ),
        windowStart=str(
            state.windowStart
        ),
        windowEnd=str(
            state.windowEnd
        ),
        source=str(
            row.get("source") or "cv"
        ),
        approaches=approach_map,
    )


# ============================================================
# NETWORK
# ============================================================

def load_network(
    net_file: Path,
):
    if not net_file.exists():
        raise FileNotFoundError(
            f"Network SUMO tidak ditemukan:\n{net_file}"
        )

    print()
    print("=" * 60)
    print("LOADING SUMO NETWORK")
    print("=" * 60)
    print(f"Network: {net_file}")

    net = sumolib.net.readNet(
        str(net_file),
        withInternal=False,
    )

    return net


# ============================================================
# FIND INTERSECTION CENTER
# ============================================================

def find_central_junction(net):
    """
    Cari junction yang paling cocok sebagai pusat
    persimpangan berdasarkan jumlah koneksi.
    """

    junctions = []

    for junction in net.getNodes():

        incoming = junction.getIncoming()
        outgoing = junction.getOutgoing()

        if not incoming:
            continue

        if not outgoing:
            continue

        score = (
            len(incoming)
            + len(outgoing)
        )

        junctions.append(
            (
                score,
                junction,
            )
        )

    if not junctions:
        raise RuntimeError(
            "Tidak ditemukan junction yang valid."
        )

    junctions.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return junctions[0][1]


# ============================================================
# EDGE DISTANCE TO JUNCTION
# ============================================================

def edge_distance_to_junction(
    edge,
    junction,
) -> float:

    shape = edge.getShape()

    if not shape:
        return 999999.0

    junction_x, junction_y = (
        junction.getCoord()
    )

    last_x, last_y = shape[-1]

    return (
        (last_x - junction_x) ** 2
        + (last_y - junction_y) ** 2
    ) ** 0.5


# ============================================================
# DETECT INCOMING EDGES
# ============================================================

def detect_incoming_edges(net):
    junction = find_central_junction(net)

    incoming = junction.getIncoming()

    if not incoming:
        raise RuntimeError(
            "Junction tidak mempunyai incoming edge."
        )

    print()
    print("=" * 60)
    print("CENTRAL JUNCTION")
    print("=" * 60)

    print(
        f"Junction: {junction.getID()}"
    )

    print()
    print("=" * 60)
    print("INCOMING EDGES")
    print("=" * 60)

    for edge in incoming:
        print(
            f"{edge.getID():30s}"
            f" length={edge.getLength():.2f}"
        )

    return junction, list(incoming)


# ============================================================
# CLASSIFY APPROACH BY GEOMETRY
# ============================================================

def classify_edges(
    junction,
    incoming_edges,
):
    """
    Mengelompokkan incoming edge berdasarkan arah
    posisi ujung edge terhadap junction.
    """

    junction_x, junction_y = (
        junction.getCoord()
    )

    candidates: dict[
        str,
        list[tuple[float, Any]]
    ] = {
        "north": [],
        "south": [],
        "east": [],
        "west": [],
    }

    for edge in incoming_edges:

        shape = edge.getShape()

        if not shape:
            continue

        x, y = shape[0]

        dx = x - junction_x
        dy = y - junction_y

        distance = (
            dx * dx
            + dy * dy
        ) ** 0.5

        if distance <= 0:
            continue

        if abs(dx) > abs(dy):

            if dx < 0:
                approach = "west"
            else:
                approach = "east"

        else:

            if dy > 0:
                approach = "north"
            else:
                approach = "south"

        candidates[approach].append(
            (
                distance,
                edge,
            )
        )

    # --------------------------------------------------------
    # SORT BY DISTANCE
    # --------------------------------------------------------

    for approach in candidates:
        candidates[approach].sort(
            key=lambda item: item[0]
        )

    print()
    print("=" * 60)
    print("DETECTED INCOMING EDGES")
    print("=" * 60)

    for approach in APPROACHES:

        print()
        print(
            f"{approach.upper()}:"
        )

        if not candidates[approach]:
            print("  NONE")
            continue

        for index, (
            distance,
            edge,
        ) in enumerate(
            candidates[approach][:5],
            start=1,
        ):

            print(
                f"  {index}. "
                f"{edge.getID()} "
                f"(distance={distance:.2f})"
            )

    return {
        approach: (
            candidates[approach][0][1]
            if candidates[approach]
            else None
        )
        for approach in APPROACHES
    }


# ============================================================
# FIND VALID DESTINATION EDGE
# ============================================================

def find_destination_edge(
    net,
    start_edge,
    junction,
):
    """
    Cari outgoing edge yang benar-benar bisa dicapai
    dari incoming edge.
    """

    outgoing_edges = list(
        junction.getOutgoing()
    )

    if not outgoing_edges:
        return None

    best_path = None
    best_cost = float("inf")
    best_edge = None

    for destination in outgoing_edges:

        if destination == start_edge:
            continue

        path, cost = (
            net.getShortestPath(
                start_edge,
                destination,
                vClass="passenger",
            )
        )

        if path is None:
            continue

        if len(path) < 2:
            continue

        if cost < best_cost:
            best_cost = cost
            best_path = path
            best_edge = destination

    if best_path is None:
        return None

    return list(best_path)


# ============================================================
# BUILD VALID ROUTE
# ============================================================

def build_route(
    net,
    start_edge,
    junction,
):
    """
    Menghasilkan route yang valid:
    
    incoming edge
          ↓
    intersection
          ↓
    outgoing edge
    """

    if start_edge is None:
        return None

    path = find_destination_edge(
        net,
        start_edge,
        junction,
    )

    if not path:
        return None

    return [
        edge.getID()
        for edge in path
    ]


# ============================================================
# GENERATE VEHICLE ROUTES
# ============================================================

def generate_vehicle_routes(
    net,
    junction,
    approach_edges,
    traffic_state,
    random_seed: int = 42,
):
    random.seed(random_seed)

    routes = []

    vehicle_counter = 0

    print()
    print("=" * 60)
    print("GENERATING VEHICLE ROUTES")
    print("=" * 60)

    for approach in APPROACHES:

        traffic = (
            traffic_state.approaches[
                approach
            ]
        )

        volume = max(
            0,
            int(traffic.volume),
        )

        start_edge = (
            approach_edges.get(
                approach
            )
        )

        if start_edge is None:
            if volume > 0:
                print(
                    f"WARNING: "
                    f"{approach.upper()} "
                    f"tidak memiliki incoming edge."
                )
            continue

        route = build_route(
            net,
            start_edge,
            junction,
        )

        if not route:

            print(
                f"WARNING: "
                f"route {approach.upper()} "
                f"tidak ditemukan."
            )

            continue

        print(
            f"{approach.upper():6s} "
            f"volume={volume:<4d} "
            f"route={' '.join(route)}"
        )

        # ----------------------------------------------------
        # DISTRIBUTE VEHICLE TYPES
        # ----------------------------------------------------

        vehicles = []

        vehicles.extend(
            ["car"] * traffic.carCount
        )

        vehicles.extend(
            ["motorcycle"]
            * traffic.motorcycleCount
        )

        vehicles.extend(
            ["bus"] * traffic.busCount
        )

        vehicles.extend(
            ["truck"] * traffic.truckCount
        )

        # Safety apabila classification
        # tidak sama dengan volume.
        while len(vehicles) < volume:
            vehicles.append("car")

        if len(vehicles) > volume:
            vehicles = vehicles[:volume]

        random.shuffle(vehicles)

        for vehicle_type in vehicles:

            routes.append(
                {
                    "id": (
                        f"veh_{vehicle_counter}"
                    ),
                    "approach": approach,
                    "type": vehicle_type,
                    "route": route,
                }
            )

            vehicle_counter += 1

    print()
    print(
        f"Generated vehicles: "
        f"{len(routes)}"
    )

    return routes


# ============================================================
# CREATE SUMO ROUTE FILE
# ============================================================

def create_route_file(
    route_file: Path,
    vehicles,
):
    with route_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
        )

        file.write("<routes>\n")

        # ----------------------------------------------------
        # VEHICLE TYPES
        # ----------------------------------------------------

        file.write(
            '    <vType '
            'id="car" '
            'vClass="passenger" '
            'accel="2.6" '
            'decel="4.5" '
            'sigma="0.5" '
            'length="4.5" '
            'maxSpeed="13.9"/>\n'
        )

        file.write(
            '    <vType '
            'id="motorcycle" '
            'vClass="motorcycle" '
            'accel="3.0" '
            'decel="5.0" '
            'sigma="0.5" '
            'length="2.0" '
            'maxSpeed="15.0"/>\n'
        )

        file.write(
            '    <vType '
            'id="bus" '
            'vClass="bus" '
            'accel="1.2" '
            'decel="3.0" '
            'sigma="0.5" '
            'length="12.0" '
            'maxSpeed="12.0"/>\n'
        )

        file.write(
            '    <vType '
            'id="truck" '
            'vClass="truck" '
            'accel="1.2" '
            'decel="3.0" '
            'sigma="0.5" '
            'length="8.0" '
            'maxSpeed="12.0"/>\n'
        )

        # ----------------------------------------------------
        # ROUTES
        # ----------------------------------------------------

        route_cache = {}

        route_counter = 0

        for vehicle in vehicles:

            route_tuple = tuple(
                vehicle["route"]
            )

            if route_tuple not in route_cache:

                route_id = (
                    f"route_{route_counter}"
                )

                route_cache[
                    route_tuple
                ] = route_id

                file.write(
                    f'    <route '
                    f'id="{route_id}" '
                    f'edges="'
                    f'{" ".join(route_tuple)}'
                    f'"/>\n'
                )

                route_counter += 1

        # ----------------------------------------------------
        # VEHICLES
        # ----------------------------------------------------

        for index, vehicle in enumerate(
            vehicles
        ):

            route_id = route_cache[
                tuple(vehicle["route"])
            ]

            depart = (
                index * 0.5
            )

            file.write(
                f'    <vehicle '
                f'id="{vehicle["id"]}" '
                f'type="{vehicle["type"]}" '
                f'route="{route_id}" '
                f'depart="{depart:.2f}" '
                f'departLane="best" '
                f'departSpeed="max"/>\n'
            )

        file.write("</routes>\n")


# ============================================================
# RUN SUMO
# ============================================================

def run_sumo(
    net_file: Path,
    route_file: Path,
    output_file: Path,
    duration: int,
    gui: bool,
    gui_delay: int,
):
    sumo_binary = get_sumo_binary(
        gui
    )

    command = [
        sumo_binary,

        "--net-file",
        str(net_file),

        "--route-files",
        str(route_file),

        "--begin",
        "0",

        "--end",
        str(duration),

        "--step-length",
        "1",

        "--seed",
        "42",

        "--quit-on-end",
    ]

    if gui:

        command.extend(
            [
                "--delay",
                str(gui_delay),
            ]
        )

    print()
    print("=" * 60)
    print("RUNNING SUMO")
    print("=" * 60)

    print(
        f"SUMO     : {sumo_binary}"
    )

    print(
        f"Network  : {net_file}"
    )

    print(
        f"Routes   : {route_file}"
    )

    print(
        f"Duration : {duration}"
    )

    print(
        f"GUI      : {gui}"
    )

    print()

    traci.start(
        command
    )

    simulation_data = {
        "simulation": {
            "durationSeconds": duration,
            "gui": gui,
        },
        "vehicles": {},
        "steps": [],
    }

    try:

        while (
            traci.simulation
            .getTime()
            < duration
        ):

            traci.simulationStep()

            current_time = (
                traci.simulation
                .getTime()
            )

            vehicle_ids = (
                traci.vehicle
                .getIDList()
            )

            # ------------------------------------------------
            # VEHICLE STATE
            # ------------------------------------------------

            current_vehicles = []

            for vehicle_id in vehicle_ids:

                vehicle_type = (
                    traci.vehicle
                    .getTypeID(
                        vehicle_id
                    )
                )

                edge_id = (
                    traci.vehicle
                    .getRoadID(
                        vehicle_id
                    )
                )

                speed = (
                    traci.vehicle
                    .getSpeed(
                        vehicle_id
                    )
                )

                waiting = (
                    traci.vehicle
                    .getWaitingTime(
                        vehicle_id
                    )
                )

                current_vehicles.append(
                    {
                        "id": vehicle_id,
                        "type": vehicle_type,
                        "edge": edge_id,
                        "speedKmh": (
                            speed * 3.6
                        ),
                        "waitingTime": waiting,
                    }
                )

            simulation_data[
                "steps"
            ].append(
                {
                    "time": current_time,
                    "vehicleCount": len(
                        vehicle_ids
                    ),
                    "vehicles": current_vehicles,
                }
            )

            if (
                gui
                and gui_delay > 0
            ):
                time.sleep(
                    gui_delay / 1000
                )

        # ----------------------------------------------------
        # FINAL VEHICLE DATA
        # ----------------------------------------------------

        for vehicle_id in (
            traci.vehicle
            .getIDList()
        ):

            simulation_data[
                "vehicles"
            ][vehicle_id] = {
                "type": (
                    traci.vehicle
                    .getTypeID(
                        vehicle_id
                    )
                ),
                "edge": (
                    traci.vehicle
                    .getRoadID(
                        vehicle_id
                    )
                ),
                "speedKmh": (
                    traci.vehicle
                    .getSpeed(
                        vehicle_id
                    )
                    * 3.6
                ),
            }

    finally:

        traci.close()

    output_file.write_text(
        json.dumps(
            simulation_data,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "SmartTwin SUMO Simulation Runner"
        )
    )

    parser.add_argument(
        "--intersection-id",
        default=None,
        help=(
            "intersectionId dari Supabase. "
            "Jika kosong, gunakan intersection "
            "terbaru yang memiliki TrafficState."
        ),
    )

    parser.add_argument(
        "--net-file",
        default=str(
            DEFAULT_NET_FILE
        ),
    )

    parser.add_argument(
        "--output",
        default=str(
            DEFAULT_RESULT_FILE
        ),
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
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

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    net_file = Path(
        args.net_file
    ).resolve()

    output_file = Path(
        args.output
    ).resolve()

    # ========================================================
    # LOAD TRAFFIC STATE FROM SUPABASE
    # ========================================================

    print()
    print("=" * 60)
    print("SMARTTWIN SUMO RUNNER")
    print("=" * 60)

    print(
        "Source : Supabase"
    )

    print(
        "Mode   : TrafficState terbaru"
    )

    if args.intersection_id:
        print(
            f"Target : "
            f"{args.intersection_id}"
        )
    else:
        print(
            "Target : ALL / latest"
        )

    traffic_state = (
        load_latest_traffic_state(
            args.intersection_id
        )
    )

    print()
    print("=" * 60)
    print("TRAFFIC STATE")
    print("=" * 60)

    print(
        f"ID           : "
        f"{traffic_state.trafficStateId}"
    )

    print(
        f"Intersection : "
        f"{traffic_state.intersectionId}"
    )

    print(
        f"Window       : "
        f"{traffic_state.windowStart}"
        f" -> "
        f"{traffic_state.windowEnd}"
    )

    print(
        f"Source       : "
        f"{traffic_state.source}"
    )

    for approach in APPROACHES:

        traffic = (
            traffic_state.approaches[
                approach
            ]
        )

        print(
            f"{approach.upper():7s} "
            f"| volume={traffic.volume:<4d} "
            f"| car={traffic.carCount:<4d} "
            f"| motor={traffic.motorcycleCount:<4d} "
            f"| bus={traffic.busCount:<4d} "
            f"| truck={traffic.truckCount:<4d} "
            f"| queue={traffic.queueLengthVeh:<4d}"
        )

    # ========================================================
    # LOAD NETWORK
    # ========================================================

    net = load_network(
        net_file
    )

    # ========================================================
    # FIND JUNCTION
    # ========================================================

    junction, incoming_edges = (
        detect_incoming_edges(
            net
        )
    )

    # ========================================================
    # CLASSIFY APPROACH
    # ========================================================

    approach_edges = (
        classify_edges(
            junction,
            incoming_edges,
        )
    )

    # ========================================================
    # GENERATE VALID VEHICLES
    # ========================================================

    vehicles = (
        generate_vehicle_routes(
            net,
            junction,
            approach_edges,
            traffic_state,
            random_seed=args.seed,
        )
    )

    if not vehicles:
        raise RuntimeError(
            "Tidak ada kendaraan yang berhasil "
            "dibuat. Periksa volume TrafficState "
            "dan mapping edge network."
        )

    # ========================================================
    # TEMP ROUTE FILE
    # ========================================================

    import tempfile

    with tempfile.TemporaryDirectory(
        prefix="smarttwin-sumo-"
    ) as temp_dir:

        route_file = (
            Path(temp_dir)
            / "traffic.rou.xml"
        )

        create_route_file(
            route_file,
            vehicles,
        )

        # ====================================================
        # RUN
        # ====================================================

        run_sumo(
            net_file=net_file,
            route_file=route_file,
            output_file=output_file,
            duration=args.duration,
            gui=args.gui,
            gui_delay=args.gui_delay,
        )

    print()
    print("=" * 60)
    print("SUMO SIMULATION SELESAI")
    print("=" * 60)

    print(
        f"TrafficState : "
        f"{traffic_state.trafficStateId}"
    )

    print(
        f"Vehicles     : "
        f"{len(vehicles)}"
    )

    print(
        f"Result       : "
        f"{output_file}"
    )


if __name__ == "__main__":
    main()