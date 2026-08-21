from __future__ import annotations

from supabase import Client

from app.services.supabase_client import get_supabase


class IntersectionRepository:

    def __init__(self, supabase: Client | None = None):
        self.supabase = supabase or get_supabase()

    def get_by_intersection_id(
        self,
        intersection_id: str,
    ) -> dict | None:
        result = self.supabase.table("intersections").select("*").eq(
            "intersectionId", intersection_id
        ).maybe_single().execute()
        return result.data if result is not None else None

    def create_intersection(
        self,
        intersection_id: str,
        name: str,
        latitude: float | None = None,
        longitude: float | None = None,
        description: str | None = None,
    ) -> dict:
        result = self.supabase.table("intersections").insert({
            "intersectionId": intersection_id,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "description": description,
            "isActive": True,
        }).execute()
        return result.data[0]

    def create_approach(
        self,
        intersection_db_id: int,
        approach: str,
        name: str | None = None,
        sort_order: int = 0,
    ) -> dict:
        result = self.supabase.table("approaches").insert({
            "intersectionId": intersection_db_id,
            "approach": approach,
            "name": name,
            "sortOrder": sort_order,
            "isActive": True,
        }).execute()
        return result.data[0]

    def create_lane(
        self,
        approach_db_id: int,
        lane_id: str,
        lane_name: str | None = None,
        lane_index: int | None = None,
    ) -> dict:
        result = self.supabase.table("lanes").insert({
            "approachId": approach_db_id,
            "laneId": lane_id,
            "laneName": lane_name,
            "laneIndex": lane_index,
            "isActive": True,
        }).execute()
        return result.data[0]