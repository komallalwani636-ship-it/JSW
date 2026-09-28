"""Authentication service for the CPL-2 Scheduling System.

Provides bcrypt-based password hashing/verification and JWT encode/decode
using python-jose.  All configuration is read from environment variables so
that the test environment can override them without code changes.

Design references: Requirements 11.1, 11.2
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ALGORITHM = "HS256"
_DEFAULT_EXPIRY_MINUTES = 60


def _jwt_secret() -> str:
    """Return the JWT signing secret from the environment.

    Raises RuntimeError if the variable is missing or empty so that the
    application fails loudly rather than signing tokens with an empty key.
    """
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is not set. "
            "Please configure it before starting the application."
        )
    return secret


def _expiry_minutes() -> int:
    """Return the token lifetime in minutes from JWT_EXPIRY_MINUTES env var."""
    raw = os.environ.get("JWT_EXPIRY_MINUTES", str(_DEFAULT_EXPIRY_MINUTES))
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError("must be positive")
        return value
    except ValueError:
        return _DEFAULT_EXPIRY_MINUTES


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash *plain* using bcrypt and return the encoded hash string.

    The returned string is suitable for storage in the ``users.password_hash``
    column (VARCHAR(128)).
    """
    hashed: bytes = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the bcrypt *hashed* value, else False."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:  # malformed hash etc.
        return False


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------


def create_access_token(data: dict) -> str:
    """Encode *data* as a signed JWT and return the compact token string.

    The payload is augmented with an ``exp`` claim computed from
    ``JWT_EXPIRY_MINUTES``.  The caller is expected to supply at least
    ``sub`` (username) and ``role`` in *data*.

    Args:
        data: Mapping of claims to include in the token payload.

    Returns:
        Compact URL-safe JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=_expiry_minutes())
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _jwt_secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify *token*, returning the payload as a plain dict.

    Args:
        token: Compact JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        jose.JWTError: If the token is expired, has an invalid signature, or
            is otherwise malformed.
    """
    return jwt.decode(token, _jwt_secret(), algorithms=[_ALGORITHM])
