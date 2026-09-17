"""add listing air_condition and seats

Revision ID: e1f2a3b4c5d6
Revises: c7d8e9f0a1b2
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('air_condition', sa.String(length=16), nullable=True))
    op.add_column('listings', sa.Column('seats', sa.String(length=4), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'seats')
    op.drop_column('listings', 'air_condition')
