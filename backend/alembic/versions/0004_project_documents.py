"""Add project document ingestion, full-text retrieval, and revision verification."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_project_documents"
down_revision = "0003_research_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_limits",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key_hash"),
    )
    op.create_index("ix_auth_rate_limits_updated", "auth_rate_limits", ["updated_at"])
    op.add_column(
        "report_versions",
        sa.Column(
            "verification_status",
            sa.String(length=12),
            server_default="completed",
            nullable=False,
        ),
    )
    op.add_column(
        "report_versions",
        sa.Column(
            "verification_results",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column("report_versions", "verification_results", server_default=None)
    op.create_index(
        "ix_report_versions_verification_status_created",
        "report_versions",
        ["verification_status", "created_at"],
    )
    op.create_table(
        "project_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("extracted_characters", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["research_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "sha256", name="uq_project_document_checksum"),
    )
    op.create_index(
        "ix_project_documents_project_created",
        "project_documents",
        ["project_id", "created_at"],
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["project_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )
    op.create_index(
        "ix_document_chunks_document_index",
        "document_chunks",
        ["document_id", "chunk_index"],
    )
    op.create_index(
        "ix_document_chunks_text_fts",
        "document_chunks",
        [sa.text("to_tsvector('english', text)")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_text_fts", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_index", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_project_documents_project_created", table_name="project_documents")
    op.drop_table("project_documents")
    op.drop_index(
        "ix_report_versions_verification_status_created",
        table_name="report_versions",
    )
    op.drop_column("report_versions", "verification_results")
    op.drop_column("report_versions", "verification_status")
    op.drop_index("ix_auth_rate_limits_updated", table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")
