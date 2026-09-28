"""Schedules router for the CPL-2 Scheduling System.

Endpoints:
    POST /api/schedules                          — generate a schedule
    GET  /api/schedules                          — list all schedules
    GET  /api/schedules/{schedule_id}            — schedule detail
    GET  /api/schedules/{schedule_id}/items      — schedule items (ordered)
    GET  /api/schedules/{schedule_id}/kpis       — KPI snapshot
    GET  /api/schedules/{schedule_id}/violations — violations list

Design references: Requirements 5.1, 5.2, 5.4, 8.1, 12.1
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from api.dependencies import get_current_user, get_db, require_planner
from api.schemas import (
    AuditEvent,
    FinalizeRequest,
    KpiResult,
    ReorderRequest,
    ScheduleDetail,
    ScheduleItem,
    ScheduleSummary,
    ViolationDetail,
)
from db.crud import (
    create_audit_event,
    create_schedule,
    create_schedule_items_bulk,
    create_violations_bulk,
    delete_audit_event,
    delete_violations,
    get_all_schedules,
    get_audit_event_by_id,
    get_audit_events,
    get_coils_by_upload,
    get_deleted_schedules,
    get_schedule,
    get_upload_file,
    get_violations,
    hard_delete_schedule,
    restore_schedule,
    soft_delete_schedule,
    update_schedule_item_positions,
    update_schedule_status,
)
from db.models import Schedule, ScheduleItem as ScheduleItemModel, User, Coil
from engine.filter_pipeline import run_filter_pipeline
from engine.kpi_calculator import compute_kpis
from engine.optimizer import optimize_schedule_sequence
from engine.parser import CoilRow
from engine.sequencer_hrpo import sequence_hrpo_hrspo
from engine.sequencer_ngo import sequence_ngo_fp
from engine.violation_detector import detect_violations, ViolationRecord

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

_FINALIZED_MSG = "Schedule is finalized. Use Unlock/Revise to edit."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_draft(schedule: Schedule) -> None:
    if schedule.status == "final":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_FINALIZED_MSG,
        )


def _fetch_schedule(db: Session, schedule_id: int) -> Schedule:
    stmt = (
        select(Schedule)
        .where(Schedule.id == schedule_id)
        .options(
            selectinload(Schedule.items).selectinload(ScheduleItemModel.coil),
            selectinload(Schedule.violations),
        )
    )
    schedule = db.execute(stmt).scalar_one_or_none()
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )
    return schedule


def _build_violation_dicts(
    sequence: list[CoilRow],
    coil_no_to_orm: dict[str, Coil],
    violations: list[ViolationRecord],
) -> list[dict]:
    violation_dicts: list[dict] = []
    for v in violations:
        row_a = sequence[v.position_a] if v.position_a < len(sequence) else None
        row_b = sequence[v.position_b] if v.position_b < len(sequence) else None
        coil_a_orm = coil_no_to_orm.get(row_a.hr_coil_no) if row_a else None
        coil_b_orm = coil_no_to_orm.get(row_b.hr_coil_no) if row_b else None
        if coil_a_orm and coil_b_orm:
            violation_dicts.append(
                {
                    "position_a": v.position_a + 1,
                    "position_b": v.position_b + 1,
                    "coil_id_a": coil_a_orm.id,
                    "coil_id_b": coil_b_orm.id,
                    "rule_type": v.rule_type,
                    "detail": v.detail,
                }
            )
    return violation_dicts


def _eligible_sequence_from_items(items: list[ScheduleItemModel]) -> list[CoilRow]:
    eligible_items = [item for item in items if not item.is_apl7]
    eligible_items.sort(key=lambda i: i.position)
    return [_orm_coil_to_row(item.coil) for item in eligible_items]


# ---------------------------------------------------------------------------
# Helper — ORM Coil → CoilRow
# ---------------------------------------------------------------------------


def _orm_coil_to_row(coil: Coil) -> CoilRow:
    """Map an ORM Coil instance to a CoilRow dataclass for the engine."""
    return CoilRow(
        hr_order_no=coil.hr_order_no,
        hr_coil_no=coil.hr_coil_no,
        thk=float(coil.thk) if coil.thk is not None else None,
        wdt=float(coil.wdt) if coil.wdt is not None else None,
        wgt=float(coil.wgt) if coil.wgt is not None else None,
        grade=coil.grade,
        age_hours=float(coil.age_hours) if coil.age_hours is not None else None,
        status=coil.status,
        cust=coil.cust,
        cr_coil_no=coil.cr_coil_no,
        routing=coil.routing,
        product=coil.product,
        act_path=int(coil.act_path) if coil.act_path is not None else None,
        prev_unit=int(coil.prev_unit) if coil.prev_unit is not None else None,
        silicon_pct=float(coil.silicon_pct) if coil.silicon_pct is not None else None,
        receiving_remarks=coil.receiving_remarks,
        order_status=coil.order_status,
        tdc=coil.tdc,
        edge_condth=coil.edge_condth,
        ord_wdth_min=float(coil.ord_wdth_min) if coil.ord_wdth_min is not None else None,
        ord_wdth_max=float(coil.ord_wdth_max) if coil.ord_wdth_max is not None else None,
        target_width=float(coil.target_width) if coil.target_width is not None else None,
        next_work_center=coil.next_work_center,
        all_columns=coil.all_columns if coil.all_columns is not None else {},
    )


# ---------------------------------------------------------------------------
# POST /api/schedules — generate a schedule
# ---------------------------------------------------------------------------


@router.post("", response_model=ScheduleSummary, status_code=200)
def generate_schedule(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> ScheduleSummary:
    """Generate a new draft schedule from an existing upload.

    Requirements: 5.1, 5.2, 5.4, 12.1
    """
    upload_id: int = body.get("upload_id")
    if upload_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="upload_id is required.",
        )

    # ---- Load upload + coils -----------------------------------------------
    upload = get_upload_file(db, upload_id)
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload {upload_id} not found.",
        )

    orm_coils: list[Coil] = get_coils_by_upload(db, upload_id)

    # ---- Convert to CoilRow for the engine ---------------------------------
    all_rows = [_orm_coil_to_row(c) for c in orm_coils]

    # ---- Filter pipeline ---------------------------------------------------
    filter_result = run_filter_pipeline(all_rows)

    # ---- Separate by product -----------------------------------------------
    hrpo_hrspo_eligible = [
        c for c in filter_result.eligible_coils
        if c.product in ("HRPO", "HRSPO")
    ]
    ngo_eligible = [
        c for c in filter_result.eligible_coils
        if c.product == "NGO FP"
    ]

    # ---- Sequence ----------------------------------------------------------
    hrpo_result = sequence_hrpo_hrspo(hrpo_hrspo_eligible)
    ngo_result = sequence_ngo_fp(ngo_eligible)

    # ---- Combine: HRPO/HRSPO first, then NGO FP ----------------------------
    combined_sequence: list[CoilRow] = hrpo_result.sequence + ngo_result.sequence

    # ---- Auto-resolve violations via constraint-guided optimization --------
    combined_sequence = optimize_schedule_sequence(combined_sequence)

    # Build a mapping from hr_coil_no → ORM Coil for position assignment
    coil_no_to_orm: dict[str, Coil] = {c.hr_coil_no: c for c in orm_coils}

    # ---- Detect violations -------------------------------------------------
    violations: list[ViolationRecord] = detect_violations(combined_sequence)

    # ---- Version label -----------------------------------------------------
    version_label = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-v1"

    # ---- KPI ---------------------------------------------------------------
    kpi = compute_kpis(
        eligible_coils=filter_result.eligible_coils,
        violations=violations,
        schedule_status="draft",
        version_label=version_label,
    )

    # ---- Persist (single transaction) --------------------------------------
    schedule = create_schedule(
        db=db,
        upload_file_id=upload_id,
        version_label=version_label,
        generated_by=current_user.id,
    )

    # Build (coil_id, position, is_apl7) list for sequenced eligible coils
    coil_id_positions: list[tuple[int, int, bool]] = []
    for pos, row in enumerate(combined_sequence, start=1):
        orm_coil = coil_no_to_orm.get(row.hr_coil_no)
        if orm_coil is not None:
            coil_id_positions.append((orm_coil.id, pos, orm_coil.is_apl7))

    # Also append APL7 coils after the regular sequence
    next_pos = len(combined_sequence) + 1
    for row in filter_result.apl7_coils:
        orm_coil = coil_no_to_orm.get(row.hr_coil_no)
        if orm_coil is not None:
            coil_id_positions.append((orm_coil.id, next_pos, True))
            next_pos += 1

    create_schedule_items_bulk(
        db=db,
        schedule_id=schedule.id,
        coil_id_positions=coil_id_positions,
    )

    # Build violation dicts (0-based positions from detector → convert to 1-based)
    violation_dicts = _build_violation_dicts(
        combined_sequence, coil_no_to_orm, violations
    )

    create_violations_bulk(
        db=db,
        schedule_id=schedule.id,
        violations=violation_dicts,
    )

    # Update KPI snapshot
    schedule.kpi_snapshot = kpi.__dict__

    create_audit_event(
        db=db,
        event_type="generate",
        user_id=current_user.id,
        schedule_id=schedule.id,
        upload_file_id=upload_id,
    )

    db.commit()
    db.refresh(schedule)

    return ScheduleSummary.model_validate(schedule)


# ---------------------------------------------------------------------------
# GET /api/schedules — list all schedules
# ---------------------------------------------------------------------------


@router.get("", response_model=List[ScheduleSummary], status_code=200)
def list_schedules(
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ScheduleSummary]:
    """Return active schedules ordered by generation time descending.

    Requirements: 5.5
    """
    schedules = get_all_schedules(db, include_deleted=include_deleted)
    return [
        ScheduleSummary(
            id=s.id,
            version_label=s.version_label,
            status=s.status,
            generated_at=s.generated_at,
            upload_file_id=s.upload_file_id,
            kpi_snapshot=s.kpi_snapshot,
            upload_filename=s.upload_file.filename if s.upload_file else None,
            generator_username=s.generator.username if s.generator else None,
            is_deleted=s.is_deleted,
            deleted_at=s.deleted_at,
        )
        for s in schedules
    ]


# ---------------------------------------------------------------------------
# GET /api/schedules/bin — list deleted schedules in the Bin
# ---------------------------------------------------------------------------


@router.get("/bin", response_model=List[ScheduleSummary], status_code=200)
def list_bin_schedules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ScheduleSummary]:
    """Return all schedules currently in the Bin (soft-deleted)."""
    schedules = get_deleted_schedules(db)
    return [
        ScheduleSummary(
            id=s.id,
            version_label=s.version_label,
            status=s.status,
            generated_at=s.generated_at,
            upload_file_id=s.upload_file_id,
            kpi_snapshot=s.kpi_snapshot,
            upload_filename=s.upload_file.filename if s.upload_file else None,
            generator_username=s.generator.username if s.generator else None,
            is_deleted=s.is_deleted,
            deleted_at=s.deleted_at,
        )
        for s in schedules
    ]


# ---------------------------------------------------------------------------
# DELETE /api/schedules/{schedule_id} — move schedule to Bin (soft-delete)
# ---------------------------------------------------------------------------


@router.delete("/{schedule_id}", status_code=200)
def move_schedule_to_bin(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> dict:
    """Move a schedule to the Bin (soft-delete)."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )
    soft_delete_schedule(db, schedule_id, current_user.id)
    create_audit_event(
        db=db,
        event_type="delete_to_bin",
        user_id=current_user.id,
        schedule_id=schedule_id,
        detail={"version_label": schedule.version_label},
    )
    db.commit()
    return {"message": f"Schedule {schedule.version_label} moved to Bin.", "id": schedule_id}


