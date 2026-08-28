from __future__ import annotations

import random
import sys
import threading
import time
import logging
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SumoController:
    """
    Long-running SUMO Controller.

    SUMO hanya dijalankan SATU KALI.

    Setelah start():

        SUMO
          |
          v
    background simulation loop
          |
          +---- simulationStep()
          |
          +---- update metrics

    TrafficState baru dapat dikirim kapan saja melalui:

        inject_demand()

    TraCI hanya boleh diakses melalui _traci_lock.
    """

    # ============================================================
    # PROJECT PATH
    # ============================================================

    PROJECT_ROOT = Path(__file__).resolve().parents[4]

    SIMULATION_DIR = PROJECT_ROOT / "simulation"
    SIMULATION_VENV_DIR = SIMULATION_DIR / ".venv"

    # SENGAJA pakai sys.prefix (root venv Python yang lagi jalan),
    # BUKAN simulation/.venv -- backend/requirements.txt sudah
    # mendeklarasikan traci/sumolib/eclipse-sumo sebagai dependency
    # backend sendiri (dipasang 25 Agustus 2026), dan simulation/.venv
    # tidak selalu ada di tiap mesin dev (CLAUDE.md: venv itu dibuat
    # terpisah, khusus buat script simulation/, bukan backend). Hardcode
    # ke simulation/.venv sebelumnya bikin SumoController gagal cari
    # binary SUMO di mesin mana pun yang venv simulation/-nya belum
    # dibuat, walau backend/.venv sendiri sudah punya SUMO lengkap.
    SUMO_VENV_DIR = Path(sys.prefix)

    SUMO_SCRIPTS_DIR = SUMO_VENV_DIR / "Scripts"

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

    CYCLE_ORDER = ("north", "east", "south", "west")
    GREEN_STATE_BY_APPROACH = {
        "south": "GGGggrrrrrrrrrrrrrrr",
        "east": "rrrrrGGGggrrrrrrrrrr",
        "north": "rrrrrrrrrrGGGggrrrrr",
        "west": "rrrrrrrrrrrrrrrGGGgg",
    }
    YELLOW_STATE_BY_APPROACH = {
        "south": "yyyyyrrrrrrrrrrrrrrr",
        "east": "rrrrryyyyyrrrrrrrrrr",
        "north": "rrrrrrrrrryyyyyrrrrr",
        "west": "rrrrrrrrrrrrrrryyyyy",
    }

    @staticmethod
    def _hide_windows_for_process(process_id: int) -> None:
        """Sembunyikan window SUMO-GUI; renderer tetap hidup untuk screenshot."""
        if os.name != "nt" or process_id <= 0:
            return

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            enum_callback_type = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )

            def hide_if_owned(hwnd: int, _lparam: int) -> bool:
                owner_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
                if owner_pid.value == process_id:
                    user32.ShowWindow(hwnd, 0)  # SW_HIDE
                return True

            user32.EnumWindows(enum_callback_type(hide_if_owned), 0)
        except Exception as exc:
            logger.warning("Gagal menyembunyikan window SUMO-GUI: %s", exc)

    # ============================================================
    # INIT
    # ============================================================

    def __init__(
        self,
        sumo_binary: str | Path | None = None,
        config_file: str | Path | None = None,
        seed: int | None = None,
        scenario: str = "Baseline",
    ) -> None:
    
        os.makedirs("cache/simulation", exist_ok=True)

        # --------------------------------------------------------
        # SUMO BINARY
        # --------------------------------------------------------

        self.sumo_binary = (
            Path(sumo_binary)
            if sumo_binary is not None
            else self._default_sumo_binary()
        )

        # --------------------------------------------------------
        # CONFIG
        # --------------------------------------------------------

        self.config_file = (
            Path(config_file)
            if config_file is not None
            else self.DEFAULT_CONFIG_FILE
        )

        self.seed = seed
        self.scenario = scenario

        # --------------------------------------------------------
        # TRACI
        # --------------------------------------------------------

        self.traci = None

        # --------------------------------------------------------
        # RUNNING STATE
        # --------------------------------------------------------

        self.running = False
        self.paused = False
        self.is_gui = False

        self._stop_event = (
            threading.Event()
        )

        self._simulation_thread: (
            threading.Thread | None
        ) = None

        # --------------------------------------------------------
        # TRACI LOCK
        # --------------------------------------------------------

        self._traci_lock = (
            threading.RLock()
        )

        # --------------------------------------------------------
        # RANDOM
        # --------------------------------------------------------

        self._rng = random.Random(
            seed
        )

        # --------------------------------------------------------
        # METRICS
        # --------------------------------------------------------

        self.spawned_total = 0

        self.departed_total = (
            defaultdict(int)
        )

        self.arrived_total = (
            defaultdict(int)
        )

        self.last_simulation_time = 0.0

        self.last_error: str | None = None

        self.active_vehicles_data: list[dict[str, Any]] = []
        
        self.active_signals_data: list[dict[str, Any]] = []

        # --------------------------------------------------------
        # VEHICLE COUNTER
        # --------------------------------------------------------

        self._vehicle_counter = 0

        # --------------------------------------------------------
        # VEHICLE -> APPROACH
        # --------------------------------------------------------

        self._vehicle_approach: dict[
            str,
            str,
        ] = {}
        self._vehicle_type: dict[str, str] = {}
        self.detected_vehicle_count = 0
        self.traffic_timestamp: str | None = None
        self.active_cycle_plan: dict[str, Any] | None = None
        self._last_screenshot_at = 0.0

        # --------------------------------------------------------
        # CURRENT DEMAND
        # --------------------------------------------------------

        self.current_demand: dict[
            str,
            dict[str, int],
        ] = {}

        # --------------------------------------------------------
        # ACTIVE VEHICLES POSITIONS
        # --------------------------------------------------------

        self.active_vehicles_data: list[
            dict[str, Any]
        ] = []

    # ============================================================
    # DEFAULT SUMO BINARY
    # ============================================================

    @classmethod
    def _default_sumo_binary(
        cls,
    ) -> Path:

        candidates = [

            cls.SUMO_SCRIPTS_DIR
            / "sumo.exe",

            cls.SUMO_BIN_DIR
            / "sumo.exe",

            cls.SIMULATION_VENV_DIR / "Scripts" / "sumo.exe",

            cls.SIMULATION_VENV_DIR
            / "Lib" / "site-packages" / "sumo" / "bin" / "sumo.exe",
        ]

        for candidate in candidates:

            if candidate.exists():
                return candidate

        return Path("sumo")

    # ============================================================
    # DEFAULT SUMO GUI
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

            cls.SIMULATION_VENV_DIR / "Scripts" / "sumo-gui.exe",

            cls.SIMULATION_VENV_DIR
            / "Lib" / "site-packages" / "sumo" / "bin" / "sumo-gui.exe",
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
                "[SUMO] Controller sudah berjalan."
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
                "Pastikan package traci sudah terinstall."
            ) from exc

        # ========================================================
        # CONFIG CHECK
        # ========================================================

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
        # BINARY CHECK
        # ========================================================

        if (
            isinstance(binary, Path)
            and not binary.exists()
            and binary.name
            in {
                "sumo.exe",
                "sumo-gui.exe",
            }
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

            "--start",
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

        if gui:
            # Renderer SUMO-GUI tetap dipakai untuk screenshot TraCI, tetapi
            # jendelanya ditempatkan di luar desktop. Frame hanya dikonsumsi
            # oleh dashboard melalui endpoint stream.
            command.extend(["--window-pos", "-32000,-32000", "--window-size", "960,540"])

        # ========================================================
        # PATH RESOLUTION & LOGGING
        # ========================================================

        config_path = Path(self.config_file)
        
        logger.info("STEP 1: Starting SUMO")
        logger.info(f"SUMO binary: {binary}")
        logger.info(f"SUMO config: {config_path}")
        logger.info(f"Exists: {config_path.exists()}")
        logger.info(f"Absolute: {config_path.resolve()}")

        if not config_path.exists():
            raise RuntimeError(
                f"Failed to start SUMO: sumocfg file not found at {config_path.resolve()}"
            )

        print()
        print("=" * 70)
        print("STARTING SUMO")
        print("=" * 70)

        print(
            "Command:",
            " ".join(command),
        )

        print("=" * 70)
        
        # Cleanup any stuck connection in the default label
        try:
            import traci
            traci.close()
        except Exception:
            pass
            
        try:
            if gui and os.name == "nt":
                import traci.main as traci_main

                original_popen = traci_main.subprocess.Popen

                def hidden_popen(*args: Any, **kwargs: Any):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    kwargs["startupinfo"] = startupinfo
                    return original_popen(*args, **kwargs)

                traci_main.subprocess.Popen = hidden_popen
                try:
                    traci.start(command)
                finally:
                    traci_main.subprocess.Popen = original_popen
            else:
                traci.start(command)
            logger.info("STEP 2: TraCI connected")
            
            tls_ids = traci.trafficlight.getIDList()
            logger.info(f"STEP 3: Traffic lights = {tls_ids}")
            
            traci.simulationStep()
            logger.info("STEP 4: Simulation step successful")

            if gui:
                # Rasio 16:9 dan crop lebih dekat agar memenuhi card web tanpa
                # letterbox, tetapi keempat mulut simpang tetap terlihat.
                traci.gui.setBoundary("View #0", 240.63, 479.635, 380.63, 558.385)
                connection = traci.getConnection()
                process = getattr(connection, "_process", None)
                if process is not None:
                    self._hide_windows_for_process(process.pid)
            
        except Exception as exc:
            logger.exception("Failed to start SUMO through TraCI")
            try:
                traci.close()
            except Exception:
                pass

            self.traci = None
            self.running = False
            self.last_error = str(exc)

            raise RuntimeError(
                f"Failed to start SUMO: {exc}\n\n"
                f"Binary : {binary}\n"
                f"Config : {self.config_file}\n"
                f"Command: {' '.join(command)}\n"
            ) from exc

        # ========================================================
        # SUCCESS
        # ========================================================

        self.traci = traci
        self.running = True
        self.is_gui = gui
        self.last_error = None
        self._stop_event.clear()

        # ========================================================
        # VEHICLE TYPES
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

            raise RuntimeError(
                "SUMO berhasil start tetapi gagal "
                "membuat vehicle types.\n\n"
                f"Error: {exc}"
            ) from exc

        # Loop harus dimulai untuk semua mode (termasuk dashboard realtime).
        # Sebelumnya blok ini tidak sengaja berada di apply_scenario_logic(),
        # sehingga controller berstatus running tetapi waktu tetap 0.
        if self._simulation_thread is None or not self._simulation_thread.is_alive():
            self._simulation_thread = threading.Thread(
                target=self._simulation_loop,
                name="sumo-realtime-loop",
                daemon=True,
            )
            self._simulation_thread.start()

        print("SUMO berhasil terhubung melalui TraCI.")
        print("SUMO realtime loop berhasil dimulai.")
        print("=" * 70)

    def apply_scenario_logic(
        self,
        logic_phases: list,
        scenario_id: str,
        tls_id: str = "SIMPANG_CENTER",
    ) -> None:
        """Suntikkan dynamic phase timing ke SUMO TraCI."""
        if self.traci is None or not self.running:
            return

        with self._traci_lock:
            try:
                logic = self.traci.trafficlight.Logic(
                    f"smarttwin-{scenario_id.lower()}", 0, 0, phases=logic_phases
                )
                self.traci.trafficlight.setProgramLogic(tls_id, logic)
                self.traci.trafficlight.setProgram(tls_id, logic.programID)
                self.traci.trafficlight.setPhase(tls_id, 0)
                logger.info(
                    f"Berhasil menerapkan scenario '{scenario_id}' pada SUMO TLS {tls_id} "
                    f"dengan siklus: {[p.duration for p in logic_phases]} s"
                )
            except Exception as exc:
                logger.error(f"Gagal set program logic TraCI: {exc}")

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

            self.EDGE_HULU[
                approach
            ],

            self.EDGE_MASUK[
                approach
            ],

            self.EDGE_KELUAR[
                destination
            ],
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

            self._vehicle_approach[
                vehicle_id
            ] = approach
            self._vehicle_type[vehicle_id] = vehicle_type

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

                # ------------------------------------------------
                # SAVE CURRENT DEMAND
                # ------------------------------------------------

                self.current_demand[
                    approach
                ] = vehicle_counts

                # ------------------------------------------------
                # SPAWN VEHICLES
                # ------------------------------------------------

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

    def sync_demand(
        self,
        demand: list[dict[str, Any]],
        *,
        traffic_timestamp: str | None = None,
    ) -> dict[str, int]:
        """Samakan kendaraan SmartTwin dengan snapshot deteksi terbaru.

        Tidak pernah membuat demand dari route demo. Kendaraan yang berlebih
        terhadap snapshot dihapus; kekurangan ditambahkan melalui TraCI.
        """
        if self.traci is None:
            raise RuntimeError("SUMO belum dijalankan.")

        added = 0
        removed = 0
        target_total = sum(
            max(0, int(item.get("targetVehicleCount", 0) or 0))
            for item in demand
        )

        with self._traci_lock:
            for item in demand:
                approach = str(item.get("approach", "")).lower().strip()
                if approach not in self.VALID_APPROACHES:
                    continue

                target = max(0, int(item.get("targetVehicleCount", 0) or 0))
                raw_counts = {
                    "motorcycle": max(0, int(item.get("motorcycleCount", 0) or 0)),
                    "car": max(0, int(item.get("carCount", 0) or 0)),
                    "bus": max(0, int(item.get("busCount", 0) or 0)),
                    "truck": max(0, int(item.get("truckCount", 0) or 0)),
                }
                raw_total = sum(raw_counts.values())
                if target > 0 and raw_total == 0:
                    raw_counts["car"] = target
                    raw_total = target

                # Alokasi kelas diskalakan agar jumlah persis densityIndex/card.
                desired = {name: 0 for name in self.VEHICLE_TYPES}
                remaining = target
                if raw_total > 0:
                    for name in list(desired)[:-1]:
                        value = round(target * raw_counts[name] / raw_total)
                        desired[name] = min(remaining, value)
                        remaining -= desired[name]
                    desired[list(desired)[-1]] = remaining

                for vehicle_type, wanted in desired.items():
                    existing = [
                        vehicle_id
                        for vehicle_id, vehicle_approach in self._vehicle_approach.items()
                        if vehicle_approach == approach
                        and self._vehicle_type.get(vehicle_id) == vehicle_type
                    ]
                    for vehicle_id in existing[wanted:]:
                        try:
                            self.traci.vehicle.remove(vehicle_id)
                            self._vehicle_approach.pop(vehicle_id, None)
                            self._vehicle_type.pop(vehicle_id, None)
                            removed += 1
                        except self.traci.TraCIException:
                            pass
                    for _ in range(max(0, wanted - len(existing))):
                        if self.add_vehicle(vehicle_type=vehicle_type, approach=approach):
                            added += 1

                self.current_demand[approach] = desired

            self.detected_vehicle_count = target_total
            self.traffic_timestamp = traffic_timestamp

        return {"added": added, "removed": removed, "total": target_total}

    def apply_cycle_plan(self, cycle_plan: dict[str, Any]) -> None:
        """Pasang siklus N-E-S-W sebagai program TLS nyata di TraCI."""
        if self.traci is None:
            raise RuntimeError("SUMO belum dijalankan.")

        phase_by_approach = {
            str(phase.get("approach", "")).lower(): phase
            for phase in cycle_plan.get("phases", [])
        }
        if set(phase_by_approach) != set(self.CYCLE_ORDER):
            raise ValueError("CyclePlan wajib berisi north, east, south, west.")

        normalized_plan = {
            **cycle_plan,
            "phases": [phase_by_approach[name] for name in self.CYCLE_ORDER],
        }
        if self.active_cycle_plan == normalized_plan:
            return

        with self._traci_lock:
            tls_ids = list(self.traci.trafficlight.getIDList())
            if not tls_ids:
                raise RuntimeError("Traffic light SUMO tidak ditemukan.")
            tls_id = tls_ids[0]
            phases = []
            for approach in self.CYCLE_ORDER:
                phase = phase_by_approach[approach]
                green = max(1, int(phase.get("greenSeconds", 1)))
                yellow = max(1, int(phase.get("yellowSeconds", 4)))
                phases.append(self.traci.trafficlight.Phase(
                    green, self.GREEN_STATE_BY_APPROACH[approach]
                ))
                phases.append(self.traci.trafficlight.Phase(
                    yellow, self.YELLOW_STATE_BY_APPROACH[approach]
                ))
            program_id = "smarttwin-live"
            logic = self.traci.trafficlight.Logic(program_id, 0, 0, phases=phases)
            self.traci.trafficlight.setProgramLogic(tls_id, logic)
            self.traci.trafficlight.setProgram(tls_id, program_id)
            self.traci.trafficlight.setPhase(tls_id, 0)
            self.active_cycle_plan = normalized_plan

    # ============================================================
    # SIMULATION LOOP
    # ============================================================

    def _simulation_loop(
        self,
    ) -> None:

        print(
            "[SUMO LOOP] "
            "Background simulation loop aktif."
        )

        last_debug_second = -1

        while not self._stop_event.is_set():

            started_at = (
                time.perf_counter()
            )

            try:

                with self._traci_lock:

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

                    # ==========================================
                    # SIMULATION STEP
                    # ==========================================

                    if not self.paused:
                        self.traci.simulationStep()

                        # ==========================================
                        # SIMULATION TIME
                        # ==========================================

                        self.last_simulation_time = (
                            self.traci.simulation.getTime()
                        )

                    # ==========================================
                    # DEPARTED
                    # ==========================================

                    if not self.paused:
                        departed_ids = (
                            self.traci
                            .simulation
                            .getDepartedIDList()
                        )

                        for vehicle_id in departed_ids:

                            approach = (
                                self._vehicle_approach.get(
                                    vehicle_id,
                                    "unknown",
                                )
                            )

                            self.departed_total[
                                approach
                            ] += 1

                    # ==========================================
                    # ARRIVED
                    # ==========================================

                    if not self.paused:
                        arrived_ids = (
                            self.traci
                            .simulation
                            .getArrivedIDList()
                        )

                        for vehicle_id in arrived_ids:

                            approach = (
                                self._vehicle_approach.pop(
                                    vehicle_id,
                                    "unknown",
                                )
                            )
                            self._vehicle_type.pop(vehicle_id, None)

                            self.arrived_total[
                                approach
                            ] += 1

                    # ==========================================
                    # ACTIVE VEHICLES POSITIONS
                    # ==========================================
                    
                    current_vehicles_data = []
                    
                    for vehicle_id in self.traci.vehicle.getIDList():
                        try:
                            x, y = self.traci.vehicle.getPosition(vehicle_id)
                            angle = self.traci.vehicle.getAngle(vehicle_id)
                            vclass = self.traci.vehicle.getVehicleClass(vehicle_id)
                            
                            current_vehicles_data.append({
                                "id": vehicle_id,
                                "x": x,
                                "y": y,
                                "angle": angle,
                                "type": vclass,
                            })
                        except self.traci.TraCIException:
                            pass
                            
                    self.active_vehicles_data = current_vehicles_data

                    # ==========================================
                    # TRAFFIC LIGHT STATE
                    # ==========================================
                    
                    current_signals_data = []
                    
                    for tls_id in self.traci.trafficlight.getIDList():
                        try:
                            state_str = self.traci.trafficlight.getRedYellowGreenState(tls_id)
                            phase = self.traci.trafficlight.getPhase(tls_id)
                            next_switch = self.traci.trafficlight.getNextSwitch(tls_id)
                            
                            remaining_seconds = max(0, next_switch - self.last_simulation_time)
                            
                            # Jangan menebak arah dari nomor index fase. Baca
                            # raw state yang benar-benar sedang diterapkan SUMO
                            # agar label dashboard dan lampu/jalur kendaraan
                            # selalu menunjuk approach yang sama.
                            active_approach = next(
                                (
                                    approach
                                    for approach, value in self.GREEN_STATE_BY_APPROACH.items()
                                    if value == state_str
                                ),
                                None,
                            )
                            phase_state = "GREEN"
                            if active_approach is None:
                                active_approach = next(
                                    (
                                        approach
                                        for approach, value in self.YELLOW_STATE_BY_APPROACH.items()
                                        if value == state_str
                                    ),
                                    self.CYCLE_ORDER[(phase // 2) % 4],
                                )
                                phase_state = "YELLOW"
                                
                            current_signals_data.append({
                                "trafficLightId": tls_id,
                                "state": phase_state,
                                "phase": phase,
                                "activeApproach": active_approach,
                                "remainingSeconds": remaining_seconds,
                                "rawState": state_str,
                            })
                        except self.traci.TraCIException:
                            pass
                            
                    self.active_signals_data = current_signals_data

                    # ==========================================
                    # SCREENSHOT (MJPEG STREAM)
                    # ==========================================
                    if self.is_gui and time.monotonic() - self._last_screenshot_at >= 0.25:
                        try:
                            frame_path = self.PROJECT_ROOT / "cache" / "simulation" / "frame.jpg"
                            frame_path.parent.mkdir(parents=True, exist_ok=True)
                            self.traci.gui.screenshot("View #0", str(frame_path))
                            self._last_screenshot_at = time.monotonic()
                        except Exception:
                            pass

                    # ==========================================
                    # SLEEP FOR NEXT STEP
                    # ==========================================
                    
                    # ==========================================
                    # DEBUG
                    # ==========================================

                    current_second = int(
                        self.last_simulation_time
                    )

                    if (
                        current_second % 10 == 0
                        and current_second
                        != last_debug_second
                    ):

                        last_debug_second = (
                            current_second
                        )

                        try:

                            active_count = (
                                self.traci
                                .vehicle
                                .getIDCount()
                            )

                            print(
                                "[SUMO LOOP] "
                                f"time="
                                f"{current_second}s "
                                f"active="
                                f"{active_count} "
                                f"spawned="
                                f"{self.spawned_total}"
                            )

                        except Exception:
                            pass

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
                    "Running flag:",
                    self.running,
                )

                print(
                    "TraCI object:",
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

                # ==============================================
                # ACTIVE VEHICLES
                # ==============================================

                active_vehicles = (
                    self.traci
                    .vehicle
                    .getIDCount()
                )

                # ==============================================
                # WAITING TIME
                # ==============================================

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

                    except self.traci.TraCIException:

                        continue

                average_waiting = (

                    sum(waiting_values)
                    / len(waiting_values)

                    if waiting_values

                    else 0.0
                )

                # ==============================================
                # SIMULATION TIME
                # ==============================================

                simulation_time = (
                    self.traci
                    .simulation
                    .getTime()
                )

                # ==============================================
                # RESULT
                # ==============================================

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

                    "running": (
                        self.running
                    ),

                    "lastError": (
                        self.last_error
                    ),
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

                    "lastError": (
                        self.last_error
                    ),
                }

    # ============================================================
    # PAUSE / RESUME
    # ============================================================

    def pause(self) -> None:
        if self.running:
            self.paused = True

    def resume(self) -> None:
        if self.running:
            self.paused = False

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
            "[SUMO] "
            "Closing realtime controller..."
        )

        # ========================================================
        # STOP LOOP
        # ========================================================

        self._stop_event.set()

        self.running = False

        # ========================================================
        # WAIT THREAD
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

        # Screenshot/GUI driver kadang tertahan di panggilan TraCI sehingga
        # thread belum keluar setelah timeout. Jangan menunggu lock selamanya;
        # hentikan process renderer lalu biarkan cleanup state diteruskan.
        thread_still_alive = thread is not None and thread.is_alive()
        if thread_still_alive and self.traci is not None:
            try:
                connection = self.traci.getConnection()
                process = getattr(connection, "_process", None)
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2.0)
            except Exception as exc:
                logger.warning("Gagal menghentikan paksa renderer SUMO: %s", exc)

        # ========================================================
        # CLOSE TRACI
        # ========================================================

        if self.traci is not None and not thread_still_alive:

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

        elif thread_still_alive:
            self.traci = None

        # ========================================================
        # RESET
        # ========================================================

        self._vehicle_approach.clear()
        self._vehicle_type.clear()

        self.current_demand.clear()

        self.last_error = None
        self.active_vehicles_data.clear()
        self.active_signals_data.clear()

        print(
            "SUMO realtime controller closed."
        )
