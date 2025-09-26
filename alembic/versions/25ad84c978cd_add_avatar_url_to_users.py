"""Add avatar_url to users table

Revision ID: 25ad84c978cd
Revises: 24ad84c978cd
Create Date: 2025-09-20 07:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '25ad84c978cd'
down_revision = '24ad84c978cd'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add avatar_url column to users table
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))

def downgrade() -> None:
    # Remove avatar_url column from users table
    op.drop_column('users', 'avatar_url')