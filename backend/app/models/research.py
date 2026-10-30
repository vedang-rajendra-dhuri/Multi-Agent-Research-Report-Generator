from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database import Base


class ResearchTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ClaimVerificationStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    NOT_CHECKED = "not_checked"
    SOURCE_UNAVAILABLE = "source_unavailable"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecisionType(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class ReportVerificationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchTask(Base):
    __tablename__ = "research_tasks"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_research_task_idempotency"),
        Index("ix_research_tasks_queue", "status", "created_at"),
        Index("ix_research_tasks_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    brief_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_briefs.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[ResearchTaskStatus] = mapped_column(
        Enum(ResearchTaskStatus, name="research_task_status", native_enum=False),
        default=ResearchTaskStatus.QUEUED,
        nullable=False,
    )
    current_stage: Mapped[str | None] = mapped_column(String(80))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    events: Mapped[list["TaskEvent"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    sources: Mapped[list["ResearchSource"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    claims: Mapped[list["ResearchClaim"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )
    report: Mapped["ResearchReportRecord | None"] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task_sequence", "task_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(80))
    agent_name: Mapped[str | None] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[ResearchTask] = relationship(back_populates="events")


class ResearchSource(Base):
    __tablename__ = "research_sources"
    __table_args__ = (
        UniqueConstraint("task_id", "provider_source_id", name="uq_research_source_provider_id"),
        Index("ix_research_sources_task_created", "task_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False
    )
    provider_source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(300))
    published_date: Mapped[str | None] = mapped_column(String(80))
    source_type: Mapped[str] = mapped_column(String(40), default="web", nullable=False)
    retrieval_status: Mapped[str] = mapped_column(String(40), default="retrieved", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[ResearchTask] = relationship(back_populates="sources")
    passages: Mapped[list["EvidencePassage"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", passive_deletes=True
    )


class EvidencePassage(Base):
    __tablename__ = "evidence_passages"
    __table_args__ = (Index("ix_evidence_passages_source", "source_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source: Mapped[ResearchSource] = relationship(back_populates="passages")
    claim_links: Mapped[list["ClaimEvidence"]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan", passive_deletes=True
    )


class ResearchClaim(Base):
    __tablename__ = "research_claims"
    __table_args__ = (Index("ix_research_claims_task", "task_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False
    )
    claim_key: Mapped[str] = mapped_column(String(80), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[ResearchTask] = relationship(back_populates="claims")
    evidence_links: Mapped[list["ClaimEvidence"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", passive_deletes=True
    )
    verifications: Mapped[list["ClaimVerification"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", passive_deletes=True
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_claims.id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidence_passages.id", ondelete="CASCADE"), nullable=False
    )

    claim: Mapped[ResearchClaim] = relationship(back_populates="evidence_links")
    evidence: Mapped[EvidencePassage] = relationship(back_populates="claim_links")


class ClaimVerification(Base):
    __tablename__ = "claim_verifications"
    __table_args__ = (Index("ix_claim_verifications_claim_checked", "claim_id", "checked_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_claims.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ClaimVerificationStatus] = mapped_column(
        Enum(ClaimVerificationStatus, name="claim_verification_status", native_enum=False),
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    verifier_model: Mapped[str | None] = mapped_column(String(120))
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    claim: Mapped[ResearchClaim] = relationship(back_populates="verifications")


class ResearchReportRecord(Base):
    __tablename__ = "research_reports"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="research_review_status", native_enum=False),
        default=ReviewStatus.PENDING,
        nullable=False,
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    task: Mapped[ResearchTask] = relationship(back_populates="report")
    versions: Mapped[list["ReportVersion"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )


class ReportVersion(Base):
    __tablename__ = "report_versions"
    __table_args__ = (
        UniqueConstraint("report_id", "version", name="uq_report_version"),
        Index(
            "ix_report_versions_verification_status_created",
            "verification_status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_reports.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[list[dict]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    methodology: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list, nullable=False
    )
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    verification_status: Mapped[ReportVerificationStatus] = mapped_column(
        Enum(
            ReportVerificationStatus,
            name="report_verification_status",
            native_enum=False,
        ),
        default=ReportVerificationStatus.COMPLETED,
        server_default=ReportVerificationStatus.COMPLETED.value,
        nullable=False,
    )
    verification_results: Mapped[list[dict]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list, nullable=False
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped[ResearchReportRecord] = relationship(back_populates="versions")
    decisions: Mapped[list["ReviewDecision"]] = relationship(
        back_populates="report_version", cascade="all, delete-orphan", passive_deletes=True
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    report_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("report_versions.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[ReviewDecisionType] = mapped_column(
        Enum(ReviewDecisionType, name="review_decision_type", native_enum=False),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report_version: Mapped[ReportVersion] = relationship(back_populates="decisions")
