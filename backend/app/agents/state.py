from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.providers.search import SearchSource


class ResearchPlan(BaseModel):
    central_question: str = Field(min_length=10, max_length=2_000)
    subquestions: list[str] = Field(min_length=1, max_length=8)
    search_queries: list[str] = Field(min_length=1, max_length=8)
    scope_boundaries: list[str] = Field(default_factory=list, max_length=12)
    report_outline: list[str] = Field(min_length=2, max_length=12)


class ClaimDraft(BaseModel):
    text: str = Field(min_length=5, max_length=2_000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    claim_type: Literal["factual", "interpretation", "recommendation"] = "factual"


class AnalysisOutput(BaseModel):
    findings: list[ClaimDraft] = Field(default_factory=list, max_length=40)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    open_questions: list[str] = Field(default_factory=list, max_length=20)
    supplementary_search_queries: list[str] = Field(default_factory=list, max_length=8)


ClaimStatus = Literal[
    "supported",
    "partially_supported",
    "contradicted",
    "unsupported",
    "not_checked",
    "source_unavailable",
]


class VerifiedClaim(BaseModel):
    claim_id: str
    status: ClaimStatus
    explanation: str = Field(max_length=1_000)


class VerificationOutput(BaseModel):
    claims: list[VerifiedClaim] = Field(default_factory=list, max_length=40)


class ReportSection(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)
    source_ids: list[str] = Field(default_factory=list, max_length=40)


class ResearchReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(min_length=1, max_length=10_000)
    sections: list[ReportSection] = Field(min_length=1, max_length=20)
    methodology: str = Field(min_length=1, max_length=5_000)
    limitations: list[str] = Field(default_factory=list, max_length=20)
    source_ids: list[str] = Field(default_factory=list, max_length=100)


class ResearchState(TypedDict, total=False):
    research_question: str
    objectives: list[str]
    scope: str | None
    source_preferences: list[str]
    recency_days: int | None
    output_language: str
    plan: ResearchPlan
    sources: list[SearchSource]
    local_sources: list[SearchSource]
    analysis: AnalysisOutput
    claims: list[VerifiedClaim]
    report: ResearchReport
    iteration: int
