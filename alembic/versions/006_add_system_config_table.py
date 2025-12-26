"""Add system_config table for configuration management

Revision ID: 006_add_system_config
Revises: 005_add_entity_type
Create Date: 2025-12-13 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_add_system_config'
down_revision = '005_add_entity_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create system_config table with key-value storage."""
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('value', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('value_type', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_secret', sa.Boolean(), default=False, server_default='false'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('updated_by', sa.String(), nullable=True)
    )
    
    # Seed with default Slack and keyword settings
    op.execute("""
        INSERT INTO system_config (key, value, value_type, category, description, is_secret) VALUES
        ('slack_webhook_url', 'null', 'string', 'Integrations', 'Slack webhook URL for alert notifications', true),
        ('slack_channel', '"#country-rebel-alerts"', 'string', 'Integrations', 'Default Slack channel', false),
        ('slack_channels_by_tier', '{"code_red": "#country-rebel-urgent", "trending_spike": "#country-rebel-trending", "standard": "#country-rebel-alerts"}', 'object', 'Integrations', 'Per-tier Slack channels', false),
        ('country_music_keywords', '[]', 'array', 'Advanced', 'Google Trends keywords (100 keywords)', false)
    """)


def downgrade() -> None:
    """Drop system_config table."""
    op.drop_table('system_config')

