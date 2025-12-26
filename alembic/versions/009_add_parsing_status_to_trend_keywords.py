"""Add parsing_status to trend_keywords

Revision ID: 009_add_parsing_status
Revises: 008_add_flexible_topic_detection
Create Date: 2024-12-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009_add_parsing_status'
down_revision = '008_add_flexible_topic_detection'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add parsing_status column to trend_keywords table."""
    op.add_column('trend_keywords', sa.Column('parsing_status', sa.String(length=50), nullable=True, server_default='success'))


def downgrade() -> None:
    """Remove parsing_status column from trend_keywords table."""
    op.drop_column('trend_keywords', 'parsing_status')

