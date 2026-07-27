"""add_validation_confidence_to_applications

Revision ID: 20260727001
Revises: 20260726001
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260727001'
down_revision: Union[str, None] = '20260726001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('applications', sa.Column('validation_confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('applications', 'validation_confidence')
