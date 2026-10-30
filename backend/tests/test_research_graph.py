from pydantic import SecretStr

from app.agents.graph import build_research_graph
from app.agents.state import (
    AnalysisOutput,
    ClaimDraft,
    ResearchPlan,
    ResearchReport,
    ReportSection,
    VerificationOutput,
    VerifiedClaim,
)
from app.providers.search import SearchSource


class StructuredModelStub:
    def __init__(self):
        self.analysis_count = 0
        self.verification_count = 0

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    def invoke(self, prompt):
        if self.schema is ResearchPlan:
            return ResearchPlan(
                central_question="Compare energy storage systems",
                subquestions=["How do the options differ?"],
                search_queries=["energy storage comparison"],
                scope_boundaries=[],
                report_outline=["Overview", "Comparison"],
            )
        if self.schema is AnalysisOutput:
            self.analysis_count += 1
            return AnalysisOutput(
                findings=[
                    ClaimDraft(
                        text="The evidence describes an energy storage system.",
                        evidence_ids=["source-one"] if self.analysis_count == 1 else [
                            "source-one",
                            "source-two",
                        ],
                    )
                ],
                supplementary_search_queries=(
                    ["battery performance research"] if self.analysis_count == 1 else []
                ),
            )
        if self.schema is VerificationOutput:
            self.verification_count += 1
            return VerificationOutput(
                claims=[
                    VerifiedClaim(
                        claim_id="claim-1",
                        status="unsupported" if self.verification_count == 1 else "supported",
                        explanation="Checked against the supplied passages.",
                    )
                ]
            )
        if self.schema is ResearchReport:
            return ResearchReport(
                executive_summary="A summary limited to available evidence.",
                sections=[
                    ReportSection(
                        title="Comparison",
                        content="See the supporting evidence.",
                        source_ids=["source-one", "invented-source"],
                    )
                ],
                methodology="Reviewed search-provider passages.",
                limitations=["The search results may not cover all evidence."],
                source_ids=["source-one", "source-two", "invented-source"],
            )
        raise AssertionError(f"Unexpected structured output schema: {self.schema}")


def source(source_id: str, url: str) -> SearchSource:
    return SearchSource(
        source_id=source_id,
        title=f"Source {source_id}",
        url=url,
        retrieved_at="2026-10-27T00:00:00Z",
        published_date=None,
        passage="An actual passage returned by the configured search adapter.",
    )


def test_workflow_runs_distinct_stages_with_bounded_supplemental_research():
    model = StructuredModelStub()
    search_calls = []
    stage_events = []
    search_results = {
        "energy storage comparison": [source("source-one", "https://example.org/one")],
        "battery performance research": [source("source-two", "https://example.org/two")],
    }

    def searcher(query, max_results):
        search_calls.append((query, max_results))
        return search_results[query]

    graph = build_research_graph(
        model_factory=lambda: model,
        searcher=searcher,
        max_iterations=2,
        event_sink=lambda stage, outcome, payload: stage_events.append((stage, outcome)),
    )
    result = graph.invoke(
        {
            "research_question": "Compare energy storage systems for grid use",
            "objectives": ["Identify tradeoffs"],
            "source_preferences": ["Academic research"],
        }
    )

    assert [query for query, _ in search_calls] == [
        "energy storage comparison",
        "battery performance research",
    ]
    assert model.analysis_count == 2
    assert model.verification_count == 2
    assert result["claims"][0].status == "supported"
    assert result["report"].source_ids == ["source-one", "source-two"]
    assert result["report"].sections[0].source_ids == ["source-one"]
    assert ("planner", "started") in stage_events
    assert ("planner", "completed") in stage_events
    assert ("writer", "completed") in stage_events


def test_verification_cannot_mark_claim_supported_without_valid_evidence():
    class UnsupportedEvidenceModel(StructuredModelStub):
        def invoke(self, prompt):
            if self.schema is AnalysisOutput:
                return AnalysisOutput(
                    findings=[
                        ClaimDraft(
                            text="This claim has a nonexistent citation.",
                            evidence_ids=["missing-source"],
                        )
                    ]
                )
            if self.schema is VerificationOutput:
                return VerificationOutput(
                    claims=[
                        VerifiedClaim(
                            claim_id="claim-1",
                            status="supported",
                            explanation="The model asserted support.",
                        )
                    ]
                )
            return super().invoke(prompt)

    model = UnsupportedEvidenceModel()
    graph = build_research_graph(
        model_factory=lambda: model,
        searcher=lambda query, max_results: [],
        max_iterations=1,
    )
    result = graph.invoke({"research_question": "Investigate a supplied research question"})

    assert result["claims"][0].status == "unsupported"
    assert result["claims"][0].explanation == "No valid evidence passage was linked to this claim."


def test_uploaded_project_evidence_is_available_to_the_workflow_without_web_search():
    class LocalEvidenceModel(StructuredModelStub):
        def invoke(self, prompt):
            if self.schema is AnalysisOutput:
                return AnalysisOutput(
                    findings=[
                        ClaimDraft(
                            text="The uploaded material describes the research topic.",
                            evidence_ids=["doc-12345678-1234-1234-1234-123456789012-chunk-0"],
                        )
                    ]
                )
            if self.schema is VerificationOutput:
                return VerificationOutput(
                    claims=[
                        VerifiedClaim(
                            claim_id="claim-1",
                            status="supported",
                            explanation="The uploaded passage directly discusses the topic.",
                        )
                    ]
                )
            if self.schema is ResearchReport:
                return ResearchReport(
                    executive_summary="Summary based on the uploaded source.",
                    sections=[
                        ReportSection(
                            title="Findings",
                            content="The source describes the topic.",
                            source_ids=[
                                "doc-12345678-1234-1234-1234-123456789012-chunk-0"
                            ],
                        )
                    ],
                    methodology="Reviewed project document evidence.",
                    limitations=["Only uploaded material was reviewed."],
                    source_ids=["doc-12345678-1234-1234-1234-123456789012-chunk-0"],
                )
            return super().invoke(prompt)

    document_source = SearchSource(
        source_id="doc-12345678-1234-1234-1234-123456789012-chunk-0",
        title="Project notes.txt",
        url="document://12345678-1234-1234-1234-123456789012",
        retrieved_at="2026-10-27T00:00:00Z",
        published_date=None,
        passage="The uploaded material describes the research topic and relevant evidence.",
        publisher="Uploaded project document",
        source_type="document",
        locator="Section 1",
    )
    graph = build_research_graph(
        model_factory=lambda: LocalEvidenceModel(),
        searcher=lambda query, max_results: [],
        max_iterations=1,
    )

    result = graph.invoke(
        {
            "research_question": "Investigate the material in my uploaded documents",
            "local_sources": [document_source],
        }
    )

    assert result["sources"][0].source_type == "document"
    assert result["claims"][0].status == "supported"
    assert result["report"].source_ids == [document_source.source_id]
