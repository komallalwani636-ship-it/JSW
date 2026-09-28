"""Pydantic v2 request/response schemas for the CPL-2 Scheduling System.

All ORM-backed models use ``model_config = ConfigDict(from_attributes=True)``
so that SQLAlchemy model instances can be directly passed to FastAPI response
serialization.

Design references: Requirements 1.7, 5.2, 8.1, 12.2
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Upload / Parse schemas
# ---------------------------------------------------------------------------


class ParseWarning(BaseModel):
    row: int
    column: str
    message: str


class ParseSummary(BaseModel):
    total_rows: int
    eligible_count: int
    apl7_count: int
    excluded_product: int
    excluded_act_path: int
    excluded_status: int
    excluded_closed: int
    parse_warnings: list[ParseWarning]


# ---------------------------------------------------------------------------
# Coil
# ---------------------------------------------------------------------------


class CoilRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hr_coil_no: str
    thk: float | None
    wdt: float | None
    wgt: float | None
    grade: str | None
    age_hours: float | None
    status: str | None
    product: str | None
    silicon_pct: float | None
    silicon_band: str | None
    is_apl7: bool
    all_columns: dict


# ---------------------------------------------------------------------------
# Violation
# ---------------------------------------------------------------------------


class ViolationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position_a: int
    position_b: int
    rule_type: str
    detail: dict


# ---------------------------------------------------------------------------
# Schedule item
# ---------------------------------------------------------------------------


class ScheduleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    coil: CoilRecord
    is_apl7: bool


# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------


class KpiResult(BaseModel):
    total_eligible: int
    hrpo_count: int
    hrpo_weight: float
    hrspo_count: int
    hrspo_weight: float
    ngo_count: int
    ngo_weight: float
    age_gt_72h: int
    age_gt_120h: int
    age_gt_168h: int
    violation_count: int
    schedule_status: str
    version_label: str


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


class ScheduleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_label: str
    status: str
    generated_at: datetime
    upload_file_id: int
    kpi_snapshot: dict | None
    upload_filename: str | None = None
    generator_username: str | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None


class ScheduleDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_label: str
    status: str
    generated_at: datetime
    upload_file_id: int
    kpi_snapshot: dict | None
    items: list[ScheduleItem]
    violations: list[ViolationDetail]


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    user_id: int
    occurred_at: datetime
    schedule_id: int | None
    upload_file_id: int | None
    detail: dict | None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ---------------------------------------------------------------------------
# Schedule mutation requests
# ---------------------------------------------------------------------------


class ReorderRequest(BaseModel):
    coil_ids: list[int]


class FinalizeRequest(BaseModel):
    override_reason: str | None = None
