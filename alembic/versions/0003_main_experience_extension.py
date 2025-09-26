"""Extend main_experiences with structured fields

Revision ID: 0003_main_experience_extension
Revises: 0002
Create Date: 2024-06-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0003_main_experience_extension"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("main_experiences") as batch_op:
        batch_op.add_column(sa.Column("experience_type", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("key_findings", mysql.JSON(), nullable=True))
        batch_op.add_column(sa.Column("practical_guidelines", mysql.JSON(), nullable=True))
        batch_op.add_column(sa.Column("literature_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("quality_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=50), nullable=False, server_default="active"))

    op.create_index(
        "ix_main_experiences_experience_type",
        "main_experiences",
        ["experience_type"],
    )
    op.create_index(
        "ix_main_experiences_status",
        "main_experiences",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_main_experiences_status", table_name="main_experiences")
    op.drop_index("ix_main_experiences_experience_type", table_name="main_experiences")

    with op.batch_alter_table("main_experiences") as batch_op:
        batch_op.drop_column("status")
        batch_op.drop_column("quality_score")
        batch_op.drop_column("literature_count")
        batch_op.drop_column("practical_guidelines")
        batch_op.drop_column("key_findings")
        batch_op.drop_column("experience_type")
