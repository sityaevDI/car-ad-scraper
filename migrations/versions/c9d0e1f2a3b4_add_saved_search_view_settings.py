"""add saved_searches.view_settings

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, no backfill: existing saved searches simply have no saved layout.
    op.add_column('saved_searches', sa.Column('view_settings', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('saved_searches', 'view_settings')
