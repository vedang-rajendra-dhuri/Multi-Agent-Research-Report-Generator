"""Create research projects and research briefs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_projects_briefs"
down_revision = "0001_users_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_projects_owner_id", "research_projects", ["owner_id"])
    op.create_index(
        "ix_research_projects_owner_updated",
        "research_projects",
        ["owner_id", "updated_at"],
    )
    op.create_table(
        "research_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("objectives", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("depth", sa.String(length=8), nullable=False),
        sa.Column(
            "source_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("recency_days", sa.Integer(), nullable=True),
        sa.Column("output_format", sa.String(length=20), nullable=False),
        sa.Column("output_language", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["research_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_briefs_project_created",
        "research_briefs",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_briefs_project_created", table_name="research_briefs")
    op.drop_table("research_briefs")
    op.drop_index("ix_research_projects_owner_updated", table_name="research_projects")
    op.drop_index("ix_research_projects_owner_id", table_name="research_projects")
    op.drop_table("research_projects")
