import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import init_test_db, override_get_db
from fastapi.testclient import TestClient
from main import app
from api.dependencies import get_db
from tests.test_property_schedule_mutations import _seed_schedule_with_coils

init_test_db()
app.dependency_overrides[get_db] = override_get_db


def test_undo_last_reorder_and_delete_audit():
    schedule_id, coil_ids, token = _seed_schedule_with_coils()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch initial schedule
    initial_res = client.get(f"/api/schedules/{schedule_id}", headers=headers)
    assert initial_res.status_code == 200
    initial_order = [item["coil"]["id"] for item in initial_res.json()["items"] if not item["is_apl7"]]

    # 2. Reorder sequence (reverse order)
    reversed_order = list(reversed(initial_order))
    reorder_res = client.patch(
        f"/api/schedules/{schedule_id}/reorder",
        json={"coil_ids": reversed_order},
        headers=headers,
    )
    assert reorder_res.status_code == 200
    current_order = [item["coil"]["id"] for item in reorder_res.json()["items"] if not item["is_apl7"]]
    assert current_order == reversed_order

    # 3. Check audit trail has reorder
    audit_res = client.get(f"/api/schedules/{schedule_id}/audit", headers=headers)
    assert audit_res.status_code == 200
    events = audit_res.json()
    reorder_events = [e for e in events if e["event_type"] == "reorder"]
    assert len(reorder_events) >= 1
    last_reorder_id = reorder_events[-1]["id"]

    # 4. Undo the last reorder
    undo_res = client.post(f"/api/schedules/{schedule_id}/undo", headers=headers)
    assert undo_res.status_code == 200
    restored_order = [item["coil"]["id"] for item in undo_res.json()["items"] if not item["is_apl7"]]
    assert restored_order == initial_order

    # 5. Check audit trail now records undo_reorder
    audit_res_after = client.get(f"/api/schedules/{schedule_id}/audit", headers=headers)
    assert audit_res_after.status_code == 200
    undo_events = [e for e in audit_res_after.json() if e["event_type"] == "undo_reorder"]
    assert len(undo_events) == 1
    assert undo_events[0]["detail"]["undone_audit_id"] == last_reorder_id

    # 6. Delete the undo audit event
    del_res = client.delete(
        f"/api/schedules/{schedule_id}/audit/{undo_events[0]['id']}",
        headers=headers,
    )
    assert del_res.status_code == 200
    assert del_res.json()["id"] == undo_events[0]["id"]

    # Verify it is deleted from audit trail
    audit_res_final = client.get(f"/api/schedules/{schedule_id}/audit", headers=headers)
    event_ids = [e["id"] for e in audit_res_final.json()]
    assert undo_events[0]["id"] not in event_ids
