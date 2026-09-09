"""Isolated SUMO replay of recorded YOLO observations with manual camera failures."""
from datetime import datetime, timezone
from threading import RLock

from app.simulation.sumo.sumo_controller import SumoController
from app.services.replay_demo_history import RecordedHistory

ARMS = ("north", "east", "south", "west")
CONTEXT = "replay-demo"


class ReplayDemoController(SumoController):
    def __init__(self):
        super().__init__(
            config_file=self.SIMULATION_DIR / "network" / "simpang4_pingit_live.sumocfg",
            context=CONTEXT, scenario="Traffic Realtime", seed=42,
        )
        self.sources = {arm: {"mode": "live", "ageSeconds": 0, "offlineSince": None} for arm in ARMS}
        self.vehicle_sources = {}
        self.history = RecordedHistory(self.PROJECT_ROOT / "cv" / "output" / "snapshot_zona.csv")
        self.history_windows = {}
        self._last_input_second = -1
        self.triggered_count = 0

    def _update_inputs(self):
        position = min(self.history.playback_start + self.last_simulation_time, self.history.end)
        for arm, source in self.sources.items():
            if source["mode"] == "replay":
                window = self.history_windows[arm]
                if not window:
                    self.current_demand[arm] = {}
                    source["dataTimestamp"] = None
                    continue
                elapsed = max(0, self.last_simulation_time - source["replayStartedAt"])
                duration = max(1, window[-1]["time"] - window[0]["time"] + 1)
                target = window[0]["time"] + elapsed % duration
                row = next((item for item in reversed(window) if item["time"] <= target), window[0])
            else:
                row = self.history.sample(arm, position)
            source["dataTimestamp"] = row["timestamp"] if row else None
            self.current_demand[arm] = row["counts"].copy() if row else {}

    def add_vehicle(self, vehicle_type, approach):
        # Capture provenance at insertion, never derive it from current camera status.
        with self._traci_lock:
            vehicle_id = f"smart_{vehicle_type}_{approach}_{self._vehicle_counter}"
            source = self.sources[approach]
            if not super().add_vehicle(vehicle_type, approach):
                return False
            self.vehicle_sources[vehicle_id] = {
                "approach": approach,
                "dataSource": source["mode"],
                "dataTimestamp": source.get("dataTimestamp"),
            }
            self._color_vehicle_by_next_tls(vehicle_id)
            return True

    def _color_vehicle_by_next_tls(self, vehicle_id):
        if self.traci is None:
            return
        replay = self.vehicle_sources.get(vehicle_id, {}).get("dataSource") == "replay"
        # Preserve normal yellow vehicles; only historical insertions are white.
        key = "replay-demo-history" if replay else "replay-demo-live"
        if self._vehicle_signal_color.get(vehicle_id) == key:
            return
        try:
            self.traci.vehicle.setColor(vehicle_id, (255, 255, 255, 255) if replay else (255, 255, 0, 255))
            self._vehicle_signal_color[vehicle_id] = key
        except self.traci.TraCIException:
            pass

    def _replenish_current_demand(self):
        # Reuse SUMO's normal continuous replenishment, including when CCTV is off.
        self.vehicle_sources = {key: value for key, value in self.vehicle_sources.items() if key in self._vehicle_approach}
        if int(self.last_simulation_time) != self._last_input_second:
            self._update_inputs()
            self._last_input_second = int(self.last_simulation_time)
        return super()._replenish_current_demand()

    def set_sources(self, offline, age_seconds, trigger=False):
        with self._traci_lock:
            now = datetime.now(timezone.utc).isoformat()
            cutoff = min(self.history.playback_start + self.last_simulation_time, self.history.end)
            newly_offline = []
            for arm in ARMS:
                previous = self.sources[arm]
                is_offline = arm in offline
                self.sources[arm] = {
                    "mode": "replay" if is_offline else "live",
                    "ageSeconds": age_seconds if is_offline else 0,
                    "offlineSince": (previous["offlineSince"] or now) if is_offline else None,
                    "replayStartedAt": previous.get("replayStartedAt", self.last_simulation_time),
                }
                if is_offline and (previous["mode"] != "replay" or previous["ageSeconds"] != age_seconds):
                    window = self.history.history_window(arm, cutoff, age_seconds)
                    self.history_windows[arm] = window
                    self.sources[arm]["replayStartedAt"] = self.last_simulation_time
                    if previous["mode"] != "replay":
                        newly_offline.append(arm)
                if is_offline and trigger and arm not in newly_offline:
                    newly_offline.append(arm)
            self._update_inputs()
            self.triggered_count = 0
            # Explicit demo trigger: insert one recorded batch immediately,
            # without recoloring/removing the vehicles already in the network.
            for arm in newly_offline:
                for kind, count in self.current_demand[arm].items():
                    for _ in range(count):
                        if self.add_vehicle(kind, arm):
                            self.triggered_count += 1
            self._replenish_current_demand()

    def snapshot(self):
        with self._traci_lock:
            vehicles = [{**vehicle, **self.vehicle_sources.get(vehicle["id"], {})} for vehicle in self.active_vehicles_data]
            arms = []
            for arm in ARMS:
                source = self.sources[arm]
                arm_vehicles = [v for v in vehicles if v.get("approach") == arm]
                arms.append({
                    "approach": arm, **source,
                    "dataTimestamp": source.get("dataTimestamp"),
                    "liveCount": sum(v.get("dataSource") == "live" for v in arm_vehicles),
                    "replayCount": sum(v.get("dataSource") == "replay" for v in arm_vehicles),
                    "targetCount": sum(self.current_demand.get(arm, {}).values()),
                })
            return {"running": self.is_running(), "simulationTimeSeconds": self.last_simulation_time,
                    "approaches": arms, "vehicles": vehicles, "lastError": self.last_error,
                    "fixture": False, "context": CONTEXT, "triggeredCount": self.triggered_count,
                    "recordingStart": datetime.fromtimestamp(self.history.start, timezone.utc).isoformat(),
                    "recordingEnd": datetime.fromtimestamp(self.history.end, timezone.utc).isoformat(),
                    "recordingEnded": self.history.playback_start + self.last_simulation_time >= self.history.end,
                    "recordingPosition": datetime.fromtimestamp(min(self.history.playback_start + self.last_simulation_time, self.history.end), timezone.utc).isoformat()}


