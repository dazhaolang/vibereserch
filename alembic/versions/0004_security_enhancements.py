"""
安全增强字段与监控表

Revision ID: 0004_security_enhancements
Revises: 0003_main_experience_extension
Create Date: 2024-06-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0004_security_enhancements"
down_revision = "0003_main_experience_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # projects 表软删除与标签
    op.add_column(
        "projects",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("projects", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("projects", sa.Column("tags", mysql.JSON(), nullable=True))

    op.create_index("idx_projects_owner_id", "projects", ["owner_id"])
    op.create_index("idx_projects_is_deleted", "projects", ["is_deleted"])

    # literature / tasks 索引
    op.create_index("idx_literature_doi", "literature", ["doi"])
    op.create_index("idx_literature_quality_score", "literature", ["quality_score"])
    op.create_index("idx_literature_created_at", "literature", ["created_at"])

    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_project_id", "tasks", ["project_id"])
    op.create_index("idx_tasks_created_at", "tasks", ["created_at"])

    # user_sessions 表
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_token", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_user_sessions_token", "user_sessions", ["session_token"], unique=True
    )
    op.create_index("idx_user_sessions_user_id", "user_sessions", ["user_id"])

    # api_access_logs 表
    op.create_table(
        "api_access_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_api_logs_user_id", "api_access_logs", ["user_id"])
    op.create_index("idx_api_logs_created_at", "api_access_logs", ["created_at"])

    # users 安全字段
    op.add_column(
        "users", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("two_factor_secret", sa.String(32), nullable=True))
    op.add_column(
        "users",
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("last_login_ip", sa.String(45), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "two_factor_enabled")
    op.drop_column("users", "two_factor_secret")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")

    op.drop_table("api_access_logs")
    op.drop_table("user_sessions")

    op.drop_index("idx_tasks_created_at", table_name="tasks")
    op.drop_index("idx_tasks_project_id", table_name="tasks")
    op.drop_index("idx_tasks_status", table_name="tasks")

    op.drop_index("idx_literature_created_at", table_name="literature")
    op.drop_index("idx_literature_quality_score", table_name="literature")
    op.drop_index("idx_literature_doi", table_name="literature")

    op.drop_index("idx_projects_is_deleted", table_name="projects")
    op.drop_index("idx_projects_owner_id", table_name="projects")

    op.drop_column("projects", "tags")
    op.drop_column("projects", "is_public")
    op.drop_column("projects", "deleted_at")
    op.drop_column("projects", "is_deleted")
