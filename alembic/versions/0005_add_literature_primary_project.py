"""add literature primary project reference

Revision ID: 0005_add_literature_primary_project
Revises: 0004_security_enhancements
Create Date: 2025-09-18 09:25:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "0005_add_literature_primary_project"
down_revision = "0004_security_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "literature",
        sa.Column("project_id", sa.Integer(), nullable=True)
    )
    op.create_index("ix_literature_project_id", "literature", ["project_id"])
    op.create_foreign_key(
        "fk_literature_project_id_projects",
        source_table="literature",
        referent_table="projects",
        local_cols=["project_id"],
        remote_cols=["id"],
        ondelete="SET NULL"
    )

    connection = op.get_bind()
    rows = connection.execute(
        text(
            """
            SELECT pla.literature_id, pla.project_id
            FROM project_literature_associations pla
            ORDER BY pla.added_at ASC
            """
        )
    ).fetchall()

    assignments = {}
    for literature_id, project_id in rows:
        assignments.setdefault(literature_id, set()).add(project_id)

    for literature_id, project_ids in assignments.items():
        if len(project_ids) == 1:
            (project_id,) = tuple(project_ids)
            connection.execute(
                text(
                    "UPDATE literature SET project_id = :project_id "
                    "WHERE id = :literature_id AND project_id IS NULL"
                ),
                {"project_id": project_id, "literature_id": literature_id}
            )


def downgrade() -> None:
    op.drop_constraint("fk_literature_project_id_projects", "literature", type_="foreignkey")
    op.drop_index("ix_literature_project_id", table_name="literature")
    op.drop_column("literature", "project_id")
