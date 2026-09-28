"""Export router for the CPL-2 Scheduling System."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from api.dependencies import get_db, require_planner
from db.crud import create_audit_event, get_schedule
from db.models import ScheduleItem, User
from engine.exporter import build_export_workbook

router = APIRouter(prefix="/api/schedules", tags=["export"])


@router.get("/{schedule_id}/export")
def export_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> StreamingResponse:
    """Export a schedule as XLSX with Plan and APL7 sheets."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )

    stmt = (
        select(ScheduleItem)
        .where(ScheduleItem.schedule_id == schedule_id)
        .order_by(ScheduleItem.position)
        .options(selectinload(ScheduleItem.coil))
    )
    items = list(db.execute(stmt).scalars().all())

    eligible_coils = [item.coil for item in items if not item.is_apl7]
    apl7_coils = [item.coil for item in items if item.is_apl7]

    workbook = build_export_workbook(
        eligible_coils=eligible_coils,
        apl7_coils=apl7_coils,
        is_draft=schedule.status == "draft",
    )

    create_audit_event(
        db=db,
        event_type="export",
        user_id=current_user.id,
        schedule_id=schedule_id,
    )
    db.commit()

    filename = f"schedule_{schedule_id}_{schedule.version_label}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
