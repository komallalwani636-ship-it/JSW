"""Add is_deleted, deleted_at, and deleted_by columns to schedules table for Bin/Trash feature.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.add_column(
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id", name="fk_schedules_deleted_by"), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.drop_column("deleted_by")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_deleted")
