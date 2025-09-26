"""Add research share persistence table

Revision ID: 27ad85c978cd
Revises: 26ad84c978cd
Create Date: 2025-03-09 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27ad85c978cd"
down_revision = "26ad84c978cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_shares",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("share_url", sa.String(length=2048), nullable=False),
        sa.Column("emails", sa.JSON(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_research_shares_token", "research_shares", ["token"], unique=True)
    op.create_index("ix_research_shares_task_id", "research_shares", ["task_id"])
    op.create_index("ix_research_shares_created_at", "research_shares", ["created_at"])
    op.create_index("ix_research_shares_expires_at", "research_shares", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_research_shares_expires_at", table_name="research_shares")
    op.drop_index("ix_research_shares_created_at", table_name="research_shares")
    op.drop_index("ix_research_shares_task_id", table_name="research_shares")
    op.drop_index("ix_research_shares_token", table_name="research_shares")
    op.drop_table("research_shares")
