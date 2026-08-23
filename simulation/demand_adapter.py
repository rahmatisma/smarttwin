from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import traci


# ============================================================
# APPROACH → SUMO EDGE
# ============================================================

APPROACH_INCOMING_EDGES: dict[str, str] = {
    "north": "484349908#2",
    "south": "134603786#2",
    "east": "153857851#4",
    "west": "590064461#2",
}


# ============================================================
# OUTGOING EDGES
# ============================================================

OUTGOING_EDGES: tuple[str, ...] = (
    "25006154#0",
    "201299423#0",
    "590386082#0",
    "153857907#0",
)


# ============================================================
# VEHICLE TYPES
# ============================================================

@dataclass(frozen=True)
class VehicleTypeConfig:
    id: str
    vclass: str
    length: float
    max_speed: float


VEHICLE_TYPES = {
    "car": VehicleTypeConfig(
        id="smart_car",
        vclass="passenger",
        length=4.5,
        max_speed=13.9,
    ),

    "motorcycle": VehicleTypeConfig(
        id="smart_motorcycle",
        vclass="motorcycle",
        length=2.5,
        max_speed=13.9,
    ),

    "bus": VehicleTypeConfig(
        id="smart_bus",
        vclass="bus",
        length=12.0,
        max_speed=13.9,
    ),

    "truck": VehicleTypeConfig(
        id="smart_truck",
        vclass="truck",
        length=8.0,
        max_speed=13.9,
    ),
}


# ============================================================
# DEMAND RESULT
# ============================================================

@dataclass
class DemandResult:
    total_vehicles: int = 0
    cars: int = 0
    motorcycles: int = 0
    buses: int = 0
    trucks: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "totalVehicles": self.total_vehicles,
            "cars": self.cars,
            "motorcycles": self.motorcycles,
            "buses": self.buses,
            "trucks": self.trucks,
        }


# ============================================================
# DEMAND ADAPTER
# ============================================================

