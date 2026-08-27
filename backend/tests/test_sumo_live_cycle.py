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

    def getIDList(self):
        return ("SIMPANG_CENTER",)

    def setProgramLogic(self, _tls_id, logic):
        self.logic = logic

    def setProgram(self, _tls_id, _program_id):
        pass

    def setPhase(self, _tls_id, phase):
        self.phase = phase


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
