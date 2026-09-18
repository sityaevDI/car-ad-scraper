"""add listing drive_type

Revision ID: a7b28c511ac5
Revises: e1f2a3b4c5d6
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b28c511ac5'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('drive_type', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'drive_type')
