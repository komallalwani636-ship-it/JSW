"""SQLAlchemy 2.0 ORM models for the CPL-2 Scheduling System.

Mirrors the PostgreSQL schema defined in the design document exactly.
All seven tables are represented:
    users, upload_files, coils, schedules, schedule_items, violations, audit_events

Design references: Requirements 5.1, 5.2, 5.4, 12.1
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import false, func


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base — alembic env.py imports this to autogenerate."""


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint("role IN ('planner', 'viewer')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    uploaded_files: Mapped[list[UploadFile]] = relationship(
        "UploadFile", foreign_keys="UploadFile.uploaded_by", back_populates="uploader"
    )
    generated_schedules: Mapped[list[Schedule]] = relationship(
        "Schedule", foreign_keys="Schedule.generated_by", back_populates="generator"
    )
    finalized_schedules: Mapped[list[Schedule]] = relationship(
        "Schedule", foreign_keys="Schedule.finalized_by", back_populates="finalizer"
    )
    unlocked_schedules: Mapped[list[Schedule]] = relationship(
        "Schedule", foreign_keys="Schedule.unlocked_by", back_populates="unlocker"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent", back_populates="user"
    )


# ---------------------------------------------------------------------------
# upload_files
# ---------------------------------------------------------------------------


class UploadFile(Base):
    __tablename__ = "upload_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    uploaded_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parse_warnings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    uploader: Mapped[User] = relationship(
        "User", foreign_keys=[uploaded_by], back_populates="uploaded_files"
    )
    coils: Mapped[list[Coil]] = relationship("Coil", back_populates="upload_file")
    schedules: Mapped[list[Schedule]] = relationship(
        "Schedule", back_populates="upload_file"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent", back_populates="upload_file"
    )


# ---------------------------------------------------------------------------
# schedules
# ---------------------------------------------------------------------------


class Schedule(Base):
    __tablename__ = "schedules"

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'final')", name="ck_schedules_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upload_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("upload_files.id"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="draft"
    )
    generated_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    generated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finalized_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    finalized_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    unlocked_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    unlocked_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    kpi_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    deleted_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", name="fk_schedules_deleted_by"), nullable=True
    )

    # Relationships
    upload_file: Mapped[UploadFile] = relationship(
        "UploadFile", back_populates="schedules"
    )
    generator: Mapped[User] = relationship(
        "User", foreign_keys=[generated_by], back_populates="generated_schedules"
    )
    finalizer: Mapped[User | None] = relationship(
        "User", foreign_keys=[finalized_by], back_populates="finalized_schedules"
    )
    unlocker: Mapped[User | None] = relationship(
        "User", foreign_keys=[unlocked_by], back_populates="unlocked_schedules"
    )
    deleter: Mapped[User | None] = relationship(
        "User", foreign_keys=[deleted_by]
    )
    items: Mapped[list[ScheduleItem]] = relationship(
        "ScheduleItem",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleItem.position",
    )
    violations: Mapped[list[Violation]] = relationship(
        "Violation", back_populates="schedule", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent", back_populates="schedule"
    )


# ---------------------------------------------------------------------------
# coils
# ---------------------------------------------------------------------------


class Coil(Base):
    __tablename__ = "coils"

    __table_args__ = (
        Index("idx_coils_upload", "upload_file_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upload_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("upload_files.id"), nullable=False
    )
    hr_order_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hr_coil_no: Mapped[str] = mapped_column(String(32), nullable=False)
    thk: Mapped[Numeric | None] = mapped_column(Numeric(6, 3), nullable=True)
    wdt: Mapped[Numeric | None] = mapped_column(Numeric(6, 1), nullable=True)
    wgt: Mapped[Numeric | None] = mapped_column(Numeric(8, 3), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    age_hours: Mapped[Numeric | None] = mapped_column(Numeric(8, 2), nullable=True)
    status: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cust: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cr_coil_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    routing: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product: Mapped[str | None] = mapped_column(String(16), nullable=True)
    act_path: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prev_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    silicon_pct: Mapped[Numeric | None] = mapped_column(Numeric(5, 3), nullable=True)
    receiving_remarks: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tdc: Mapped[str | None] = mapped_column(String(32), nullable=True)  # TDC scheduling grade (Tdc column)
    edge_condth: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ord_wdth_min: Mapped[Numeric | None] = mapped_column(Numeric(6, 1), nullable=True)
    ord_wdth_max: Mapped[Numeric | None] = mapped_column(Numeric(6, 1), nullable=True)
    target_width: Mapped[Numeric | None] = mapped_column(Numeric(6, 1), nullable=True)
    next_work_center: Mapped[str | None] = mapped_column(String(32), nullable=True)
    all_columns: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_apl7: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    silicon_band: Mapped[str | None] = mapped_column(String(8), nullable=True)
    parse_warning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    upload_file: Mapped[UploadFile] = relationship(
        "UploadFile", back_populates="coils"
    )
    schedule_items: Mapped[list[ScheduleItem]] = relationship(
        "ScheduleItem", back_populates="coil"
    )
    violations_as_a: Mapped[list[Violation]] = relationship(
        "Violation",
        foreign_keys="Violation.coil_id_a",
        back_populates="coil_a",
    )
    violations_as_b: Mapped[list[Violation]] = relationship(
        "Violation",
        foreign_keys="Violation.coil_id_b",
        back_populates="coil_b",
    )


# ---------------------------------------------------------------------------
# schedule_items
# ---------------------------------------------------------------------------


class ScheduleItem(Base):
    __tablename__ = "schedule_items"

    __table_args__ = (
        UniqueConstraint("schedule_id", "position", name="uq_schedule_items_pos"),
        Index("idx_schedule_items_schedule", "schedule_id", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    coil_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("coils.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_apl7: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Relationships
    schedule: Mapped[Schedule] = relationship("Schedule", back_populates="items")
    coil: Mapped[Coil] = relationship("Coil", back_populates="schedule_items")


# ---------------------------------------------------------------------------
# violations
# ---------------------------------------------------------------------------


class Violation(Base):
    __tablename__ = "violations"

    __table_args__ = (
        Index("idx_violations_schedule", "schedule_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    position_a: Mapped[int] = mapped_column(Integer, nullable=False)
    position_b: Mapped[int] = mapped_column(Integer, nullable=False)
    coil_id_a: Mapped[int] = mapped_column(
        Integer, ForeignKey("coils.id"), nullable=False
    )
    coil_id_b: Mapped[int] = mapped_column(
        Integer, ForeignKey("coils.id"), nullable=False
    )
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Relationships
    schedule: Mapped[Schedule] = relationship("Schedule", back_populates="violations")
    coil_a: Mapped[Coil] = relationship(
        "Coil", foreign_keys=[coil_id_a], back_populates="violations_as_a"
    )
    coil_b: Mapped[Coil] = relationship(
        "Coil", foreign_keys=[coil_id_b], back_populates="violations_as_b"
    )


# ---------------------------------------------------------------------------
# audit_events
# ---------------------------------------------------------------------------


class AuditEvent(Base):
    __tablename__ = "audit_events"

    __table_args__ = (
        Index("idx_audit_schedule", "schedule_id"),
        Index("idx_audit_upload", "upload_file_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("schedules.id"), nullable=True
    )
    upload_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("upload_files.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    occurred_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    schedule: Mapped[Schedule | None] = relationship(
        "Schedule", back_populates="audit_events"
    )
    upload_file: Mapped[UploadFile | None] = relationship(
        "UploadFile", back_populates="audit_events"
    )
    user: Mapped[User] = relationship("User", back_populates="audit_events")
