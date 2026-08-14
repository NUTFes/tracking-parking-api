"""Seeds the canonical demo dataset: 7 named parking lots matching the
campus map pins (services/web/src/campusMapPins.ts) and 1 device on 講義棟北2.

Destructive: deletes ALL existing parking lots and devices first (which
cascades their events/commands/activities) so the DB always ends up in
exactly this state. Local/dev environments only — never run against a
database with real data.

    docker compose exec api python scripts/seed_demo_data.py
"""
from app.database import SessionLocal
from app.repositories.device_repository import DeviceRepository
from app.repositories.parking_lot_repository import ParkingLotRepository
from app.security import generate_secret_token, hash_token

# Capacities are placeholders — edit via admin-web once the real per-lot
# capacity is known.
PARKING_LOTS = [
    {"name": "イチョウ通り", "capacity": 35},
    {"name": "RIセンター北", "capacity": 15},
    {"name": "講義棟西2", "capacity": 20},
    {"name": "講義棟西1", "capacity": 25},
    {"name": "講義棟北2", "capacity": 30},
    {"name": "体育館下", "capacity": 40},
    {"name": "地域防災実践研究センター下", "capacity": 20},
]

DEVICE = {"device_code": "kougitou-hoku2-01", "parking_lot_name": "講義棟北2"}


def main() -> None:
    db = SessionLocal()
    try:
        parking_lots = ParkingLotRepository(db)
        devices = DeviceRepository(db)

        # This script defines the canonical seed state, so start from empty.
        for device in devices.list_all():
            db.delete(device)
        for lot in parking_lots.list_all():
            db.delete(lot)
        db.flush()

        name_to_lot_id = {}
        for spec in PARKING_LOTS:
            lot = parking_lots.create(name=spec["name"], capacity=spec["capacity"])
            db.flush()  # populate lot.id
            name_to_lot_id[spec["name"]] = lot.id

        api_key = generate_secret_token()
        devices.create(
            device_code=DEVICE["device_code"],
            name=None,
            parking_lot_id=name_to_lot_id[DEVICE["parking_lot_name"]],
            api_key_hash=hash_token(api_key),
        )
        db.commit()

        print("Seeded parking lots:")
        for spec in PARKING_LOTS:
            print(f"  - {spec['name']} (capacity={spec['capacity']})")
        print(f"Seeded device '{DEVICE['device_code']}' on '{DEVICE['parking_lot_name']}'")
        print(f"Device API key (shown once, save it now): {api_key}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
