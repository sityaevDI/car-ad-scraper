"""add market tables

Revision ID: c7d8e9f0a1b2
Revises: d5e6f7a8b9c0
Create Date: 2026-09-16 00:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Curated starter list of equipment slugs known to plausibly move resale price — not exhaustive,
# see app/models/market.py::MarketEquipmentWeight. Percentages are directional placeholders.
_EQUIPMENT_WEIGHTS = [
    ("adaptive_cruise_control", 1.5),
    ("panoramic_roof", 1.5),
    ("massage_seats", 1.5),
    ("matrix_headlights", 1.5),
    ("navigation_system", 1.0),
    ("heated_seats", 1.0),
    ("ventilated_seats", 1.0),
    ("camera_360", 1.0),
    ("head_up_display", 1.0),
    ("air_suspension", 2.0),
    ("digital_instrument_cluster", 0.7),
    ("led_headlights", 0.7),
    ("xenon_headlights", 0.5),
    ("keyless_start", 0.5),
    ("seat_memory", 0.5),
    ("sport_seats", 0.5),
]


_SEGMENT_CRITERIA_COLUMNS = [
    sa.Column('source_id', sa.Uuid(), nullable=False),
    sa.Column('make', sa.String(length=64), nullable=False),
    sa.Column('model', sa.String(length=128), nullable=False),
    sa.Column('production_year', sa.Integer(), nullable=False),
    sa.Column('fuel_type', sa.String(length=32), nullable=True),
    sa.Column('transmission', sa.String(length=32), nullable=True),
    sa.Column('body_type', sa.String(length=32), nullable=True),
    sa.Column('engine_volume_bucket', sa.Integer(), nullable=True),
    sa.Column('mileage_bucket', sa.Integer(), nullable=False),
]


def upgrade() -> None:
    op.create_table(
        'market_price_snapshots',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('segment_key', sa.String(length=64), nullable=False),
        *[c.copy() for c in _SEGMENT_CRITERIA_COLUMNS],
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('algorithm_version', sa.String(length=16), nullable=False),
        sa.Column('sample_size', sa.Integer(), nullable=False),
        sa.Column('filtered_sample_size', sa.Integer(), nullable=False),
        sa.Column('estimated_price', sa.Integer(), nullable=True),
        sa.Column('price_low', sa.Integer(), nullable=True),
        sa.Column('price_high', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('confidence', sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_market_price_snapshots')),
    )
    op.create_index(
        'ix_market_price_snapshots_segment_key_computed_at',
        'market_price_snapshots',
        ['segment_key', 'computed_at'],
    )

    op.create_table(
        'market_dirty_segments',
        sa.Column('segment_key', sa.String(length=64), nullable=False),
        sa.Column('marked_at', sa.DateTime(timezone=True), nullable=False),
        *[c.copy() for c in _SEGMENT_CRITERIA_COLUMNS],
        sa.PrimaryKeyConstraint('segment_key', name=op.f('pk_market_dirty_segments')),
    )

    op.create_table(
        'market_configs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('min_sample_size', sa.Integer(), nullable=False),
        sa.Column('mileage_bucket_km', sa.Integer(), nullable=False),
        sa.Column('outlier_iqr_multiplier', sa.Float(), nullable=False),
        sa.Column('deviation_market_band_pct', sa.Float(), nullable=False),
        sa.Column('deviation_significant_band_pct', sa.Float(), nullable=False),
        sa.Column('confidence_medium_min_sample', sa.Integer(), nullable=False),
        sa.Column('confidence_high_min_sample', sa.Integer(), nullable=False),
        sa.Column('confidence_high_dispersion_ratio', sa.Float(), nullable=False),
        sa.Column('max_equipment_adjustment_pct', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_market_configs')),
    )

    op.create_table(
        'market_equipment_weights',
        sa.Column('equipment_slug', sa.String(length=64), nullable=False),
        sa.Column('adjustment_pct', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('equipment_slug', name=op.f('pk_market_equipment_weights')),
    )

    weights_table = sa.table(
        'market_equipment_weights',
        sa.column('equipment_slug', sa.String),
        sa.column('adjustment_pct', sa.Float),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        weights_table,
        [
            {'equipment_slug': slug, 'adjustment_pct': pct, 'created_at': now, 'updated_at': now}
            for slug, pct in _EQUIPMENT_WEIGHTS
        ],
    )


def downgrade() -> None:
    op.drop_table('market_equipment_weights')
    op.drop_table('market_configs')
    op.drop_table('market_dirty_segments')
    op.drop_index('ix_market_price_snapshots_segment_key_computed_at', table_name='market_price_snapshots')
    op.drop_table('market_price_snapshots')
