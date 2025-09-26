"""Add notifications table

Revision ID: 24ad84c978cd
Revises: 23ad73c978cd
Create Date: 2025-09-20 06:59:07.822746
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '24ad84c978cd'
down_revision = '23ad73c978cd'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('type', sa.Enum('task_completed', 'task_failed', 'membership_expiring', 'membership_expired', 'system_alert', 'project_shared', 'comment_added', name='notificationtype'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('status', sa.Enum('unread', 'read', 'archived', name='notificationstatus'), nullable=False, default='unread'),
        sa.Column('action_url', sa.String(500), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4'
    )


def downgrade() -> None:
    # Drop notifications table
    op.drop_table('notifications')