"""Property-based tests for the schedules endpoint.

# Feature: cpl2-scheduling-system, Property 15: Schedule version record completeness

For any schedule generation, querying the stored schedule record should return
a unique ID, a non-null generation timestamp, the generating user's identity,
and a status of 'draft'.

**Validates: Requirements 5.1, 5.2, 5.4**
"""

from __future__ import annotations

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
from db.models import User, UploadFile
from engine.filter_pipeline import FilterResult
from engine.sequencer_hrpo import HrpoSequenceResult
from engine.sequencer_ngo import NgoSequenceResult
from engine.kpi_calculator import KpiResult


# ---------------------------------------------------------------------------
# Mocked engine return values
# ---------------------------------------------------------------------------

_MOCK_FILTER_RESULT = FilterResult(
    eligible_coils=[],
    apl7_coils=[],
    excluded_product=0,
    excluded_act_path=0,
    excluded_status=0,
    excluded_closed=0,
    apl7_count=0,
)

_MOCK_HRPO_RESULT = HrpoSequenceResult(sequence=[], unresolvable_tdc_pairs=[])
_MOCK_NGO_RESULT = NgoSequenceResult(sequence=[], unsequenced=[])

_MOCK_VIOLATIONS: list = []

_MOCK_KPI = KpiResult(
    total_eligible=0,
    hrpo_count=0,
    hrpo_weight=0.0,
    hrspo_count=0,
    hrspo_weight=0.0,
    ngo_count=0,
    ngo_weight=0.0,
    age_gt_72h=0,
    age_gt_120h=0,
    age_gt_168h=0,
    violation_count=0,
    schedule_status="draft",
    version_label="2024-01-01-v1",
)


# ---------------------------------------------------------------------------
# Planner setup
# ---------------------------------------------------------------------------

_planner_id: int | None = None
_upload_id: int | None = None


def _get_or_create_planner_and_upload() -> tuple[int, int, str]:
    """Return (planner_id, upload_id, access_token)."""
    global _planner_id, _upload_id

    db = TestingSessionLocal()
    try:
        if _planner_id is None:
            user = User(
                username="test_planner_sched",
                password_hash=hash_password("password"),
                role="planner",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            _planner_id = user.id

        if _upload_id is None:
            upload = UploadFile(
                filename="test.xlsx",
                file_path="/tmp/test.xlsx",
                uploaded_by=_planner_id,
                row_count=0,
                parse_warnings=[],
            )
            db.add(upload)
            db.commit()
            db.refresh(upload)
            _upload_id = upload.id

        token = create_access_token({"sub": "test_planner_sched", "role": "planner"})
        return _planner_id, _upload_id, token
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Build TestClient
# ---------------------------------------------------------------------------


def _build_client():
    from main import app
    from api.dependencies import get_db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    return client


# ---------------------------------------------------------------------------
# Property 15: Schedule version record completeness
# ---------------------------------------------------------------------------


@given(st.just(None))  # single property — no randomness needed beyond the DB
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=list(HealthCheck),
    database=None,
)
def test_schedule_version_record_completeness(_: None) -> None:
    """
    **Validates: Requirements 5.1, 5.2, 5.4**

    After POST /api/schedules with a valid upload_id, GET /api/schedules/{id}
    returns:
    1. Unique non-null id.
    2. Non-null generated_at.
    3. status == "draft".
    4. Correct upload_file_id.
    """
    planner_id, upload_id, token = _get_or_create_planner_and_upload()
    client = _build_client()

    with (
        patch("api.routers.schedules.run_filter_pipeline", return_value=_MOCK_FILTER_RESULT),
        patch("api.routers.schedules.sequence_hrpo_hrspo", return_value=_MOCK_HRPO_RESULT),
        patch("api.routers.schedules.sequence_ngo_fp", return_value=_MOCK_NGO_RESULT),
        patch("api.routers.schedules.detect_violations", return_value=_MOCK_VIOLATIONS),
        patch("api.routers.schedules.compute_kpis", return_value=_MOCK_KPI),
    ):
        response = client.post(
            "/api/schedules",
            json={"upload_id": upload_id},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Body: {response.text}"
    )

    data = response.json()
    schedule_id = data.get("id")
    assert schedule_id is not None, f"Response missing id: {data}"
    assert isinstance(schedule_id, int), f"id is not an int: {schedule_id!r}"

    # ---- GET /api/schedules/{id} ----
    get_response = client.get(
        f"/api/schedules/{schedule_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200, (
        f"GET /api/schedules/{schedule_id} returned {get_response.status_code}. "
        f"Body: {get_response.text}"
    )

    rec = get_response.json()

    # 1. Unique non-null id
    assert rec["id"] is not None, "id is None"
    assert isinstance(rec["id"], int), f"id is not an int: {rec['id']!r}"

    # 2. Non-null generated_at
    assert rec["generated_at"] is not None, "generated_at is None"

    # 3. status == "draft"
    assert rec["status"] == "draft", (
        f"Expected status='draft', got '{rec['status']}'"
    )

    # 4. Correct upload_file_id
    assert rec["upload_file_id"] == upload_id, (
        f"Expected upload_file_id={upload_id}, got {rec['upload_file_id']}"
    )
