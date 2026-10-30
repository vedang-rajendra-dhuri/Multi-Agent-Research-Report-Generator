"""Add research tasks, events, evidence and versioned reports."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_research_records"
down_revision = "0002_projects_briefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128)),
        sa.Column("status", sa.String(length=14), nullable=False),
        sa.Column("current_stage", sa.String(length=80)),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("worker_id", sa.String(length=120)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("safe_error_code", sa.String(length=80)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
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
        sa.ForeignKeyConstraint(["project_id"], ["research_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brief_id"], ["research_briefs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_research_task_idempotency"),
    )
    op.create_index("ix_research_tasks_queue", "research_tasks", ["status", "created_at"])
    op.create_index(
        "ix_research_tasks_owner_created", "research_tasks", ["owner_id", "created_at"]
    )
    op.create_table(
        "task_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("stage", sa.String(length=80)),
        sa.Column("agent_name", sa.String(length=80)),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_events_task_sequence", "task_events", ["task_id", "id"])
    op.create_table(
        "research_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_source_id", sa.String(length=64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("publisher", sa.String(length=300)),
        sa.Column("published_date", sa.String(length=80)),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("retrieval_status", sa.String(length=40), nullable=False),
        sa.Column(
            "metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id", "provider_source_id", name="uq_research_source_provider_id"
        ),
    )
    op.create_index(
        "ix_research_sources_task_created", "research_sources", ["task_id", "created_at"]
    )
    op.create_table(
        "research_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_key", sa.String(length=80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_claims_task", "research_claims", ["task_id"])
    op.create_table(
        "research_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_status", sa.String(length=8), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_table(
        "evidence_passages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("locator", sa.String(length=300)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["research_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_passages_source", "evidence_passages", ["source_id"])
    op.create_table(
        "claim_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=19), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("verifier_model", sa.String(length=120)),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["research_claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_claim_verifications_claim_checked",
        "claim_verifications",
        ["claim_id", "checked_at"],
    )
    op.create_table(
        "report_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("methodology", sa.Text(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_id"], ["research_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "version", name="uq_report_version"),
    )
    op.create_table(
        "claim_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["research_claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_passages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence"),
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=18), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["report_version_id"], ["report_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("review_decisions")
    op.drop_table("claim_evidence")
    op.drop_table("report_versions")
    op.drop_index("ix_claim_verifications_claim_checked", table_name="claim_verifications")
    op.drop_table("claim_verifications")
    op.drop_index("ix_evidence_passages_source", table_name="evidence_passages")
    op.drop_table("evidence_passages")
    op.drop_table("research_reports")
    op.drop_index("ix_research_claims_task", table_name="research_claims")
    op.drop_table("research_claims")
    op.drop_index("ix_research_sources_task_created", table_name="research_sources")
    op.drop_table("research_sources")
    op.drop_index("ix_task_events_task_sequence", table_name="task_events")
    op.drop_table("task_events")
    op.drop_index("ix_research_tasks_owner_created", table_name="research_tasks")
    op.drop_index("ix_research_tasks_queue", table_name="research_tasks")
    op.drop_table("research_tasks")
