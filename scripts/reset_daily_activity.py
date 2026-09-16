"""Resets today's parking activity (entry/exit events, counts, activity log) directly in
the DB. parking_lots itself (name/capacity/map position) and devices are left untouched.

The existing Admin API `POST /parking-lots/reset-all` only zeroes current_count/system_count,
and that reset itself gets logged to parking_activities -- history isn't cleared. Use this
script when parking_events/parking_activities themselves need to be emptied out (e.g. before
an event day starts).

Targets:
  - parking_events      : all rows removed (TRUNCATE)
  - parking_activities   : all rows removed (TRUNCATE)
  - parking_lots          : current_count / system_count set to 0 (other columns untouched)

Left alone: parking_lots itself, devices, device_commands, admin_users, admin_refresh_tokens.

TRUNCATE is safe here without touching foreign key checks: parking_events/parking_activities
are only FK children (device_id -> devices, parking_lot_id -> parking_lots) -- no table has a
FK referencing either of them.

Run this while no devices are actively sending events. Resetting mid-traffic can race with a
background task still applying an in-flight parking_events row to system_count.

    PYTHONPATH=. .venv/bin/python scripts/reset_daily_activity.py             # counts, then confirm
    PYTHONPATH=. .venv/bin/python scripts/reset_daily_activity.py --dry-run
    PYTHONPATH=. .venv/bin/python scripts/reset_daily_activity.py --yes

    docker compose exec api python scripts/reset_daily_activity.py
"""
import argparse
import sys

from sqlalchemy import text

from app.database import SessionLocal

COUNTS_SQL = """
    SELECT
      (SELECT COUNT(*) FROM parking_events)                      AS parking_events,
      (SELECT COUNT(*) FROM parking_activities)                  AS parking_activities,
      (SELECT COALESCE(SUM(current_count), 0) FROM parking_lots) AS sum_current_count,
      (SELECT COALESCE(SUM(system_count), 0) FROM parking_lots)  AS sum_system_count
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset today's parking activity (events/activities/counts)")
    parser.add_argument("--dry-run", action="store_true", help="only show the current counts, change nothing")
    parser.add_argument("-y", "--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        counts = db.execute(text(COUNTS_SQL)).one()
        print(
            f"parking_events={counts.parking_events} parking_activities={counts.parking_activities} "
            f"sum_current_count={counts.sum_current_count} sum_system_count={counts.sum_system_count}"
        )

        if args.dry_run:
            print("--dry-run のため変更していません")
            return

        if not args.yes:
            reply = input("上記をリセットします（parking_lots本体・devicesは変更しません）。よろしいですか？ [y/N] ")
            if reply.strip().lower() not in ("y", "yes"):
                print("中止しました")
                sys.exit(1)

        db.execute(text("TRUNCATE TABLE parking_events"))
        db.execute(text("TRUNCATE TABLE parking_activities"))
        db.execute(text("UPDATE parking_lots SET current_count = 0, system_count = 0"))
        db.commit()
        print("完了")
    finally:
        db.close()


if __name__ == "__main__":
    main()
