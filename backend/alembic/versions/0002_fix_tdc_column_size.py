"""Fix coils.tdc column size from String(4) to String(32).

TDC scheduling grade values like JVPFB60AJS are 10 characters; the original
String(4) silently truncated them, breaking TDC non-adjacency enforcement.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't enforce column lengths so this is a no-op for SQLite,
    # but it is important for PostgreSQL deployments.
    with op.batch_alter_table("coils") as batch_op:
        batch_op.alter_column(
            "tdc",
            existing_type=sa.String(4),
            type_=sa.String(32),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("coils") as batch_op:
        batch_op.alter_column(
            "tdc",
            existing_type=sa.String(32),
            type_=sa.String(4),
            existing_nullable=True,
        )
