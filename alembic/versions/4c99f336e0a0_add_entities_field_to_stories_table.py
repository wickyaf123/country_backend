"""Add entities field to stories table

Revision ID: 4c99f336e0a0
Revises: 4ecb311a9106
Create Date: 2025-11-17 20:22:58.539043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c99f336e0a0'
down_revision: Union[str, None] = '4ecb311a9106'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add entities column to stories table
    op.add_column('stories', sa.Column('entities', sa.JSON(), nullable=True))
    
    # Set default empty dict for existing stories
    op.execute("UPDATE stories SET entities = '{}' WHERE entities IS NULL")


def downgrade() -> None:
    # Remove entities column from stories table
    op.drop_column('stories', 'entities')
