"""add notification listing_id

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('notifications', sa.Column('listing_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('fk_notifications_listing_id_listings'), 'notifications', 'listings', ['listing_id'], ['id']
    )
    op.create_index(op.f('ix_notifications_listing_id'), 'notifications', ['listing_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_listing_id'), table_name='notifications')
    op.drop_constraint(op.f('fk_notifications_listing_id_listings'), 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'listing_id')
