"""Add Firecrawl scraping fields to items table

Revision ID: 004_add_firecrawl_fields
Revises: 003_link_awario_to_stories
Create Date: 2025-12-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_add_firecrawl_fields'
down_revision = '003_link_awario_to_stories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Firecrawl web scraping fields to items table."""
    # Add new columns for full article scraping
    op.add_column('items', sa.Column('full_content', sa.Text(), nullable=True))
    op.add_column('items', sa.Column('scrape_status', sa.String(), nullable=False, server_default='pending'))
    op.add_column('items', sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('items', sa.Column('scrape_error', sa.Text(), nullable=True))
    op.add_column('items', sa.Column('content_metadata', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    """Remove Firecrawl fields from items table."""
    op.drop_column('items', 'content_metadata')
    op.drop_column('items', 'scrape_error')
    op.drop_column('items', 'scraped_at')
    op.drop_column('items', 'scrape_status')
    op.drop_column('items', 'full_content')

