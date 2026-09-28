"""Property-based tests for role enforcement.

# Feature: cpl2-scheduling-system, Property 21: Role enforcement

For any write endpoint (upload, generate, reorder, finalize, unlock, export)
called with a Viewer-role JWT the response should be 403.
For any protected endpoint called without a JWT the response should be 401.

**Validates: Requirements 11.5, 11.6, 11.7, 11.8**
"""

from __future__ import annotations

import os

# Set env vars before any application modules are imported so that
# auth_service and db/session pick up the test configuration.
os.environ.setdefault("JWT_SECRET", "test-secret-for-property-tests")
os.environ.setdefault("JWT_EXPIRY_MINUTES", "60")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from unittest.mock import MagicMock

from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from api.auth_service import create_access_token

# ---------------------------------------------------------------------------
# Write endpoints under test
# Write endpoints are those that mutate state and require the 'planner' role.
# ---------------------------------------------------------------------------

WRITE_ENDPOINTS: list[tuple[str, str]] = [
    ("POST", "/api/uploads"),
    ("POST", "/api/schedules"),
    ("PATCH", "/api/schedules/1/reorder"),
    ("POST", "/api/schedules/1/finalize"),
    ("POST", "/api/schedules/1/unlock"),
    ("GET", "/api/schedules/1/export"),
]

# ---------------------------------------------------------------------------
# Minimal test application
#
# We build a slim FastAPI app that registers stub versions of every write
# endpoint.  Each stub depends on ``require_planner`` (which in turn calls
# ``get_current_user``).  This lets us test role enforcement logic without a
# real database or scheduling engine.
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """Return a minimal FastAPI application covering all write endpoints."""
    from api.dependencies import require_planner
    from db.models import User

    app = FastAPI()

    # ------------------------------------------------------------------
    # Stub database dependency — returns a MagicMock session so that
    # get_current_user can call get_user_by_username without a real DB.
    # We override this per-test via app.dependency_overrides.
    # ------------------------------------------------------------------

    # Stub endpoints — all protected by require_planner

    @app.post("/api/uploads")
    def stub_upload(planner: User = Depends(require_planner)):
        return {"status": "ok"}

    @app.post("/api/schedules")
    def stub_generate(planner: User = Depends(require_planner)):
        return {"status": "ok"}

    @app.patch("/api/schedules/{schedule_id}/reorder")
    def stub_reorder(schedule_id: int, planner: User = Depends(require_planner)):
        return {"status": "ok"}

    @app.post("/api/schedules/{schedule_id}/finalize")
    def stub_finalize(schedule_id: int, planner: User = Depends(require_planner)):
        return {"status": "ok"}

    @app.post("/api/schedules/{schedule_id}/unlock")
    def stub_unlock(schedule_id: int, planner: User = Depends(require_planner)):
        return {"status": "ok"}

    @app.get("/api/schedules/{schedule_id}/export")
    def stub_export(schedule_id: int, planner: User = Depends(require_planner)):
        return {"status": "ok"}

    return app


# ---------------------------------------------------------------------------
# Helper — build a mock User for the given role
# ---------------------------------------------------------------------------


def _mock_user(role: str) -> MagicMock:
    user = MagicMock()
    user.username = "testuser"
    user.role = role
    user.id = 1
    return user


# ---------------------------------------------------------------------------
# Helper — patch get_current_user to return a pre-built user
# ---------------------------------------------------------------------------


def _make_client_with_user(role: str) -> TestClient:
    """Return a TestClient whose get_current_user always returns *role* user."""
    app = _build_test_app()
    mock_user = _mock_user(role)

    from api.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: mock_user
    return TestClient(app, raise_server_exceptions=False)


def _make_unauthenticated_client() -> TestClient:
    """Return a TestClient that enforces real JWT validation (no override)."""
    app = _build_test_app()

    # Override get_db so no real DB connection is attempted, but keep
    # get_current_user real so that missing/invalid tokens trigger 401.
    from api.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Property 21a — Viewer JWT → write endpoints → 403
# ---------------------------------------------------------------------------


@given(
    endpoint=st.sampled_from(WRITE_ENDPOINTS),
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_viewer_gets_403_on_write_endpoints(endpoint: tuple[str, str]) -> None:
    """
    **Validates: Requirements 11.5, 11.7, 11.8**

    For any write endpoint called with a valid Viewer-role JWT the response
    status code must be 403 (Forbidden).
    """
    method, path = endpoint
    client = _make_client_with_user("viewer")

    # Generate a real Viewer JWT so the Authorization header is syntactically
    # valid — the dependency override returns the viewer user unconditionally,
    # so require_planner is what raises the 403.
    viewer_token = create_access_token({"sub": "testuser", "role": "viewer"})
    headers = {"Authorization": f"Bearer {viewer_token}"}

    response = client.request(method, path, headers=headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN, (
        f"{method} {path} with Viewer JWT returned {response.status_code}, "
        f"expected 403. Body: {response.text}"
    )


# ---------------------------------------------------------------------------
# Property 21b — No JWT → any protected endpoint → 401
# ---------------------------------------------------------------------------


@given(
    endpoint=st.sampled_from(WRITE_ENDPOINTS),
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_no_jwt_gets_401_on_protected_endpoints(endpoint: tuple[str, str]) -> None:
    """
    **Validates: Requirements 11.7**

    For any protected endpoint called without an Authorization header the
    response status code must be 401 (Unauthorized).
    """
    method, path = endpoint
    # Use a client with a real (non-overridden) get_current_user dependency so
    # that the absence of a token is properly rejected.
    client = _make_unauthenticated_client()

    response = client.request(method, path)  # no Authorization header

    assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
        f"{method} {path} without JWT returned {response.status_code}, "
        f"expected 401. Body: {response.text}"
    )
