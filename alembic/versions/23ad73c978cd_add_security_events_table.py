"""Add security_events table

Revision ID: 23ad73c978cd
Revises: 0005_add_literature_primary_project
Create Date: 2025-09-20 06:50:07.822746
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '23ad73c978cd'
down_revision = '0005_add_literature_primary_project'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create security_events table
    op.create_table(
        'security_events',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('event_type', sa.Enum('login', 'logout', 'password_change', 'failed_login', name='securityeventtype'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),  # IPv6 support
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('device_info', sa.String(500), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4'
    )


def downgrade() -> None:
    # Drop security_events table
    op.drop_table('security_events')
