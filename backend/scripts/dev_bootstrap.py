"""Create tables and default users for local development."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.auth_service import hash_password
from db.crud import create_user, get_user_by_username
from db.models import Base
from db.session import SessionLocal, engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for username, password, role in (
            ("planner", "planner", "planner"),
            ("viewer", "viewer", "viewer"),
        ):
            if get_user_by_username(db, username) is None:
                create_user(db, username, hash_password(password), role)
                print(f"Created user: {username} / {password} ({role})")
            else:
                print(f"User already exists: {username}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
