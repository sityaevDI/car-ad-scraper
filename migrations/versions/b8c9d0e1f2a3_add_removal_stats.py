"""add removal_stats

Revision ID: b8c9d0e1f2a3
Revises: a7b28c511ac5
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b28c511ac5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'removal_stats',
        sa.Column('stat_date', sa.Date(), nullable=False),
        sa.Column('period_days', sa.Integer(), nullable=False),
        sa.Column('make', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('removed_count', sa.Integer(), nullable=False),
        sa.Column('median_days_on_market', sa.Float(), nullable=True),
        sa.Column('median_price_at_removal', sa.Integer(), nullable=True),
        sa.Column('price_cut_share', sa.Float(), nullable=True),
        sa.Column('median_price_cut_pct', sa.Float(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_removal_stats')),
        sa.UniqueConstraint('stat_date', 'period_days', 'make', 'model', name='uq_removal_stats_scope'),
    )
    op.create_index(op.f('ix_removal_stats_stat_date'), 'removal_stats', ['stat_date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_removal_stats_stat_date'), table_name='removal_stats')
    op.drop_table('removal_stats')