class DemandAdapter:
    """
    Mengubah TrafficState menjadi kendaraan SUMO.

    TrafficState
        ↓
    DemandAdapter
        ↓
    TraCI vehicle.add()
        ↓
    SUMO
    """

    def __init__(
        self,
        route_prefix: str = "smart_route",
        vehicle_prefix: str = "smart_vehicle",
    ) -> None:

        self.route_prefix = route_prefix
        self.vehicle_prefix = vehicle_prefix

        self.route_counter = 0
        self.vehicle_counter = 0

    # ========================================================
    # VEHICLE TYPES
    # ========================================================

    def ensure_vehicle_types(self) -> None:
        """
        Membuat vehicle type jika belum ada.
        """

        existing_types = set(
            traci.vehicletype.getIDList()
        )

        for config in VEHICLE_TYPES.values():

            if config.id in existing_types:
                continue

            traci.vehicletype.copy(
                "DEFAULT_VEHTYPE",
                config.id,
            )

            traci.vehicletype.setVehicleClass(
                config.id,
                config.vclass,
            )

            traci.vehicletype.setLength(
                config.id,
                config.length,
            )

            traci.vehicletype.setMaxSpeed(
                config.id,
                config.max_speed,
            )

    # ========================================================
    # ROUTE
    # ========================================================

    def create_route(
        self,
        incoming_edge: str,
        outgoing_edge: str,
    ) -> str:
        """
        Membuat route sederhana:

            incoming edge → outgoing edge
        """

        route_id = (
            f"{self.route_prefix}_"
            f"{self.route_counter}"
        )

        self.route_counter += 1

        traci.route.add(
            route_id,
            [
                incoming_edge,
                outgoing_edge,
            ],
        )

        return route_id

    # ========================================================
    # FIND VALID OUTGOING EDGE
    # ========================================================

    def find_valid_route(
        self,
        incoming_edge: str,
    ) -> str | None:
        """
        Mencoba seluruh outgoing edge sampai
        menemukan route yang diterima SUMO.
        """

        for outgoing_edge in OUTGOING_EDGES:

            try:

                route_id = self.create_route(
                    incoming_edge,
                    outgoing_edge,
                )

                return route_id

            except Exception:

                continue

        return None

    # ========================================================
    # ADD VEHICLE
    # ========================================================

    def add_vehicle(
        self,
        approach: str,
        vehicle_type: str,
    ) -> bool:
        """
        Menambahkan satu kendaraan ke SUMO.
        """

        incoming_edge = (
            APPROACH_INCOMING_EDGES.get(
                approach
            )
        )

        if incoming_edge is None:
            return False

        route_id = self.find_valid_route(
            incoming_edge
        )

        if route_id is None:
            return False

        vehicle_id = (
            f"{self.vehicle_prefix}_"
            f"{self.vehicle_counter}"
        )

        self.vehicle_counter += 1

        type_config = VEHICLE_TYPES.get(
            vehicle_type
        )

        if type_config is None:
            return False

        try:

            traci.vehicle.add(
                vehID=vehicle_id,
                routeID=route_id,
                typeID=type_config.id,
                depart=0,
            )

            return True

        except Exception:

            return False

    # ========================================================
    # ADD APPROACH DEMAND
    # ========================================================

    def add_approach_demand(
        self,
        approach_state: Any,
    ) -> DemandResult:
        """
        Menambahkan seluruh kendaraan
        dari satu approach.
        """

        approach = str(
            approach_state.approach
        ).lower()

        result = DemandResult()

        # ----------------------------------------------------
        # Cars
        # ----------------------------------------------------

        car_count = int(
            approach_state.carCount or 0
        )

        for _ in range(car_count):

            if self.add_vehicle(
                approach,
                "car",
            ):

                result.total_vehicles += 1
                result.cars += 1

        # ----------------------------------------------------
        # Motorcycles
        # ----------------------------------------------------

        motorcycle_count = int(
            approach_state.motorcycleCount or 0
        )

        for _ in range(motorcycle_count):

            if self.add_vehicle(
                approach,
                "motorcycle",
            ):

                result.total_vehicles += 1
                result.motorcycles += 1

        # ----------------------------------------------------
        # Buses
        # ----------------------------------------------------

        bus_count = int(
            approach_state.busCount or 0
        )

        for _ in range(bus_count):

            if self.add_vehicle(
                approach,
                "bus",
            ):

                result.total_vehicles += 1
                result.buses += 1

        # ----------------------------------------------------
        # Trucks
        # ----------------------------------------------------

        truck_count = int(
            approach_state.truckCount or 0
        )

        for _ in range(truck_count):

            if self.add_vehicle(
                approach,
                "truck",
            ):

                result.total_vehicles += 1
                result.trucks += 1

        return result

    # ========================================================
    # ADD TRAFFIC STATE DEMAND
    # ========================================================

    def add_traffic_state(
        self,
        traffic_state: Any,
    ) -> DemandResult:
        """
        Mengubah seluruh TrafficState
        menjadi kendaraan SUMO.
        """

        self.ensure_vehicle_types()

        total = DemandResult()

        print()
        print("=" * 70)
        print("CREATING SUMO DEMAND")
        print("=" * 70)

        for approach_state in (
            traffic_state.approaches
        ):

            approach = (
                approach_state.approach
            )

            result = (
                self.add_approach_demand(
                    approach_state
                )
            )

            print(
                f"{approach.upper():<8} | "
                f"vehicles={result.total_vehicles:<4} | "
                f"car={result.cars:<4} | "
                f"motor={result.motorcycles:<4} | "
                f"bus={result.buses:<4} | "
                f"truck={result.trucks:<4}"
            )

            total.total_vehicles += (
                result.total_vehicles
            )

            total.cars += result.cars
            total.motorcycles += (
                result.motorcycles
            )
            total.buses += result.buses
            total.trucks += result.trucks

        print("-" * 70)

        print(
            f"TOTAL    | "
            f"vehicles={total.total_vehicles}"
        )

        print("=" * 70)

        return total


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "DemandAdapter module."
    )