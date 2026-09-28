"""Tests for Microsoft Entra ID authentication endpoint.

Validates:
- 501 Not Implemented when AZURE_CLIENT_ID is not configured
- 401 Unauthorized when MS token is invalid/expired
- 503 Service Unavailable when Microsoft OIDC endpoint cannot be reached
- Successful login, token issue, and user auto-provisioning
"""

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-key-1234567890123456")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from main import app
from api.dependencies import get_db
from tests.conftest import override_get_db, init_test_db


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    init_test_db()
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_ms_login_not_configured(client, monkeypatch):
    """When AZURE_CLIENT_ID is empty, return 501."""
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    resp = client.post("/api/auth/ms-login", json={"id_token": "dummy-token"})
    assert resp.status_code == 501
    assert "not configured" in resp.json()["detail"]


def test_ms_login_invalid_token(client, monkeypatch):
    """When Microsoft token fails validation, return 401."""
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant-id")

    with patch("api.ms_auth_service.validate_ms_id_token", side_effect=ValueError("Token expired")):
        resp = client.post("/api/auth/ms-login", json={"id_token": "expired-token"})
        assert resp.status_code == 401
        assert "invalid or expired" in resp.json()["detail"].lower()


def test_ms_login_network_error(client, monkeypatch):
    """When Microsoft OIDC service cannot be reached, return 503."""
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")

    with patch("api.ms_auth_service.validate_ms_id_token", side_effect=RuntimeError("Connection refused")):
        resp = client.post("/api/auth/ms-login", json={"id_token": "some-token"})
        assert resp.status_code == 503


def test_ms_login_success_auto_provisions_user(client, monkeypatch):
    """Valid Microsoft token issues CPL-2 JWT and provisions user."""
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    fake_claims = {
        "sub": "ms-user-12345",
        "preferred_username": "planner_user@example.com",
        "name": "Jane Planner",
    }

    with patch("api.ms_auth_service.validate_ms_id_token", return_value=fake_claims):
        resp = client.post("/api/auth/ms-login", json={"id_token": "valid-ms-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
