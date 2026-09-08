"""Build a repeatable vehicle population from one observed TrafficState."""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any

APPROACHES = ("north", "east", "south", "west")
COUNT_FIELDS = (("motorcycle", "motorcycleCount"), ("car", "carCount"),
                ("bus", "busCount"), ("truck", "truckCount"))


def snapshot_population(state: Any) -> list[dict[str, Any]]:
    rows = {str(item.approach): item for item in state.approaches}
    if set(rows) != set(APPROACHES):
        raise ValueError("Evaluasi memerlukan TrafficState lengkap untuk empat lengan.")
    population = []
    for approach in APPROACHES:
        row = rows[approach]
        counts = {}
        for vehicle_type, field in COUNT_FIELDS:
            value = getattr(row, field, None)
            if value is None or isinstance(value, bool) or int(value) != value or value < 0:
                raise ValueError(f"Jumlah kendaraan {field} tidak valid untuk {approach}.")
            counts[vehicle_type] = int(value)
        population.append({"approach": approach, "counts": counts})
    return population


def population_hash(population: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(population, sort_keys=True).encode()).hexdigest()


def inject_population(connection: Any, population: list[dict[str, Any]], seed: int) -> int:
    # Reuse the live renderer's vehicle dimensions, road mapping and turn ratios.
    from app.simulation.sumo.sumo_controller import SumoController

    rng = random.Random(seed)
    for vehicle_type, config in SumoController.VEHICLE_TYPES.items():
        connection.vehicletype.copy("DEFAULT_VEHTYPE", vehicle_type)
        connection.vehicletype.setVehicleClass(vehicle_type, config["vclass"])
        connection.vehicletype.setLength(vehicle_type, config["length"])
        connection.vehicletype.setWidth(vehicle_type, config["width"])
        connection.vehicletype.setMaxSpeed(vehicle_type, config["maxSpeed"])
    count = 0
    for row in population:
        approach = row["approach"]
        for vehicle_type, total in row["counts"].items():
            for _ in range(total):
                turn = rng.choices(list(SumoController.TURN_DISTRIBUTION),
                                   weights=list(SumoController.TURN_DISTRIBUTION.values()))[0]
                destination = SumoController.TURN_MAPPING[approach][turn]
                route = connection.simulation.findRoute(
                    SumoController.EDGE_HULU[approach], SumoController.EDGE_KELUAR[destination],
                    vType=vehicle_type,
                )
                if not route.edges:
                    raise RuntimeError(f"Rute evaluasi tidak tersedia: {approach}/{turn}.")
                route_id = f"evaluation_route_{count}"
                connection.route.add(route_id, route.edges)
                connection.vehicle.add(f"evaluation_{approach}_{count}", route_id,
                                       typeID=vehicle_type, depart="now", departLane="best", departSpeed="0")
                count += 1
    return count
