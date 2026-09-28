"""Microsoft Entra ID (Azure AD) authentication service for the CPL-2 Scheduling System.

Validates Microsoft ID tokens using Microsoft's public JWKS keys.
The frontend uses MSAL.js to authenticate; the resulting ID token is sent
to /api/auth/ms-login which validates it and issues a CPL-2 JWT.

Configuration (environment variables):
    AZURE_TENANT_ID    — Azure AD tenant ID (or "common" for multi-tenant)
    AZURE_CLIENT_ID    — Azure AD application (client) ID

Design references: Requirements 11.2, 11.3
"""

from __future__ import annotations

import os
import logging
from functools import lru_cache

import requests
from jose import jwt as jose_jwt, JWTError

logger = logging.getLogger(__name__)

_MICROSOFT_OIDC_CONFIG_URL = (
    "https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
)


def _tenant_id() -> str:
    return os.environ.get("AZURE_TENANT_ID", "common")


def _client_id() -> str:
    cid = os.environ.get("AZURE_CLIENT_ID", "")
    if not cid:
        raise RuntimeError(
            "AZURE_CLIENT_ID environment variable is not set. "
            "Configure it with your Azure App Registration client ID."
        )
    return cid


@lru_cache(maxsize=1)
def _get_jwks_uri() -> str:
    """Fetch the JWKS URI from Microsoft's OIDC discovery document (cached)."""
    url = _MICROSOFT_OIDC_CONFIG_URL.format(tenant_id=_tenant_id())
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()["jwks_uri"]
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch Microsoft OIDC config from {url}: {exc}") from exc


def _get_jwks() -> dict:
    """Fetch current JWKS from Microsoft (not cached — keys rotate)."""
    jwks_uri = _get_jwks_uri()
    try:
        resp = requests.get(jwks_uri, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch Microsoft JWKS from {jwks_uri}: {exc}") from exc


def validate_ms_id_token(id_token: str) -> dict:
    """Validate a Microsoft ID token and return the decoded claims.

    Performs:
      - Signature verification using Microsoft's public JWKS
      - Audience check (must equal AZURE_CLIENT_ID)
      - Expiry check (exp claim)
      - Issuer check (must be Microsoft)

    Args:
        id_token: The raw Microsoft ID token string (JWT).

    Returns:
        Decoded claims dict with at least: sub, preferred_username or email, name.

    Raises:
        ValueError: If the token is invalid, expired, or from wrong audience.
    """
    client_id = _client_id()
    tenant_id = _tenant_id()

    try:
        jwks = _get_jwks()

        # Decode header to get kid
        header = jose_jwt.get_unverified_header(id_token)
        kid = header.get("kid")

        # Find matching key
        rsa_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key.get("use", "sig"),
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if rsa_key is None:
            raise ValueError("No matching key found in Microsoft JWKS for the token's kid.")

        # Build valid issuers (single tenant or common/organizations)
        if tenant_id in ("common", "organizations"):
            # We can't verify issuer precisely for multi-tenant; still check audience/exp
            options = {"verify_iss": False}
            issuer = None
        else:
            options = {"verify_iss": True}
            issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"

        claims = jose_jwt.decode(
            id_token,
            rsa_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
            options=options,
        )

        return claims

    except JWTError as exc:
        raise ValueError(f"Microsoft ID token validation failed: {exc}") from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise ValueError(f"Unexpected error validating Microsoft ID token: {exc}") from exc


def extract_identity_from_ms_claims(claims: dict) -> tuple[str, str]:
    """Extract a username and display name from validated Microsoft token claims.

    Args:
        claims: Decoded MS ID token claims dict.

    Returns:
        (username, display_name) tuple where username is the unique identifier
        used for DB lookup (preferred_username or email or sub).
    """
    # preferred_username is typically the UPN (e.g. john@company.com)
    username = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn")
        or claims.get("sub", "")
    ).lower().strip()

    display_name = (
        claims.get("name")
        or claims.get("given_name", "")
        or username
    )

    return username, display_name
