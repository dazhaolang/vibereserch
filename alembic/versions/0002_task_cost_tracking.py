"""Add cost tracking columns to tasks

Revision ID: 0002
Revises: 0001
Create Date: 2024-05-29 01:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('token_usage', sa.Float(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('cost_estimate', sa.Float(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('cost_breakdown', mysql.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_column('cost_breakdown')
        batch_op.drop_column('cost_estimate')
        batch_op.drop_column('token_usage')