# ---------------------------------------------------------------------------
# POST /api/schedules/{schedule_id}/restore — restore schedule from Bin
# ---------------------------------------------------------------------------


@router.post("/{schedule_id}/restore", status_code=200)
def restore_schedule_from_bin(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> dict:
    """Restore a schedule from the Bin back to active History."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )
    restore_schedule(db, schedule_id)
    create_audit_event(
        db=db,
        event_type="restore_from_bin",
        user_id=current_user.id,
        schedule_id=schedule_id,
        detail={"version_label": schedule.version_label},
    )
    db.commit()
    return {"message": f"Schedule {schedule.version_label} restored from Bin.", "id": schedule_id}


# ---------------------------------------------------------------------------
# DELETE /api/schedules/{schedule_id}/permanent — hard delete
# ---------------------------------------------------------------------------


@router.delete("/{schedule_id}/permanent", status_code=200)
def permanently_delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> dict:
    """Permanently delete a schedule from the database."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )
    version_label = schedule.version_label
    hard_delete_schedule(db, schedule_id)
    db.commit()
    return {"message": f"Schedule {version_label} permanently deleted.", "id": schedule_id}


# ---------------------------------------------------------------------------
# GET /api/schedules/{schedule_id} — schedule detail
# ---------------------------------------------------------------------------


@router.get("/{schedule_id}", response_model=ScheduleDetail, status_code=200)
def get_schedule_detail(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScheduleDetail:
    """Return full schedule detail including items and violations.

    Requirements: 5.5
    """
    stmt = (
        select(Schedule)
        .where(Schedule.id == schedule_id)
        .options(
            selectinload(Schedule.items).selectinload(ScheduleItemModel.coil),
            selectinload(Schedule.violations),
        )
    )
    schedule = db.execute(stmt).scalar_one_or_none()

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )

    return ScheduleDetail.model_validate(schedule)


@router.get("/{schedule_id}/items", response_model=List[ScheduleItem], status_code=200)
def get_items(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ScheduleItem]:
    """Return schedule items ordered by position.

    Requirements: 9.1
    """
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )

    stmt = (
        select(ScheduleItemModel)
        .where(ScheduleItemModel.schedule_id == schedule_id)
        .order_by(ScheduleItemModel.position)
        .options(selectinload(ScheduleItemModel.coil))
    )
    items = list(db.execute(stmt).scalars().all())
    return [ScheduleItem.model_validate(item) for item in items]


