"""Enhance Alert model for trend and competitor alerts

Revision ID: 002_enhance_alert_model
Revises: 001_add_apify_fields
Create Date: 2024-11-12 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_enhance_alert_model'
down_revision = '001_add_apify_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enhance alerts table for trend and competitor alerts."""
    # Make story_id nullable
    op.alter_column('alerts', 'story_id', nullable=True)
    
    # Add new columns
    op.add_column('alerts', sa.Column('alert_type', sa.String(), nullable=False, server_default='story'))
    op.add_column('alerts', sa.Column('entity_name', sa.String(), nullable=True))
    op.add_column('alerts', sa.Column('alert_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove enhancements from alerts table."""
    op.drop_column('alerts', 'alert_metadata')
    op.drop_column('alerts', 'entity_name')
    op.drop_column('alerts', 'alert_type')
    
    # Make story_id non-nullable again
    op.alter_column('alerts', 'story_id', nullable=False)
