"""Add is_starred flag to literature

Revision ID: 26ad84c978cd
Revises: 25ad84c978cd
Create Date: 2025-09-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '26ad84c978cd'
down_revision = '25ad84c978cd'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'literature',
        sa.Column('is_starred', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )
    op.create_index('ix_literature_is_starred', 'literature', ['is_starred'])


def downgrade() -> None:
    op.drop_index('ix_literature_is_starred', table_name='literature')
    op.drop_column('literature', 'is_starred')
