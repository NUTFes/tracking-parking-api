"""Creates (or resets the password of) an Admin console user.

There is no public sign-up endpoint by design — admin accounts are provisioned
out-of-band with this script:
    PYTHONPATH=. .venv/bin/python scripts/create_admin_user.py <username>
"""
import argparse
import getpass
import sys

from app.database import SessionLocal
from app.models.admin_user import AdminUser
from app.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset a trapa Admin console user")
    parser.add_argument("username")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Confirm password: "):
        print("Passwords did not match", file=sys.stderr)
        sys.exit(1)
    if len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.query(AdminUser).filter(AdminUser.username == args.username).first()
        if user is None:
            db.add(AdminUser(username=args.username, password_hash=hash_password(password)))
            action = "created"
        else:
            user.password_hash = hash_password(password)
            action = "updated"
        db.commit()
        print(f"admin user '{args.username}' {action}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
