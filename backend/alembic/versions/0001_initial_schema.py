"""Initial schema — creates all 7 tables for the CPL-2 Scheduling System.

Revision ID: 0001
Revises: (none)
Create Date: 2024-01-01 00:00:00.000000

Requirements: 5.3
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# upgrade — create tables in dependency order
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # 1. users (no FK dependencies)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("role IN ('planner', 'viewer')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    # 2. upload_files (FK → users)
    op.create_table(
        "upload_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("parse_warnings", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. schedules (FK → upload_files, users × 3)
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_file_id", sa.Integer(), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("generated_by", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finalized_by", sa.Integer(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlocked_by", sa.Integer(), nullable=True),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("kpi_snapshot", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'final')", name="ck_schedules_status"
        ),
        sa.ForeignKeyConstraint(["upload_file_id"], ["upload_files.id"]),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["finalized_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["unlocked_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. coils (FK → upload_files)
    op.create_table(
        "coils",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_file_id", sa.Integer(), nullable=False),
        sa.Column("hr_order_no", sa.String(32), nullable=True),
        sa.Column("hr_coil_no", sa.String(32), nullable=False),
        sa.Column("thk", sa.Numeric(6, 3), nullable=True),
        sa.Column("wdt", sa.Numeric(6, 1), nullable=True),
        sa.Column("wgt", sa.Numeric(8, 3), nullable=True),
        sa.Column("grade", sa.String(32), nullable=True),
        sa.Column("age_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("status", sa.String(8), nullable=True),
        sa.Column("cust", sa.String(64), nullable=True),
        sa.Column("cr_coil_no", sa.String(32), nullable=True),
        sa.Column("routing", sa.String(32), nullable=True),
        sa.Column("product", sa.String(16), nullable=True),
        sa.Column("act_path", sa.Integer(), nullable=True),
        sa.Column("prev_unit", sa.Integer(), nullable=True),
        sa.Column("silicon_pct", sa.Numeric(5, 3), nullable=True),
        sa.Column("receiving_remarks", sa.String(64), nullable=True),
        sa.Column("order_status", sa.String(16), nullable=True),
        sa.Column("tdc", sa.String(4), nullable=True),
        sa.Column("edge_condth", sa.String(32), nullable=True),
        sa.Column("ord_wdth_min", sa.Numeric(6, 1), nullable=True),
        sa.Column("ord_wdth_max", sa.Numeric(6, 1), nullable=True),
        sa.Column("target_width", sa.Numeric(6, 1), nullable=True),
        sa.Column("next_work_center", sa.String(32), nullable=True),
        sa.Column("all_columns", sa.JSON(), nullable=False),
        sa.Column(
            "is_apl7",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("silicon_band", sa.String(8), nullable=True),
        sa.Column("parse_warning", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["upload_file_id"], ["upload_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. schedule_items (FK → schedules CASCADE, coils)
    op.create_table(
        "schedule_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("coil_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "is_apl7",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["schedules.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["coil_id"], ["coils.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_id", "position", name="uq_schedule_items_pos"),
    )

    # 6. violations (FK → schedules CASCADE, coils × 2)
    op.create_table(
        "violations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("position_a", sa.Integer(), nullable=False),
        sa.Column("position_b", sa.Integer(), nullable=False),
        sa.Column("coil_id_a", sa.Integer(), nullable=False),
        sa.Column("coil_id_b", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["schedules.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["coil_id_a"], ["coils.id"]),
        sa.ForeignKeyConstraint(["coil_id_b"], ["coils.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 7. audit_events (FK → schedules, upload_files, users)
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=True),
        sa.Column("upload_file_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"]),
        sa.ForeignKeyConstraint(["upload_file_id"], ["upload_files.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ---------------------------------------------------------------------------
    # Indexes (5 required)
    # ---------------------------------------------------------------------------
    op.create_index("idx_coils_upload", "coils", ["upload_file_id"])
    op.create_index(
        "idx_schedule_items_schedule", "schedule_items", ["schedule_id", "position"]
    )
    op.create_index("idx_violations_schedule", "violations", ["schedule_id"])
    op.create_index("idx_audit_schedule", "audit_events", ["schedule_id"])
    op.create_index("idx_audit_upload", "audit_events", ["upload_file_id"])


# ---------------------------------------------------------------------------
# downgrade — drop tables in reverse dependency order
# ---------------------------------------------------------------------------


def downgrade() -> None:
    op.drop_index("idx_audit_upload", table_name="audit_events")
    op.drop_index("idx_audit_schedule", table_name="audit_events")
    op.drop_index("idx_violations_schedule", table_name="violations")
    op.drop_index("idx_schedule_items_schedule", table_name="schedule_items")
    op.drop_index("idx_coils_upload", table_name="coils")

    op.drop_table("audit_events")
    op.drop_table("violations")
    op.drop_table("schedule_items")
    op.drop_table("coils")
    op.drop_table("schedules")
    op.drop_table("upload_files")
    op.drop_table("users")
