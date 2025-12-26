"""Add flexible topic detection fields

Revision ID: 008_add_flexible_topic_detection
Revises: 007_add_performance_indexes
Create Date: 2025-12-13 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_add_flexible_topic_detection'
down_revision = '007_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """Add has_google_trends field to hot_topics table."""
    # Add has_google_trends column to hot_topics
    op.add_column('hot_topics', 
        sa.Column('has_google_trends', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Update existing records: set has_google_trends=true if trend_items > 0
    op.execute("""
        UPDATE hot_topics 
        SET has_google_trends = true 
        WHERE trend_items > 0
    """)


def downgrade():
    """Remove has_google_trends field from hot_topics table."""
    op.drop_column('hot_topics', 'has_google_trends')








