"""FastAPI dependency functions for the CPL-2 Scheduling System.

Provides:
    get_db()          — yields a SQLAlchemy Session per request
    get_current_user() — validates Bearer JWT and returns the User ORM object
    require_planner()  — enforces Planner role; raises 403 for Viewers

Design references: Requirements 11.3, 11.7, 11.8
"""

from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from api.auth_service import decode_token
from db.crud import get_user_by_username
from db.models import User
from db.session import SessionLocal

# OAuth2 scheme — FastAPI uses this to extract the Bearer token from the
# "Authorization: Bearer <token>" header and to generate the OpenAPI security
# scheme.  auto_error=True means FastAPI will automatically return 401 when the
# header is absent.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate the JWT and return the corresponding User from the database.

    Raises:
        HTTPException(401): If the token is missing, expired, invalid, or the
            referenced user does not exist in the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except JWTError:
        raise credentials_exception

    username: str | None = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = get_user_by_username(db, username)
    if user is None:
        raise credentials_exception

    return user


def require_planner(
    current_user: User = Depends(get_current_user),
) -> User:
    """Enforce that the authenticated user holds the 'planner' role.

    Raises:
        HTTPException(403): If the user's role is not 'planner'.

    Returns:
        The authenticated User object (same as *current_user*) for downstream
        use in route handlers.
    """
    if current_user.role != "planner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user