# ---------------------------------------------------------------------------
# GET /api/schedules/{schedule_id}/kpis — KPI snapshot
# ---------------------------------------------------------------------------


@router.get("/{schedule_id}/kpis", response_model=KpiResult, status_code=200)
def get_kpis(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KpiResult:
    """Return the KPI snapshot for a schedule.

    Requirements: 8.1, 8.5
    """
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )
    if schedule.kpi_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No KPI snapshot for schedule {schedule_id}.",
        )

    return KpiResult(**schedule.kpi_snapshot)


# ---------------------------------------------------------------------------
# GET /api/schedules/{schedule_id}/violations — violations list
# ---------------------------------------------------------------------------


@router.get(
    "/{schedule_id}/violations",
    response_model=List[ViolationDetail],
    status_code=200,
)
def get_violations_list(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ViolationDetail]:
    """Return all violations for a schedule.

    Requirements: 7.2, 7.3
    """
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )

    violations = get_violations(db, schedule_id)
    return [ViolationDetail.model_validate(v) for v in violations]


# ---------------------------------------------------------------------------
# PATCH /api/schedules/{schedule_id}/reorder
# ---------------------------------------------------------------------------


@router.patch("/{schedule_id}/reorder", response_model=ScheduleDetail, status_code=200)
def reorder_schedule(
    schedule_id: int,
    body: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> ScheduleDetail:
    """Reorder eligible coils in a draft schedule and recompute violations."""
    schedule = _fetch_schedule(db, schedule_id)
    _ensure_draft(schedule)

    non_apl7_items = [item for item in schedule.items if not item.is_apl7]
    apl7_items = [item for item in schedule.items if item.is_apl7]
    current_coil_ids = {item.coil_id for item in non_apl7_items}

    if set(body.coil_ids) != current_coil_ids or len(body.coil_ids) != len(current_coil_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="coil_ids must contain exactly the current eligible coil IDs.",
        )

    coil_id_to_item = {item.coil_id: item for item in non_apl7_items}
    old_positions = {item.coil_id: item.position for item in non_apl7_items}

    new_positions: list[tuple[int, int]] = []
    position_changes: list[dict] = []
    for idx, coil_id in enumerate(body.coil_ids, start=1):
        new_positions.append((coil_id, idx))
        old_pos = old_positions[coil_id]
        if old_pos != idx:
            position_changes.append(
                {
                    "coil_id": coil_id,
                    "hr_coil_no": coil_id_to_item[coil_id].coil.hr_coil_no,
                    "old_position": old_pos,
                    "new_position": idx,
                }
            )

    update_schedule_item_positions(db, schedule_id, new_positions)

    next_pos = len(body.coil_ids) + 1
    apl7_positions: list[tuple[int, int]] = []
    for item in sorted(apl7_items, key=lambda i: i.position):
        apl7_positions.append((item.coil_id, next_pos))
        next_pos += 1
    if apl7_positions:
        update_schedule_item_positions(db, schedule_id, apl7_positions)

    schedule = _fetch_schedule(db, schedule_id)
    sequence = _eligible_sequence_from_items(list(schedule.items))
    violations = detect_violations(sequence)

    orm_coils = get_coils_by_upload(db, schedule.upload_file_id)
    coil_no_to_orm = {c.hr_coil_no: c for c in orm_coils}

    delete_violations(db, schedule_id)
    create_violations_bulk(
        db,
        schedule_id,
        _build_violation_dicts(sequence, coil_no_to_orm, violations),
    )

    if schedule.kpi_snapshot:
        kpi_data = dict(schedule.kpi_snapshot)
        kpi_data["violation_count"] = len(violations)
        kpi_data["schedule_status"] = schedule.status
        schedule.kpi_snapshot = kpi_data

    create_audit_event(
        db=db,
        event_type="reorder",
        user_id=current_user.id,
        schedule_id=schedule_id,
        detail={"position_changes": position_changes},
    )

    db.commit()
    return ScheduleDetail.model_validate(_fetch_schedule(db, schedule_id))


# ---------------------------------------------------------------------------
# POST /api/schedules/{schedule_id}/optimize
# ---------------------------------------------------------------------------


@router.post("/{schedule_id}/optimize", response_model=ScheduleDetail, status_code=200)
def optimize_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> ScheduleDetail:
    """Auto-resolve violations in a draft schedule using constraint-guided permutation search."""
    schedule = _fetch_schedule(db, schedule_id)
    _ensure_draft(schedule)

    non_apl7_items = sorted([item for item in schedule.items if not item.is_apl7], key=lambda i: i.position)

    if len(non_apl7_items) <= 1:
        return ScheduleDetail.model_validate(schedule)

    coil_rows = [_orm_coil_to_row(item.coil) for item in non_apl7_items]
    coil_no_to_coil_id = {item.coil.hr_coil_no: item.coil_id for item in non_apl7_items}

    optimized_rows = optimize_schedule_sequence(coil_rows)
    optimized_coil_ids = [
        coil_no_to_coil_id[r.hr_coil_no]
        for r in optimized_rows
        if r.hr_coil_no in coil_no_to_coil_id
    ]

    return reorder_schedule(
        schedule_id=schedule_id,
        body=ReorderRequest(coil_ids=optimized_coil_ids),
        db=db,
        current_user=current_user,
    )


# ---------------------------------------------------------------------------
# POST /api/schedules/{schedule_id}/finalize
# ---------------------------------------------------------------------------


@router.post("/{schedule_id}/finalize", response_model=ScheduleSummary, status_code=200)
def finalize_schedule(
    schedule_id: int,
    body: FinalizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> ScheduleSummary:
    """Finalize a draft schedule."""
    schedule = _fetch_schedule(db, schedule_id)
    _ensure_draft(schedule)

    violations = get_violations(db, schedule_id)
    if violations and not (body.override_reason and body.override_reason.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Override reason required when violations are present.",
        )

    now = datetime.now(timezone.utc)
    schedule = update_schedule_status(
        db,
        schedule_id,
        "final",
        finalized_by=current_user.id,
        finalized_at=now,
        override_reason=body.override_reason.strip() if body.override_reason else None,
    )

    if schedule.kpi_snapshot:
        kpi_data = dict(schedule.kpi_snapshot)
        kpi_data["schedule_status"] = "final"
        schedule.kpi_snapshot = kpi_data

    create_audit_event(
        db=db,
        event_type="finalize",
        user_id=current_user.id,
        schedule_id=schedule_id,
        detail={"override_reason": body.override_reason},
    )

    db.commit()
    db.refresh(schedule)
    return ScheduleSummary.model_validate(schedule)


# ---------------------------------------------------------------------------
# POST /api/schedules/{schedule_id}/unlock
# ---------------------------------------------------------------------------


@router.post("/{schedule_id}/unlock", response_model=ScheduleSummary, status_code=200)
def unlock_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> ScheduleSummary:
    """Unlock a finalized schedule back to draft."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )
    if schedule.status != "final":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Schedule is not finalized.",
        )

    now = datetime.now(timezone.utc)
    schedule = update_schedule_status(
        db,
        schedule_id,
        "draft",
        unlocked_by=current_user.id,
        unlocked_at=now,
    )

    if schedule.kpi_snapshot:
        kpi_data = dict(schedule.kpi_snapshot)
        kpi_data["schedule_status"] = "draft"
        schedule.kpi_snapshot = kpi_data

    create_audit_event(
        db=db,
        event_type="unlock",
        user_id=current_user.id,
        schedule_id=schedule_id,
    )

    db.commit()
    db.refresh(schedule)
    return ScheduleSummary.model_validate(schedule)


# ---------------------------------------------------------------------------
# GET /api/schedules/{schedule_id}/audit
# ---------------------------------------------------------------------------


@router.get("/{schedule_id}/audit", response_model=List[AuditEvent], status_code=200)
def get_schedule_audit(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> List[AuditEvent]:
    """Return chronological audit events for a schedule (Planner only)."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )

    events = get_audit_events(db, schedule_id)
    return [AuditEvent.model_validate(e) for e in events]


# ---------------------------------------------------------------------------
# POST /api/schedules/{schedule_id}/undo
# ---------------------------------------------------------------------------


@router.post("/{schedule_id}/undo", response_model=ScheduleDetail, status_code=200)
def undo_last_reorder(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> ScheduleDetail:
    """Revert the most recent sequence change / reorder on a draft schedule."""
    schedule = _fetch_schedule(db, schedule_id)
    _ensure_draft(schedule)

    events = get_audit_events(db, schedule_id)
    undone_ids = {
        e.detail.get("undone_audit_id")
        for e in events
        if e.event_type == "undo_reorder" and e.detail and "undone_audit_id" in e.detail
    }

    eligible_reorders = [
        e
        for e in reversed(events)
        if e.event_type == "reorder"
        and e.detail
        and e.detail.get("position_changes")
        and e.id not in undone_ids
    ]

    if not eligible_reorders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No previous sequence changes available to undo.",
        )

    target_event = eligible_reorders[0]
    position_changes = target_event.detail.get("position_changes", [])

    non_apl7_items = sorted(
        [item for item in schedule.items if not item.is_apl7],
        key=lambda i: i.position,
    )
    coil_positions = {item.coil_id: item.position for item in non_apl7_items}

    for change in position_changes:
        cid = change["coil_id"]
        if cid in coil_positions:
            coil_positions[cid] = change["old_position"]

    restored_coil_ids = sorted(coil_positions.keys(), key=lambda cid: coil_positions[cid])
    new_positions = [(cid, idx) for idx, cid in enumerate(restored_coil_ids, start=1)]
    update_schedule_item_positions(db, schedule_id, new_positions)

    schedule = _fetch_schedule(db, schedule_id)
    sequence = _eligible_sequence_from_items(list(schedule.items))
    violations = detect_violations(sequence)

    orm_coils = get_coils_by_upload(db, schedule.upload_file_id)
    coil_no_to_orm = {c.hr_coil_no: c for c in orm_coils}

    delete_violations(db, schedule_id)
    create_violations_bulk(
        db,
        schedule_id,
        _build_violation_dicts(sequence, coil_no_to_orm, violations),
    )

    if schedule.kpi_snapshot:
        kpi_data = dict(schedule.kpi_snapshot)
        kpi_data["violation_count"] = len(violations)
        kpi_data["schedule_status"] = schedule.status
        schedule.kpi_snapshot = kpi_data

    create_audit_event(
        db=db,
        event_type="undo_reorder",
        user_id=current_user.id,
        schedule_id=schedule_id,
        detail={
            "undone_audit_id": target_event.id,
            "reverted_position_changes": position_changes,
        },
    )

    db.commit()
    return ScheduleDetail.model_validate(_fetch_schedule(db, schedule_id))


# ---------------------------------------------------------------------------
# POST /api/schedules/{schedule_id}/audit/{audit_id}/revert
# ---------------------------------------------------------------------------


@router.post(
    "/{schedule_id}/audit/{audit_id}/revert",
    response_model=ScheduleDetail,
    status_code=200,
)
def revert_schedule_audit_event(
    schedule_id: int,
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> ScheduleDetail:
    """Revert the position changes associated with a specific audit event."""
    schedule = _fetch_schedule(db, schedule_id)
    _ensure_draft(schedule)

    event = get_audit_event_by_id(db, audit_id)
    if event is None or event.schedule_id != schedule_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event {audit_id} not found for schedule {schedule_id}.",
        )

    position_changes = (event.detail or {}).get("position_changes", [])
    if not position_changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audit event {audit_id} has no sequence position changes to revert.",
        )

    non_apl7_items = sorted(
        [item for item in schedule.items if not item.is_apl7],
        key=lambda i: i.position,
    )
    coil_positions = {item.coil_id: item.position for item in non_apl7_items}

    for change in position_changes:
        cid = change["coil_id"]
        if cid in coil_positions:
            coil_positions[cid] = change["old_position"]

    restored_coil_ids = sorted(coil_positions.keys(), key=lambda cid: coil_positions[cid])
    new_positions = [(cid, idx) for idx, cid in enumerate(restored_coil_ids, start=1)]
    update_schedule_item_positions(db, schedule_id, new_positions)

    schedule = _fetch_schedule(db, schedule_id)
    sequence = _eligible_sequence_from_items(list(schedule.items))
    violations = detect_violations(sequence)

    orm_coils = get_coils_by_upload(db, schedule.upload_file_id)
    coil_no_to_orm = {c.hr_coil_no: c for c in orm_coils}

    delete_violations(db, schedule_id)
    create_violations_bulk(
        db,
        schedule_id,
        _build_violation_dicts(sequence, coil_no_to_orm, violations),
    )

    if schedule.kpi_snapshot:
        kpi_data = dict(schedule.kpi_snapshot)
        kpi_data["violation_count"] = len(violations)
        kpi_data["schedule_status"] = schedule.status
        schedule.kpi_snapshot = kpi_data

    create_audit_event(
        db=db,
        event_type="undo_reorder",
        user_id=current_user.id,
        schedule_id=schedule_id,
        detail={
            "undone_audit_id": audit_id,
            "reverted_position_changes": position_changes,
        },
    )

    db.commit()
    return ScheduleDetail.model_validate(_fetch_schedule(db, schedule_id))


# ---------------------------------------------------------------------------
# DELETE /api/schedules/{schedule_id}/audit/{audit_id}
# ---------------------------------------------------------------------------


@router.delete("/{schedule_id}/audit/{audit_id}", status_code=200)
def delete_schedule_audit_event(
    schedule_id: int,
    audit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> dict:
    """Delete an audit event from the schedule audit log (Planner only)."""
    schedule = get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found.",
        )

    event = get_audit_event_by_id(db, audit_id)
    if event is None or event.schedule_id != schedule_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event {audit_id} not found for schedule {schedule_id}.",
        )

    delete_audit_event(db, audit_id)
    db.commit()
    return {"message": f"Audit event {audit_id} deleted successfully.", "id": audit_id}

