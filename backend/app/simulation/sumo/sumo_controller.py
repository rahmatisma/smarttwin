from __future__ import annotations

import random
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


class SumoController:
    """
    Long-running SUMO Controller.

    SUMO hanya dijalankan SATU KALI selama controller aktif.

    Alur:

        TrafficState
             ↓
        inject_demand()
             ↓
        SUMO simulationStep()
             ↓
        metrics

    Background thread menjalankan simulationStep()
    setiap 1 detik.

    TraCI hanya boleh diakses satu thread pada satu waktu,
    sehingga semua operasi TraCI dilindungi oleh _traci_lock.
    """

    # ============================================================
    # PROJECT PATH
    # ============================================================

    # File:
    # backend/app/simulation/sumo/sumo_controller.py
    #
    # parents:
    # [0] sumo
    # [1] simulation
    # [2] app
    # [3] backend
    # [4] smarttwin
    #
    PROJECT_ROOT = Path(__file__).resolve().parents[4]

    SIMULATION_DIR = PROJECT_ROOT / "simulation"

    SUMO_VENV_DIR = SIMULATION_DIR / ".venv"

    SUMO_SCRIPTS_DIR = (
        SUMO_VENV_DIR / "Scripts"
    )

    SUMO_BIN_DIR = (
        SUMO_VENV_DIR
        / "Lib"
        / "site-packages"
        / "sumo"
        / "bin"
    )

    NETWORK_DIR = (
        SIMULATION_DIR / "network"
    )

    DEFAULT_CONFIG_FILE = (
        NETWORK_DIR
        / "simpang4_pingit.sumocfg"
    )

    # ============================================================
    # EDGE CONFIGURATION
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
    # VEHICLE TYPES
    # ============================================================

    VEHICLE_TYPES = {
        "motorcycle": {
            "vclass": "motorcycle",
            "length": 2.2,
            "width": 0.9,
            "maxSpeed": 13.9,
        },
        "car": {
            "vclass": "passenger",
            "length": 5.0,
            "width": 1.8,
            "maxSpeed": 13.9,
        },
        "bus": {
            "vclass": "bus",
            "length": 12.0,
            "width": 2.5,
            "maxSpeed": 13.9,
        },
        "truck": {
            "vclass": "truck",
            "length": 10.0,
            "width": 2.5,
            "maxSpeed": 13.9,
        },
    }

    VALID_APPROACHES = {
        "north",
        "south",
        "east",
        "west",
    }

    # ============================================================
    # INIT
    # ============================================================

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

        # ========================================================
        # TRACI
        # ========================================================

        self.traci = None

        # ========================================================
        # REALTIME STATE
        # ========================================================

        self.running = False

        self._stop_event = threading.Event()

        self._simulation_thread: (
            threading.Thread | None
        ) = None

        # ========================================================
        # TRACI LOCK
        # ========================================================

        self._traci_lock = threading.RLock()

        # ========================================================
        # RANDOM
        # ========================================================

        self._rng = random.Random(seed)

        # ========================================================
        # METRICS
        # ========================================================

        self.spawned_total = 0

        self.departed_total = defaultdict(int)

        self.arrived_total = defaultdict(int)

        self.last_simulation_time = 0.0

        self.last_error: str | None = None

        # ========================================================
        # VEHICLE COUNTER
        # ========================================================

        self._vehicle_counter = 0

        # ========================================================
        # APPROACH DEMAND
        # ========================================================

        self.current_demand: dict[
            str,
            dict[str, int],
        ] = {}

    # ============================================================
    # SUMO BINARY
    # ============================================================

    @classmethod
    def _default_sumo_binary(
        cls,
    ) -> Path:
        """
        Prioritas:

        1. simulation/.venv/Scripts/sumo.exe
        2. simulation/.venv/Lib/site-packages/sumo/bin/sumo.exe
        3. PATH
        """

        candidates = [
            cls.SUMO_SCRIPTS_DIR / "sumo.exe",
            cls.SUMO_BIN_DIR / "sumo.exe",
        ]

        for candidate in candidates:

            if candidate.exists():
                return candidate

        return Path("sumo")

    # ============================================================
    # SUMO GUI BINARY
    # ============================================================

    @classmethod
    def _default_sumo_gui_binary(
        cls,
    ) -> Path:

        candidates = [
            cls.SUMO_SCRIPTS_DIR
            / "sumo-gui.exe",

            cls.SUMO_BIN_DIR
            / "sumo-gui.exe",
        ]

        for candidate in candidates:

            if candidate.exists():
                return candidate

        return Path("sumo-gui")

    # ============================================================
    # START
    # ============================================================

    def start(
        self,
        gui: bool = False,
        gui_delay_ms: int = 0,
    ) -> None:

        # ========================================================
        # ALREADY RUNNING
        # ========================================================

        if (
            self.running
            and self.traci is not None
        ):
            print(
                "[SUMO] Controller sudah running."
            )
            return

        # ========================================================
        # IMPORT TRACI
        # ========================================================

        try:

            import traci

        except ImportError as exc:

            raise RuntimeError(
                "TraCI belum tersedia di environment backend. "
                "Pastikan package traci terinstall pada "
                "virtual environment backend."
            ) from exc

        # ========================================================
        # CHECK CONFIG
        # ========================================================

        if self.config_file is None:

            raise ValueError(
                "Config file SUMO belum diberikan."
            )

        if not self.config_file.exists():

            raise FileNotFoundError(
                "SUMO config file tidak ditemukan: "
                f"{self.config_file}"
            )

        # ========================================================
        # SELECT BINARY
        # ========================================================

        if gui:

            binary = (
                self._default_sumo_gui_binary()
            )

        else:

            binary = self.sumo_binary

        # ========================================================
        # CHECK BINARY
        # ========================================================

        if (
            isinstance(binary, Path)
            and binary.name
            not in {
                "sumo",
                "sumo.exe",
                "sumo-gui",
                "sumo-gui.exe",
            }
            and not binary.exists()
        ):

            raise FileNotFoundError(
                f"SUMO binary tidak ditemukan: {binary}"
            )

        if (
            isinstance(binary, Path)
            and binary.name
            in {
                "sumo.exe",
                "sumo-gui.exe",
            }
            and not binary.exists()
        ):

            raise FileNotFoundError(
                f"SUMO binary tidak ditemukan: {binary}"
            )

        # ========================================================
        # COMMAND
        # ========================================================

        command = [
            str(binary),
            "-c",
            str(self.config_file),
            "--step-length",
            "1",
            "--no-step-log",
        ]

        # ========================================================
        # SEED
        # ========================================================

        if self.seed is not None:

            command.extend(
                [
                    "--seed",
                    str(self.seed),
                ]
            )

        # ========================================================
        # GUI DELAY
        # ========================================================

        if (
            gui
            and gui_delay_ms > 0
        ):

            command.extend(
                [
                    "--delay",
                    str(gui_delay_ms),
                ]
            )

        # ========================================================
        # LOG
        # ========================================================

        print()
        print("=" * 70)
        print("STARTING SUMO")
        print("=" * 70)

        print(
            f"Binary : {binary}"
        )

        print(
            f"Config : {self.config_file}"
        )

        print(
            f"Command: {' '.join(command)}"
        )

        print("=" * 70)

        # ========================================================
        # START SUMO THROUGH TRACI
        # ========================================================

        try:

            traci.start(
                command,
                label="smarttwin",
            )

        except Exception as exc:

            # ----------------------------------------------------
            # Cleanup jika koneksi setengah terbuka
            # ----------------------------------------------------

            try:

                traci.close()

            except Exception:

                pass

            self.traci = None

            self.running = False

            self.last_error = str(exc)

            raise RuntimeError(
                "Gagal menjalankan SUMO melalui TraCI.\n\n"
                f"Binary : {binary}\n"
                f"Config : {self.config_file}\n"
                f"Command: {' '.join(command)}\n"
                f"Error  : {exc}"
            ) from exc

        # ========================================================
        # CONNECTION SUCCESS
        # ========================================================

        self.traci = traci

        self.running = True

        self.last_error = None

        self._stop_event.clear()

        # ========================================================
        # CREATE VEHICLE TYPES
        # ========================================================

        try:

            with self._traci_lock:

                self.create_vehicle_types()

        except Exception as exc:

            self.running = False

            try:

                with self._traci_lock:

                    self.traci.close()

            except Exception:

                pass

            self.traci = None

            self.last_error = str(exc)

            raise RuntimeError(
                "SUMO berhasil start tetapi gagal "
                "membuat vehicle types.\n\n"
                f"Error: {exc}"
            ) from exc

        # ========================================================
        # START BACKGROUND LOOP
        # ========================================================

        self._simulation_thread = (
            threading.Thread(
                target=self._simulation_loop,
                name="sumo-realtime-loop",
                daemon=True,
            )
        )

        self._simulation_thread.start()

        print(
            "SUMO berhasil terhubung melalui TraCI."
        )

        print(
            "SUMO realtime loop berhasil dimulai."
        )

        print("=" * 70)

    # ============================================================
    # CREATE VEHICLE TYPES
    # ============================================================

    def create_vehicle_types(
        self,
    ) -> None:

        if self.traci is None:

            raise RuntimeError(
                "SUMO belum dijalankan."
            )

        traci = self.traci

        existing_types = set(
            traci.vehicletype.getIDList()
        )

        for (
            vehicle_type,
            config,
        ) in self.VEHICLE_TYPES.items():

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

            traci.vehicletype.setMaxSpeed(
                vehicle_type,
                config["maxSpeed"],
            )

    # ============================================================
    # BUILD ROUTE
    # ============================================================

    def build_route(
        self,
        approach: str,
    ) -> list[str]:

        approach = (
            str(approach)
            .lower()
            .strip()
        )

        if (
            approach
            not in self.VALID_APPROACHES
        ):

            raise ValueError(
                f"Approach tidak valid: {approach}"
            )

        turn = self._rng.choices(
            list(
                self.TURN_DISTRIBUTION.keys()
            ),
            weights=list(
                self.TURN_DISTRIBUTION.values()
            ),
            k=1,
        )[0]

        destination = (
            self.TURN_MAPPING[
                approach
            ][turn]
        )

        return [
            self.EDGE_HULU[approach],
            self.EDGE_MASUK[approach],
            self.EDGE_KELUAR[destination],
        ]

    # ============================================================
    # ADD VEHICLE
    # ============================================================

    def add_vehicle(
        self,
        vehicle_type: str,
        approach: str,
    ) -> bool:

        if self.traci is None:

            raise RuntimeError(
                "SUMO belum dijalankan."
            )

        if (
            vehicle_type
            not in self.VEHICLE_TYPES
        ):

            return False

        approach = (
            str(approach)
            .lower()
            .strip()
        )

        if (
            approach
            not in self.VALID_APPROACHES
        ):

            return False

        vehicle_id = (
            f"smart_{vehicle_type}_"
            f"{approach}_"
            f"{self._vehicle_counter}"
        )

        route_id = (
            f"smart_route_"
            f"{self._vehicle_counter}"
        )

        self._vehicle_counter += 1

        try:

            edges = self.build_route(
                approach
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

            self.spawned_total += 1

            return True

        except self.traci.TraCIException:

            return False

    # ============================================================
    # INJECT DEMAND
    # ============================================================

    def inject_demand(
        self,
        demand: list[dict[str, Any]],
    ) -> dict[str, int]:

        if self.traci is None:

            raise RuntimeError(
                "SUMO belum dijalankan."
            )

        result = {
            "motorcycle": 0,
            "car": 0,
            "bus": 0,
            "truck": 0,
            "total": 0,
        }

        with self._traci_lock:

            for item in demand:

                approach = str(
                    item.get(
                        "approach",
                        "",
                    )
                ).lower().strip()

                if (
                    approach
                    not in self.VALID_APPROACHES
                ):
                    continue

                vehicle_counts = {
                    "motorcycle": max(
                        0,
                        int(
                            item.get(
                                "motorcycleCount",
                                0,
                            )
                            or 0
                        ),
                    ),
                    "car": max(
                        0,
                        int(
                            item.get(
                                "carCount",
                                0,
                            )
                            or 0
                        ),
                    ),
                    "bus": max(
                        0,
                        int(
                            item.get(
                                "busCount",
                                0,
                            )
                            or 0
                        ),
                    ),
                    "truck": max(
                        0,
                        int(
                            item.get(
                                "truckCount",
                                0,
                            )
                            or 0
                        ),
                    ),
                }

                self.current_demand[
                    approach
                ] = vehicle_counts

                for (
                    vehicle_type,
                    count,
                ) in vehicle_counts.items():

                    for _ in range(count):

                        success = (
                            self.add_vehicle(
                                vehicle_type=vehicle_type,
                                approach=approach,
                            )
                        )

                        if success:

                            result[
                                vehicle_type
                            ] += 1

                            result[
                                "total"
                            ] += 1

        return result

    # ============================================================
    # SIMULATION LOOP
    # ============================================================

    def _simulation_loop(
        self,
    ) -> None:

        """
        Background realtime loop.

        1 simulation step = 1 detik.

        Loop:

            simulationStep()
                 ↓
            collect metrics
                 ↓
            sleep
                 ↓
            repeat
        """

        print(
            "[SUMO LOOP] "
            "Background simulation loop aktif."
        )

        while not self._stop_event.is_set():

            started_at = (
                time.perf_counter()
            )

            try:

                with self._traci_lock:

                    # --------------------------------------------
                    # CHECK TRACI
                    # --------------------------------------------

                    if self.traci is None:

                        print(
                            "[SUMO LOOP] "
                            "TraCI object sudah None."
                        )

                        break

                    if not self.running:

                        print(
                            "[SUMO LOOP] "
                            "Controller tidak running."
                        )

                        break

                    # --------------------------------------------
                    # SIMULATION STEP
                    # --------------------------------------------

                    self.traci.simulationStep()

                    # --------------------------------------------
                    # SIMULATION TIME
                    # --------------------------------------------

                    self.last_simulation_time = (
                        self.traci
                        .simulation
                        .getTime()
                    )

                    # --------------------------------------------
                    # DEPARTED
                    # --------------------------------------------

                    departed_ids = (
                        self.traci
                        .simulation
                        .getDepartedIDList()
                    )

                    for vehicle_id in departed_ids:

                        approach = (
                            self._extract_approach(
                                vehicle_id
                            )
                        )

                        self.departed_total[
                            approach
                        ] += 1

                    # --------------------------------------------
                    # ARRIVED
                    # --------------------------------------------

                    arrived_ids = (
                        self.traci
                        .simulation
                        .getArrivedIDList()
                    )

                    for vehicle_id in arrived_ids:

                        approach = (
                            self._extract_approach(
                                vehicle_id
                            )
                        )

                        self.arrived_total[
                            approach
                        ] += 1

                    # --------------------------------------------
                    # DEBUG
                    # --------------------------------------------

                    if (
                        int(
                            self.last_simulation_time
                        )
                        % 10
                        == 0
                    ):

                        try:

                            active_count = (
                                self.traci
                                .vehicle
                                .getIDCount()
                            )

                            print(
                                "[SUMO LOOP] "
                                f"time="
                                f"{self.last_simulation_time:.0f}s "
                                f"active="
                                f"{active_count} "
                                f"spawned="
                                f"{self.spawned_total}"
                            )

                        except Exception:

                            pass

            # ====================================================
            # SUMO / TRACI ERROR
            # ====================================================

            except Exception as exc:

                self.last_error = str(exc)

                print()
                print("=" * 70)
                print(
                    "[SUMO REALTIME ERROR]"
                )
                print("=" * 70)

                print(
                    "Error type:",
                    type(exc).__name__,
                )

                print(
                    "Error:",
                    exc,
                )

                print(
                    "Simulation time:",
                    self.last_simulation_time,
                )

                print(
                    "Spawned vehicles:",
                    self.spawned_total,
                )

                print(
                    "Running:",
                    self.running,
                )

                print(
                    "TraCI available:",
                    self.traci is not None,
                )

                print("=" * 70)

                self.running = False

                break

            # ====================================================
            # REALTIME CLOCK
            # ====================================================

            elapsed = (
                time.perf_counter()
                - started_at
            )

            sleep_time = max(
                0.0,
                1.0 - elapsed,
            )

            if self._stop_event.wait(
                sleep_time
            ):
                break

        print(
            "[SUMO LOOP] "
            "Background simulation loop berhenti."
        )

    # ============================================================
    # EXTRACT APPROACH
    # ============================================================

    @staticmethod
    def _extract_approach(
        vehicle_id: str,
    ) -> str:

        parts = str(
            vehicle_id
        ).split("_")

        for approach in (
            "north",
            "south",
            "east",
            "west",
        ):

            if approach in parts:
                return approach

        return "unknown"

    # ============================================================
    # GET METRICS
    # ============================================================

    def get_metrics(
        self,
    ) -> dict[str, Any]:

        if self.traci is None:

            return {
                "durationSeconds": 0,
                "spawnedVehicles": 0,
                "departedVehicles": 0,
                "arrivedVehicles": 0,
                "activeVehicles": 0,
                "averageWaitingTimeSeconds": 0.0,
                "departedByApproach": {},
                "arrivedByApproach": {},
                "simulationTimeSeconds": 0.0,
                "running": False,
                "lastError": self.last_error,
            }

        with self._traci_lock:

            try:

                # --------------------------------------------
                # ACTIVE VEHICLES
                # --------------------------------------------

                active_vehicles = (
                    self.traci
                    .vehicle
                    .getIDCount()
                )

                # --------------------------------------------
                # WAITING TIME
                # --------------------------------------------

                waiting_values: list[
                    float
                ] = []

                for vehicle_id in (
                    self.traci
                    .vehicle
                    .getIDList()
                ):

                    try:

                        waiting = (
                            self.traci
                            .vehicle
                            .getAccumulatedWaitingTime(
                                vehicle_id
                            )
                        )

                        waiting_values.append(
                            float(waiting)
                        )

                    except (
                        self.traci
                        .TraCIException
                    ):

                        continue

                average_waiting = (
                    sum(waiting_values)
                    / len(waiting_values)
                    if waiting_values
                    else 0.0
                )

                # --------------------------------------------
                # SIMULATION TIME
                # --------------------------------------------

                simulation_time = (
                    self.traci
                    .simulation
                    .getTime()
                )

                # --------------------------------------------
                # RESULT
                # --------------------------------------------

                return {
                    "durationSeconds": int(
                        simulation_time
                    ),
                    "spawnedVehicles": (
                        self.spawned_total
                    ),
                    "departedVehicles": sum(
                        self.departed_total.values()
                    ),
                    "arrivedVehicles": sum(
                        self.arrived_total.values()
                    ),
                    "activeVehicles": (
                        active_vehicles
                    ),
                    "averageWaitingTimeSeconds": round(
                        average_waiting,
                        2,
                    ),
                    "departedByApproach": dict(
                        self.departed_total
                    ),
                    "arrivedByApproach": dict(
                        self.arrived_total
                    ),
                    "simulationTimeSeconds": (
                        simulation_time
                    ),
                    "running": self.running,
                    "lastError": self.last_error,
                }

            except Exception as exc:

                self.last_error = str(exc)

                return {
                    "durationSeconds": int(
                        self.last_simulation_time
                    ),
                    "spawnedVehicles": (
                        self.spawned_total
                    ),
                    "departedVehicles": sum(
                        self.departed_total.values()
                    ),
                    "arrivedVehicles": sum(
                        self.arrived_total.values()
                    ),
                    "activeVehicles": 0,
                    "averageWaitingTimeSeconds": 0.0,
                    "departedByApproach": dict(
                        self.departed_total
                    ),
                    "arrivedByApproach": dict(
                        self.arrived_total
                    ),
                    "simulationTimeSeconds": (
                        self.last_simulation_time
                    ),
                    "running": False,
                    "lastError": self.last_error,
                }

    # ============================================================
    # IS RUNNING
    # ============================================================

    def is_running(
        self,
    ) -> bool:

        return (
            self.running
            and self.traci is not None
        )

    # ============================================================
    # CLOSE
    # ============================================================

    def close(
        self,
    ) -> None:

        print(
            "[SUMO] Closing realtime controller..."
        )

        # ========================================================
        # SIGNAL BACKGROUND LOOP TO STOP
        # ========================================================

        self._stop_event.set()

        self.running = False

        # ========================================================
        # WAIT BACKGROUND THREAD
        # ========================================================

        thread = (
            self._simulation_thread
        )

        if (
            thread is not None
            and thread.is_alive()
            and thread
            is not threading.current_thread()
        ):

            thread.join(
                timeout=3.0
            )

        self._simulation_thread = None

        # ========================================================
        # CLOSE TRACI
        # ========================================================

        if self.traci is not None:

            try:

                with self._traci_lock:

                    self.traci.close()

            except Exception as exc:

                print(
                    "[SUMO] Error ketika "
                    "menutup TraCI:"
                )

                print(exc)

            finally:

                self.traci = None

        # ========================================================
        # RESET STATE
        # ========================================================

        self.last_error = None

        print(
            "[SUMO] Realtime controller closed."
        )