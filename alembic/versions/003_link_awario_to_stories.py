"""link_awario_to_stories

Revision ID: 003_link_awario_to_stories
Revises: 4c99f336e0a0
Create Date: 2025-12-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_link_awario_to_stories'
down_revision: Union[str, None] = '4c99f336e0a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add story_id foreign key to awario_mentions table to link mentions to stories."""
    
    # Add story_id column to awario_mentions
    op.add_column(
        'awario_mentions',
        sa.Column('story_id', sa.String(36), nullable=True)
    )
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_awario_mentions_story_id',
        'awario_mentions',
        'stories',
        ['story_id'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # Create index for faster queries
    op.create_index(
        'ix_awario_mentions_story_id',
        'awario_mentions',
        ['story_id']
    )


def downgrade() -> None:
    """Remove story_id foreign key from awario_mentions table."""
    
    # Drop index
    op.drop_index('ix_awario_mentions_story_id', 'awario_mentions')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_awario_mentions_story_id', 'awario_mentions', type_='foreignkey')
    
    # Drop column
    op.drop_column('awario_mentions', 'story_id')

