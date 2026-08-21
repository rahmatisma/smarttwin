from app.services.supabase_client import get_supabase


def seed_database():
    supabase = get_supabase()
    intersection_result = supabase.table("intersections").select("id").eq(
        "intersectionId", "simpang4-pingit"
    ).maybe_single().execute()

    if intersection_result is None or not intersection_result.data:
        intersection = supabase.table("intersections").insert({
            "intersectionId": "simpang4-pingit",
            "name": "Simpang 4 Pingit",
            "description": "Persimpangan SmartTwin",
            "isActive": True,
        }).execute().data[0]
    else:
        intersection = intersection_result.data

    for sort_order, direction in enumerate(("north", "south", "east", "west"), start=1):
        approach_result = supabase.table("approaches").select("id").eq(
            "intersectionId", intersection["id"]
        ).eq("approach", direction).maybe_single().execute()
        approach = approach_result.data if approach_result and approach_result.data else supabase.table("approaches").insert({
            "intersectionId": intersection["id"],
            "approach": direction,
            "name": direction.title(),
            "sortOrder": sort_order,
            "isActive": True,
        }).execute().data[0]

        for lane_index in range(1, 4):
            lane_id = f"lane_{lane_index}"
            existing = supabase.table("lanes").select("id").eq(
                "approachId", approach["id"]
            ).eq("laneId", lane_id).maybe_single().execute()
            if existing is None or not existing.data:
                supabase.table("lanes").insert({
                    "approachId": approach["id"],
                    "laneId": lane_id,
                    "laneName": f"{direction} Lane {lane_index}",
                    "laneIndex": lane_index,
                    "isActive": True,
                }).execute()

    print("Database seed Supabase berhasil.")


if __name__ == "__main__":
    seed_database()