"""Authentication router for the CPL-2 Scheduling System.

Endpoints:
    POST /api/auth/login       — issue a JWT on valid username/password credentials
    POST /api/auth/ms-login    — validate a Microsoft Entra ID token and issue a CPL-2 JWT
    POST /api/auth/refresh     — issue a fresh JWT for an already-authenticated user

Design references: Requirements 11.2, 11.3
"""

from __future__ import annotations

# ruff: noqa: B008

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth_service import (
    _expiry_minutes,
    create_access_token,
    hash_password,
    verify_password,
)
from api.dependencies import get_current_user, get_db
from db.crud import create_user, get_user_by_username
from db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas (local — full schemas live in api/schemas.py)
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_token_response(user: User) -> TokenResponse:
    """Create a JWT for *user* and wrap it in a TokenResponse."""
    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=_expiry_minutes() * 60,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT",
)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Validate username/password and return an access token.

    Returns the same 401 error regardless of whether the username or the
    password is wrong, to avoid disclosing which field was incorrect.

    Requirements: 11.2, 11.3
    """
    # Look up user — intentionally use the same error for "not found" and
    # "wrong password" so the response never reveals which field was wrong.
    _AUTH_FAILURE = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = get_user_by_username(db, body.username)
    if user is None:
        raise _AUTH_FAILURE

    if not verify_password(body.password, user.password_hash):
        raise _AUTH_FAILURE

    return _build_token_response(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an existing JWT",
)
def refresh(
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    """Issue a new token with a fresh expiry for an already-authenticated user.

    The existing token is validated via the ``get_current_user`` dependency;
    if it is expired or invalid the dependency will return 401 before this
    handler runs.

    Requirements: 11.2
    """
    return _build_token_response(current_user)


# ---------------------------------------------------------------------------
# Microsoft Entra ID (Azure AD) login
# ---------------------------------------------------------------------------


class MsLoginRequest(BaseModel):
    """Request body for Microsoft Entra ID login.

    The frontend (MSAL.js) completes the OAuth2/OIDC flow and sends the
    resulting ID token here for server-side validation.
    """
    id_token: str


@router.post(
    "/ms-login",
    response_model=TokenResponse,
    summary="Authenticate via Microsoft Entra ID (Azure AD)",
)
def ms_login(
    body: MsLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Validate a Microsoft Entra ID token and return a CPL-2 JWT.

    The frontend uses MSAL.js to complete the Microsoft OIDC flow, then POSTs
    the resulting ID token to this endpoint. The server validates the token
    using Microsoft's public JWKS endpoint (no client secret needed for ID
    token validation).

    New users are auto-provisioned on first login with the 'viewer' role.
    Existing users retain their configured role (planner / viewer).

    To enable this endpoint, set AZURE_TENANT_ID and AZURE_CLIENT_ID in your
    environment. If AZURE_CLIENT_ID is not set, returns 501 Not Implemented.

    Requirements: 11.2, 11.3
    """
    # Lazy import — avoids errors if msal/requests aren't installed for
    # environments that only use password auth
    try:
        from api.ms_auth_service import (
            extract_identity_from_ms_claims,
            validate_ms_id_token,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Microsoft authentication dependencies are not installed.",
        ) from exc

    azure_client_id = os.environ.get("AZURE_CLIENT_ID", "")
    if not azure_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Microsoft authentication is not configured on this server. "
                "Set AZURE_TENANT_ID and AZURE_CLIENT_ID environment variables."
            ),
        )

    try:
        claims = validate_ms_id_token(body.id_token)
    except ValueError as exc:
        logger.warning("MS token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Microsoft ID token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RuntimeError as exc:
        logger.error("MS auth configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not contact Microsoft authentication service.",
        ) from exc

    username, display_name = extract_identity_from_ms_claims(claims)

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract user identity from Microsoft token.",
        )

    # Auto-provision new users as 'viewer'; existing users keep their role
    user = get_user_by_username(db, username)
    if user is None:
        logger.info("Auto-provisioning new MS user: %s (%s)", username, display_name)
        user = create_user(
            db,
            username=username,
            password_hash=hash_password(os.urandom(32).hex()),  # random — MS users don't use passwords
            role="viewer",
        )

    return _build_token_response(user)

