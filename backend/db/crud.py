"""CRUD functions for the CPL-2 Scheduling System.

All functions accept a SQLAlchemy 2.0 synchronous Session as their first
parameter and do NOT commit — transaction management is the caller's
responsibility.

Design references: Requirements 5.1, 5.2, 12.1
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.models import (
    AuditEvent,
    Coil,
    Schedule,
    ScheduleItem,
    UploadFile,
    User,
    Violation,
)

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def get_user_by_username(db: Session, username: str) -> User | None:
    """Return the User with the given username, or None if not found."""
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Return the User with the given primary key, or None if not found."""
    return db.get(User, user_id)


def create_user(db: Session, username: str, password_hash: str, role: str) -> User:
    """Insert a new user row and return the refreshed ORM object."""
    user = User(username=username, password_hash=password_hash, role=role)
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Upload Files
# ---------------------------------------------------------------------------


def create_upload_file(
    db: Session,
    filename: str,
    file_path: str,
    uploaded_by: int,
    row_count: int,
    parse_warnings: list,
) -> UploadFile:
    """Insert a new upload_files row and return the refreshed ORM object."""
    upload = UploadFile(
        filename=filename,
        file_path=file_path,
        uploaded_by=uploaded_by,
        row_count=row_count,
        parse_warnings=parse_warnings,
    )
    db.add(upload)
    db.flush()
    db.refresh(upload)
    return upload


def get_upload_file(db: Session, upload_id: int) -> UploadFile | None:
    """Return the UploadFile with the given primary key, or None."""
    return db.get(UploadFile, upload_id)


# ---------------------------------------------------------------------------
# Coils
# ---------------------------------------------------------------------------


def create_coils_bulk(db: Session, coils: list[dict]) -> list[Coil]:
    """Bulk-insert a list of coil attribute dicts and return the inserted objects.

    Each dict must contain keys that match Coil column names.  The objects are
    flushed (but not committed) so their server-generated primary keys are
    available immediately.
    """
    if not coils:
        return []

    objects = [Coil(**coil_dict) for coil_dict in coils]
    db.add_all(objects)
    db.flush()
    for obj in objects:
        db.refresh(obj)
    return objects


def get_coils_by_upload(db: Session, upload_id: int) -> list[Coil]:
    """Return all coils belonging to the given upload, in insertion order."""
    stmt = select(Coil).where(Coil.upload_file_id == upload_id)
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


def create_schedule(
    db: Session,
    upload_file_id: int,
    version_label: str,
    generated_by: int,
) -> Schedule:
    """Insert a new schedule row with status='draft' and return it refreshed."""
    schedule = Schedule(
        upload_file_id=upload_file_id,
        version_label=version_label,
        generated_by=generated_by,
        status="draft",
    )
    db.add(schedule)
    db.flush()
    db.refresh(schedule)
    return schedule


def get_schedule(db: Session, schedule_id: int) -> Schedule | None:
    """Return the Schedule with the given primary key, or None."""
    return db.get(Schedule, schedule_id)


