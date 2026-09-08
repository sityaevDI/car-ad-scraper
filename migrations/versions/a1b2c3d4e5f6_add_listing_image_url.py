"""add listing image_url

Revision ID: a1b2c3d4e5f6
Revises: 6893edef29c3
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6893edef29c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('image_url', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'image_url')
