from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ResearchDepth(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ResearchProject(Base):
    __tablename__ = "research_projects"
    __table_args__ = (
        Index("ix_research_projects_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="research_project_status", native_enum=False),
        default=ProjectStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    briefs: Mapped[list["ResearchBrief"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list["ProjectDocument"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class ResearchBrief(Base):
    __tablename__ = "research_briefs"
    __table_args__ = (
        Index("ix_research_briefs_project_created", "project_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    research_question: Mapped[str] = mapped_column(Text, nullable=False)
    objectives: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list, nullable=False
    )
    scope: Mapped[str | None] = mapped_column(Text)
    depth: Mapped[ResearchDepth] = mapped_column(
        Enum(ResearchDepth, name="research_depth", native_enum=False),
        default=ResearchDepth.STANDARD,
        nullable=False,
    )
    source_preferences: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=list, nullable=False
    )
    recency_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_format: Mapped[str] = mapped_column(String(20), default="markdown", nullable=False)
    output_language: Mapped[str] = mapped_column(String(80), default="en", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped[ResearchProject] = relationship(back_populates="briefs")
