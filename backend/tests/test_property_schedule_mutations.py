"""Property-based tests for schedule mutation endpoints.

Covers Properties 16–20 for finalize, unlock, reorder, and audit completeness.
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
from db.models import Coil, Schedule, ScheduleItem, UploadFile, User, Violation
from engine.filter_pipeline import FilterResult
from engine.kpi_calculator import KpiResult
from engine.sequencer_hrpo import HrpoSequenceResult
from engine.sequencer_ngo import NgoSequenceResult
from engine.violation_detector import ViolationRecord

_MOCK_FILTER = FilterResult(
    eligible_coils=[],
    apl7_coils=[],
    excluded_product=0,
    excluded_act_path=0,
    excluded_status=0,
    excluded_closed=0,
    apl7_count=0,
)
_MOCK_HRPO = HrpoSequenceResult(sequence=[], unresolvable_tdc_pairs=[])
_MOCK_NGO = NgoSequenceResult(sequence=[], unsequenced=[])
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

_planner_id: int | None = None


def _build_client() -> TestClient:
    from api.dependencies import get_db
    from main import app

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, raise_server_exceptions=False)


def _planner_token() -> tuple[int, str]:
    global _planner_id
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.username == "mutation_planner").one_or_none()
        if user is None:
            user = User(
                username="mutation_planner",
                password_hash=hash_password("password"),
                role="planner",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        _planner_id = user.id
        token = create_access_token({"sub": "mutation_planner", "role": "planner"})
        return _planner_id, token
    finally:
        db.close()


def _seed_schedule_with_coils() -> tuple[int, list[int], str]:
    """Create upload + 2-coil schedule; return schedule_id, coil_ids, token."""
    planner_id, token = _planner_token()
    db = TestingSessionLocal()
    try:
        upload = UploadFile(
            filename="seed.xlsx",
            file_path="/tmp/seed.xlsx",
            uploaded_by=planner_id,
            row_count=2,
            parse_warnings=[],
        )
        db.add(upload)
        db.flush()

        coils = []
        for idx in range(2):
            coil = Coil(
                upload_file_id=upload.id,
                hr_coil_no=f"COIL-{idx}",
                all_columns={"HR Coil No": f"COIL-{idx}", "Product": "HRPO"},
                is_apl7=False,
            )
            db.add(coil)
            coils.append(coil)
        db.flush()

        schedule = Schedule(
            upload_file_id=upload.id,
            version_label="test-v1",
            generated_by=planner_id,
            status="draft",
            kpi_snapshot=_MOCK_KPI.__dict__,
        )
        db.add(schedule)
        db.flush()

        coil_ids = []
        for pos, coil in enumerate(coils, start=1):
            db.add(
                ScheduleItem(
                    schedule_id=schedule.id,
                    coil_id=coil.id,
                    position=pos,
                    is_apl7=False,
                )
            )
            coil_ids.append(coil.id)

        from db.crud import create_audit_event

        create_audit_event(
            db=db,
            event_type="generate",
            user_id=planner_id,
            schedule_id=schedule.id,
            upload_file_id=upload.id,
        )
        db.commit()
        return schedule.id, coil_ids, token
    finally:
        db.close()


def _engine_patches():
    return (
        patch("api.routers.schedules.run_filter_pipeline", return_value=_MOCK_FILTER),
        patch("api.routers.schedules.sequence_hrpo_hrspo", return_value=_MOCK_HRPO),
        patch("api.routers.schedules.sequence_ngo_fp", return_value=_MOCK_NGO),
        patch("api.routers.schedules.detect_violations", return_value=[]),
        patch("api.routers.schedules.compute_kpis", return_value=_MOCK_KPI),
    )


# Feature: cpl2-scheduling-system, Property 16: Schedule lock on finalization


@given(st.just(None))
@settings(max_examples=3, deadline=None, suppress_health_check=list(HealthCheck), database=None)
def test_schedule_lock_on_finalization(_: None) -> None:
    schedule_id, _, token = _seed_schedule_with_coils()
    client = _build_client()
    headers = {"Authorization": f"Bearer {token}"}

    finalize = client.post(f"/api/schedules/{schedule_id}/finalize", json={}, headers=headers)
    assert finalize.status_code == 200

    reorder = client.patch(
        f"/api/schedules/{schedule_id}/reorder",
        json={"coil_ids": []},
        headers=headers,
    )
    assert reorder.status_code == 409


# Feature: cpl2-scheduling-system, Property 17: Finalize-then-unlock round trip


@given(st.just(None))
@settings(max_examples=3, deadline=None, suppress_health_check=list(HealthCheck), database=None)
def test_finalize_unlock_round_trip(_: None) -> None:
    schedule_id, coil_ids, token = _seed_schedule_with_coils()
    client = _build_client()
    headers = {"Authorization": f"Bearer {token}"}

    before = client.get(f"/api/schedules/{schedule_id}/items", headers=headers).json()
    positions_before = [(item["coil"]["id"], item["position"]) for item in before]

    assert client.post(f"/api/schedules/{schedule_id}/finalize", json={}, headers=headers).status_code == 200
    unlock = client.post(f"/api/schedules/{schedule_id}/unlock", headers=headers)
    assert unlock.status_code == 200
    assert unlock.json()["status"] == "draft"

    after = client.get(f"/api/schedules/{schedule_id}/items", headers=headers).json()
    positions_after = [(item["coil"]["id"], item["position"]) for item in after]
    assert positions_before == positions_after


# Feature: cpl2-scheduling-system, Property 18: Override reason requirement


@given(st.just(None))
@settings(max_examples=3, deadline=None, suppress_health_check=list(HealthCheck), database=None)
def test_override_reason_required(_: None) -> None:
    schedule_id, coil_ids, token = _seed_schedule_with_coils()
    db = TestingSessionLocal()
    try:
        db.add(
            Violation(
                schedule_id=schedule_id,
                position_a=1,
                position_b=2,
                coil_id_a=coil_ids[0],
                coil_id_b=coil_ids[1],
                rule_type="thickness",
                detail={"measured_diff": 2.0},
            )
        )
        db.commit()
    finally:
        db.close()

    client = _build_client()
    headers = {"Authorization": f"Bearer {token}"}

    rejected = client.post(f"/api/schedules/{schedule_id}/finalize", json={}, headers=headers)
    assert rejected.status_code == 422

    accepted = client.post(
        f"/api/schedules/{schedule_id}/finalize",
        json={"override_reason": "Approved by supervisor"},
        headers=headers,
    )
    assert accepted.status_code == 200


# Feature: cpl2-scheduling-system, Property 19: Reorder triggers violation recomputation


@given(st.just(None))
@settings(max_examples=3, deadline=None, suppress_health_check=list(HealthCheck), database=None)
def test_reorder_recomputes_violations(_: None) -> None:
    schedule_id, coil_ids, token = _seed_schedule_with_coils()
    client = _build_client()
    headers = {"Authorization": f"Bearer {token}"}

    violation = ViolationRecord(
        position_a=0,
        position_b=1,
        rule_type="width",
        detail={"measured_diff": 400},
    )

    with patch("api.routers.schedules.detect_violations", return_value=[violation]):
        response = client.patch(
            f"/api/schedules/{schedule_id}/reorder",
            json={"coil_ids": list(reversed(coil_ids))},
            headers=headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["violations"]) == 1
    assert body["violations"][0]["rule_type"] == "width"


# Feature: cpl2-scheduling-system, Property 20: Audit event completeness


@given(st.just(None))
@settings(max_examples=3, deadline=None, suppress_health_check=list(HealthCheck), database=None)
def test_audit_event_completeness(_: None) -> None:
    schedule_id, coil_ids, token = _seed_schedule_with_coils()
    client = _build_client()
    headers = {"Authorization": f"Bearer {token}"}

    client.patch(
        f"/api/schedules/{schedule_id}/reorder",
        json={"coil_ids": list(reversed(coil_ids))},
        headers=headers,
    )
    client.post(f"/api/schedules/{schedule_id}/finalize", json={}, headers=headers)
    client.post(f"/api/schedules/{schedule_id}/unlock", headers=headers)
    client.get(f"/api/schedules/{schedule_id}/export", headers=headers)

    audit = client.get(f"/api/schedules/{schedule_id}/audit", headers=headers)
    assert audit.status_code == 200
    event_types = {event["event_type"] for event in audit.json()}
    for expected in {"generate", "reorder", "finalize", "unlock", "export"}:
        assert expected in event_types
