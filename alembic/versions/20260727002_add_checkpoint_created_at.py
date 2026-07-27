"""Add created_at column to checkpoints table for TTL cleanup.

Revision ID: 20260727002
Revises: 20260727001
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727002"
down_revision: str = "20260727001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "checkpoints",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE checkpoints SET created_at = now() WHERE created_at IS NULL"
    )
    op.alter_column(
        "checkpoints",
        "created_at",
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.create_index(
        "ix_checkpoints_created_at",
        "checkpoints",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_checkpoints_created_at", table_name="checkpoints")
    op.drop_column("checkpoints", "created_at")
