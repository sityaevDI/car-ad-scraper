"""add job_type to scheduled_scrapes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'scheduled_scrapes',
        sa.Column(
            'job_type',
            sa.Enum(
                'SEARCH', 'LISTING_REFRESH', 'SAVED_SEARCH_REFRESH', 'FULL_SOURCE_REFRESH', 'MARKET_REFRESH',
                name='scrapejobtype', native_enum=False, length=32,
            ),
            nullable=False,
            server_default='SEARCH',
        ),
    )
    with op.batch_alter_table('scheduled_scrapes') as batch_op:
        batch_op.alter_column('job_type', server_default=None)


def downgrade() -> None:
    op.drop_column('scheduled_scrapes', 'job_type')
