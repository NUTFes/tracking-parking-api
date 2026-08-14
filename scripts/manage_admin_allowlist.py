"""Adds or removes a Google account from the admin-web allow-list.

There is no public sign-up endpoint by design — only pre-approved Google
accounts (verified NUTFes executive-committee addresses) can log into
admin-web:
    PYTHONPATH=. .venv/bin/python scripts/manage_admin_allowlist.py add 25.m.kitano.nutfes@gmail.com
    PYTHONPATH=. .venv/bin/python scripts/manage_admin_allowlist.py remove 25.m.kitano.nutfes@gmail.com
"""
import argparse
import sys

from app.database import SessionLocal
from app.google_auth import NUTFES_EMAIL_PATTERN
from app.models.admin_user import AdminUser


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the trapa admin-web Google-account allow-list")
    parser.add_argument("action", choices=["add", "remove"])
    parser.add_argument("email")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not NUTFES_EMAIL_PATTERN.match(email):
        print(f"'{email}' does not match the NN.x.lastname.nutfes@gmail.com format", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.query(AdminUser).filter(AdminUser.email == email).first()
        if args.action == "add":
            if user is None:
                db.add(AdminUser(email=email))
                db.commit()
                print(f"'{email}' added to the admin allow-list")
            else:
                print(f"'{email}' is already allowed")
        else:
            if user is not None:
                db.delete(user)
                db.commit()
                print(f"'{email}' removed from the admin allow-list")
            else:
                print(f"'{email}' was not in the allow-list")
    finally:
        db.close()


if __name__ == "__main__":
    main()
