"""add listing equipment

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'listings',
        sa.Column('equipment', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
    )
    op.alter_column('listings', 'equipment', server_default=None)
    op.create_index(
        op.f('ix_listings_equipment'), 'listings', ['equipment'], unique=False, postgresql_using='gin'
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_listings_equipment'), table_name='listings', postgresql_using='gin')
    op.drop_column('listings', 'equipment')
