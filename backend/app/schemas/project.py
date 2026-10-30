from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.project import ProjectStatus, ResearchDepth


NonEmptyTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
ResearchQuestion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=5000)
]


class ProjectCreate(BaseModel):
    title: NonEmptyTitle
    description: str | None = Field(default=None, max_length=5000)


class ProjectUpdate(BaseModel):
    title: NonEmptyTitle | None = None
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectResponse]
    total: int
    limit: int
    offset: int


class ResearchBriefCreate(BaseModel):
    research_question: ResearchQuestion
    objectives: list[str] = Field(default_factory=list, max_length=20)
    scope: str | None = Field(default=None, max_length=10_000)
    depth: ResearchDepth = ResearchDepth.STANDARD
    source_preferences: list[str] = Field(default_factory=list, max_length=20)
    recency_days: int | None = Field(default=None, ge=1, le=36_500)
    output_format: str = Field(default="markdown", pattern="^markdown$")
    output_language: str = Field(default="en", min_length=2, max_length=80)

    @field_validator("objectives")
    @classmethod
    def validate_objectives(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 500 for value in cleaned):
            raise ValueError("Objectives must contain 1-500 non-whitespace characters.")
        return cleaned

    @field_validator("source_preferences")
    @classmethod
    def validate_source_preferences(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 120 for value in cleaned):
            raise ValueError("Source preferences must contain 1-120 non-whitespace characters.")
        return cleaned


class ResearchBriefResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    research_question: str
    objectives: list[str]
    scope: str | None
    depth: ResearchDepth
    source_preferences: list[str]
    recency_days: int | None
    output_format: str
    output_language: str
    created_at: datetime
