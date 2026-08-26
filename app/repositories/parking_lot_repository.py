from sqlalchemy.orm import Session

from app.models.parking_lot import ParkingLot


class ParkingLotRepository:
    """DB access for parking_lots. No business rules here — callers
    (usecases) decide what a query result means; this class only knows SQL."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, name: str, capacity: int, x_percent: float | None = None, y_percent: float | None = None
    ) -> ParkingLot:
        lot = ParkingLot(name=name, capacity=capacity)
        # Only override the model's default (dead-center) when the caller
        # explicitly passes a position — used by scripts/seed_demo_data.py
        # to place the canonical demo lots at their real map spots.
        if x_percent is not None:
            lot.x_percent = x_percent
        if y_percent is not None:
            lot.y_percent = y_percent
        self.db.add(lot)
        return lot

    def list_all(self) -> list[ParkingLot]:
        return self.db.query(ParkingLot).order_by(ParkingLot.id).all()

    def get(self, lot_id: int) -> ParkingLot | None:
        return self.db.get(ParkingLot, lot_id)

    def get_for_update(self, lot_id: int) -> ParkingLot | None:
        """Row-locks the lot so concurrent entry/exit events from different
        devices at the same lot serialize instead of racing on current_count."""
        return self.db.query(ParkingLot).filter(ParkingLot.id == lot_id).with_for_update().first()

    def update(
        self,
        lot: ParkingLot,
        *,
        name: str | None,
        capacity: int | None,
        x_percent: float | None = None,
        y_percent: float | None = None,
    ) -> ParkingLot:
        if name is not None:
            lot.name = name
        if capacity is not None:
            lot.capacity = capacity
        if x_percent is not None:
            lot.x_percent = x_percent
        if y_percent is not None:
            lot.y_percent = y_percent
        return lot

    def delete(self, lot: ParkingLot) -> None:
        self.db.delete(lot)
