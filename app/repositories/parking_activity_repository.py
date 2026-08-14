from sqlalchemy.orm import Session

from app.models.parking_activity import ParkingActivity


class ParkingActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        parking_lot_id: int,
        activity_type: str,
        delta: int,
        count_after: int,
        actor_label: str,
        note: str | None,
    ) -> ParkingActivity:
        activity = ParkingActivity(
            parking_lot_id=parking_lot_id,
            activity_type=activity_type,
            delta=delta,
            count_after=count_after,
            actor_label=actor_label,
            note=note,
        )
        self.db.add(activity)
        return activity

    def list_for_lot(self, parking_lot_id: int, *, limit: int) -> list[ParkingActivity]:
        return (
            self.db.query(ParkingActivity)
            .filter(ParkingActivity.parking_lot_id == parking_lot_id)
            .order_by(ParkingActivity.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_recent(self, *, limit: int) -> list[ParkingActivity]:
        return self.db.query(ParkingActivity).order_by(ParkingActivity.created_at.desc()).limit(limit).all()