def get_all_schedules(db: Session, include_deleted: bool = False) -> list[Schedule]:
    """Return all active (non-deleted) schedules ordered by generation time descending."""
    stmt = (
        select(Schedule)
        .options(
            selectinload(Schedule.upload_file),
            selectinload(Schedule.generator),
        )
    )
    if not include_deleted:
        stmt = stmt.where(Schedule.is_deleted.is_(False))
    stmt = stmt.order_by(Schedule.generated_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_deleted_schedules(db: Session) -> list[Schedule]:
    """Return all schedules currently in the Bin (soft-deleted)."""
    stmt = (
        select(Schedule)
        .where(Schedule.is_deleted.is_(True))
        .options(
            selectinload(Schedule.upload_file),
            selectinload(Schedule.generator),
            selectinload(Schedule.deleter),
        )
        .order_by(Schedule.deleted_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def soft_delete_schedule(db: Session, schedule_id: int, user_id: int) -> Schedule:
    """Move a schedule to the Bin (soft delete)."""
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise ValueError(f"Schedule {schedule_id} not found.")
    schedule.is_deleted = True
    schedule.deleted_at = datetime.now(timezone.utc)
    schedule.deleted_by = user_id
    db.flush()
    db.refresh(schedule)
    return schedule


def restore_schedule(db: Session, schedule_id: int) -> Schedule:
    """Restore a schedule from the Bin."""
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise ValueError(f"Schedule {schedule_id} not found.")
    schedule.is_deleted = False
    schedule.deleted_at = None
    schedule.deleted_by = None
    db.flush()
    db.refresh(schedule)
    return schedule


def hard_delete_schedule(db: Session, schedule_id: int) -> bool:
    """Permanently delete a schedule and its cascading items/violations from the DB."""
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        return False
    db.delete(schedule)
    db.flush()
    return True


def update_schedule_status(
    db: Session,
    schedule_id: int,
    status: str,
    **kwargs: Any,
) -> Schedule:
    """Update a schedule's status and any additional keyword-argument columns.

    Accepted extra kwargs include: ``finalized_by``, ``finalized_at``,
    ``unlocked_by``, ``unlocked_at``, ``override_reason``, ``kpi_snapshot``.

    Raises ValueError if the schedule does not exist.
    """
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise ValueError(f"Schedule {schedule_id} not found.")

    schedule.status = status
    for key, value in kwargs.items():
        if not hasattr(schedule, key):
            raise AttributeError(f"Schedule has no column '{key}'.")
        setattr(schedule, key, value)

    db.flush()
    db.refresh(schedule)
    return schedule


# ---------------------------------------------------------------------------
# Schedule Items
# ---------------------------------------------------------------------------


def create_schedule_items_bulk(
    db: Session,
    schedule_id: int,
    coil_id_positions: list[tuple[int, int, bool]],
) -> None:
    """Bulk-insert schedule items.

    Args:
        db: Active SQLAlchemy session.
        schedule_id: Foreign key for the parent schedule.
        coil_id_positions: List of (coil_id, position, is_apl7) tuples.
    """
    if not coil_id_positions:
        return

    mappings = [
        {
            "schedule_id": schedule_id,
            "coil_id": coil_id,
            "position": position,
            "is_apl7": is_apl7,
        }
        for coil_id, position, is_apl7 in coil_id_positions
    ]
    db.bulk_insert_mappings(ScheduleItem, mappings)  # type: ignore[arg-type]
    db.flush()


def get_schedule_items(db: Session, schedule_id: int) -> list[ScheduleItem]:
    """Return all schedule items for the given schedule, ordered by position."""
    stmt = (
        select(ScheduleItem)
        .where(ScheduleItem.schedule_id == schedule_id)
        .order_by(ScheduleItem.position)
    )
    return list(db.execute(stmt).scalars().all())


def update_schedule_item_positions(
    db: Session,
    schedule_id: int,
    new_positions: list[tuple[int, int]],
) -> None:
    """Update the position of each coil in a schedule.

    Args:
        db: Active SQLAlchemy session.
        schedule_id: The schedule whose items are being reordered.
        new_positions: List of (coil_id, new_position) tuples.
    """
    if not new_positions:
        return

    position_map: dict[int, int] = {
        coil_id: new_pos for coil_id, new_pos in new_positions
    }

    stmt = select(ScheduleItem).where(ScheduleItem.schedule_id == schedule_id)
    items = list(db.execute(stmt).scalars().all())

    # Two-phase update avoids UNIQUE(schedule_id, position) violations when swapping.
    offset = max((item.position for item in items), default=0) + len(items) + 1000
    for item in items:
        if item.coil_id in position_map:
            item.position = position_map[item.coil_id] + offset
    db.flush()

    for item in items:
        if item.coil_id in position_map:
            item.position = position_map[item.coil_id]

    db.flush()


# ---------------------------------------------------------------------------
# Violations
# ---------------------------------------------------------------------------


def delete_violations(db: Session, schedule_id: int) -> None:
    """Delete all violation rows for the given schedule."""
    stmt = select(Violation).where(Violation.schedule_id == schedule_id)
    violations = db.execute(stmt).scalars().all()
    for v in violations:
        db.delete(v)
    db.flush()


def create_violations_bulk(
    db: Session,
    schedule_id: int,
    violations: list[dict],
) -> None:
    """Bulk-insert violation records for a schedule.

    Each dict in ``violations`` must contain the fields that map to
    Violation columns: ``position_a``, ``position_b``, ``coil_id_a``,
    ``coil_id_b``, ``rule_type``, ``detail``.
    """
    if not violations:
        return

    mappings = [{"schedule_id": schedule_id, **v} for v in violations]
    db.bulk_insert_mappings(Violation, mappings)  # type: ignore[arg-type]
    db.flush()


def get_violations(db: Session, schedule_id: int) -> list[Violation]:
    """Return all violations for the given schedule."""
    stmt = select(Violation).where(Violation.schedule_id == schedule_id)
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Audit Events
# ---------------------------------------------------------------------------


def create_audit_event(
    db: Session,
    event_type: str,
    user_id: int,
    schedule_id: int | None = None,
    upload_file_id: int | None = None,
    detail: dict | None = None,
) -> AuditEvent:
    """Insert an audit event and return the refreshed ORM object."""
    event = AuditEvent(
        event_type=event_type,
        user_id=user_id,
        schedule_id=schedule_id,
        upload_file_id=upload_file_id,
        detail=detail,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    return event


def get_audit_events(db: Session, schedule_id: int) -> list[AuditEvent]:
    """Return audit events for the given schedule, ordered by occurred_at ascending."""
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.schedule_id == schedule_id)
        .order_by(AuditEvent.occurred_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_audit_event_by_id(db: Session, audit_id: int) -> AuditEvent | None:
    """Return audit event by primary key ID."""
    return db.get(AuditEvent, audit_id)


def delete_audit_event(db: Session, audit_id: int) -> bool:
    """Delete an audit event by ID. Return True if found and deleted."""
    event = db.get(AuditEvent, audit_id)
    if not event:
        return False
    db.delete(event)
    db.flush()
    return True

