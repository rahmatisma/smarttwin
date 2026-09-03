from __future__ import annotations

import random
import sys
import threading
import time
import logging
import os
import subprocess
from collections import defaultdict, deque
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

    # SENGAJA pakai sys.prefix (venv Python yang lagi jalan), bukan
    # hardcode ke simulation/.venv -- sejak backend, simulation, dan
    # decision_engine digabung jadi satu venv di root repo (30 Agustus
    # 2026), requirements.txt root sudah mendeklarasikan
    # traci/sumolib/eclipse-sumo, jadi sys.prefix selalu benar tidak
    # peduli dari venv mana proses ini dijalankan.
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

    # Screenshot harus dibuat langsung pada rasio card dashboard. Mengandalkan
    # ukuran window SUMO-GUI menghasilkan viewport sekitar 950x278 di Windows;
    # ketika di-stretch oleh browser hasilnya terlihat pecah.
    STREAM_FRAME_WIDTH = 1280
    STREAM_FRAME_HEIGHT = 720

    # Area kamera ketat di sekitar simpang supaya framing mirip CCTV asli.
    # Format override: xmin,ymin,xmax,ymax, contoh di .env.example (root repo).
    # Kendaraan disisipkan dengan departPos="last" (lihat add_vehicle) supaya
    # antrean menumpuk dari mulut simpang ke belakang dan tetap masuk crop --
    # bukan tersebar jauh di ruas pendekat Selatan yang 515 m di peta OSM.
    DEFAULT_STREAM_VIEW_BOUNDARY = (240.63, 479.635, 380.63, 558.385)

    # Berapa lama clock CCTV (dan penguncian fase TLS ke situ) masih dianggap
    # sah setelah POST /sync-clock terakhir. Frontend mengirim tiap ~1 dtk;
    # kalau berhenti (video buffering, tab background, pause) clock BEKU di
    # posisi terakhir alih-alih lari di kecepatan wall-clock -- sebelumnya
    # get_display_time() menambah (monotonic - synced_at) tanpa batas sehingga
    # fase lampu SUMO ngebut jauh mendahului video.
    CAMERA_CLOCK_STALE_SECONDS = 4.0

    @classmethod
    def _stream_view_boundary(cls) -> tuple[float, float, float, float]:
        raw_boundary = os.getenv("SMARTTWIN_SUMO_VIEW_BOUNDARY", "").strip()
        if not raw_boundary:
            return cls.DEFAULT_STREAM_VIEW_BOUNDARY

        try:
            boundary = tuple(float(value.strip()) for value in raw_boundary.split(","))
        except ValueError:
            logger.warning(
                "SMARTTWIN_SUMO_VIEW_BOUNDARY tidak valid; memakai default %s",
                cls.DEFAULT_STREAM_VIEW_BOUNDARY,
            )
            return cls.DEFAULT_STREAM_VIEW_BOUNDARY

        if len(boundary) != 4 or boundary[0] >= boundary[2] or boundary[1] >= boundary[3]:
            logger.warning(
                "SMARTTWIN_SUMO_VIEW_BOUNDARY harus xmin,ymin,xmax,ymax; "
                "memakai default %s",
                cls.DEFAULT_STREAM_VIEW_BOUNDARY,
            )
            return cls.DEFAULT_STREAM_VIEW_BOUNDARY

        return boundary

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

    @classmethod
    def _keep_renderer_window_hidden(cls, process_id: int) -> None:
        """Tangkap window GUI yang baru dibuat sesudah TraCI tersambung."""
        if os.name != "nt" or process_id <= 0:
            return

        def hide_repeatedly() -> None:
            # SUMO-GUI kadang membuat ulang top-level window sesaat setelah
            # start. Satu ShowWindow terlalu dini sehingga popup masih muncul.
            for _ in range(30):
                cls._hide_windows_for_process(process_id)
                time.sleep(0.1)

        threading.Thread(
            target=hide_repeatedly,
            name="sumo-gui-window-hider",
            daemon=True,
        ).start()

    # ============================================================
    # INIT
    # ============================================================

    def __init__(
        self,
        sumo_binary: str | Path | None = None,
        config_file: str | Path | None = None,
        seed: int | None = None,
        scenario: str = "Baseline",
        context: str = "default",
    ) -> None:

        os.makedirs("cache/simulation", exist_ok=True)

        # --------------------------------------------------------
        # CONTEXT
        # --------------------------------------------------------
        # Membedakan instance SUMO ini dari instance lain yang mungkin
        # jalan bersamaan (mis. "dashboard" vs "digitaltwin") -- dipakai
        # untuk nama file screenshot supaya keduanya tidak saling timpa.
        # Lihat get_simulation_frame()/stream_simulation() di sisi API.

        self.context = context

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

        # Waktu tampilan mengikuti siklus CCTV. Waktu internal SUMO tetap
        # monoton supaya kendaraan terus berjalan ketika rekaman mengulang.
        self._camera_clock_time: float | None = None
        self._camera_clock_duration: float | None = None
        self._camera_clock_synced_at: float | None = None

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

        # --------------------------------------------------------
        # LIVE TRAFFIC METRICS (buat kartu statistik Digital Twin)
        # --------------------------------------------------------

        self.live_queue_length_veh: int = 0
        self.live_queue_busiest_approach: str | None = None
        self.live_total_queue_length_veh: int = 0
        self.live_avg_delay_seconds: float = 0.0
        self.live_throughput_veh_per_min: float = 0.0
        self.live_visible_vehicle_count: int = 0
        self.live_last_sync_failed_insertions: int = 0
        self.live_last_sync_failed_by_approach: dict[str, int] = {}

        # Timestamp simulasi (detik) tiap kendaraan "arrived", dipakai
        # menghitung laju 60 detik TERAKHIR -- bukan rata-rata sejak
        # simulasi mulai (itu nyaris tidak bergerak begitu simulasi
        # sudah jalan lama, dan tidak mencerminkan kondisi "sekarang").
        self._arrival_timeline: deque[float] = deque()

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
    # X DISPLAY PREFLIGHT (sumo-gui, POSIX)
    # ============================================================

    @staticmethod
    def _ensure_display_for_gui() -> None:
        """Pastikan sumo-gui punya X display sebelum di-spawn.

        Di pod RunPod headless, sumo-gui butuh virtual display Xvfb
        (``DISPLAY=:99``, disiapkan ``scripts/runpod_setup.sh``). Kalau
        backend dijalankan tanpa ``source .venv/bin/activate``, ``DISPLAY``
        kosong -> sumo-gui langsung exit ("FXApp::openDisplay: unable to
        open display") dan TraCI cuma melihat "TraCI server already
        finished". Deteksi lebih awal: pakai X server yang sudah jalan bila
        ketemu, kalau tidak lempar pesan yang jelas (bukan traceback TraCI).
        """

        if os.name == "nt":
            return

        if os.environ.get("DISPLAY"):
            return

        socket_dir = Path("/tmp/.X11-unix")
        sockets = (
            sorted(socket_dir.glob("X*"))
            if socket_dir.is_dir()
            else []
        )

        if sockets:

            display = ":" + sockets[0].name[1:]
            os.environ["DISPLAY"] = display

            logger.warning(
                "DISPLAY belum diset -- memakai X server yang terdeteksi "
                "(%s). Jalankan `source .venv/bin/activate` sebelum uvicorn "
                "supaya environment SUMO lengkap.",
                display,
            )

            return

        raise RuntimeError(
            "sumo-gui butuh X display tapi DISPLAY tidak diset dan tidak "
            "ada Xvfb yang jalan. Di pod RunPod: jalankan "
            "`bash scripts/runpod_setup.sh` (menyalakan Xvfb :99), lalu "
            "start backend dengan `source .venv/bin/activate` aktif."
        )

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

            self._ensure_display_for_gui()

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

            # Tanpa ini, sumo-gui TIDAK otomatis keluar/nutup window
            # begitu koneksi TraCI ditutup (traci.close() di close())
            # -- ia cuma berhenti melangkah dan window-nya nyangkut
            # menunggu diklik X manual. Karena window-nya sengaja
            # ditaruh di luar layar (--window-pos di bawah), tanpa
            # flag ini window itu jadi proses zombie yang harus
            # dicari lewat Alt+Tab dulu baru bisa ditutup.
            "--quit-on-end",
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
        
        # Bersihkan koneksi macet KHUSUS label context ini (sisa crash
        # sebelumnya) -- BUKAN traci.close() global. traci.close() global
        # menutup "current connection" modul TraCI siapa pun, jadi kalau
        # context "dashboard" sedang jalan lalu context "digitaltwin" mau
        # start, ini dulu yang mematikan simulasi dashboard. Baca lebih
        # lengkap di komentar dekat `conn = traci.getConnection(...)` di
        # bawah.
        try:
            from traci import connection as traci_connection
            if traci_connection.has(self.context):
                traci_connection.get(self.context).close()
        except Exception:
            pass

        conn = None
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
                    traci.start(command, label=self.context)
                finally:
                    traci_main.subprocess.Popen = original_popen
            else:
                traci.start(command, label=self.context)
            logger.info("STEP 2: TraCI connected")

            # Pegang koneksi milik context INI secara eksplisit lewat label,
            # bukan modul `traci` bare -- modul cuma tahu satu "current
            # connection" global yang gampang ketiban switch tiap kali
            # context lain start()/simulationStep() di thread lain (tiap
            # context punya thread loop-nya sendiri, lihat _simulation_loop).
            # Semua panggilan TraCI controller ini sesudah titik ini WAJIB
            # lewat conn (disimpan sebagai self.traci), tidak pernah lewat
            # modul traci lagi, supaya dua context tidak saling menimpa
            # koneksi satu sama lain.
            conn = traci.getConnection(self.context)
            # Banyak tempat lain di file ini menulis `self.traci.TraCIException`
            # seolah self.traci adalah modul traci (yang punya atribut itu).
            # Objek koneksi tidak otomatis punya atribut itu, jadi ditempel
            # manual sekali di sini supaya titik-titik itu tidak perlu diubah.
            conn.TraCIException = traci.TraCIException

            tls_ids = conn.trafficlight.getIDList()
            logger.info(f"STEP 3: Traffic lights = {tls_ids}")

            conn.simulationStep()
            logger.info("STEP 4: Simulation step successful")

            if gui:
                # Crop dilakukan oleh kamera SUMO, bukan CSS browser, sehingga
                # area yang dipilih tetap dirender tajam pada resolusi stream.
                conn.gui.setBoundary("View #0", *self._stream_view_boundary())
                process = getattr(conn, "_process", None)
                if process is not None:
                    self._keep_renderer_window_hidden(process.pid)

        except Exception as exc:
            logger.exception("Failed to start SUMO through TraCI")
            try:
                if conn is not None:
                    conn.close()
                else:
                    from traci import connection as traci_connection
                    if traci_connection.has(self.context):
                        traci_connection.get(self.context).close()
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

        self.traci = conn
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

            # departPos="last" -> SUMO menyisipkan tepat di belakang kendaraan
            # terakhir di lajur (atau di ujung lajur kalau kosong), bukan di
            # pos 0. Tanpa ini, kendaraan lengan Selatan lahir 515 m dari
            # simpang (ruas pendekat Jl. Tentara Pelajar sepanjang itu di peta
            # OSM) lalu butuh ~45 detik sampai -- antreannya tersebar jauh di
            # luar crop kamera. Dengan "last" antrean menumpuk dari mulut
            # simpang ke belakang dan bagian depannya tetap masuk crop.
            self.traci.vehicle.add(
                vehID=vehicle_id,
                routeID=route_id,
                typeID=vehicle_type,
                depart="now",
                departPos="last",
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
        failed_insertions = 0
        failed_by_approach: dict[str, int] = {}
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
                        else:
                            # add_vehicle() menelan TraCIException diam-diam
                            # (mis. ruas masuk terlalu padat untuk disisipi
                            # kendaraan baru -- ruas EDGE_MASUK cuma 6-12m).
                            # Dicatat di sini supaya gap antara "Deteksi"
                            # (target_total) dan jumlah kendaraan yang
                            # benar-benar ada di network bisa DIBUKTIKAN
                            # penyebabnya, bukan cuma diduga wajar/tidak.
                            failed_insertions += 1
                            failed_by_approach[approach] = (
                                failed_by_approach.get(approach, 0) + 1
                            )

                self.current_demand[approach] = desired

            self.detected_vehicle_count = target_total
            self.traffic_timestamp = traffic_timestamp
            self.live_last_sync_failed_insertions = failed_insertions
            self.live_last_sync_failed_by_approach = failed_by_approach

        return {
            "added": added,
            "removed": removed,
            "total": target_total,
            "failedInsertions": failed_insertions,
        }

    def _replenish_current_demand(self) -> int:
        """Jaga jumlah kendaraan live sesuai snapshot CCTV terakhir.

        Dipanggil dari loop saat lock TraCI sudah dipegang. Kendaraan yang
        sudah tiba diganti, sehingga simulasi realtime tidak kosong setelah
        satu batch awal selesai melintasi simpang.
        """
        added = 0
        for approach, desired_counts in self.current_demand.items():
            for vehicle_type, wanted in desired_counts.items():
                existing_count = sum(
                    1
                    for vehicle_id, vehicle_approach in self._vehicle_approach.items()
                    if vehicle_approach == approach
                    and self._vehicle_type.get(vehicle_id) == vehicle_type
                )
                for _ in range(max(0, wanted - existing_count)):
                    if self.add_vehicle(vehicle_type=vehicle_type, approach=approach):
                        added += 1
        return added

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

    def _camera_clock_is_fresh(self) -> bool:
        """True kalau POST /sync-clock terakhir masih dalam jendela stale."""
        if self._camera_clock_synced_at is None:
            return False
        return (
            time.monotonic() - self._camera_clock_synced_at
            <= self.CAMERA_CLOCK_STALE_SECONDS
        )

    def get_display_time(self) -> float:
        """Kembalikan clock CCTV yang berjalan, atau clock mesin sebagai fallback."""
        if self._camera_clock_time is None or self._camera_clock_synced_at is None:
            return self.last_simulation_time
        # Interpolasi maksimal CAMERA_CLOCK_STALE_SECONDS setelah POST terakhir.
        # Lewat itu clock beku di posisi terakhir -- lebih baik lampu "macet"
        # daripada lari sendiri jauh mendahului video CCTV.
        elapsed = min(
            self.CAMERA_CLOCK_STALE_SECONDS,
            max(0.0, time.monotonic() - self._camera_clock_synced_at),
        )
        display_time = self._camera_clock_time + elapsed
        if self._camera_clock_duration:
            display_time %= self._camera_clock_duration
        return display_time

    def _pick_camera_phase(self, clock_time: float) -> tuple[int, float]:
        """(phase_index, sisa_detik) untuk waktu video tertentu vs active_cycle_plan."""
        durations: list[int] = []
        for phase in self.active_cycle_plan["phases"]:
            durations.extend([
                max(1, int(phase.get("greenSeconds", 1))),
                max(1, int(phase.get("yellowSeconds", 4))),
            ])
        cycle_seconds = sum(durations)
        offset = max(0.0, float(clock_time)) % cycle_seconds
        phase_index = 0
        elapsed_in_phase = offset
        for index, duration in enumerate(durations):
            if elapsed_in_phase < duration:
                phase_index = index
                break
            elapsed_in_phase -= duration
        remaining = max(0.05, durations[phase_index] - elapsed_in_phase)
        return phase_index, remaining

    def _apply_tls_phase(self, phase_index: int, remaining: float) -> None:
        """Set fase TLS kalau beda dari sekarang. Pemanggil WAJIB pegang _traci_lock."""
        tls_ids = list(self.traci.trafficlight.getIDList())
        if not tls_ids:
            return
        tls_id = tls_ids[0]
        current_phase = self.traci.trafficlight.getPhase(tls_id)
        current_remaining = max(
            0.0,
            self.traci.trafficlight.getNextSwitch(tls_id) - self.last_simulation_time,
        )
        # Toleransi 0.6 dtk (dulu 1.25): _enforce_camera_clock_phase() memanggil
        # ini tiap step, jadi koreksi lebih ketat = lampu SUMO makin nempel ke
        # video. Masih ada ambang supaya tidak setPhaseDuration tiap step (bikin
        # countdown kedip).
        if current_phase != phase_index or abs(current_remaining - remaining) > 0.6:
            self.traci.trafficlight.setPhase(tls_id, phase_index)
            self.traci.trafficlight.setPhaseDuration(tls_id, remaining)

    def _enforce_camera_clock_phase(self) -> None:
        """Kunci fase TLS ke clock CCTV tiap step loop.

        Tanpa ini program TLS SUMO jalan sendiri di antara POST /sync-clock --
        kalau POST-nya jarang/berhenti, fase lampu melenceng jauh dari video.
        Pemanggil (loop simulasi) sudah pegang _traci_lock (RLock).
        """
        if (
            self.traci is None
            or not self.active_cycle_plan
            or not self._camera_clock_is_fresh()
        ):
            return
        phase_index, remaining = self._pick_camera_phase(self.get_display_time())
        self._apply_tls_phase(phase_index, remaining)

    def sync_signal_clock(
        self,
        video_time_seconds: float,
        video_duration_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Selaraskan fase TLS dengan clock CCTV tanpa mereset simulasi."""
        if self.traci is None or not self.running or not self.active_cycle_plan:
            raise RuntimeError("CyclePlan SUMO belum aktif.")

        self._camera_clock_duration = (
            max(0.001, float(video_duration_seconds))
            if video_duration_seconds is not None
            else self._camera_clock_duration
        )
        self._camera_clock_time = max(0.0, float(video_time_seconds))
        if self._camera_clock_duration:
            self._camera_clock_time %= self._camera_clock_duration
        self._camera_clock_synced_at = time.monotonic()

        phase_index, remaining = self._pick_camera_phase(float(video_time_seconds))

        with self._traci_lock:
            self._apply_tls_phase(phase_index, remaining)

        return {
            "synced": True,
            "videoTimeSeconds": video_time_seconds,
            "phase": phase_index,
            "remainingSeconds": remaining,
            "videoDurationSeconds": self._camera_clock_duration,
        }

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
                        # KUNCI FASE TLS KE CLOCK CCTV
                        # ==========================================
                        # Program TLS SUMO jalan sendiri di antara POST
                        # /sync-clock; ini menariknya balik ke posisi video
                        # tiap step selama POST terakhir masih segar.
                        self._enforce_camera_clock_phase()

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

                            self._arrival_timeline.append(
                                self.last_simulation_time
                            )

                        # Snapshot CCTV merepresentasikan okupansi realtime,
                        # bukan batch kendaraan sekali jalan. Isi kembali
                        # kendaraan yang sudah keluar agar target tetap hidup.
                        self._replenish_current_demand()

                    # ==========================================
                    # ACTIVE VEHICLES POSITIONS
                    # ==========================================
                    
                    current_vehicles_data = []
                    waiting_values: list[float] = []

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

                            # Dipakai kartu "Hasil Simulasi" (Digital Twin) --
                            # dihitung sekali di sini, bukan panggilan TraCI
                            # terpisah lagi di get_metrics(), supaya tidak
                            # dobel jalan per-kendaraan tiap step.
                            waiting_values.append(
                                self.traci.vehicle.getAccumulatedWaitingTime(
                                    vehicle_id
                                )
                            )
                        except self.traci.TraCIException:
                            pass

                    self.active_vehicles_data = current_vehicles_data

                    # Kartu "Current Vehicles" dulu menghitung SEMUA
                    # kendaraan di seluruh network (633x1020m), padahal
                    # video cuma menampilkan crop kamera (~140x79m di
                    # sekitar simpang, lihat _stream_view_boundary()) --
                    # jadi angkanya jauh lebih besar dari yang kelihatan di
                    # layar (edge upstream lengan Selatan saja 515m,
                    # jauh di luar crop). Dihitung terpisah di sini supaya
                    # kartu bisa nunjukkan angka yang benar-benar cocok
                    # dengan apa yang terlihat.
                    view_xmin, view_ymin, view_xmax, view_ymax = (
                        self._stream_view_boundary()
                    )
                    self.live_visible_vehicle_count = sum(
                        1
                        for vehicle in current_vehicles_data
                        if view_xmin <= vehicle["x"] <= view_xmax
                        and view_ymin <= vehicle["y"] <= view_ymax
                    )

                    self.live_avg_delay_seconds = (
                        sum(waiting_values) / len(waiting_values)
                        if waiting_values
                        else 0.0
                    )

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
                    # LIVE TRAFFIC METRICS (antrean + throughput)
                    # ==========================================
                    # Dipakai kartu "Queue Length"/"Traffic Flow" di halaman
                    # Digital Twin -- dihitung sekali per step, sama seperti
                    # posisi kendaraan/sinyal di atas, bukan dipanggil TraCI
                    # langsung dari endpoint (lihat komentar di
                    # get_simulation_state()).

                    # Per lengan, bukan dijumlah -- total 4 lengan sekaligus
                    # jadi angka yang tidak actionable ("7 kendaraan" di mana
                    # persisnya?). Kartu menampilkan lengan TERPADAT saja,
                    # konsisten dengan panel Rekomendasi di sebelahnya yang
                    # juga per-lengan.
                    queue_by_approach: dict[str, int] = {}

                    for approach, edge_id in self.EDGE_MASUK.items():
                        try:
                            queue_by_approach[approach] = (
                                self.traci
                                .edge
                                .getLastStepHaltingNumber(edge_id)
                            )
                        except self.traci.TraCIException:
                            queue_by_approach[approach] = 0

                    busiest_approach = max(
                        queue_by_approach,
                        key=queue_by_approach.get,
                    )

                    queue_length_veh = queue_by_approach[busiest_approach]
                    self.live_queue_busiest_approach = busiest_approach

                    self.live_queue_length_veh = queue_length_veh

                    # Total 4 lengan sekaligus -- dipakai panel "Hasil
                    # Simulasi" (LOS/delay/antrean simpang secara keseluruhan),
                    # beda tujuan dari live_queue_length_veh di atas yang
                    # sengaja per-lengan (lengan terpadat) untuk kartu Queue
                    # Length.
                    self.live_total_queue_length_veh = sum(
                        queue_by_approach.values()
                    )

                    # Buang catatan arrived yang lebih tua dari 60 detik
                    # simulasi terakhir, sisanya dihitung langsung sebagai
                    # "kendaraan/menit" -- laju SEKARANG, bukan rata-rata
                    # sepanjang simulasi (yang nyaris tidak berubah lagi
                    # setelah simulasi jalan lama).
                    cutoff = self.last_simulation_time - 60

                    while (
                        self._arrival_timeline
                        and self._arrival_timeline[0] < cutoff
                    ):
                        self._arrival_timeline.popleft()

                    self.live_throughput_veh_per_min = float(
                        len(self._arrival_timeline)
                    )

                    # ==========================================
                    # SCREENSHOT (MJPEG STREAM)
                    # ==========================================
                    if self.is_gui and time.monotonic() - self._last_screenshot_at >= 0.25:
                        try:
                            frame_path = self.PROJECT_ROOT / "cache" / "simulation" / f"frame_{self.context}.jpg"
                            next_frame_path = frame_path.with_name(f"frame_{self.context}.next.jpg")
                            frame_path.parent.mkdir(parents=True, exist_ok=True)
                            self.traci.gui.screenshot(
                                "View #0",
                                str(next_frame_path),
                                width=self.STREAM_FRAME_WIDTH,
                                height=self.STREAM_FRAME_HEIGHT,
                            )
                            # Pembaca selalu melihat frame lama atau frame baru
                            # secara utuh, tidak pernah JPEG yang sedang ditulis.
                            os.replace(next_frame_path, frame_path)
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
                                f"{int(self.get_display_time())}s "
                                f"engineTime={current_second}s "
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
                # self.traci SUDAH jadi objek koneksi milik context ini
                # (bukan modul traci) -- lihat catatan di start().
                process = getattr(self.traci, "_process", None)
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
        self._arrival_timeline.clear()
        self.live_queue_length_veh = 0
        self.live_queue_busiest_approach = None
        self.live_total_queue_length_veh = 0
        self.live_avg_delay_seconds = 0.0
        self.live_throughput_veh_per_min = 0.0
        self.live_visible_vehicle_count = 0
        self.live_last_sync_failed_insertions = 0
        self.live_last_sync_failed_by_approach = {}

        print(
            "SUMO realtime controller closed."
        )
