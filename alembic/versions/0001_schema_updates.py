"""Add literature metadata fields and remove legacy vector columns

Revision ID: 0001
Revises: 
Create Date: 2024-05-29 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- literature table updates ---
    with op.batch_alter_table('literature') as batch_op:
        batch_op.add_column(sa.Column('external_ids', mysql.JSON(), nullable=True))
        batch_op.add_column(sa.Column('reference_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('fields_of_study', mysql.JSON(), nullable=True))
        batch_op.add_column(sa.Column('raw_data', mysql.JSON(), nullable=True))
        batch_op.add_column(sa.Column('is_open_access', sa.Boolean(), server_default=sa.text('0'), nullable=False))

    # remove legacy vector columns / indexes if they exist
    op.execute("DROP INDEX IF EXISTS idx_literature_title_embedding ON literature")
    op.execute("DROP INDEX IF EXISTS idx_literature_abstract_embedding ON literature")
    op.execute("ALTER TABLE literature DROP COLUMN IF EXISTS title_embedding")
    op.execute("ALTER TABLE literature DROP COLUMN IF EXISTS abstract_embedding")

    # --- literature_segments table updates ---
    with op.batch_alter_table('literature_segments') as batch_op:
        batch_op.add_column(sa.Column('extraction_method', sa.String(length=100), nullable=True))

    op.execute("DROP INDEX IF EXISTS idx_segments_content_embedding ON literature_segments")
    op.execute("ALTER TABLE literature_segments DROP COLUMN IF EXISTS content_embedding")


def downgrade() -> None:
    with op.batch_alter_table('literature_segments') as batch_op:
        batch_op.drop_column('extraction_method')

    with op.batch_alter_table('literature') as batch_op:
        batch_op.drop_column('is_open_access')
        batch_op.drop_column('raw_data')
        batch_op.drop_column('fields_of_study')
        batch_op.drop_column('reference_count')
        batch_op.drop_column('external_ids')
