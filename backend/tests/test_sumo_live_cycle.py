from types import SimpleNamespace

from app.simulation.sumo.sumo_controller import SumoController


class FakeTrafficLight:
    class Phase:
        def __init__(self, duration, state):
            self.duration = duration
            self.state = state

    class Logic:
        def __init__(self, program_id, logic_type, current_phase, phases):
            self.programID = program_id
            self.phases = phases

    def __init__(self):
        self.logic = None
        self.phase = None
        self.phase_duration = None

    def getIDList(self):
        return ("SIMPANG_CENTER",)

    def setProgramLogic(self, _tls_id, logic):
        self.logic = logic

    def setProgram(self, _tls_id, _program_id):
        pass

    def setPhase(self, _tls_id, phase):
        self.phase = phase

    def getPhase(self, _tls_id):
        return self.phase

    def getNextSwitch(self, _tls_id):
        return 0

    def setPhaseDuration(self, _tls_id, duration):
        self.phase_duration = duration


def test_live_cycle_is_installed_in_north_east_south_west_order():
    controller = SumoController()
    traffic_light = FakeTrafficLight()
    controller.traci = SimpleNamespace(trafficlight=traffic_light)
    controller.apply_cycle_plan({
        "source": "scenario-generator",
        "phases": [
            {"approach": "west", "greenSeconds": 20, "yellowSeconds": 4},
            {"approach": "south", "greenSeconds": 30, "yellowSeconds": 4},
            {"approach": "east", "greenSeconds": 25, "yellowSeconds": 4},
            {"approach": "north", "greenSeconds": 35, "yellowSeconds": 4},
        ],
    })

    assert [phase.duration for phase in traffic_light.logic.phases] == [
        35, 4, 25, 4, 30, 4, 20, 4
    ]
    assert [phase["approach"] for phase in controller.active_cycle_plan["phases"]] == [
        "north", "east", "south", "west"
    ]
    assert traffic_light.phase == 0


def test_reapplying_identical_cycle_does_not_reset_phase():
    controller = SumoController()
    traffic_light = FakeTrafficLight()
    controller.traci = SimpleNamespace(trafficlight=traffic_light)
    plan = {
        "phases": [
            {"approach": name, "greenSeconds": 20, "yellowSeconds": 4}
            for name in ("north", "east", "south", "west")
        ]
    }
    controller.apply_cycle_plan(plan)
    traffic_light.phase = 4
    controller.apply_cycle_plan(plan)

    assert traffic_light.phase == 4


def test_camera_clock_selects_yellow_phase_without_resetting_simulation_time():
    controller = SumoController()
    traffic_light = FakeTrafficLight()
    controller.traci = SimpleNamespace(trafficlight=traffic_light)
    controller.running = True
    controller.last_simulation_time = 123
    controller.apply_cycle_plan({
        "phases": [
            {"approach": name, "greenSeconds": 20, "yellowSeconds": 4}
            for name in ("north", "east", "south", "west")
        ]
    })

    result = controller.sync_signal_clock(21.0)

    assert result["phase"] == 1
    assert traffic_light.phase == 1
    assert traffic_light.phase_duration == 3.0
    assert controller.last_simulation_time == 123


def test_camera_clock_wraps_display_time_without_resetting_sumo():
    controller = SumoController()
    traffic_light = FakeTrafficLight()
    controller.traci = SimpleNamespace(trafficlight=traffic_light)
    controller.running = True
    controller.last_simulation_time = 1130
    controller.apply_cycle_plan({
        "phases": [
            {"approach": name, "greenSeconds": 20, "yellowSeconds": 4}
            for name in ("north", "east", "south", "west")
        ]
    })

    controller.sync_signal_clock(2.0, 1128.0)

    assert 2.0 <= controller.get_display_time() < 2.1
    assert controller.last_simulation_time == 1130


def test_realtime_demand_is_replenished_after_vehicles_leave(monkeypatch):
    controller = SumoController()
    controller.current_demand = {
        "north": {"motorcycle": 1, "car": 2, "bus": 0, "truck": 0}
    }
    controller._vehicle_approach = {"existing-car": "north"}
    controller._vehicle_type = {"existing-car": "car"}
    counter = 0

    def fake_add_vehicle(*, vehicle_type, approach):
        nonlocal counter
        counter += 1
        vehicle_id = f"new-{counter}"
        controller._vehicle_approach[vehicle_id] = approach
        controller._vehicle_type[vehicle_id] = vehicle_type
        return True

    monkeypatch.setattr(controller, "add_vehicle", fake_add_vehicle)

    assert controller._replenish_current_demand() == 2
    assert controller._replenish_current_demand() == 0
