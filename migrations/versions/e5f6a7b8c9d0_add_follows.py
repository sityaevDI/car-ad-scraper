"""add follows

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-10 00:00:00.000000

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
    op.create_table(
        'follows',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('listing_id', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], name=op.f('fk_follows_listing_id_listings')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_follows_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_follows')),
        sa.UniqueConstraint('user_id', 'listing_id', name='uq_follows_user_id_listing_id'),
    )
    op.create_index(op.f('ix_follows_user_id'), 'follows', ['user_id'], unique=False)
    op.create_index(op.f('ix_follows_listing_id'), 'follows', ['listing_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_follows_listing_id'), table_name='follows')
    op.drop_index(op.f('ix_follows_user_id'), table_name='follows')
    op.drop_table('follows')
