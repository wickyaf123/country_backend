"""Add country music RSS sources

Revision ID: 4ecb311a9106
Revises: 002_enhance_alert_model
Create Date: 2025-11-17 19:58:48.097734

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '4ecb311a9106'
down_revision: Union[str, None] = '002_enhance_alert_model'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add country music RSS sources."""
    
    # RSS sources data (excluding CMT since it's not working)
    sources_data = [
        {
            'id': str(uuid.uuid4()),
            'name': 'Rolling Stone Country',
            'type': 'rss',
            'handle': 'https://www.rollingstone.com/music/music-country/feed/',
            'credibility_score': 0.85,
            'is_active': True,
            'fetch_interval_minutes': 15
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Music Row Magazine',
            'type': 'rss',
            'handle': 'https://musicrow.com/feed/',
            'credibility_score': 0.8,
            'is_active': True,
            'fetch_interval_minutes': 15
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Billboard Country',
            'type': 'rss',
            'handle': 'https://www.billboard.com/c/music/country/feed/',
            'credibility_score': 0.9,
            'is_active': True,
            'fetch_interval_minutes': 15
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Taste of Country',
            'type': 'rss',
            'handle': 'https://tasteofcountry.com/feed/',
            'credibility_score': 0.75,
            'is_active': True,
            'fetch_interval_minutes': 15
        }
    ]
    
    # Insert each source
    for source in sources_data:
        op.execute(
            text("""
                INSERT INTO sources (id, name, type, handle, credibility_score, is_active, fetch_interval_minutes, source_metadata)
                VALUES (:id, :name, :type, :handle, :credibility_score, :is_active, :fetch_interval_minutes, '{}')
            """),
            {
                'id': source['id'],
                'name': source['name'],
                'type': source['type'],
                'handle': source['handle'],
                'credibility_score': source['credibility_score'],
                'is_active': source['is_active'],
                'fetch_interval_minutes': source['fetch_interval_minutes']
            }
        )


def downgrade() -> None:
    """Remove country music RSS sources."""
    
    source_handles = [
        'https://www.rollingstone.com/music/music-country/feed/',
        'https://musicrow.com/feed/',
        'https://www.billboard.com/c/music/country/feed/',
        'https://tasteofcountry.com/feed/'
    ]
    
    for handle in source_handles:
        op.execute(
            text("DELETE FROM sources WHERE handle = :handle"),
            {'handle': handle}
        )
