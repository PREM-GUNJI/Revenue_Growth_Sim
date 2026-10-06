"""Create or reset a sign-in user: `python -m backend.auth_users EMAIL [--name "Full Name"]`.

The password is read from the AUTH_NEW_PASSWORD environment variable if set,
otherwise prompted for without echo. It is never written anywhere but its hash.
"""

from __future__ import annotations

import argparse
import getpass
import os

from backend.auth import upsert_user
from backend.db import initialize_database


def display_name_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    return " ".join(part.capitalize() for part in local.replace("_", ".").split(".") if part)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--name", help="Display name (default: derived from the email)")
    args = parser.parse_args()
    password = os.getenv("AUTH_NEW_PASSWORD") or getpass.getpass("Password: ")
    if not initialize_database():
        print("DATABASE_URL is not configured.")
        return 1
    outcome = upsert_user(args.email, password, args.name or display_name_from_email(args.email))
    print(f"{outcome}: {args.email.strip().lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
