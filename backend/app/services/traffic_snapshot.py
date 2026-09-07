"""Resolve an explicit, complete observation without silently changing its ID."""
from app.pipeline.traffic_state_builder import BuiltTrafficState
from app.services.traffic_service import TrafficService


def load_snapshot(intersection_id: str, traffic_state_id: int | None = None) -> BuiltTrafficState:
    service = TrafficService()
    if traffic_state_id is None:
        rows = service.get_latest_traffic(intersection_id=intersection_id, limit=1)
        if not rows:
            raise ValueError("TrafficState belum tersedia.")
        traffic_state_id = int(rows[0]["trafficState"]["id"])
    row = service.get_traffic_state(intersection_id=intersection_id, traffic_state_id=traffic_state_id)
    if not row:
        raise ValueError("TrafficState tidak ditemukan untuk simpang ini.")
    if {item["approach"] for item in row["approaches"]} != {"north", "east", "south", "west"}:
        raise ValueError("TrafficState belum lengkap untuk empat lengan.")
    state = row["trafficState"]
    return BuiltTrafficState(trafficStateId=traffic_state_id, intersectionId=intersection_id,
                             windowStart=state["windowStart"], windowEnd=state["windowEnd"],
                             source=state.get("source") or "cv", approaches=row["approaches"])
