from __future__ import annotations

from supabase import Client

from app.schemas.traffic import TrafficState
from app.services.supabase_client import get_supabase


class TrafficStateRepository:

    def __init__(self, supabase: Client | None = None):
        self.supabase = supabase or get_supabase()

    def save_state(
        self,
        state: TrafficState,
    ) -> dict:
        intersection_result = (
            self.supabase.table("intersections")
            .select("id")
            .eq("intersectionId", state.intersectionId)
            .maybe_single()
            .execute()
        )
        if intersection_result is None or not intersection_result.data:
            raise ValueError(
                f"Intersection tidak ditemukan: {state.intersectionId}"
            )
        intersection_id = intersection_result.data["id"]

        existing_result = (
            self.supabase.table("trafficStates")
            .select("id")
            .eq("intersectionId", intersection_id)
            .eq("windowStart", state.windowStart.isoformat())
            .eq("windowEnd", state.windowEnd.isoformat())
            .maybe_single()
            .execute()
        )
        if existing_result is not None and existing_result.data:
            traffic_state_id = existing_result.data["id"]
        else:
            inserted = self.supabase.table("trafficStates").insert({
                "intersectionId": intersection_id,
                "windowStart": state.windowStart.isoformat(),
                "windowEnd": state.windowEnd.isoformat(),
                "source": "backend",
            }).execute()
            traffic_state_id = inserted.data[0]["id"]

        approach_rows = self.supabase.table("approaches").select("id, approach").eq(
            "intersectionId", intersection_id
        ).execute()
        approach_ids = {row["approach"]: row["id"] for row in (approach_rows.data or [])}

        payload = []
        for approach_state in state.approaches:
            approach_id = approach_ids.get(approach_state.approach)
            if approach_id is None:
                raise ValueError(
                    f"Approach tidak ditemukan: {approach_state.approach}"
                )
            payload.append({
                "trafficStateId": traffic_state_id,
                "approachId": approach_id,
                **approach_state.model_dump(
                    by_alias=True,
                ),
            })

        if payload:
            self.supabase.table("trafficApproachStates").upsert(
                payload, on_conflict="trafficStateId,approachId"
            ).execute()

        return {"id": traffic_state_id, "intersectionId": intersection_id}