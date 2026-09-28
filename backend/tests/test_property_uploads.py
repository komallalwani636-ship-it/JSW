"""Property-based tests for the uploads endpoint.

# Feature: cpl2-scheduling-system, Property 4: Upload record completeness

For any successful .xlsx upload, querying the stored upload record should
return the original filename, a non-null timestamp, and the uploading user's
identity.

**Validates: Requirements 1.6, 1.7**
"""

from __future__ import annotations

import io
import os
import sys

from unittest.mock import patch

from fastapi.testclient import TestClient
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from conftest import TestingSessionLocal, init_test_db, override_get_db

init_test_db()

from api.auth_service import create_access_token, hash_password
from db.models import User
from engine.parser import ParseResult
from engine.filter_pipeline import FilterResult

# ---------------------------------------------------------------------------
# Build TestClient with overrides
# ---------------------------------------------------------------------------


def _build_client():
    """Build a TestClient with SQLite in-memory DB and mocked engine calls."""
    from main import app
    from api.dependencies import get_db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    return client


# ---------------------------------------------------------------------------
# Create a planner user in the test DB (once)
# ---------------------------------------------------------------------------

_planner_id: int | None = None


def _get_or_create_planner() -> tuple[int, str]:
    """Return (planner_user_id, access_token), creating the user if needed."""
    global _planner_id

    db = TestingSessionLocal()
    try:
        if _planner_id is None:
            user = User(
                username="test_planner",
                password_hash=hash_password("password"),
                role="planner",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            _planner_id = user.id

        token = create_access_token({"sub": "test_planner", "role": "planner"})
        return _planner_id, token
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Mocked engine return values
# ---------------------------------------------------------------------------

_MOCK_PARSE_RESULT = ParseResult(rows=[], warnings=[], total_rows=0)
_MOCK_FILTER_RESULT = FilterResult(
    eligible_coils=[],
    apl7_coils=[],
    excluded_product=0,
    excluded_act_path=0,
    excluded_status=0,
    excluded_closed=0,
    apl7_count=0,
)


# ---------------------------------------------------------------------------
# Property 4: Upload record completeness
# ---------------------------------------------------------------------------


@given(
    filename=st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    ),
)
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=list(HealthCheck),
    database=None,
)
def test_upload_record_completeness(filename: str) -> None:
    """
    **Validates: Requirements 1.6, 1.7**

    For any successful .xlsx upload:
    1. Response status is 200 and upload_id is an integer.
    2. GET /api/uploads/{upload_id} returns status 200, filename ends with the
       generated filename, uploaded_at is not None, uploaded_by == planner id.
    """
    planner_id, token = _get_or_create_planner()
    client = _build_client()

    xlsx_filename = f"{filename}.xlsx"
    file_content = b"fake xlsx content"

    with (
        patch(
            "api.routers.uploads.parse_hrstock_report",
            return_value=_MOCK_PARSE_RESULT,
        ),
        patch(
            "api.routers.uploads.run_filter_pipeline",
            return_value=_MOCK_FILTER_RESULT,
        ),
    ):
        response = client.post(
            "/api/uploads",
            files={"file": (xlsx_filename, io.BytesIO(file_content), "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Body: {response.text}"
    )

    data = response.json()
    assert "upload_id" in data, f"Response missing upload_id: {data}"
    upload_id = data["upload_id"]
    assert isinstance(upload_id, int), f"upload_id is not an int: {upload_id!r}"

    # ---- GET the upload record ----
    get_response = client.get(
        f"/api/uploads/{upload_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200, (
        f"GET /api/uploads/{upload_id} returned {get_response.status_code}. "
        f"Body: {get_response.text}"
    )

    rec = get_response.json()
    assert rec["filename"].endswith(xlsx_filename), (
        f"Expected filename to end with '{xlsx_filename}', got '{rec['filename']}'"
    )
    assert rec["uploaded_at"] is not None, "uploaded_at is None"
    assert rec["uploaded_by"] == planner_id, (
        f"Expected uploaded_by={planner_id}, got {rec['uploaded_by']}"
    )