class ReplayDemoService:
    def __init__(self):
        self.controller = None
        self.lock = RLock()

    def start(self):
        with self.lock:
            if self.controller and self.controller.is_running():
                return self.controller.snapshot()
            if self.controller:
                self.controller.close()
            controller = ReplayDemoController()
            try:
                controller.start(gui=True, gui_delay_ms=0)
                controller.apply_cycle_plan({
                    "phases": [{"approach": arm, "greenSeconds": 8, "yellowSeconds": 3} for arm in ARMS],
                    "source": "replay-demo-recorded-yolo", "startOffsetSeconds": 0,
                })
                controller.set_sources([], 300)
            except Exception:
                controller.close()
                raise
            self.controller = controller
            return controller.snapshot()

    def state(self):
        with self.lock:
            return self.controller.snapshot() if self.controller else {"running": False, "approaches": [], "vehicles": [], "fixture": True}

    def set_sources(self, offline, age_seconds, trigger=False):
        with self.lock:
            if not self.controller or not self.controller.is_running():
                raise ValueError("Nyalakan SUMO demo terlebih dahulu.")
            self.controller.set_sources(offline, age_seconds, trigger)
            return self.controller.snapshot()

    def stop(self):
        with self.lock:
            if self.controller:
                self.controller.close()
                self.controller = None
            return {"running": False, "approaches": [], "vehicles": []}


replay_demo_service = ReplayDemoService()
