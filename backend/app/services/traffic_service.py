from app.schemas.traffic import TrafficState
from app.pipeline.traffic_state_builder import build_latest_traffic_state


def get_current_traffic_state() -> TrafficState:
    """
    Mengambil traffic state terbaru dari Traffic State Builder.

    Traffic State Builder bertanggung jawab untuk:
    - membaca CSV CV
    - melakukan agregasi lane -> approach
    - membentuk time window
    - mengubah nama field CSV menjadi nama contract
    - menghasilkan TrafficState

    Service ini hanya menjadi penghubung antara
    Traffic State Builder dan API route.
    """
    return build_latest_traffic_state()