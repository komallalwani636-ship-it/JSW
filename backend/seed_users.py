"""One-time seed script: create initial planner and viewer accounts.

Run after migrations:
    python seed_users.py

Override credentials via environment variables:
    SEED_PLANNER_USER / SEED_PLANNER_PASS
    SEED_VIEWER_USER  / SEED_VIEWER_PASS
"""

from __future__ import annotations

import os

from api.auth_service import hash_password
from db.crud import create_user, get_user_by_username
from db.session import SessionLocal

PLANNER_USER = os.environ.get("SEED_PLANNER_USER", "planner")
PLANNER_PASS = os.environ.get("SEED_PLANNER_PASS", "planner123")
VIEWER_USER  = os.environ.get("SEED_VIEWER_USER",  "viewer")
VIEWER_PASS  = os.environ.get("SEED_VIEWER_PASS",  "viewer123")


def seed():
    db = SessionLocal()
    try:
        for username, password, role in [
            (PLANNER_USER, PLANNER_PASS, "planner"),
            (VIEWER_USER,  VIEWER_PASS,  "viewer"),
        ]:
            if get_user_by_username(db, username) is None:
                create_user(db, username, hash_password(password), role)
                db.commit()
                print(f"Created {role}: {username}")
            else:
                print(f"Already exists: {username}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
