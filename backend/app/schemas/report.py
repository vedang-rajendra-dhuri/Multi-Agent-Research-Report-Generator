from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.research import (
    ClaimVerificationStatus,
    ReportVerificationStatus,
    ReviewStatus,
)


class EvidencePassageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    text: str
    locator: str | None
    created_at: datetime


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_source_id: str
    url: str
    title: str
    publisher: str | None
    published_date: str | None
    source_type: str
    retrieval_status: str
    created_at: datetime
    passages: list[EvidencePassageResponse]


class ClaimVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ClaimVerificationStatus
    explanation: str
    checked_at: datetime


class ClaimEvidenceResponse(BaseModel):
    evidence_id: UUID
    source_id: UUID
    provider_source_id: str
    passage: str


class ClaimResponse(BaseModel):
    id: UUID
    claim_key: str
    text: str
    claim_type: str
    evidence: list[ClaimEvidenceResponse]
    verifications: list[ClaimVerificationResponse]


class ReportVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    executive_summary: str
    sections: list[dict]
    methodology: str
    limitations: list[str]
    markdown: str
    verification_status: ReportVerificationStatus
    verification_results: list[dict[str, object]]
    created_at: datetime


class ReportDetailResponse(BaseModel):
    id: UUID
    task_id: UUID
    review_status: ReviewStatus
    current_version: int
    version: ReportVersionResponse
    sources: list[SourceResponse]
    claims: list[ClaimResponse]


class ReportReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def rejected_review_requires_reason(self):
        if self.decision == "rejected" and not (self.comment and self.comment.strip()):
            raise ValueError("A reason is required when rejecting a report.")
        return self


class ReportReviewResponse(BaseModel):
    report_id: UUID
    task_id: UUID
    review_status: ReviewStatus
    task_status: str
    current_version: int


class ReportSectionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)
    source_ids: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("title", "content", mode="before")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("source_ids")
    @classmethod
    def require_unique_section_sources(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Section source IDs must be unique.")
        return values


class ReportRevisionRequest(BaseModel):
    base_version: int = Field(ge=1)
    executive_summary: str = Field(min_length=1, max_length=10_000)
    sections: list[ReportSectionRevision] = Field(min_length=1, max_length=20)
    methodology: str = Field(min_length=1, max_length=5_000)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    source_ids: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("executive_summary", "methodology", mode="before")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("limitations")
    @classmethod
    def trim_limitations(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @model_validator(mode="after")
    def validate_revision_citations(self):
        total_characters = (
            len(self.executive_summary)
            + len(self.methodology)
            + sum(len(section.title) + len(section.content) for section in self.sections)
            + sum(len(limitation) for limitation in self.limitations)
        )
        if total_characters > 50_000:
            raise ValueError("A revised report is limited to 50,000 characters.")
        source_ids = set(self.source_ids)
        if len(source_ids) != len(self.source_ids):
            raise ValueError("Report source IDs must be unique.")
        if any(not set(section.source_ids).issubset(source_ids) for section in self.sections):
            raise ValueError("Section citations must be included in the report source IDs.")
        return self
