"""add scrape_rate_limits

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scrape_rate_limits',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('request_delay_seconds', sa.Float(), nullable=False),
        sa.Column('request_jitter_seconds', sa.Float(), nullable=False),
        sa.Column('network_error_retry_delay_seconds', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_scrape_rate_limits')),
    )


def downgrade() -> None:
    op.drop_table('scrape_rate_limits')
