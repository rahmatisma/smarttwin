from datetime import datetime

from app.pipeline.traffic_state_builder import (
    ApproachTrafficState,
    BuiltTrafficState,
)

from app.simulation.sumo.traffic_state_adapter import (
    SumoTrafficStateAdapter,
)


def test_traffic_state_to_sumo_demand():

    # SumoTrafficStateAdapter.to_demand() menerima
    # BuiltTrafficState (hasil TrafficStateBuilder),
    # BUKAN TrafficState (schema API) -- approach di sini
    # sengaja plain string, bukan enum Approach.

    state = BuiltTrafficState(
        trafficStateId=1,
        intersectionId="simpang4-pingit",
        windowStart=datetime(
            2026, 8, 15, 16, 30, 12
        ),
        windowEnd=datetime(
            2026, 8, 15, 16, 30, 17
        ),
        approaches=[
            ApproachTrafficState(
                approach="south",
                volume=10,
                queueLengthVeh=5,
                queueLengthMEst=12.5,
                densityIndex=25.0,
                avgSpeedKmh=None,
            )
        ],
    )

    adapter = SumoTrafficStateAdapter(
        approach_to_edge={
            "south": "south_in",
        }
    )

    demand = adapter.to_demand(state)

    assert len(demand) == 1

    assert demand[0]["approach"] == "south"
    assert demand[0]["edge_id"] == "south_in"
    assert demand[0]["volume"] == 10