"""add performance indexes

Revision ID: 007_add_performance_indexes
Revises: 006_add_system_config_table
Create Date: 2025-12-13 

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_performance_indexes'
down_revision = '006_add_system_config_table'
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes for better query performance."""
    
    # Stories table indexes
    op.create_index('ix_stories_impact_score', 'stories', ['impact_score'], unique=False)
    op.create_index('ix_stories_status', 'stories', ['status'], unique=False)
    op.create_index('ix_stories_verification_state', 'stories', ['verification_state'], unique=False)
    op.create_index('ix_stories_first_seen_at', 'stories', ['first_seen_at'], unique=False)
    op.create_index('ix_stories_impact_score_first_seen', 'stories', ['impact_score', 'first_seen_at'], unique=False)
    
    # Alerts table indexes
    op.create_index('ix_alerts_delivered_at', 'alerts', ['delivered_at'], unique=False)
    op.create_index('ix_alerts_created_at', 'alerts', ['created_at'], unique=False)
    
    # Trends table indexes
    op.create_index('ix_trends_source', 'trends', ['source'], unique=False)
    op.create_index('ix_trends_recorded_at', 'trends', ['recorded_at'], unique=False)
    op.create_index('ix_trends_score', 'trends', ['score'], unique=False)
    op.create_index('ix_trends_entity', 'trends', ['entity'], unique=False)
    op.create_index('ix_trends_score_recorded', 'trends', ['score', 'recorded_at'], unique=False)
    
    # Items table indexes for scraping queries
    op.create_index('ix_items_scrape_status', 'items', ['scrape_status'], unique=False)
    op.create_index('ix_items_last_scraped', 'items', ['last_scraped'], unique=False)
    
    # Story items junction table
    op.create_index('ix_story_items_story_id', 'story_items', ['story_id'], unique=False)
    op.create_index('ix_story_items_item_id', 'story_items', ['item_id'], unique=False)


def downgrade():
    """Remove performance indexes."""
    
    # Stories table indexes
    op.drop_index('ix_stories_impact_score', table_name='stories')
    op.drop_index('ix_stories_status', table_name='stories')
    op.drop_index('ix_stories_verification_state', table_name='stories')
    op.drop_index('ix_stories_first_seen_at', table_name='stories')
    op.drop_index('ix_stories_impact_score_first_seen', table_name='stories')
    
    # Alerts table indexes
    op.drop_index('ix_alerts_delivered_at', table_name='alerts')
    op.drop_index('ix_alerts_created_at', table_name='alerts')
    
    # Trends table indexes
    op.drop_index('ix_trends_source', table_name='trends')
    op.drop_index('ix_trends_recorded_at', table_name='trends')
    op.drop_index('ix_trends_score', table_name='trends')
    op.drop_index('ix_trends_entity', table_name='trends')
    op.drop_index('ix_trends_score_recorded', table_name='trends')
    
    # Items table indexes
    op.drop_index('ix_items_scrape_status', table_name='items')
    op.drop_index('ix_items_last_scraped', table_name='items')
    
    # Story items junction table
    op.drop_index('ix_story_items_story_id', table_name='story_items')
    op.drop_index('ix_story_items_item_id', table_name='story_items')

