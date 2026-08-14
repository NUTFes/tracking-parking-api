from sqlalchemy.orm import Session

from app.models.parking_lot import ParkingLot


class ParkingLotRepository:
    """DB access for parking_lots. No business rules here — callers
    (usecases) decide what a query result means; this class only knows SQL."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, *, name: str, capacity: int) -> ParkingLot:
        lot = ParkingLot(name=name, capacity=capacity)
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

    def update(self, lot: ParkingLot, *, name: str | None, capacity: int | None) -> ParkingLot:
        if name is not None:
            lot.name = name
        if capacity is not None:
            lot.capacity = capacity
        return lot

    def delete(self, lot: ParkingLot) -> None:
        self.db.delete(lot)
