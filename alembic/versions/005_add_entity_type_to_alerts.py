"""Add entity_type field to alerts table

Revision ID: 005_add_entity_type
Revises: 004_add_firecrawl_fields
Create Date: 2025-12-13 12:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005_add_entity_type'
down_revision = '004_add_firecrawl_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add entity_type field to alerts table."""
    op.add_column('alerts', sa.Column('entity_type', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove entity_type field from alerts table."""
    op.drop_column('alerts', 'entity_type')

