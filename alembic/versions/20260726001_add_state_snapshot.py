"""add state_snapshot to applications

Revision ID: 2026-07-26-001
Revises: 2026-07-25-001
Create Date: 2026-07-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2026-07-26-001'
down_revision: str | None = '2026-07-25-001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('applications', sa.Column('state_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('applications', 'state_snapshot')
