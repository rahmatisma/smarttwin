from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models.intersection import Intersection
from app.db.models.approach import ApproachModel
from app.db.models.lane import Lane


def seed_database():
    db = SessionLocal()

    try:
        # ====================================================
        # INTERSECTION
        # ====================================================

        intersection = db.scalar(
            select(Intersection).where(
                Intersection.intersectionId
                == "simpang4-pingit"
            )
        )

        if intersection is None:
            intersection = Intersection(
                intersectionId="simpang4-pingit",
                name="Simpang 4 Pingit",
                description=(
                    "Persimpangan SmartTwin"
                ),
                isActive=True,
            )

            db.add(intersection)
            db.flush()

        # ====================================================
        # APPROACHES
        # ====================================================

        approaches = {}

        for sort_order, direction in enumerate(
            [
                "north",
                "south",
                "east",
                "west",
            ],
            start=1,
        ):
            approach = db.scalar(
                select(ApproachModel).where(
                    ApproachModel.intersectionId
                    == intersection.id,
                    ApproachModel.approach
                    == direction,
                )
            )

            if approach is None:
                approach = ApproachModel(
                    intersectionId=intersection.id,
                    approach=direction,
                    name=direction.title(),
                    sortOrder=sort_order,
                    isActive=True,
                )

                db.add(approach)
                db.flush()

            approaches[direction] = approach

        # ====================================================
        # LANES
        # ====================================================

        for direction, approach in approaches.items():

            for lane_index in range(1, 4):

                lane_id = f"lane_{lane_index}"

                existing_lane = db.scalar(
                    select(Lane).where(
                        Lane.approachId
                        == approach.id,
                        Lane.laneId
                        == lane_id,
                    )
                )

                if existing_lane is None:
                    lane = Lane(
                        approachId=approach.id,
                        laneId=lane_id,
                        laneName=(
                            f"{direction} "
                            f"Lane {lane_index}"
                        ),
                        laneIndex=lane_index,
                        isActive=True,
                    )

                    db.add(lane)

        # ====================================================
        # COMMIT
        # ====================================================

        db.commit()

        print(
            "Database seed berhasil."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()