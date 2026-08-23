from __future__ import annotations

import random

from collections import defaultdict
from pathlib import Path
from typing import Any


class SumoController:
    """
    Controller untuk menjalankan simulasi SUMO melalui TraCI.

    Struktur project yang digunakan:

        smarttwin/
        ├── backend/
        │   └── app/
        │       └── simulation/
        │           └── sumo/
        │               └── sumo_controller.py
        │
        └── simulation/
            ├── .venv/
            │   └── Scripts/
            │       ├── sumo.exe
            │       └── sumo-gui.exe
            │
            └── network/
                └── simpang4_pingit.sumocfg

    Tugas:
        1. Menentukan executable SUMO
        2. Start SUMO
        3. Membuat vehicle type
        4. Membuat route
        5. Spawn kendaraan berdasarkan traffic demand
        6. Menjalankan simulation step
        7. Mengumpulkan metrics
        8. Menutup SUMO
    """

    # ========================================================
    # PROJECT PATH
    # ========================================================

    # File ini:
    #
    # backend/app/simulation/sumo/sumo_controller.py
    #
    # parents[0] = backend/app/simulation/sumo
    # parents[1] = backend/app/simulation
    # parents[2] = backend/app
    # parents[3] = backend
    # parents[4] = smarttwin
    #
    PROJECT_ROOT = Path(__file__).resolve().parents[4]

    SIMULATION_DIR = PROJECT_ROOT / "simulation"

    SUMO_VENV_DIR = SIMULATION_DIR / ".venv"

    SUMO_SCRIPTS_DIR = SUMO_VENV_DIR / "Scripts"

    SUMO_BIN_DIR = (
        SUMO_VENV_DIR
        / "Lib"
        / "site-packages"
        / "sumo"
        / "bin"
    )

    NETWORK_DIR = SIMULATION_DIR / "network"

    DEFAULT_CONFIG_FILE = (
        NETWORK_DIR / "simpang4_pingit.sumocfg"
    )

    # ========================================================
    # VEHICLE TYPES
    # ========================================================

    VEHICLE_TYPES = {
        "motorcycle": {
            "vclass": "motorcycle",
            "length": 2.2,
            "width": 0.9,
        },
        "car": {
            "vclass": "passenger",
            "length": 5.0,
            "width": 1.8,
        },
        "bus": {
            "vclass": "bus",
            "length": 12.0,
            "width": 2.5,
        },
        "truck": {
            "vclass": "truck",
            "length": 10.0,
            "width": 2.5,
        },
    }

    # ========================================================
    # TURN DISTRIBUTION
    # ========================================================

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

    # ========================================================
    # EDGE CONFIGURATION
    # ========================================================

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

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        sumo_binary: str | Path | None = None,
        config_file: str | Path | None = None,
        seed: int | None = None,
    ) -> None:

        self.sumo_binary = (
            Path(sumo_binary)
            if sumo_binary is not None
            else self._default_sumo_binary()
        )

        self.config_file = (
            Path(config_file)
            if config_file is not None
            else self.DEFAULT_CONFIG_FILE
        )

        self.seed = seed
        self.traci = None

    # ========================================================
    # FIND SUMO BINARY
    # ========================================================

    @classmethod
    def _default_sumo_binary(cls) -> Path:
        """
        Menentukan lokasi SUMO executable.

        Prioritas:

        1. simulation/.venv/Scripts/sumo.exe
        2. simulation/.venv/Lib/site-packages/sumo/bin/sumo.exe
        3. fallback ke 'sumo' dari PATH.
        """

        candidates = [
            cls.SUMO_SCRIPTS_DIR / "sumo.exe",
            cls.SUMO_BIN_DIR / "sumo.exe",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return Path("sumo")

    # ========================================================
    # FIND SUMO GUI
    # ========================================================

    @classmethod
    def _default_sumo_gui_binary(cls) -> Path:
        """
        Menentukan lokasi SUMO-GUI executable.
        """

        candidates = [
            cls.SUMO_SCRIPTS_DIR / "sumo-gui.exe",
            cls.SUMO_BIN_DIR / "sumo-gui.exe",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return Path("sumo-gui")

    # ========================================================
    # START
    # ========================================================

    def start(
        self,
        gui: bool = False,
        gui_delay_ms: int = 100,
    ) -> None:

        try:
            import traci
        except ImportError as exc:
            raise RuntimeError(
                "TraCI belum tersedia. "
                "Pastikan package traci sudah terinstall "
                "di virtual environment backend."
            ) from exc

        # ----------------------------------------------------
        # CHECK CONFIG
        # ----------------------------------------------------

        if self.config_file is None:
            raise ValueError(
                "Config file SUMO belum diberikan."
            )

        if not self.config_file.exists():
            raise FileNotFoundError(
                f"SUMO config file tidak ditemukan: "
                f"{self.config_file}"
            )

        # ----------------------------------------------------
        # SELECT BINARY
        # ----------------------------------------------------

        if gui:
            binary = self._default_sumo_gui_binary()
        else:
            binary = self.sumo_binary

        # ----------------------------------------------------
        # CHECK BINARY
        # ----------------------------------------------------

        if (
            isinstance(binary, Path)
            and binary.name != "sumo"
            and binary.name != "sumo-gui"
            and not binary.exists()
        ):
            raise FileNotFoundError(
                f"SUMO binary tidak ditemukan: {binary}"
            )

        # ----------------------------------------------------
        # COMMAND
        # ----------------------------------------------------

        command = [
            str(binary),
            "-c",
            str(self.config_file),
            "--step-length",
            "1",
            "--no-step-log",
            "--no-warnings",
        ]

        if self.seed is not None:
            command.extend(
                [
                    "--seed",
                    str(self.seed),
                ]
            )

        if gui:
            command.extend(
                [
                    "--delay",
                    str(gui_delay_ms),
                ]
            )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("STARTING SUMO")
        print("=" * 70)
        print(f"Binary : {binary}")
        print(f"Config : {self.config_file}")
        print(f"Command: {' '.join(command)}")
        print("=" * 70)

        # ----------------------------------------------------
        # START TRACI
        # ----------------------------------------------------

        try:
            traci.start(command)
        except Exception as exc:
            raise RuntimeError(
                "Gagal menjalankan SUMO melalui TraCI.\n\n"
                f"Binary   : {binary}\n"
                f"Config   : {self.config_file}\n"
                f"Command  : {' '.join(command)}\n"
                f"Error    : {exc}"
            ) from exc

        self.traci = traci

        print("SUMO berhasil terhubung melalui TraCI.")
        print("=" * 70)

    # ========================================================
    # VEHICLE TYPES
    # ========================================================

    def create_vehicle_types(self) -> None:

        if self.traci is None:
            raise RuntimeError(
                "SUMO belum dijalankan."
            )

        traci = self.traci

        existing_types = set(
            traci.vehicletype.getIDList()
        )

        for vehicle_type, config in (
            self.VEHICLE_TYPES.items()
        ):

            if vehicle_type in existing_types:
                continue

            try:
                traci.vehicletype.copy(
                    "DEFAULT_VEHTYPE",
                    vehicle_type,
                )
            except traci.TraCIException:
                continue

            traci.vehicletype.setVehicleClass(
                vehicle_type,
                config["vclass"],
            )

            traci.vehicletype.setLength(
                vehicle_type,
                config["length"],
            )

            traci.vehicletype.setWidth(
                vehicle_type,
                config["width"],
            )

    # ========================================================
    # BUILD ROUTE
    # ========================================================

    def build_route(
        self,
        approach: str,
        rng: random.Random,
    ) -> list[str]:

        approach = str(approach).lower()

        if approach not in self.TURN_MAPPING:
            raise ValueError(
                f"Approach tidak valid: {approach}"
            )

        turn = rng.choices(
            list(
                self.TURN_DISTRIBUTION.keys()
            ),
            weights=list(
                self.TURN_DISTRIBUTION.values()
            ),
            k=1,
        )[0]

        destination = self.TURN_MAPPING[
            approach
        ][turn]

        return [
            self.EDGE_HULU[approach],
            self.EDGE_MASUK[approach],
            self.EDGE_KELUAR[destination],
        ]

    # ========================================================
    # ADD VEHICLE
    # ========================================================

    def add_vehicle(
        self,
        vehicle_id: str,
        vehicle_type: str,
        approach: str,
        rng: random.Random,
    ) -> bool:

        if self.traci is None:
            raise RuntimeError(
                "SUMO belum dijalankan."
            )

        if vehicle_type not in self.VEHICLE_TYPES:
            return False

        route_id = f"route_{vehicle_id}"

        try:
            edges = self.build_route(
                approach,
                rng,
            )

            self.traci.route.add(
                route_id,
                edges,
            )

            self.traci.vehicle.add(
                vehID=vehicle_id,
                routeID=route_id,
                typeID=vehicle_type,
                depart="now",
            )

            return True

        except self.traci.TraCIException:
            return False

    # ========================================================
    # RUN SIMULATION
    # ========================================================

    def run(
        self,
        demand: list[dict[str, Any]],
        duration_seconds: int,
    ) -> dict[str, Any]:

        if self.traci is None:
            raise RuntimeError(
                "SUMO belum dijalankan."
            )

        if duration_seconds <= 0:
            raise ValueError(
                "duration_seconds harus lebih besar dari 0."
            )

        rng = random.Random(self.seed)

        # ----------------------------------------------------
        # TARGET DEMAND
        # ----------------------------------------------------

        target: dict[
            str,
            dict[str, int],
        ] = {}

        for item in demand:

            approach = str(
                item["approach"]
            ).lower()

            target[approach] = {
                "motorcycle": int(
                    item.get(
                        "motorcycleCount",
                        0,
                    )
                ),
                "car": int(
                    item.get(
                        "carCount",
                        0,
                    )
                ),
                "bus": int(
                    item.get(
                        "busCount",
                        0,
                    )
                ),
                "truck": int(
                    item.get(
                        "truckCount",
                        0,
                    )
                ),
            }

        departed = defaultdict(int)
        arrived = defaultdict(int)

        waiting_times: defaultdict[
            str,
            list[float],
        ] = defaultdict(list)

        spawned = 0

        # ====================================================
        # SIMULATION LOOP
        # ====================================================

        for second in range(
            duration_seconds
        ):

            # ------------------------------------------------
            # SPAWN
            # ------------------------------------------------

            for approach, counts in target.items():

                for vehicle_type, total in (
                    counts.items()
                ):

                    if total <= 0:
                        continue

                    interval = max(
                        1,
                        duration_seconds // total,
                    )

                    if second % interval != 0:
                        continue

                    index = (
                        second // interval
                    )

                    if index >= total:
                        continue

                    vehicle_id = (
                        f"{vehicle_type}_"
                        f"{approach}_"
                        f"{second}_"
                        f"{index}"
                    )

                    success = self.add_vehicle(
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

            self.traci.simulationStep()

            # ------------------------------------------------
            # DEPARTED
            # ------------------------------------------------

            for vehicle_id in (
                self.traci.simulation
                .getDepartedIDList()
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
                self.traci.simulation
                .getArrivedIDList()
            ):

                parts = vehicle_id.split("_")

                approach = (
                    parts[1]
                    if len(parts) > 1
                    else "unknown"
                )

                arrived[approach] += 1

            # ------------------------------------------------
            # WAITING TIME
            # ------------------------------------------------

            for vehicle_id in (
                self.traci.vehicle.getIDList()
            ):

                parts = vehicle_id.split("_")

                if len(parts) < 2:
                    continue

                approach = parts[1]

                waiting = (
                    self.traci.vehicle
                    .getAccumulatedWaitingTime(
                        vehicle_id
                    )
                )

                waiting_times[
                    approach
                ].append(waiting)

        # ====================================================
        # METRICS
        # ====================================================

        all_waiting: list[float] = []

        for values in waiting_times.values():
            all_waiting.extend(values)

        average_waiting = (
            sum(all_waiting)
            / len(all_waiting)
            if all_waiting
            else 0.0
        )

        return {
            "durationSeconds": duration_seconds,

            "spawnedVehicles": spawned,

            "departedVehicles": sum(
                departed.values()
            ),

            "arrivedVehicles": sum(
                arrived.values()
            ),

            "activeVehicles": (
                self.traci.vehicle.getIDCount()
            ),

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

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:

        if self.traci is not None:

            try:
                self.traci.close()

            except Exception:
                pass

            finally:
                self.traci = None