"""Add Apify fields to Trend model

Revision ID: 001_add_apify_fields
Revises: 
Create Date: 2024-11-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_apify_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Apify-specific fields to trends table."""
    # Add new columns to trends table
    op.add_column('trends', sa.Column('search_volume', sa.Integer(), nullable=True))
    op.add_column('trends', sa.Column('related_queries', sa.JSON(), nullable=True))
    op.add_column('trends', sa.Column('geo_data', sa.JSON(), nullable=True))
    op.add_column('trends', sa.Column('time_range', sa.String(), nullable=True))
    op.add_column('trends', sa.Column('apify_run_id', sa.String(), nullable=True))
    op.add_column('trends', sa.Column('raw_data', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove Apify-specific fields from trends table."""
    op.drop_column('trends', 'raw_data')
    op.drop_column('trends', 'apify_run_id')
    op.drop_column('trends', 'time_range')
    op.drop_column('trends', 'geo_data')
    op.drop_column('trends', 'related_queries')
    op.drop_column('trends', 'search_volume')
