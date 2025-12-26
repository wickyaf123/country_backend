"""Add extended Awario fields for enhanced scoring

Revision ID: 007_add_awario_extended
Revises: 006_add_system_config
Create Date: 2025-12-13 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_add_awario_extended'
down_revision = '006_add_system_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add 10 new fields to awario_mentions table for enhanced scoring."""
    
    # Extended author information
    op.add_column('awario_mentions', sa.Column('author_bio', sa.Text(), nullable=True))
    op.add_column('awario_mentions', sa.Column('author_username', sa.String(), nullable=True))
    op.add_column('awario_mentions', sa.Column('author_website', sa.String(), nullable=True))
    
    # Source information with index
    op.add_column('awario_mentions', sa.Column('domain_name', sa.String(), nullable=True))
    op.create_index('ix_awario_mentions_domain_name', 'awario_mentions', ['domain_name'])
    
    # Enhanced location
    op.add_column('awario_mentions', sa.Column('city', sa.String(), nullable=True))
    
    # Twitter-specific fields with index on tweet_id
    op.add_column('awario_mentions', sa.Column('tweet_id', sa.String(), nullable=True))
    op.add_column('awario_mentions', sa.Column('tweet_author_id', sa.String(), nullable=True))
    op.create_index('ix_awario_mentions_tweet_id', 'awario_mentions', ['tweet_id'])
    
    # Workflow flags
    op.add_column('awario_mentions', sa.Column('is_starred', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('awario_mentions', sa.Column('is_done', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove extended Awario fields."""
    
    # Drop indexes first
    op.drop_index('ix_awario_mentions_tweet_id', table_name='awario_mentions')
    op.drop_index('ix_awario_mentions_domain_name', table_name='awario_mentions')
    
    # Drop columns
    op.drop_column('awario_mentions', 'is_done')
    op.drop_column('awario_mentions', 'is_starred')
    op.drop_column('awario_mentions', 'tweet_author_id')
    op.drop_column('awario_mentions', 'tweet_id')
    op.drop_column('awario_mentions', 'city')
    op.drop_column('awario_mentions', 'domain_name')
    op.drop_column('awario_mentions', 'author_website')
    op.drop_column('awario_mentions', 'author_username')
    op.drop_column('awario_mentions', 'author_bio')

